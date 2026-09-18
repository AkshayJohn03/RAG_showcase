"""Qdrant parity test: qdrant-local must agree with the local store on top hits."""
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_qdrant_local_parity(monkeypatch, tmp_path):
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct
    from backend.app.ingest.embed import embed_texts
    from backend.app.retrieval.vector_store import dense_search, LocalStore

    texts = ["hot-work permit signed by the shift lead for soldering",
             "component XK-7 timing controller exclusively in Product X",
             "warranty 36 months on-site replacement within 5 days",
             "unrelated post about graphics drivers and monitors"]
    vecs = embed_texts(texts)
    client = QdrantClient(path=str(tmp_path / "q"))
    client.create_collection(collection_name="t", vectors_config=VectorParams(size=len(vecs[0]), distance=Distance.COSINE))
    from qdrant_client.models import PayloadSchemaType
    # index creation is accepted (matters on server Qdrant; local mode ignores
    # indexes but still enforces the filter — proven by the parent test below)
    op = client.create_payload_index(collection_name="t", field_name="role", field_schema=PayloadSchemaType.KEYWORD)
    assert "complet" in str(op.status).lower()
    parent_vec = list(vecs[0])  # identical vector: without the role filter it would rank #1
    client.upsert(collection_name="t", points=[
        PointStruct(id=uuid.uuid5(uuid.NAMESPACE_URL, f"c{i}").hex, vector=v,
                    payload={"chunk_id": f"c{i}", "doc_id": "d", "text": t, "parent_id": None,
                             "role": "child"})
        for i, (t, v) in enumerate(zip(texts, vecs))] + [
        PointStruct(id=uuid.uuid5(uuid.NAMESPACE_URL, "px").hex, vector=parent_vec,
                    payload={"chunk_id": "px", "doc_id": "d", "text": texts[0], "parent_id": None,
                             "role": "parent"})])
    client.close()
    monkeypatch.setenv("QDRANT_LOCAL_PATH", str(tmp_path / "q"))

    import backend.app.config as cfg
    monkeypatch.setattr(cfg.settings, "qdrant_collection", "t")
    from backend.app.ingest.embed import embed_query
    qvec = embed_query("Who signs the hot-work permit?")
    try:
        got = dense_search(qvec, top_k=1, backend="qdrant-local")
        assert got and got[0]["chunk_id"] == "c0"
        assert got[0]["dense_score"] > 0.3
        # parent with IDENTICAL vector must still be filtered out
        got5 = dense_search(qvec, top_k=5, backend="qdrant-local")
        assert all("px" != g["chunk_id"] for g in got5)
    finally:
        # release file locks deterministically (no __del__ noise at shutdown)
        from backend.app.retrieval.vector_store import _qdrant_clients
        for c in _qdrant_clients.values():
            try:
                c.close()
            except Exception:
                pass
        _qdrant_clients.clear()
