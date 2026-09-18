"""Minimal Prometheus exposition (stdlib only).

Tracks: request counts + latency histograms per endpoint, indexed-chunk gauge,
eval gate status, feedback votes. Scrape with Prometheus, alert with Alertmanager.
"""
from __future__ import annotations
import threading

_lock = threading.Lock()
_counts: dict[tuple[str, int], int] = {}
_counters: dict[tuple[str, tuple], int] = {}
_hists: dict[str, list[int]] = {}
_gauges: dict[str, float] = {}
BUCKETS = [25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]


def observe(path: str, status: int, ms: int) -> None:
    route = "/" + (path.strip("/").split("/")[0] if path.strip("/") else "")
    with _lock:
        _counts[(route, status)] = _counts.get((route, status), 0) + 1
        _hists.setdefault(route, []).append(ms)
        if len(_hists[route]) > 2000:  # rolling window, not unbounded
            _hists[route] = _hists[route][-2000:]


def set_gauge(name: str, value: float) -> None:
    with _lock:
        _gauges[name] = value


def bump(name: str, labels: dict | None = None) -> None:
    """Monotonic counter with REAL Prometheus labels (not string-interpolated)."""
    key = (name, tuple(sorted((labels or {}).items())))
    with _lock:
        _counters[key] = _counters.get(key, 0) + 1


def _esc(value: str) -> str:
    """Prometheus label escaping: backslash, double-quote, newline."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def exposition() -> str:
    lines = ["# HELP rag_requests_total HTTP requests by route and status",
             "# TYPE rag_requests_total counter"]
    with _lock:
        for (route, status), n in sorted(_counts.items()):
            lines.append(f'rag_requests_total{{route="{_esc(route)}",status="{status}"}} {n}')
        lines.append("# HELP rag_events_total domain events (feedback votes, fallbacks)")
        lines.append("# TYPE rag_events_total counter")
        for (name, labels), n in sorted(_counters.items()):
            lab = "".join(f',{k}="{_esc(str(v))}"' for k, v in labels)
            lines.append(f'rag_events_total{{event="{_esc(name)}"{lab}}} {n}')
        lines.append("# HELP rag_request_ms request latency milliseconds (raw recent observations summarized)")
        lines.append("# TYPE rag_request_ms summary")
        for route, obs in sorted(_hists.items()):
            if not obs:
                continue
            s = sorted(obs)
            lines.append(f'rag_request_ms_count{{route="{route}"}} {len(s)}')
            lines.append(f'rag_request_ms_sum{{route="{route}"}} {sum(s)}')
            lines.append(f'rag_request_ms_p50{{route="{route}"}} {s[len(s)//2]}')
            lines.append(f'rag_request_ms_p95{{route="{route}"}} {s[min(len(s)-1, int(len(s)*0.95))]}')
        lines.append("# HELP rag_gauge operational gauges")
        lines.append("# TYPE rag_gauge gauge")
        for name, val in sorted(_gauges.items()):
            lines.append(f'rag_gauge{{name="{_esc(name)}"}} {val}')
    return "\n".join(lines) + "\n"
