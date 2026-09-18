"""Fetch a real benchmark corpus (20 Newsgroups, sklearn) as scale distractors.

Writes N posts to data/01_raw/scale_20news/ so the SAME index holds 4 enterprise
docs + ~2000 real-world noisy documents — the "needle in a bigger haystack" test
reviewers ask for. Incremental ingest picks them up on next run.
"""
from pathlib import Path

CATS = ["comp.graphics", "comp.os.ms-windows.misc", "comp.sys.ibm.pc.hardware", "sci.electronics"]
PER_CAT = 500

out = Path("data/01_raw/scale_20news")
out.mkdir(parents=True, exist_ok=True)
# fresh snapshot each fetch (avoid half-written state from interrupted runs)
for p in out.glob("*.txt"):
    p.unlink()

from sklearn.datasets import fetch_20newsgroups
ng = fetch_20newsgroups(subset="train", categories=CATS, remove=("headers", "footers", "quotes"))

kept = 0
per_cat = {c: 0 for c in CATS}
for text, target in zip(ng.data, ng.target):
    cat = ng.target_names[target]
    if per_cat[cat] >= PER_CAT:
        continue
    text = (text or "").strip()
    if len(text) < 200:  # skip one-liners and empty posts
        continue
    (out / f"scale_20news_{cat}_{per_cat[cat]:04d}.txt").write_text(text, encoding="utf-8")
    per_cat[cat] += 1
    kept += 1

print(f"kept={kept} per_cat={per_cat}")
