from sinnix_runtime.observe.sources.xtask import resolve_running


def _row(**extra):
    row = {"status": "running", "pid": 42, "boot_id": "b1", "process_start": 7, "agentctl_job": None}
    row.update(extra)
    return row


def test_live_running_row_stays_running():
    out = resolve_running(_row(), boot_id=lambda: "b1", process_start=lambda pid: 7, timed_out=lambda j: False)
    assert out["status"] == "running"


def test_row_from_another_boot_is_interrupted():
    out = resolve_running(_row(), boot_id=lambda: "b2", process_start=lambda pid: 7, timed_out=lambda j: False)
    assert out["status"] == "interrupted"


def test_dead_row_with_timed_out_job_reads_timeout():
    out = resolve_running(
        _row(agentctl_job="polylogue-check-1"),
        boot_id=lambda: "b1",
        process_start=lambda pid: None,
        timed_out=lambda j: j == "polylogue-check-1",
    )
    assert out["status"] == "timeout"


def test_finished_rows_are_untouched():
    row = _row(status="passed")
    assert resolve_running(row) is row
