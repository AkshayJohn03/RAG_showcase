"""Run the data lifecycle: raw → cleaned → chunked → vectors + bm25 + graph.

Incremental by default: docs whose content hash is unchanged reuse their stored
vectors (no re-embed); removed docs are purged (covers GDPR deletion); only new
or changed docs pay embedding cost. Use --full to force a clean rebuild.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HASHES = ROOT / "data" / "04_vectors" / "doc_hashes.json"
VEC_FILE = ROOT / "data" / "04_vectors" / "vectors.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", default="parent_child", choices=["sliding", "semantic", "parent_child"])
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--overlap", type=int, default=80)
    ap.add_argument("--full", action="store_true", help="ignore hashes, rebuild everything")
    args = ap.parse_args()

    import sys
    sys.path.insert(0, str(ROOT))
    from backend.app.ingest.parser import load_raw
    from backend.app.ingest.cleaner import clean_text
    from backend.app.ingest.chunker import chunk_doc
    from backend.app.ingest.embed import embed_texts
    from backend.app.retrieval.multimodal import annotate_all
    from backend.app.retrieval.graph import extract_triples, save_graph
    from backend.app.retrieval.bm25 import tokenize

    raw = load_raw(ROOT / "data" / "01_raw")
    print(f"[ingest] {len(raw)} raw docs, strategy={args.strategy}")
    (ROOT / "data" / "02_cleaned").mkdir(parents=True, exist_ok=True)
    (ROOT / "data" / "03_chunked").mkdir(parents=True, exist_ok=True)
    (ROOT / "data" / "04_vectors").mkdir(parents=True, exist_ok=True)

    prev_hashes = json.loads(HASHES.read_text(encoding="utf-8")) if HASHES.exists() and not args.full else {}
    prev_manifest = {}
    man_file = ROOT / "data" / "04_vectors" / "manifest.json"
    if man_file.exists() and not args.full:
        try:
            prev_manifest = json.loads(man_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    strategy_changed = prev_manifest.get("strategy") != args.strategy
    prev_rows = {r["chunk_id"]: r for r in json.loads(VEC_FILE.read_text(encoding="utf-8"))} if VEC_FILE.exists() and not args.full else {}

    new_hashes, all_chunks, reused, rebuilt = {}, [], 0, 0
    clean_in, clean_out = 0, 0
    for d in raw:
        cleaned, report = clean_text(d["text"])
        # hash the CLEANED text: cleaner-rule changes must invalidate vectors
        # (hashing raw text silently kept stale embeddings after cleaning fixes)
        h = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:16]
        new_hashes[d["doc_id"]] = h
        clean_in += report["chars_in"]
        clean_out += report["chars_out"]
        cleaned_path = (ROOT / "data" / "02_cleaned" / d["doc_id"]).with_suffix(".txt")
        cleaned_path.parent.mkdir(parents=True, exist_ok=True)
        cleaned_path.write_text(cleaned, encoding="utf-8")
        chunks = chunk_doc(cleaned, d["doc_id"], args.strategy, size=args.size, overlap=args.overlap)
        changed = strategy_changed or prev_hashes.get(d["doc_id"]) != h
        for c in chunks:
            c["_fresh"] = changed
        rebuilt += changed
        all_chunks.extend(chunks)
        print(f"  {d['doc_id']}: {report['chars_in']}->{report['chars_out']} chars, {len(chunks)} chunks {'[rebuilt]' if changed else '[reused]'}")
    removed = [doc for doc in prev_hashes if doc not in new_hashes]
    if removed:
        print(f"[ingest] purged removed docs: {removed}")
    HASHES.write_text(json.dumps(new_hashes, indent=2), encoding="utf-8")

    all_chunks = annotate_all(all_chunks)
    # retrieval index = children (or all chunks for sliding/semantic)
    indexed = [c for c in all_chunks if c.get("role", "child") != "parent"] if args.strategy == "parent_child" else all_chunks
    indexed.sort(key=lambda c: (c["doc_id"], c.get("seq", 0)))
    fresh = [c for c in indexed if c.pop("_fresh", True)]
    stale_ids = {c["chunk_id"] for c in indexed} | {c["chunk_id"] for c in all_chunks if c.get("role") == "parent"}
    print(f"[ingest] embedding {len(fresh)} fresh chunks, reusing {len(indexed)-len(fresh)} (+parents)")

    def row_for(c, v):
        return {"chunk_id": c["chunk_id"], "doc_id": c["doc_id"], "text": c["text"],
                "parent_id": c.get("parent_id"), "role": c.get("role", "child"), "vector": v}

    store = [row_for(c, v) for c, v in zip(fresh, embed_texts([c["text"] for c in fresh]) if fresh else [])]
    have = {s["chunk_id"] for s in store}
    for c in indexed + [c for c in all_chunks if c.get("role") == "parent"]:
        c.pop("_fresh", None)
        if c["chunk_id"] in have:
            continue
        old = prev_rows.get(c["chunk_id"])
        if old and old.get("text") == c["text"] and old.get("vector"):
            store.append({**old, "role": c.get("role", "child"), "parent_id": c.get("parent_id")})  # refresh role metadata
            reused += 1
        else:
            store.append(row_for(c, embed_texts([c["text"]])[0]))
            rebuilt += 1
        have.add(c["chunk_id"])
    # drop vectors for removed docs / stale chunk ids (GDPR deletion propagates here)
    store = [r for r in store if r["chunk_id"] in stale_ids]
    VEC_FILE.write_text(json.dumps(store), encoding="utf-8")
    print(f"[ingest] vectors reused={reused} embedded={rebuilt} purged_stale={len(stale_ids - {r['chunk_id'] for r in store})}")

    (ROOT / "data" / "04_vectors" / "bm25.json").write_text(json.dumps(
        {"metas": [{"chunk_id": c["chunk_id"], "doc_id": c["doc_id"], "text": c["text"],
                    "parent_id": c.get("parent_id")} for c in indexed],
         "tokenized": [tokenize(c["text"]) for c in indexed]}), encoding="utf-8")

    (ROOT / "data" / "03_chunked" / f"chunks_{args.strategy}.json").write_text(
        json.dumps(all_chunks, indent=2), encoding="utf-8")

    triples = extract_triples(all_chunks)
    try:
        from backend.app.retrieval.graph_llm import extract_llm, merge_aliases
        llm_triples = extract_llm(all_chunks)
        if llm_triples:
            print(f"[ingest] LLM triples: {len(llm_triples)}")
        triples = merge_aliases(triples + llm_triples)
    except Exception as e:
        print(f"[ingest] graph LLM pass skipped: {e}")
    save_graph(triples)
    # lifecycle proof: cleaning totals + measured inter-chunk overlap
    by_doc: dict[str, list[str]] = {}
    for c in indexed:
        by_doc.setdefault(c["doc_id"], []).append(c["text"])
    overlaps = []
    for texts in by_doc.values():
        for a, b in zip(texts, texts[1:]):
            ta, tb = set(a.lower().split()), set(b.lower().split())
            if ta and tb:
                overlaps.append(len(ta & tb) / min(len(ta), len(tb)))
    sizes = [c.get("token_est", 0) for c in indexed]
    stats = {"cleaned_chars_in": clean_in, "cleaned_chars_out": clean_out,
             "clean_reduction_pct": round(100 * (1 - clean_out / max(1, clean_in)), 1),
             "avg_chunk_tokens": round(sum(sizes) / max(1, len(sizes)), 1),
             "mean_consecutive_overlap": round(sum(overlaps) / max(1, len(overlaps)), 3),
             "docs_with_overlap": sum(1 for v in by_doc.values() if len(v) > 1)}
    print(f"[ingest] clean {clean_in}->{clean_out} chars (-{stats['clean_reduction_pct']}%), "
          f"avg_chunk={stats['avg_chunk_tokens']} tok, mean_overlap={stats['mean_consecutive_overlap']}")
    # scaffolding watchlist: fail loudly if dev notes ever reach the index again
    WATCH = ["vector-only query", "why this document exists", "test query:",
             "relational note", "row-level fact tests"]
    leaks = [(c["chunk_id"]) for c in all_chunks
             if any(w in c["text"].lower() for w in WATCH)]
    if leaks:
        print(f"[ingest] WARNING: scaffolding leaked into {len(leaks)} chunks: {leaks[:5]}")
    else:
        print("[ingest] scaffolding watchlist: clean (0 leaks)")
    manifest = {"strategy": args.strategy, "docs": len(raw), "chunks_total": len(all_chunks),
                "indexed": len(indexed), "triples": len(triples), **stats}
    (ROOT / "data" / "04_vectors" / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[ingest] done: {manifest}")


if __name__ == "__main__":
    main()
