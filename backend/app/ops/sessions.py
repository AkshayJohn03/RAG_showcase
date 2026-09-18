"""Conversation memory: last N turns per session (in-memory, capped).

Enterprise note: swap for Redis (keyed by user id from SSO) when multi-turn
must survive restarts or span replicas. History is injected into the grounded
prompt so follow-ups ("and its warranty?") resolve against prior context.
"""
from __future__ import annotations
from collections import deque

MAX_SESSIONS = 200
TURNS_KEPT = 6

_sessions: dict[str, deque] = {}


def remember(session_id: str, question: str, answer: str) -> None:
    if not session_id:
        return
    dq = _sessions.setdefault(session_id, deque(maxlen=TURNS_KEPT))
    dq.append({"q": question[:500], "a": answer[:800]})
    while len(_sessions) > MAX_SESSIONS:
        _sessions.pop(next(iter(_sessions)))


def recall(session_id: str) -> list[dict]:
    return list(_sessions.get(session_id, []))


def history_block(session_id: str) -> str:
    turns = recall(session_id)
    if not turns:
        return ""
    lines = [f"User: {t['q']}\nAssistant: {t['a']}" for t in turns]
    return "Conversation so far (for follow-up context):\n" + "\n".join(lines) + "\n"
