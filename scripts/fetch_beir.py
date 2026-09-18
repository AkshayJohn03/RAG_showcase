"""Fetch BEIR SciFact (fact-verification retrieval benchmark).

Source: official BEIR hosting (Thakur et al., NeurIPS 2021).
Layout after run: data/beir/scifact/{corpus.jsonl, queries.jsonl, qrels/test.tsv}
"""
import urllib.request
import zipfile
from pathlib import Path

URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip"
DEST = Path("data/beir")
DEST.mkdir(parents=True, exist_ok=True)
ZIP = DEST / "scifact.zip"

if not (DEST / "scifact" / "corpus.jsonl").exists():
    print(f"fetching {URL} ...", flush=True)
    import shutil
    import subprocess
    # curl preference order: POSIX curl → Windows curl.exe (uses the Windows cert
    # store, surviving corporate TLS proxies that break Python's ssl module) →
    # urllib fallback (may fail behind MITM proxies; then download manually).
    curl = shutil.which("curl") or shutil.which("curl.exe")
    if curl:
        subprocess.run([curl, "-L", "-o", str(ZIP), URL], check=True)
    else:
        import urllib.request
        urllib.request.urlretrieve(URL, ZIP)
    print("extracting...", flush=True)
    with zipfile.ZipFile(ZIP, "r") as z:
        z.extractall(DEST)
    ZIP.unlink()
    print("done.", flush=True)
else:
    print("scifact already present.", flush=True)

for f in ["corpus.jsonl", "queries.jsonl"]:
    p = DEST / "scifact" / f
    n = sum(1 for _ in p.open(encoding="utf-8"))
    print(f"{f}: {n} lines")
print("qrels:", [p.name for p in (DEST / "scifact" / "qrels").glob("*")])
