import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).parents[3] / "scripts/sinnix-borg-drill"


def run_drill(tmp_path, response, list_exit=0):
    mock = tmp_path / "borg"
    mock.write_text(f"#!{sys.executable}\n" + """
import json, os, sys
with open(os.environ['CALLS'], 'a') as f:
    f.write(json.dumps(sys.argv[1:]) + '\\n')
if sys.argv[1] == 'list':
    print(os.environ['RESPONSE'])
    print('synthetic listing diagnostic', file=sys.stderr)
    sys.exit(int(os.environ['LIST_EXIT']))
""")
    mock.chmod(0o755)
    log = tmp_path / "receipt.jsonl"
    env = dict(os.environ, PATH=str(tmp_path) + ":" + os.environ["PATH"],
               BORG_PASSCOMMAND="unused", SINNIX_BORG_GLOBAL_LOCK=str(tmp_path / "lock"),
               TMPDIR=str(tmp_path), CALLS=str(tmp_path / "calls"), RESPONSE=response,
               LIST_EXIT=str(list_exit))
    result = subprocess.run(["bash", str(SCRIPT), "--verify-data", "--repo", "fixture",
                             "--log", str(log)], env=env, capture_output=True, text=True)
    receipts = [json.loads(s) for s in log.read_text().splitlines()] if log.exists() else []
    calls = [json.loads(s) for s in (tmp_path / "calls").read_text().splitlines()]
    return result, receipts, calls


@pytest.mark.parametrize("status,response", [(1, ""), (2, ""), (1, '{"archives":[]}')])
def test_failed_listing_is_not_an_empty_repository(tmp_path, status, response):
    result, receipts, calls = run_drill(tmp_path, response, status)
    assert result.returncode != 0
    assert receipts[0]["status"] == "failed"
    assert receipts[0]["exit_code"] == status
    assert "synthetic listing diagnostic" in receipts[0]["stderr_tail"]
    assert len(calls) == 1


@pytest.mark.parametrize("response", ['invalid', '{}', '{"archives":null}'])
def test_malformed_listing_has_a_failure_receipt(tmp_path, response):
    result, receipts, calls = run_drill(tmp_path, response)
    assert result.returncode != 0
    assert receipts[0]["status"] == "failed"
    assert len(calls) == 1


def test_successful_empty_listing_remains_distinct(tmp_path):
    result, receipts, calls = run_drill(tmp_path, '{"archives":[]}')
    assert result.returncode == 0
    assert receipts[0]["status"] == "no_archives"
    assert len(calls) == 1


def test_selected_archive_is_checked_by_exact_address(tmp_path):
    response = json.dumps({"archives": [{"archive": "prefix", "time": "2999-01-01T00:00:00"}]})
    result, receipts, calls = run_drill(tmp_path, response)
    assert result.returncode == 0, result.stderr
    assert calls[-1] == ["check", "--verify-data", "fixture::prefix"]
    assert receipts[0]["archive"] == "prefix"
