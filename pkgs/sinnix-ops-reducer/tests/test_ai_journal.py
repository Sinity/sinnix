import json
import sys

from sinnix_ops_reducer.pages import ai


def test_journal_limits_rows_and_fields_before_capture(tmp_path, monkeypatch):
    producer = tmp_path / "journalctl"
    observation = tmp_path / "emitted.json"
    producer.write_text(
        "#!" + sys.executable + "\n"
        "import json,sys\nfrom pathlib import Path\n"
        "args=sys.argv; count=int(args[args.index('-n')+1]) if '-n' in args else 1000\n"
        "selected=next((set(a.split('=',1)[1].split(',')) for a in args if a.startswith('--output-fields=')),None)\n"
        "for i in range(1000-count,1000):\n"
        " row={'JOB_RESULT':'done','JOB_TYPE':'start','UNIT':'fixture.service','__REALTIME_TIMESTAMP':str(i+1),'MESSAGE':'unused payload'*100}\n"
        " if selected is not None: row={k:v for k,v in row.items() if k in selected}\n"
        " print(json.dumps(row))\n"
        + "Path(" + repr(str(observation)) + ").write_text(json.dumps({'count':count,'fields':list(row),'args':args[1:]}))\n"
    )
    producer.chmod(0o700)
    monkeypatch.setattr(ai.shutil, "which", lambda _: str(producer))
    monkeypatch.setattr(ai, "GPU_EVICTION_MAX_EVENTS", 2)
    events, error = ai.gpu_lifecycle_events(["fixture.service", "second.service"])
    assert error is None
    assert events == [
        {"unit": "fixture.service", "type": "start", "ts": 999},
        {"unit": "fixture.service", "type": "start", "ts": 1000},
    ]
    emitted = json.loads(observation.read_text())
    assert emitted["count"] == 2  # A late Python slice alone must fail.
    assert set(emitted["fields"]) == {"JOB_RESULT", "JOB_TYPE", "UNIT", "__REALTIME_TIMESTAMP"}
    assert emitted["args"][emitted["args"].index("--since") + 1] == ai.GPU_EVICTION_SINCE
    assert emitted["args"].count("-u") == 2
    assert "fixture.service" in emitted["args"] and "second.service" in emitted["args"]
