"""Cleaning: normalize whitespace, preserve tables/code, strip boilerplate."""
import re

BOILERPLATE = re.compile(r"(page \d+ of \d+|confidential — internal|draft v\d+)", re.I)
# Test scaffolding that must never reach answers: author notes explaining WHY a
# doc exists, inline test prompts, and self-descriptive meta sentences. These
# read as development comments, not enterprise content — the quoter cannot tell
# them apart, so they leak into answers ("A vector-only query for...").
SCAFFOLD_HEADING = re.compile(r"^#{1,3}\s+(why this document exists|relational note)\b.*$", re.I | re.M)
TEST_QUERY_LINE = re.compile(r"^test query:.*$", re.I | re.M)
META_SENTENCE = re.compile(
    r"\s*This row-level fact tests table-aware parsing and parent-child chunking"
    r"( \([^)]*\))?\.?\s*", re.I)


def _strip_scaffold_sections(text: str) -> tuple[str, int]:
    """Drop whole sections headed as scaffolding (heading → next heading/EOF)."""
    lines, out, dropped, skipping = text.split("\n"), [], 0, False
    for ln in lines:
        if re.match(r"^#{1,3}\s+", ln.strip()):
            skipping = bool(SCAFFOLD_HEADING.match(ln.strip()))
        if skipping:
            dropped += 1
            continue
        out.append(ln)
    return "\n".join(out), dropped


def clean_text(text: str) -> tuple[str, dict]:
    report = {"chars_in": len(text)}
    text, report["scaffold_sections_dropped"] = _strip_scaffold_sections(text)
    n_testq = len(TEST_QUERY_LINE.findall(text))
    text = TEST_QUERY_LINE.sub("", text)
    report["test_query_lines_dropped"] = n_testq
    n_meta = len(META_SENTENCE.findall(text))
    text = META_SENTENCE.sub(" ", text)
    report["meta_sentences_dropped"] = n_meta
    # normalize line endings + tabs
    text = text.replace("\r\n", "\n").replace("\t", " ")
    # protect markdown tables: collapse >2 blank lines but never inside tables
    lines = []
    for ln in text.split("\n"):
        stripped = ln.strip()
        if stripped.startswith("|"):
            lines.append(re.sub(r"\s+", " ", ln).strip())
        else:
            lines.append(re.sub(r"[ \u00a0]+", " ", ln).rstrip())
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = BOILERPLATE.sub("", text)
    text = text.strip()
    report.update({"chars_out": len(text), "reduction_pct": round(100 * (1 - len(text) / max(1, report["chars_in"])), 1)})
    return text, report
