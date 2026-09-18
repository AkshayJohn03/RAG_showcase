"""LLM client: Ollama / OpenAI when configured, else grounded extractive fallback."""
from __future__ import annotations
from typing import Iterator


def _messages(prompt: str) -> list[dict]:
    return [{"role": "system", "content": "Answer only from context, with citations."},
            {"role": "user", "content": prompt}]


def generate_stream(prompt: str, question: str, contexts: list[dict]) -> Iterator[str]:
    """Yield answer text incrementally. Ollama streams live tokens; OpenAI and the
    extractive fallback yield word-chunks (same content as generate())."""
    from backend.app.config import settings
    provider = settings.llm_provider.lower()
    if provider == "ollama":
        yielded = False
        try:
            import ollama
            for chunk in ollama.chat(model=settings.ollama_model, messages=_messages(prompt),
                                     think=False, stream=True,
                                     options={"temperature": 0.1, "num_predict": 250}):
                delta = (chunk.get("message") or {}).get("content", "")
                if delta:
                    yielded = True
                    yield delta
        except Exception:
            pass
        if yielded:
            return
    # non-streaming providers / fallback: chunk the collected answer
    answer, _ = generate(prompt, question, contexts)
    for i in range(0, len(answer.split(" ")), 8):
        yield " ".join(answer.split(" ")[i:i + 8]) + " "


def generate(prompt: str, question: str, contexts: list[dict]) -> tuple[str, str]:
    from backend.app.config import settings
    provider = settings.llm_provider.lower()
    if provider == "ollama":
        try:
            import ollama
            r = ollama.chat(model=settings.ollama_model,
                            messages=[{"role": "system", "content": "Answer only from context, with citations."},
                                      {"role": "user", "content": prompt}],
                            think=False,  # reasoning traces cost minutes on CPU; grounded QA doesn't need them
                            options={"temperature": 0.1, "num_predict": 250})
            return r["message"]["content"], f"ollama/{settings.ollama_model}"
        except Exception as e:
            pass
    if provider == "openai" and settings.openai_api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)
            r = client.chat.completions.create(model=settings.openai_model,
                messages=[{"role": "system", "content": "Answer only from context, with citations."},
                          {"role": "user", "content": prompt}], temperature=0.1, max_tokens=400)
            return r.choices[0].message.content, f"openai/{settings.openai_model}"
        except Exception:
            pass
    # extractive fallback: most query-relevant sentences + citations (still grounded)
    import re
    qtok = set(re.findall(r"[a-z0-9]+", question.lower()))
    # Quoting units are whole structural blocks, never line fragments: prose
    # paragraphs rejoin wrapped lines so sentences stay complete (a fragment like
    # "requires a hot-work" glues to the next quote and poisons faithfulness);
    # bullets/headings/tables start new blocks so distractor bullets can't ride
    # along; tables travel with their caption (rows supply IDs, prose scores).
    _BLOCK_START = re.compile(r"^(?:[-*#>]|\d+[.)]|\|)")
    sents = []
    max_rs = max([(c.get("rerank_score") or 0) for c in contexts[:3]] + [0])
    for c in contexts[:3]:
        # source weight: the reranker already scored distractors ~0 — quoting
        # must respect that instead of letting lexical overlap resurrect them
        src_w = 0.25 + 0.75 * ((c.get("rerank_score") or 0) / max_rs) if max_rs else 1.0
        blocks: list[str] = []
        buf: list[str] = []
        def flush():
            if buf:
                blocks.append(" ".join(buf))
                buf.clear()
        for ln in c.get("text", "").split("\n"):
            ln = ln.strip()
            if not ln:
                flush()
            elif ln.startswith("|"):
                if buf and not buf[-1].startswith("|"):
                    flush()
                buf.append(ln)
            elif _BLOCK_START.match(ln):
                flush()
                buf.append(ln)
            else:
                buf.append(ln)  # wrapped prose line: rejoins the sentence
        flush()
        units: list[str] = []
        i = 0
        while i < len(blocks):
            b = blocks[i]
            if b.startswith("|") and i + 1 < len(blocks) and not blocks[i + 1].startswith("|"):
                units.append(b + " " + blocks[i + 1])  # table + caption
                i += 2
            else:
                units.append(b)
                i += 1
        for u in units:
            parts = [u] if u.startswith("|") else re.split(r"(?<=[.!?])\s+", u)
            for s in parts:
                if len(s.strip()) < 20:
                    continue
                overlap = len(qtok & set(re.findall(r"[a-z0-9]+", s.lower()))) * src_w
                sents.append((overlap, s.strip(), c))
    sents.sort(key=lambda t: t[0], reverse=True)
    # de-dupe: parent expansion often surfaces the same sentence via child + parent
    seen, uniq = set(), []
    for ov, s, c in sents:
        key = s.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append((ov, s, c))
    top = uniq[:3]
    # drop weak tail sentences (e.g. distractor-vendor text): keep only
    # sentences scoring at least half of the best one
    if top:
        best = max(ov for ov, _, _ in top)
        cutoff = max(1, best * 0.5)
        strong = [t for t in top if t[0] >= cutoff]
        top = strong or top[:1]
    if not top or top[0][0] == 0:
        return ("I don't have that in the indexed context. Try asking about Product X supply chain, SAF-114, or the Q3 field report.", "extractive/no-llm")
    answer = " ".join(f"{s} [{c.get('doc_id','?')}]" for _, s, c in top)
    return answer, "extractive/no-llm"
