"""Smoke tour: exercises every live endpoint and prints a PASS/FAIL report.

Usage (backend must be running):
    python scripts/smoke.py [--base http://localhost:8000] [--query "..."]

Checks: health, metrics, query (+trace/citations/verification), stream events,
feedback round-trip, eval history, graph neighbors, frontend reachability is
reported separately (npm dev is manual — see start-all.bat).
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request

OK, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def check(name: str, fn):
    try:
        detail = fn() or ""
        results.append((OK, name, str(detail)))
    except Exception as e:
        results.append((FAIL, name, f"{e.__class__.__name__}: {str(e)[:160]}"))


def get(base: str, path: str):
    with urllib.request.urlopen(base + path, timeout=30) as r:
        return r.status, r.read().decode("utf-8", "replace")


def post(base: str, path: str, payload: dict):
    req = urllib.request.Request(base + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--query", default="What does SAF-114 require?")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    def health():
        s, b = get(base, "/health")
        d = json.loads(b)
        assert s == 200 and d["status"] == "ok", b[:200]
        return f"chunks={d['chunks_indexed']} llm={d['llm']}"

    def metrics():
        s, b = get(base, "/metrics")
        assert s == 200 and "rag_requests_total" in b
        return "exposition valid"

    def query():
        s, r = post(base, "/query", {"query": args.query, "top_k": 10})
        assert s == 200 and r["answer"] and r["citations"], json.dumps(r)[:200]
        steps = [t["step"] for t in r.get("trace", [])]
        assert "retrieve" in steps, f"trace={steps}"
        return f"{r['model']} citations={len(r['citations'])} gate={r.get('verification', {}).get('eval_gate')}"

    def stream():
        with urllib.request.urlopen(
                base + "/query/stream?query=" + urllib.parse.quote(args.query), timeout=120) as r:
            body = r.read().decode("utf-8", "replace")
        kinds = {l.split("data:")[0].strip() for l in body.split("\n\n") if l.startswith("event:")}
        assert {"event: trace", "event: token", "event: done"} <= kinds, kinds
        return f"events={sorted(kinds)}"

    def feedback():
        s, r = post(base, "/feedback", {"session_id": "smoke", "query": args.query, "vote": "up"})
        assert r.get("ok") is True
        s2, b2 = get(base, "/feedback/stats")
        assert json.loads(b2)["up"] >= 1
        return "vote recorded + counted"

    def history():
        s, b = get(base, "/eval/history?limit=1")
        assert isinstance(json.loads(b)["runs"], list)
        return "history readable"

    def graph():
        s, b = get(base, "/graph/neighbors?entity=Product%20X")
        assert len(json.loads(b)["triples"]) >= 1
        return f"{len(json.loads(b)['triples'])} triples"

    check("health", health)
    check("metrics", metrics)
    check("query", query)
    check("stream", stream)
    check("feedback", feedback)
    check("eval-history", history)
    check("graph", graph)

    width = max(len(n) for _, n, _ in results)
    failed = 0
    for status, name, detail in results:
        failed += status == FAIL
        print(f"[{status}] {name.ljust(width)}  {detail}")
    print(f"\n{len(results) - failed}/{len(results)} checks passed.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
