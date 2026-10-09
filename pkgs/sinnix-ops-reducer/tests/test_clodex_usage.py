import importlib
import json
from pathlib import Path

import pytest
from sinnix_ops_reducer.clodex_usage import clodex_usage
from sinnix_ops_reducer.reducer import Reducer

usage_module = importlib.import_module("sinnix_ops_reducer.clodex_usage")


def usage_row(tokens: object) -> bytes:
    return (
        json.dumps(
            {
                "event": "response_usage",
                "route": "translated",
                "inputTokens": tokens,
                "outputTokens": 1,
                "cacheReadInputTokens": 0,
                "cacheCreationInputTokens": 0,
            }
        )
        + "\n"
    ).encode()


def test_accounting_reads_the_end_of_a_growing_log(tmp_path: Path) -> None:
    path = tmp_path / "usage.jsonl"
    path.write_bytes(usage_row(7) + b"{}\n" * (usage_module.MAX_BYTES // 3 + 1))
    with path.open("ab") as handle:
        handle.write(usage_row(91))
    value, _health = clodex_usage(path)
    assert value["requests"] == 1 and value["input_tokens"] == 91


@pytest.mark.parametrize("boundary", [b"\n", b"x"])
def test_tail_preserves_only_complete_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: bytes
) -> None:
    first, second = usage_row(7), usage_row(91)
    monkeypatch.setattr(usage_module, "MAX_BYTES", len(first + second))
    path = tmp_path / "usage.jsonl"
    path.write_bytes(b"prefix" + boundary + first + second)
    value, _health = clodex_usage(path)
    assert value["requests"] == (2 if boundary == b"\n" else 1)
    assert value["input_tokens"] == (98 if boundary == b"\n" else 91)


@pytest.mark.parametrize("invalid", [float("inf"), float("nan"), True, -1])
def test_invalid_counts_do_not_crash_or_manufacture_usage(
    tmp_path: Path, invalid: object
) -> None:
    path = tmp_path / "usage.jsonl"
    path.write_bytes(usage_row(invalid) + usage_row(91))
    value, _health = clodex_usage(path)
    assert value["requests"] == 1 and value["input_tokens"] == 91


def test_routed_usage_is_aggregated_without_request_data(tmp_path: Path) -> None:
    path = tmp_path / "inference-requests.jsonl"
    path.write_text(
        "\n".join(
            json.dumps(row)
            for row in [
                {
                    "event": "response_usage",
                    "route": "translated",
                    "inputTokens": 12,
                    "outputTokens": 4,
                    "cacheReadInputTokens": 2,
                    "cacheCreationInputTokens": 1,
                    "timestamp": "2026-09-01T00:00:00Z",
                    "requestPreview": "SECRET",
                },
                {
                    "event": "response_usage",
                    "route": "translated",
                    "inputTokens": 8,
                    "outputTokens": 3,
                    "cacheReadInputTokens": 0,
                    "cacheCreationInputTokens": 0,
                    "timestamp": "2026-09-01T00:01:00Z",
                },
                {
                    "event": "response_usage",
                    "route": "passthrough",
                    "inputTokens": 999,
                    "outputTokens": 999,
                },
            ]
        )
        + "\n"
    )
    value, health = clodex_usage(path)
    assert value == {
        "requests": 2,
        "input_tokens": 20,
        "output_tokens": 7,
        "cache_read_tokens": 2,
        "cache_write_tokens": 1,
        "last_recorded_at": "2026-09-01T00:01:00Z",
    }
    assert health["status"] == "healthy"
    assert "SECRET" not in json.dumps(value)


def test_missing_accounting_is_unavailable_not_zero(tmp_path: Path) -> None:
    value, health = clodex_usage(tmp_path / "missing.jsonl")
    assert value == {}
    assert health["status"] == "unavailable"


def test_usage_fixture_is_published_with_source_health_and_is_mutable(
    tmp_path: Path,
) -> None:
    path = tmp_path / "inference-requests.jsonl"
    path.write_text(
        json.dumps(
            {
                "event": "response_usage",
                "route": "translated",
                "inputTokens": 5,
                "outputTokens": 2,
                "cacheReadInputTokens": 1,
                "cacheCreationInputTokens": 0,
                "timestamp": "2026-09-01T00:00:00Z",
                "requestBody": "PRIVATE_REQUEST",
            }
        )
        + "\n"
    )
    reducer = Reducer(
        tmp_path / "status.json",
        tmp_path / "token",
        lambda: {"report": 1},
        clodex_usage_source=lambda: clodex_usage(path),
    )

    snapshot = reducer.refresh()

    assert snapshot["sources"]["clodex"] == {
        "status": "healthy",
        "source": "clodex-inference-accounting",
        "freshness": "current",
        "degradation": None,
        "observed_at": snapshot["observed_at"],
    }
    assert snapshot["state"]["clodex"]["output_tokens"] == 2
    serialized = json.dumps(snapshot)
    assert "PRIVATE_REQUEST" not in serialized

    path.write_text(
        json.dumps(
            {
                "event": "response_usage",
                "route": "translated",
                "inputTokens": 5,
                "outputTokens": 9,
                "cacheReadInputTokens": 1,
                "cacheCreationInputTokens": 0,
            }
        )
        + "\n"
    )
    changed = reducer.refresh()
    assert changed["state"]["clodex"]["output_tokens"] == 9

    path.unlink()
    unavailable = reducer.refresh()
    assert unavailable["state"]["clodex"] == {}
    assert unavailable["sources"]["clodex"]["status"] == "unavailable"
