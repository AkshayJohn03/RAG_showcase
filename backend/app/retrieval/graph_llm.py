"""LLM graph extraction + entity normalization (graceful: regex-only without an LLM).

Pipeline: regex triples (graph.py) → LLM pass over relation-bearing chunks →
normalize + merge aliases → save. The LLM pass only runs when LLM_PROVIDER is
ollama/openai AND only on chunks matching relation keywords (a handful in the
enterprise docs; scale distractors are skipped by the prefilter).
"""
from __future__ import annotations
import json
import re

REL_HINT = re.compile(r"\b(uses|use|supplies|supplied by|provides|provides?|vendor|manufactured by|approved for)\b", re.I)
SUFFIX = re.compile(r"\s+(GmbH|Inc\.?|LLC|Ltd\.?)$", re.I)


def canonical(entity: str) -> str:
    e = re.sub(r"\s+", " ", entity).strip().strip(".,;:")
    if re.match(r"^product\s+[a-z]$", e, re.I):
        return "Product " + e.split()[-1].upper()
    m = re.match(r"^component\s+([a-z]{1,3}-?\d+)$", e, re.I)
    if m:
        return f"Component {m.group(1).upper()}"
    if re.match(r"^[a-z]{1,3}-?\d+$", e, re.I):
        return f"Component {e.upper()}"
    return e


def _is_component(name: str) -> bool:
    return name.startswith("Component ")


def _orient(s: str, r: str, o: str) -> tuple[str, str, str]:
    """Relation-direction guard: components don't supply products; flip those."""
    if r == "supplies" and _is_component(s) and not _is_component(o):
        return o, "uses", s
    if r == "supplied_by" and not _is_component(s) and _is_component(o):
        return o, "supplied_by", s
    return s, r, o


def merge_aliases(triples: list[dict]) -> list[dict]:
    """Merge 'Nordwerk' → 'Nordwerk Precision GmbH' style aliases (substring rule)."""
    names = {t["s"] for t in triples} | {t["o"] for t in triples}
    canon = {}
    for n in names:
        c = canonical(n)
        canon[n] = c
    # longest-name-wins for substring aliases
    by_lower = sorted(set(canon.values()), key=len, reverse=True)
    def resolve(c: str) -> str:
        for long in by_lower:
            if c != long and c.lower() in long.lower() and len(c) < len(long):
                return long
        return c
    out, seen = [], set()
    for t in triples:
        key = _orient(resolve(canon[t["s"]]), t["r"], resolve(canon[t["o"]]))
        if key not in seen:
            seen.add(key)
            out.append({"s": key[0], "r": key[1], "o": key[2], "chunk_id": t.get("chunk_id", "")})
    return out


SYS = ("Extract entity relations as JSON list. Entities: products, components, suppliers. "
       "Relations: uses, supplied_by, supplies. Reply ONLY with JSON like "
       '[{"s":"Product X","r":"uses","o":"Component XK-7"}]. If none, reply [].')


def _llm_triples(text: str) -> list[dict]:
    from backend.app.config import settings
    provider = settings.llm_provider.lower()
    raw = ""
    try:
        if provider == "ollama":
            import ollama
            r = ollama.chat(model=settings.ollama_model,
                            messages=[{"role": "system", "content": SYS},
                                      {"role": "user", "content": text[:1500]}],
                            think=False, options={"temperature": 0.0, "num_predict": 200})
            raw = r["message"]["content"]
        elif provider == "openai" and settings.openai_api_key:
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)
            r = client.chat.completions.create(model=settings.openai_model,
                messages=[{"role": "system", "content": SYS}, {"role": "user", "content": text[:1500]}],
                temperature=0.0, max_tokens=200)
            raw = r.choices[0].message.content
    except Exception:
        return []
    try:
        start, end = raw.index("["), raw.rindex("]") + 1
        items = json.loads(raw[start:end])
        return [{"s": str(x["s"]), "r": str(x["r"]), "o": str(x["o"])} for x in items
                if all(k in x for k in ("s", "r", "o"))]
    except Exception:
        return []


def extract_llm(chunks: list[dict], cap: int = 20) -> list[dict]:
    from backend.app.config import settings
    if settings.llm_provider.lower() not in ("ollama", "openai"):
        return []
    out = []
    for c in chunks:
        if len(out) >= cap:
            break
        if c.get("doc_id", "").startswith("scale_20news"):
            continue
        if not REL_HINT.search(c.get("text", "")):
            continue
        for t in _llm_triples(c["text"]):
            out.append({**t, "chunk_id": c["chunk_id"]})
    return out
