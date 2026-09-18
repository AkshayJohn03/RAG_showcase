"""Single source of truth for filesystem locations, anchored to the repo root.

Every module must resolve data files through here — never `Path("data/...")`
relative to the process working directory (breaks the moment uvicorn starts
anywhere but the repo root, e.g. `cd backend && uvicorn app.main:app`).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
VECTORS_DIR = DATA / "04_vectors"
VEC_PATH = VECTORS_DIR / "vectors.json"
BM25_PATH = VECTORS_DIR / "bm25.json"
GRAPH_PATH = VECTORS_DIR / "graph.json"
QDRANT_LOCAL_PATH = VECTORS_DIR / "qdrant_local"
EVAL_DIR = DATA / "eval"
HIST_PATH = EVAL_DIR / "history.jsonl"
FEED_PATH = EVAL_DIR / "feedback.jsonl"
BASELINE_PATH = EVAL_DIR / "baseline.json"
