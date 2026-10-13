"""Negative evidence cases through the real collector and capability readers."""

import json
import os
import sqlite3
import time

from test_atuin_matching import _make_atuin_db, census


def test_zero_upper_bounds_are_not_replaced_with_now(tmp_path, monkeypatch):
    _make_atuin_db(tmp_path / ".local/share/atuin/history.db", ["neutral"])
    monkeypatch.setattr(census, "HOME", tmp_path)
    assert census.atuin_evidence(["neutral"], 0, 0)["neutral"]["n"] == 0
    captured = []
    monkeypatch.setattr(
        census,
        "run",
        lambda argv, **_kwargs: (
            captured.append(argv) or type("Result", (), {"text": ""})()
        ),
    )
    census.journal_count("neutral.service", 1, False, until=0)
    assert "--until=@0" in captured[0]
    source = tmp_path / "event"
    source.write_text("neutral")
    os.utime(source, (1, 1))
    assert census.lane_freshness(str(source), -5, 0)["n"] == 0


def test_literal_shell_matches_are_not_invocations_and_window_is_real(
    tmp_path, monkeypatch
):
    db = tmp_path / ".local/share/atuin/history.db"
    _make_atuin_db(
        db,
        [
            'echo "sinnix capabilities"',
            "sinnix capabilities",
            "sinnix-capabilities",
            "sinnix capabilities_old",
        ],
    )
    monkeypatch.setattr(census, "HOME", tmp_path)
    result = census.atuin_evidence(
        ["sinnix capabilities"], 2_000_000_000, 3_000_000_000
    )
    assert result["sinnix capabilities"]["n"] == 1
    result = census.atuin_evidence(["sinnix capabilities"], 0, 10_000_000_000)
    assert (
        result["sinnix capabilities"]["n"] == 1
    )  # quoted end does not match this literal
    assert result["sinnix capabilities"]["type"] == "shell-history-match"
    assert result["sinnix capabilities"]["caller_identity"] == "unknown"
    assert (
        census.verdict({"atuin": {"n": 0}, "polylogue": {"n": 5}}, [], False)
        == "unknown"
    )
    assert census.verdict({"journald": {"n": 20}}, [], False) == "unknown"
    assert census.verdict({"filesystem": {"n": 1}}, [], False) == "unknown"
    assert census.verdict({"atuin": {"n": 0}}, [], False) == "unknown"


def audit_db(path, events):
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE events(sequence INTEGER PRIMARY KEY, event_id TEXT, occurred_at REAL, operation TEXT, outcome TEXT, payload_json TEXT, profile TEXT)"
        )
        conn.executemany("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?)", events)


def test_audit_is_typed_bounded_windowed_and_private(tmp_path):
    path = tmp_path / "audit.sqlite3"
    audit_db(
        path,
        [
            (
                1,
                "old",
                1,
                "files.read",
                "ok",
                "SECRET raw arguments transcript",
                "operator",
            ),
            (2, "real", 101, "files.read", "ok", "SECRET", "operator"),
            (3, "failed", 102, "files.read", "error", "SECRET", "supplied-agent"),
            (4, "failed", 102, "files.read", "error", "SECRET", "operator"),
            (5, "future", 400, "files.read", "ok", "SECRET", "operator"),
        ],
    )
    result = census.gateway_evidence(path, 100, 200, 3)
    assert result["capped"] and result["count_basis"] == "lower-bound"
    assert result["actions"]["files.read"]["n"] == 1
    result = census.gateway_evidence(path, 100, 200, 10)
    assert result["actions"]["files.read"]["outcomes"] == {"ok": 1, "error": 1}
    assert result["caller_identity"] == "unknown"
    encoded = json.dumps(result)
    for private in [
        "SECRET",
        "payload_json",
        "supplied-agent",
        "operator",
        "transcript",
    ]:
        assert private not in encoded
    assert (
        census.gateway_evidence(tmp_path / "missing", 100, 200)["status"]
        == "unavailable"
    )
    malformed = tmp_path / "bad"
    malformed.write_text("bad")
    assert census.gateway_evidence(malformed, 100, 200)["status"] == "unavailable"


def test_real_collector_public_dispatch_dependency_and_missing_inventory(
    tmp_path, monkeypatch, capsys
):
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    for name in ["modules", "flake", "pkgs", "dots", "docs", ".agentctl"]:
        (repo / name).mkdir()
    (repo / "scripts/sinnix-capabilities").write_text(
        "# @sinnix-package\n# runtimeInputs: @helper\n"
    )
    (repo / "scripts/sinnix-helper").write_text("# @sinnix-package: skip\n")
    index = tmp_path / "index.json"
    index.write_text(
        json.dumps(
            {
                "schema": "sinnix-capability-index-v1",
                "revision": "r",
                "rows": [
                    {
                        "kind": "script",
                        "name": "sinnix-capabilities",
                        "invoke": "sinnix capabilities",
                    },
                    {
                        "kind": "command",
                        "name": "typed",
                        "invoke": "sinnix-agent-gateway call files.read",
                    },
                ],
            }
        )
    )
    _make_atuin_db(
        tmp_path / ".local/share/atuin/history.db",
        ["sinnix capabilities", "echo sinnix-capabilities # quoted/prose occurrence"],
    )
    with sqlite3.connect(tmp_path / ".local/share/atuin/history.db") as conn:
        conn.execute(
            "UPDATE history SET timestamp = ?", (time.time_ns() - 2_000_000_000,)
        )
    now = int(time.time())
    audit = tmp_path / "audit.sqlite3"
    audit_db(
        audit,
        [
            (1, "ok", now - 1, "files.read", "ok", "PRIVATE", "operator"),
            (2, "failed", now - 2, "files.read", "error", "PRIVATE", "operator"),
        ],
    )
    monkeypatch.setattr(census, "REPO", repo)
    monkeypatch.setattr(census, "HOME", tmp_path)
    monkeypatch.setattr(census, "INVENTORY", tmp_path / "absent-runtime")
    monkeypatch.setattr(census, "SECRET_DIR", tmp_path / "absent-secrets")
    out = tmp_path / "report.jsonl"
    monkeypatch.setattr(
        "sys.argv",
        [
            "census",
            "--index",
            str(index),
            "--gateway-audit",
            str(audit),
            "--classes",
            "scripts,commands,services,secrets",
            "--jsonl-out",
            str(out),
            "--json",
        ],
    )
    assert census.main() == 0
    snapshot = json.loads(capsys.readouterr().out)
    rows = {r["name"]: r for r in snapshot["rows"]}
    assert rows["sinnix-capabilities"]["evidence"]["atuin"]["identities"] == [
        "sinnix capabilities",
        "sinnix-capabilities",
    ]
    assert rows["sinnix-capabilities"]["verdict"] == "shell-match-observed"
    assert rows["sinnix-helper"]["verdict"] == "referenced-only"
    assert rows["sinnix-helper"]["dependency_consumers"] == ["sinnix-capabilities"]
    assert rows["typed"]["verdict"] == "attempt-observed"
    assert rows["typed"]["evidence"]["gateway"]["outcomes"] == {"ok": 1, "error": 1}
    assert {g["class"] for g in snapshot["coverage_gaps"]} == {"services", "secrets"}
    assert "PRIVATE" not in out.read_text()
    monkeypatch.setattr(
        "sys.argv",
        [
            "census",
            "--index",
            str(tmp_path / "absent"),
            "--classes",
            "features,skills",
            "--no-write",
            "--json",
        ],
    )
    assert census.main() == 0
    missing = json.loads(capsys.readouterr().out)
    assert missing["row_count"] == 0
    assert {g["class"] for g in missing["coverage_gaps"]} == {"features", "skills"}


def test_history_append_never_truncates_torn_history(tmp_path):
    path = tmp_path / "census.jsonl"
    path.write_bytes(b'old historical row\n{"torn":')
    census.append_snapshot(path, {"complete": True})
    assert path.read_bytes().startswith(b'old historical row\n{"torn":\n')


def test_startup_freshness_and_secret_inventory_never_prove_client_use(
    tmp_path, monkeypatch, capsys
):
    inventory = tmp_path / "runtime.json"
    inventory.write_text(json.dumps({"surfaces": {"idle": {"unit": "idle.service"}}}))
    index = tmp_path / "index.json"
    capture = tmp_path / "producer"
    capture.write_text("producer bytes")
    index.write_text(
        json.dumps(
            {
                "schema": "sinnix-capability-index-v1",
                "revision": "r",
                "rows": [
                    {"kind": "capture-lane", "name": "producer", "path": str(capture)}
                ],
            }
        )
    )
    secret = tmp_path / "secrets"
    secret.mkdir()
    (secret / "retained.age").write_text("DO NOT READ ME")
    monkeypatch.setattr(census, "INVENTORY", inventory)
    monkeypatch.setattr(census, "SECRET_DIR", secret)
    monkeypatch.setattr(census, "HOME", tmp_path)
    monkeypatch.setattr(census, "journal_count", lambda *args, **kwargs: 17)
    monkeypatch.setattr(census, "static_refs", lambda name: [])
    monkeypatch.setattr(
        "sys.argv",
        [
            "census",
            "--index",
            str(index),
            "--gateway-audit",
            str(tmp_path / "missing"),
            "--classes",
            "services,capture-lanes,secrets,skills",
            "--no-write",
            "--json",
        ],
    )
    assert census.main() == 0
    snap = json.loads(capsys.readouterr().out)
    rows = {r["name"]: r for r in snap["rows"]}
    assert rows["idle"]["evidence"]["journald"]["n"] == 17
    assert rows["idle"]["verdict"] == "unknown"
    assert rows["producer"]["verdict"] == "unknown"
    assert rows["retained"]["never_prune"] and rows["retained"]["verdict"] == "unknown"
    assert "DO NOT READ ME" not in json.dumps(snap)
    assert any(g["class"] == "skills" for g in snap["coverage_gaps"])


def test_malformed_and_duplicate_declaration_rows_are_rejected():
    base = {
        "schema": "sinnix-capability-index-v1",
        "rows": [{"kind": "script", "name": "x"}],
    }
    assert census.load_capability_index(base) is not None
    assert census.load_capability_index({**base, "rows": base["rows"] * 2}) is None
    assert census.load_capability_index({**base, "rows": [None]}) is None


def test_static_search_is_literal_and_excludes_generated_cache(tmp_path, monkeypatch):
    for directory in [
        "modules",
        "flake",
        "scripts",
        "pkgs",
        "dots",
        "docs",
        ".agentctl",
    ]:
        (tmp_path / directory).mkdir()
    (tmp_path / "modules/near.nix").write_text("scriptXname")
    (tmp_path / "modules/real.nix").write_text("script.name")
    (tmp_path / "pkgs/.pytest_cache").mkdir()
    (tmp_path / "pkgs/.pytest_cache/nodeids").write_text("script.name")
    monkeypatch.setattr(census, "REPO", tmp_path)
    assert census.static_refs("script.name") == ["modules/real.nix"]


def test_shell_like_wildcards_are_literal(tmp_path, monkeypatch):
    _make_atuin_db(
        tmp_path / ".local/share/atuin/history.db",
        ["foo_bar", "fooXbar", "100%cmd", "100XXcmd"],
    )
    monkeypatch.setattr(census, "HOME", tmp_path)
    result = census.atuin_evidence(["foo_bar", "100%cmd"], 0, 10_000_000_000)
    assert result["foo_bar"]["n"] == result["100%cmd"]["n"] == 1
