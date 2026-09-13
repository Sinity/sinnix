"""Native Beads JSON retains types across the process adapter."""

from __future__ import annotations

from test_beads import beads_service, commands


def test_metadata_values_are_not_coerced_into_cli_strings(tmp_path):
    beads, log = beads_service(tmp_path)
    values = {
        "array": ["a", 2],
        "object": {"nested": True},
        "integer": 7,
        "float": 1.25,
        "boolean": False,
        "null": None,
        "string": "text",
        "literal_true": "true",
        "literal_null": "null",
        "literal_number": "123",
        "literal_array": "[1,2]",
    }
    payload = {
        "path": {"id": "fixture-1"},
        "body": {
            "actor": "operator",
            "expected_version": 7773497739344011640,
            "patch": {"metadata": {"set": values}},
        },
    }
    result = beads.native("fixture", "updateIssue", payload, write=True)
    assert commands(log)[-1]["payload"] == payload
    assert result["request"]["body"]["expected_version"] == 7773497739344011640
