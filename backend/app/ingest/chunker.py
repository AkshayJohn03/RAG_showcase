"""Senior chunking: sliding-window (sentence-aware + overlap), semantic, parent-child.

Every chunk: {chunk_id, doc_id, text, parent_id, strategy, token_est, table_flag}
Sorted deterministically by (doc_id, seq) so the pipeline is reproducible.
"""
from __future__ import annotations
import re

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9#|\-])")


def est_tokens(s: str) -> int:
    return max(1, len(s) // 4)


def sentences(text: str) -> list[str]:
    parts = [p.strip() for p in SENT_SPLIT.split(text.strip()) if p.strip()]
    return parts or [text.strip()]


def _is_table_block(block: str) -> bool:
    lines = [l for l in block.split("\n") if l.strip().startswith("|")]
    return len(lines) >= 2


def sliding_window(text: str, doc_id: str, size: int = 512, overlap: int = 80) -> list[dict]:
    """Sentence-aware sliding window with token overlap carried between chunks."""
    sents = sentences(text.replace("\n\n", "\n"))
    chunks, cur, cur_tok = [], [], 0
    seq = 0
    for s in sents:
        t = est_tokens(s)
        if cur and cur_tok + t > size:
            chunk_text = " ".join(cur)
            chunks.append({"chunk_id": f"{doc_id}#s{seq}", "doc_id": doc_id,
                           "text": chunk_text, "parent_id": None, "strategy": "sliding",
                           "token_est": cur_tok, "table_flag": False, "seq": seq})
            seq += 1
            # overlap: walk back from end until overlap budget filled
            keep, kept = [], 0
            for prev in reversed(cur):
                pt = est_tokens(prev)
                if kept + pt > overlap:
                    break
                keep.append(prev)
                kept += pt
            cur, cur_tok = list(reversed(keep)), kept
        cur.append(s)
        cur_tok += t
    if cur:
        chunks.append({"chunk_id": f"{doc_id}#s{seq}", "doc_id": doc_id,
                       "text": " ".join(cur), "parent_id": None, "strategy": "sliding",
                       "token_est": cur_tok, "table_flag": False, "seq": seq})
    return chunks


def semantic(text: str, doc_id: str, size: int = 512) -> list[dict]:
    """Breakpoint chunking: split paragraphs, merge small ones, break large ones on sentences.
    With real embeddings this uses cosine-drop breakpoints; here the structural
    heuristic keeps tables/paragraphs intact (deterministic, dependency-free)."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, buf, buf_tok, seq = [], "", 0, 0
    def flush():
        nonlocal buf, buf_tok, seq
        if buf.strip():
            chunks.append({"chunk_id": f"{doc_id}#m{seq}", "doc_id": doc_id,
                           "text": buf.strip(), "parent_id": None, "strategy": "semantic",
                           "token_est": buf_tok, "table_flag": _is_table_block(buf), "seq": seq})
            seq += 1
            buf, buf_tok = "", 0
    for p in paras:
        pt = est_tokens(p)
        if _is_table_block(p):
            flush()
            chunks.append({"chunk_id": f"{doc_id}#m{seq}", "doc_id": doc_id, "text": p,
                           "parent_id": None, "strategy": "semantic",
                           "token_est": pt, "table_flag": True, "seq": seq})
            seq += 1
            continue
        if buf_tok + pt > size and buf:
            flush()
        if pt > size:  # oversize para → sentence split
            flush()
            for c in sliding_window(p, doc_id, size=size, overlap=40):
                c["chunk_id"] = f"{doc_id}#m{seq}"
                c["strategy"] = "semantic"
                c["seq"] = seq
                chunks.append(c)
                seq += 1
        else:
            buf = (buf + "\n\n" + p).strip() if buf else p
            buf_tok += pt
    flush()
    return chunks


def parent_child(text: str, doc_id: str, parent_size: int = 1000, child_size: int = 220, overlap: int = 40) -> list[dict]:
    """Parents (~1000 tok) for generation context; children (~220 tok) for retrieval.
    Children carry parent_id so the retriever returns small precise hits and the
    generator receives the full parent — the classic precision/context tradeoff fix."""
    parents = sliding_window(text, doc_id, size=parent_size, overlap=overlap)
    out, cseq = [], 0
    for pi, p in enumerate(parents):
        parent_id = f"{doc_id}#p{pi}"
        p = dict(p)
        p.update({"chunk_id": parent_id, "strategy": "parent_child_parent", "role": "parent", "seq": pi})
        out.append(p)
        for ch in sliding_window(p["text"], doc_id, size=child_size, overlap=30):
            out.append({"chunk_id": f"{parent_id}c{cseq}", "doc_id": doc_id, "text": ch["text"],
                        "parent_id": parent_id, "strategy": "parent_child",
                        "token_est": ch["token_est"], "table_flag": _is_table_block(ch["text"]),
                        "role": "child", "seq": cseq})
            cseq += 1
    # deterministic sort: parents first per doc, then children
    out.sort(key=lambda c: (c["doc_id"], 0 if c.get("role") == "parent" else 1, c["seq"]))
    return out


def chunk_doc(text: str, doc_id: str, strategy: str, size: int = 512, overlap: int = 80) -> list[dict]:
    if strategy == "semantic":
        return semantic(text, doc_id, size=size)
    if strategy == "parent_child":
        return parent_child(text, doc_id)
    return sliding_window(text, doc_id, size=size, overlap=overlap)
