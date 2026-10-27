import subprocess

from sinnix_lib.notify import notify_phone


def test_phone_sink_deduplicates_and_expires(tmp_path, monkeypatch):
    monkeypatch.setattr("os.geteuid", lambda: 1000)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr("shutil.which", lambda _: "/synthetic/dispatcher")
    clock = [1000]
    monkeypatch.setattr("time.time", lambda: clock[0])
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, "run", run)
    assert notify_phone("title", "body", key="alarm")
    assert not notify_phone("title", "changed", key="alarm")
    assert notify_phone("title", "body", key="other")
    clock[0] += 301
    assert notify_phone("title", "body", key="alarm")
    assert len(calls) == 3
    assert calls[0][0] == ["/synthetic/dispatcher", "notify", "title", "body"]
    assert calls[0][1]["timeout"] == 2


def test_phone_sink_timeout_is_silent_and_not_retried(tmp_path, monkeypatch):
    monkeypatch.setattr("os.geteuid", lambda: 1000)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr("shutil.which", lambda _: "/synthetic/dispatcher")
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        raise subprocess.TimeoutExpired(args, 2)

    monkeypatch.setattr(subprocess, "run", run)
    assert not notify_phone("title", "body", key="alarm")
    assert not notify_phone("title", "body", key="alarm")
    assert len(calls) == 1


def test_system_alarm_queues_as_session_owner(tmp_path, monkeypatch):
    from pathlib import Path
    from sinnix_lib import notify

    monkeypatch.setattr("os.geteuid", lambda: 0)
    monkeypatch.setattr("shutil.which", lambda _: "/synthetic/dispatcher")
    monkeypatch.setenv("SINNIX_RUNTIME_DIR", str(tmp_path / "runtime"))
    users = tmp_path / "users"
    bus = users / "1000/bus"
    bus.parent.mkdir(parents=True)
    bus.touch()
    monkeypatch.setattr(Path, "is_socket", lambda path: path == bus)
    monkeypatch.setattr(notify, "USER_BUS_ROOT", users)
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, "run", run)
    assert notify_phone("title", "body", key="alarm")
    assert calls == [
        [
            "sudo",
            "-u",
            "#1000",
            "--",
            "/synthetic/dispatcher",
            "notify",
            "title",
            "body",
        ]
    ]
