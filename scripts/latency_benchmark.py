"""Read-only latency benchmark for the local MCP service and representative tools."""
from __future__ import annotations

import statistics
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def measure(label, fn, repeats=5):
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        try:
            result = fn()
            samples.append((time.perf_counter() - start) * 1000)
            if isinstance(result, dict) and result.get("error"):
                print(f"  note: {result['error']}")
        except Exception as exc:
            print(f"  error: {type(exc).__name__}: {exc}")
    if samples:
        ordered = sorted(samples)
        p95_index = min(len(ordered) - 1, int(0.95 * len(ordered)))
        print(f"{label:34} avg={statistics.mean(samples):7.2f} ms min={min(samples):7.2f} ms max={max(samples):7.2f} ms p95~={ordered[p95_index]:7.2f} ms")


def get_health(url):
    req = urllib.request.Request(url, headers={"User-Agent": "MCP-Latency-Benchmark/1.0"})
    with urllib.request.urlopen(req, timeout=12) as response:
        response.read()
        return response.status


def main():
    print("MCP latency benchmark (read-only; times are approximate)")
    print(f"Repository: {ROOT}")
    tunnel_file = ROOT / "runtime" / "tunnel.url"
    public_url = tunnel_file.read_text(encoding="utf-8").strip() if tunnel_file.exists() else ""
    measure("local health HTTP", lambda: get_health("http://127.0.0.1:8766/health"))
    if public_url.startswith("https://"):
        measure("public tunnel health HTTP", lambda: get_health(public_url + "/health"), repeats=5)
    else:
        print("public tunnel health HTTP          skipped (runtime/tunnel.url unavailable)")

    from app.tools import filesystem, git, search, workspace, quick_inspect
    measure("repository listing", workspace.list_repositories)
    measure("shallow file listing", lambda: filesystem.list_files(".", recursive=False, max_results=100))
    measure("targeted Python search", lambda: search.search_code("def ", file_extension="py", max_results=20))
    measure("git status", git.git_status)
    measure("combined workspace inspection", lambda: quick_inspect.inspect_workspace(max_files=60))
    print("Benchmark complete. The benchmark itself is read-only.")


if __name__ == "__main__":
    main()
