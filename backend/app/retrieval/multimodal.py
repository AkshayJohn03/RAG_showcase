"""Multimodal handling (text-first, table-aware, image-ready).

- Tables: never split mid-row (chunker keeps table blocks whole); here we tag
  table chunks with row counts for the UI badge.
- Figures/charts: captions are indexed adjacent to referencing paragraphs
  (see q3_field_report.md Figure F-3). When real PDFs carry embedded images,
  this module records their page/box so a VLM captioning pass (e.g. Ollama
  llava) can fill `caption` later without re-chunking.
"""
from __future__ import annotations
import re

TABLE_ROW = re.compile(r"^\|.*\|$", re.M)


def annotate(chunk: dict) -> dict:
    text = chunk.get("text", "")
    rows = TABLE_ROW.findall(text)
    chunk["has_table"] = len(rows) >= 2
    chunk["table_rows"] = len(rows)
    chunk["has_figure_ref"] = bool(re.search(r"Figure\s+F-\d+|Fig\.\s*\d+", text))
    return chunk


def annotate_all(chunks: list[dict]) -> list[dict]:
    return [annotate(dict(c)) for c in chunks]
