"""Push vectors.json into embedded Qdrant (data/04_vectors/qdrant_local).

Proves the Qdrant code path without Docker: after this, queries with
VECTOR_BACKEND=qdrant-local hit a real vector DB. Server mode (docker compose)
uses the same functions with VECTOR_BACKEND=qdrant.
"""
import sys
import time
import uuid
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import settings

import json
ap = argparse.ArgumentParser()
ap.add_argument("--limit", type=int, default=0, help="push only first N rows (smoke test; 0 = all)")
ap.add_argument("--remote", action="store_true", help="push to settings.qdrant_url instead of local path")
ap.add_argument("--wait", type=int, default=0,
                help="wait up to N seconds for remote Qdrant TCP readiness (k8s Job race guard)")
args = ap.parse_args()
print("loading vectors.json...", flush=True)
t0 = time.time()
rows = json.loads((ROOT / "data" / "04_vectors" / "vectors.json").read_text(encoding="utf-8"))
if args.limit:
    # enterprise docs first so smoke tests cover the golden set
    rows = sorted(rows, key=lambda r: (0 if not r["doc_id"].startswith("scale_") else 1, r["chunk_id"]))[:args.limit]
print(f"loaded {len(rows)} rows in {round(time.time()-t0, 1)}s", flush=True)

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

dim = len(rows[0]["vector"])
if args.remote:
    from qdrant_client import QdrantClient as _QC
    if args.wait:
        import socket
        import urllib.request
        from urllib.parse import urlparse
        host = urlparse(settings.qdrant_url).hostname or "localhost"
        port = urlparse(settings.qdrant_url).port or 6333
        # TCP open only proves the socket bound; /readyz proves WAL replay and
        # segment loading finished (a TCP-only probe routes traffic too early).
        deadline = time.time() + args.wait
        ready = False
        while time.time() <= deadline and not ready:
            try:
                socket.create_connection((host, port), timeout=5).close()
                with urllib.request.urlopen(f"{settings.qdrant_url.rstrip('/')}/readyz", timeout=5) as r:
                    ready = r.status == 200
            except OSError:
                ready = False
            if not ready:
                time.sleep(2)
        if not ready:
            raise SystemExit(f"qdrant not ready at {host}:{port} after {args.wait}s")
        print(f"qdrant ready at {host}:{port}", flush=True)
    client = _QC(url=settings.qdrant_url)
    where = settings.qdrant_url
else:
    client = QdrantClient(path=str(ROOT / "data" / "04_vectors" / "qdrant_local"))
    where = "qdrant_local/"
if not client.collection_exists(settings.qdrant_collection):
    client.create_collection(collection_name=settings.qdrant_collection,
                             vectors_config=VectorParams(size=dim, distance=Distance.COSINE))
    print(f"collection created dim={dim}", flush=True)
else:
    print("collection exists — idempotent upsert (deterministic UUIDs overwrite in place)", flush=True)
# payload index on `role`: the serving path filters must_not parent on EVERY
# query — without an index Qdrant falls back to sequential payload scans that
# grow with the collection (fatal past ~100k points).
from qdrant_client.models import PayloadSchemaType
try:
    client.create_payload_index(collection_name=settings.qdrant_collection,
                                field_name="role", field_schema=PayloadSchemaType.KEYWORD)
    print("payload index on role: created", flush=True)
except Exception as e:
    print(f"payload index on role: already exists ({e.__class__.__name__})", flush=True)
pts = [PointStruct(id=uuid.uuid5(uuid.NAMESPACE_URL, r["chunk_id"]).hex,
                   vector=r["vector"],
                   payload={"chunk_id": r["chunk_id"], "doc_id": r["doc_id"],
                            "text": r["text"], "parent_id": r.get("parent_id"),
                            "role": r.get("role", "child")})
       for r in rows]
print(f"built {len(pts)} points in {round(time.time()-t0, 1)}s, upserting...", flush=True)
for i in range(0, len(pts), 256):
    client.upsert(collection_name=settings.qdrant_collection, points=pts[i:i + 256], wait=True)
    print(f"  {min(i+256, len(pts))}/{len(pts)} ({round(time.time()-t0, 1)}s)", flush=True)
# prune stale points (removed docs) WITHOUT dropping the live collection:
# deterministic UUIDs mean upsert already overwrote everything current.
# Skipped for --limit smoke pushes (a subset is not the full desired state).
if not args.limit:
    new_ids = {p.id for p in pts}
    stale: list[str] = []
    offset = None
    from qdrant_client.models import Filter, HasIdCondition
    while True:
        batch, offset = client.scroll(collection_name=settings.qdrant_collection, limit=512,
                                      offset=offset, with_payload=False, with_vectors=False)
        stale += [p.id for p in batch if p.id not in new_ids]
        if offset is None:
            break
    if stale:
        client.delete(collection_name=settings.qdrant_collection,
                      points_selector=Filter(must=[HasIdCondition(has_id=stale)]))
        print(f"pruned {len(stale)} stale points", flush=True)
client.close()
print(f"pushed {len(pts)} points → {where}{settings.qdrant_collection} total={round(time.time()-t0, 1)}s", flush=True)
