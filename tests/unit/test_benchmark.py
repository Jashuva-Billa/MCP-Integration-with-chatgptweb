"""Unit tests for benchmark metric aggregation."""
from app.core.benchmark import _aggregate


def test_benchmark_aggregates_success_regression_latency_and_cost():
    summary = _aggregate("sample-agent", [
        {"success": True, "regression": False, "repair_attempts": 1, "tool_failures": 0,
         "latency_seconds": 4.0, "cost_usd": 0.01},
        {"success": False, "regression": True, "repair_attempts": 3, "tool_failures": 2,
         "latency_seconds": 6.0, "cost_usd": 0.03},
    ])
    assert summary["cases"] == 2
    assert summary["success_rate"] == 0.5
    assert summary["regression_rate"] == 0.5
    assert summary["mean_repair_attempts"] == 2
    assert summary["mean_tool_failures"] == 1
    assert summary["mean_latency_seconds"] == 5
    assert summary["known_cost_usd"] == 0.04


def test_benchmark_does_not_invent_cost():
    summary = _aggregate("sample-agent", [
        {"success": True, "latency_seconds": 1, "cost_usd": None},
    ])
    assert summary["known_cost_usd"] is None


def test_record_external_chatgpt_benchmark_without_api(tmp_path, monkeypatch):
    import app.core.benchmark as benchmark

    monkeypatch.setattr(benchmark, "_BENCH_DIR", tmp_path)
    monkeypatch.setattr(benchmark, "_BENCH_FILE", tmp_path / "runs.jsonl")
    result = benchmark.record_external_benchmark_result(
        case_name="parser-regression",
        agent_name="ChatGPT Web",
        success=True,
        baseline_test_passed=True,
        final_test_passed=True,
        repair_attempts=1,
        tool_failures=0,
        latency_seconds=42.5,
        repository_revision="abc123",
    )
    assert result["success"] is True
    report = benchmark.get_benchmark_report()
    assert report["total_runs"] == 1
    assert report["records"][0]["agent"] == "ChatGPT Web"
    assert report["records"][0]["cost_usd"] is None
    assert report["summary"][0]["success_rate"] == 1.0
