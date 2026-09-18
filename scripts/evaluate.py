"""CI-gatable eval: python scripts/evaluate.py [--fail-under 0.6] [--save-baseline] [--compare-baseline].

--save-baseline   snapshot current summary to data/eval/baseline.json
--compare-baseline fail if faithfulness or recall drops >0.1 vs baseline (drift gate)
Every run is appended to data/eval/history.jsonl for trend tracking.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.eval.run_eval import run_all
from backend.app.eval.history import record_eval

BASE = ROOT / "data" / "eval" / "baseline.json"

ap = argparse.ArgumentParser()
ap.add_argument("--fail-under", type=float, default=0.6)
ap.add_argument("--save-baseline", action="store_true")
ap.add_argument("--compare-baseline", action="store_true")
ap.add_argument("--mode", default="hybrid", choices=["dense", "bm25", "hybrid"])
ap.add_argument("--no-rerank", action="store_true")
ap.add_argument("--agent", action="store_true",
                help="evaluate the full agentic path (slower, covers ReAct+GraphRAG)")
ap.add_argument("--save-to", default="", help="save full result JSON (e.g. data/eval/llm_eval.json)")
args = ap.parse_args()
res = run_all(mode=args.mode, use_rerank=not args.no_rerank, use_agent=args.agent)
record_eval(res["summary"])
if args.save_to:
    Path(args.save_to).write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"full result saved → {args.save_to}")
print(json.dumps(res["summary"], indent=2))
for row in res["per_question"]:
    print(row)
ok = res["summary"]["gate"] == "PASS"
if args.save_baseline:
    BASE.write_text(json.dumps(res["summary"], indent=2), encoding="utf-8")
    print(f"baseline saved → {BASE}")
if args.compare_baseline and BASE.exists():
    base = json.loads(BASE.read_text(encoding="utf-8"))
    for metric in ("faith", "r@5", "ndcg@5"):
        drop = base.get(metric, 0) - res["summary"].get(metric, 0)
        status = "DRIFT" if drop > 0.1 else "stable"
        print(f"{metric}: baseline={base.get(metric)} now={res['summary'].get(metric)} drift={round(drop,3)} [{status}]")
        if drop > 0.1:
            ok = False
print(f"GATE: {'PASS' if ok else 'FAIL'}")
sys.exit(0 if ok else 1)
