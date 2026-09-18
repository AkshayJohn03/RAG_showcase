"""RAGAS-style metrics, dependency-free.

Retrieval: Precision@k, Recall@k, MRR, NDCG@k, Context Precision/Recall.
Generation: Faithfulness (claim grounding heuristic), Answer Relevance
(keyword coverage + query-term overlap). Deterministic — CI-safe.
"""
from __future__ import annotations
import math
import re


def precision_at_k(retrieved: list[str], relevant: set[str], k: int = 5) -> float:
    top = retrieved[:k]
    return len([c for c in top if c in relevant or any(r in c for r in relevant)]) / max(1, k)


def recall_at_k(retrieved_docs: list[str], relevant_docs: set[str], k: int = 5) -> float:
    # doc-level recall: did we surface every gold document?
    got = {d for d in retrieved_docs[:k] if d in relevant_docs}
    return len(got) / max(1, len(relevant_docs))


def mrr(retrieved: list[str], relevant: set[str]) -> float:
    for i, c in enumerate(retrieved, start=1):
        if c in relevant or any(r in c for r in relevant):
            return 1.0 / i
    return 0.0


def _doc_of(chunk_id: str) -> str:
    return chunk_id.split("#")[0]


def _doc_hit(doc: str, relevant: set[str]) -> bool:
    return doc in relevant or any(r == doc or doc.endswith("/" + r) for r in relevant)


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int = 5) -> float:
    """Standard NDCG@k over doc-deduped rankings: multiple chunks from one gold
    doc count once, positioned at the doc's FIRST chunk rank (a doc first hit at
    chunk rank 5 discounts as rank 5, not rank 2). IDCG assumes min(k, |gold|)
    ideal hits, so a perfect ranking always scores 1.0."""
    first_pos: dict[str, int] = {}
    for rank, c in enumerate(retrieved[:k], start=1):
        d = _doc_of(c)
        if d not in first_pos:
            first_pos[d] = rank
    docs = list(first_pos)
    dcg = sum((1 / math.log2(first_pos[d] + 1)) if _doc_hit(d, relevant) else 0.0 for d in docs[:k])
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(k, len(relevant))))
    return round(dcg / ideal if ideal else 0.0, 4)


NEG = {"not", "never", "no", "n't", "without", "fails", "failed", "against", "none"}


def _sent_grounded(sent: str, ctx_sets: list[set], ctx_all: set) -> bool:
    """Shared verdict: joined-overlap base + two-way polarity guard.
    Negations are scanned on the RAW sentence (length filtering would drop
    'not'/'no' before the guard ever sees them)."""
    toks = [t for t in re.findall(r"[a-z0-9]+", sent.lower()) if len(t) > 3]
    if not toks or sum(1 for t in toks if t in ctx_all) / len(toks) < 0.5:
        return False
    tset = set(toks)
    negs = {t for t in re.findall(r"[a-z0-9']+", sent.lower()) if t in NEG or t.endswith("n't")}
    if negs:
        # direction 1: answer negates what context affirms → need shared negation
        return any(negs & cs and len(tset & cs) / len(toks) >= 0.5 for cs in ctx_sets)
    # direction 2: answer affirms what context negates (highest-risk hallucination)
    return not any((NEG & cs) - tset and len(tset & cs) / len(toks) >= 0.6 for cs in ctx_sets)


def faithfulness(answer: str, contexts: list) -> float:
    """Fraction of CITED SPANS grounded in their CITED document.

    The answer is split on [file.md] citation chips: each span must ground in
    the contexts of the doc it cites (catches right-words-wrong-source,
    Frankenstein quotes glued across clauses, and hallucinated filenames — a
    cited doc with no matching context scores 0). Spans without citations fall
    back to all contexts. A correct abstention scores 1.0 — the grounded prompt
    explicitly instructs it.
    contexts: raw strings (back-compat) or dicts with text/doc_id.
    Documented limit: token-overlap heuristic, not an NLI model; use an LLM
    judge for release-grade eval.
    """
    if _is_abstention(answer):
        return 1.0
    by_doc: dict[str, list[str]] = {}
    for c in contexts:
        if isinstance(c, dict):
            by_doc.setdefault(str(c.get("doc_id", "?")), []).append(str(c.get("text", "")))
        else:
            by_doc.setdefault("?", []).append(str(c))
    spans = _split_cited_spans(answer)
    if not spans:
        return 0.0

    def sets_for(docs: list[str]) -> tuple[list[set], set]:
        pool = [t for d in docs for t in by_doc.get(d, [])]
        if not pool and not docs:
            pool = [t for texts in by_doc.values() for t in texts]
        sets = [set(re.findall(r"[a-z0-9]+", s.lower()))
                for t in pool for s in re.split(r"(?<=[.!?])\s+|\n+", t) if len(s.strip()) > 8]
        return sets, set().union(*sets) if sets else set()

    grounded = total = 0
    for text, docs in spans:
        total += 1
        # multi-cite span: grounded if it grounds in ANY cited doc
        if any(_sent_grounded(text, *sets_for([d])) for d in docs) if docs else _sent_grounded(text, *sets_for([])):
            grounded += 1
    return grounded / total if total else 0.0


_ABSTAIN = re.compile(r"(i don'?t have|no information|(do|does) not (contain|mention|state|have)|not (found|present|contained|mentioned)|cannot answer|unable to answer|isn'?t (in|covered)|lack\w* (information|context))", re.I)


def _is_abstention(answer: str) -> bool:
    """Any phrasing of a correct refusal — not one hardcoded prefix."""
    first = answer.strip().split("\n")[0]
    return bool(_ABSTAIN.search(first[:300]))


CITE = re.compile(r"\[([^\]]+\.(?:md|txt|pdf|docx|html))\]")


def _split_cited_spans(answer: str) -> list[tuple[str, list[str]]]:
    """Split an answer into (sentence, cited-docs) pairs.

    Sentences are the unit: a chip attaches ONLY to an adjacent sentence —
    trailing chip after its end, leading chip before its start, consecutive
    chips all attach to the adjacent sentence. Uncited sentences stay neutral
    (docs=[]) instead of bleeding into a neighbor's document.
    """
    toks: list[tuple[str, str]] = []
    last = 0
    for m in CITE.finditer(answer):
        for s in re.split(r"(?<=[.!?])\s+|\n+", answer[last:m.start()]):
            if s.strip():
                toks.append(("sent", s.strip()))
        toks.append(("cite", m.group(1).strip()))
        last = m.end()
    for s in re.split(r"(?<=[.!?])\s+|\n+", answer[last:]):
        if s.strip():
            toks.append(("sent", s.strip()))

    spans: list[tuple[str, list[str]]] = []
    pending: list[str] = []  # leading chips awaiting the next sentence
    i = 0
    while i < len(toks):
        kind, val = toks[i]
        if kind == "cite":
            pending.append(val)
            i += 1
            continue
        docs = list(pending)
        pending = []
        j = i + 1
        while j < len(toks) and toks[j][0] == "cite":
            docs.append(toks[j][1])
            j += 1
        # keep any substantive fragment (>= 3 chars stripped): short facts like
        # "Fact one [a.md]" must count, not vanish with their citation
        if len(val.strip(" .,\n\t")) >= 3:
            spans.append((val, docs))
        i = j
    return spans


def answer_relevance(answer: str, question: str, keywords: list[str]) -> float:
    a = answer.lower()
    if not keywords:
        return 0.0
    return sum(1 for k in keywords if k.lower() in a) / len(keywords)
