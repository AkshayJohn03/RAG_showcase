"""Eval run history (JSONL) + user feedback store (JSONL).

history.jsonl: every /eval and scripts/evaluate.py run appends {ts, summary}.
  → powers the trend panel and the drift gate (compare vs baseline).
feedback.jsonl: dashboard thumbs up/down {ts, session, query, vote, note}.
  → weekly sample feeds the golden set; tracks online quality post-deploy.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

from backend.app.paths import HIST_PATH as HIST, FEED_PATH as FEED


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": datetime.now(timezone.utc).isoformat(), **row}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def record_eval(summary: dict, strategy: str = "") -> None:
    _append(HIST, {"summary": summary, "strategy": strategy})


def record_feedback(session: str, query: str, vote: str, note: str = "") -> None:
    _append(FEED, {"session": session[:64], "query": query[:500],
                   "vote": vote, "note": note[:500]})


def read_history(limit: int = 30) -> list[dict]:
    if not HIST.exists():
        return []
    rows = [json.loads(l) for l in HIST.read_text(encoding="utf-8").splitlines() if l.strip()]
    return rows[-limit:]


def feedback_stats() -> dict:
    if not FEED.exists():
        return {"up": 0, "down": 0}
    up = down = 0
    for l in FEED.read_text(encoding="utf-8").splitlines():
        try:
            v = json.loads(l).get("vote")
            up += v == "up"
            down += v == "down"
        except Exception:
            pass
    return {"up": up, "down": down}
