"""Cleaning: normalize whitespace, preserve tables/code, strip boilerplate."""
import re

BOILERPLATE = re.compile(r"(page \d+ of \d+|confidential — internal|draft v\d+)", re.I)


def clean_text(text: str) -> tuple[str, dict]:
    report = {"chars_in": len(text)}
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
