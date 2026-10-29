# Real guest sensors. The maintained synthetic signal matrix stays separate.
{ pkgs, host }:
let
  fixture = pkgs.writeText "earlyoom-real-pressure.py" (
    builtins.readFile ./earlyoom_real_pressure.py
  );
  evidence = pkgs.writeText "earlyoom-pressure-evidence.py" (
    builtins.readFile ./earlyoom_pressure_evidence.py
  );
  command = mode: "${pkgs.python3}/bin/python3 ${fixture} ${mode}";
in
pkgs.testers.runNixOSTest {
  name = "earlyoom-real-pressure";
  globalTimeout = 360;
  nodes.machine = { lib, ... }: {
    virtualisation.memorySize = 1536;
    virtualisation.cores = 2;
    virtualisation.graphics = false;
    virtualisation.qemu.options = [ "-vga none" ];
    virtualisation.qemu.consoles = [ "ttyS0" ];
    virtualisation.diskSize = 512;
    virtualisation.emptyDiskImages = [ 512 ];
    zramSwap = {
      enable = true;
      memoryMax = 128 * 1024 * 1024;
    };
    users.users.fixture = {
      isNormalUser = true;
      uid = 1000;
      linger = true;
    };
    environment.systemPackages = [ pkgs.python3 ];
    services.earlyoom = {
      enable = true;
      inherit (host.services.earlyoom) package enableNotifications;
    };
    systemd.services.earlyoom = {
      wantedBy = lib.mkForce [ ];
      environment.EARLYOOM_ARGS = lib.mkForce host.systemd.services.earlyoom.environment.EARLYOOM_ARGS;
    };
    systemd.user.slices.agent-tool.sliceConfig = {
      # Real reclaim produces PSI; no fabricated sensor or hard memcg OOM.
      MemoryHigh = "900M";
    };
    systemd.user.services.pressure-victim.serviceConfig = {
      ExecStart = command "victim";
      Slice = "agent-tool.slice";
      OOMScoreAdjust = 1000;
      RuntimeMaxSec = "140s";
      TimeoutStopSec = "1s";
    };
    systemd.user.services.pressure-observer.serviceConfig = {
      ExecStart = command "observe";
      Slice = "app.slice";
      OOMScoreAdjust = 0;
      RuntimeMaxSec = "150s";
      TimeoutStopSec = "1s";
    };
    systemd.services.pressure-sampler.serviceConfig = {
      ExecStart = command "sample";
      RuntimeMaxSec = "150s";
      TimeoutStopSec = "1s";
      OOMScoreAdjust = -1000;
    };
    systemd.services.pressure-transition = {
      path = [
        pkgs.util-linux
        pkgs.systemd
      ];
      serviceConfig = {
        ExecStart = command "transition";
        RuntimeMaxSec = "75s";
        TimeoutStopSec = "1s";
        OOMScoreAdjust = -1000;
      };
    };
    # Guest disk work is finite and independently bounded by the host operation.
    systemd.services.pressure-io.serviceConfig = {
      ExecStart = command "io";
      IOAccounting = true;
      RuntimeMaxSec = "140s";
      TimeoutStopSec = "1s";
      OOMScoreAdjust = -1000;
    };
  };
  testScript = ''
    import json
    import time
    import runpy

    gate_helpers = runpy.run_path("${evidence}")
    start_all()
    machine.wait_for_unit("multi-user.target")
    machine.wait_for_unit("user@1000.service")
    user = "runuser -u fixture -- env XDG_RUNTIME_DIR=/run/user/1000 systemctl --user"
    machine.succeed("mkdir -m 777 /run/real-pressure")
    machine.succeed("${command "graphics"}")
    machine.succeed("mkfs.ext4 -q /dev/vdb; mkdir -p /mnt/pressure; mount /dev/vdb /mnt/pressure")
    machine.succeed("systemctl cat earlyoom.service > /run/real-pressure/earlyoom-unit.txt")
    machine.succeed("swapon --show --bytes > /run/real-pressure/swap-before.txt")
    machine.succeed("systemctl start earlyoom.service")
    machine.wait_until_succeeds("journalctl -u earlyoom.service -o cat --no-pager | grep -q '^mem avail:'", timeout=60)
    machine.succeed(f"{user} start pressure-observer.service pressure-victim.service")
    machine.succeed("systemctl start pressure-io.service pressure-sampler.service pressure-transition.service")
    machine.wait_until_succeeds("test -s /run/real-pressure/observe.ready -a -s /run/real-pressure/victim.ready -a -s /run/real-pressure/io.ready -a -s /run/real-pressure/sample.ready -a -s /run/real-pressure/transition.ready", timeout=30)
    for unit in ("pressure-observer.service", "pressure-victim.service"):
        machine.succeed(f"{user} is-active --quiet {unit}")
    for unit in ("pressure-io.service", "pressure-sampler.service", "pressure-transition.service"):
        machine.succeed(f"systemctl is-active --quiet {unit}")
    protected_pid = machine.succeed(f"{user} show pressure-observer.service -p MainPID --value").strip()
    victim_pid = machine.succeed(f"{user} show pressure-victim.service -p MainPID --value").strip()
    assert protected_pid != "0" and victim_pid != "0", "fixture failed to start"
    machine.succeed("cat /proc/vmstat > /run/real-pressure/vmstat-before.txt")
    machine.succeed("test ! -e /run/real-pressure/go")
    machine.succeed("journalctl -u earlyoom.service -o json --no-pager > /run/real-pressure/earlyoom-before-go.jsonl")
    started = time.monotonic()
    try:
        machine.succeed("read -r begin ignored < /proc/uptime; echo \"$begin\" > /run/real-pressure/go-new; mv /run/real-pressure/go-new /run/real-pressure/go")
        machine.wait_until_succeeds("journalctl -u earlyoom.service -o cat --no-pager | grep -q 'sending SIGKILL'", timeout=95)
        elapsed = time.monotonic() - started
        earlyoom_log = machine.succeed("journalctl -u earlyoom.service -o cat --no-pager")
        machine.succeed("journalctl -u earlyoom.service -o json --no-pager > /run/real-pressure/earlyoom.jsonl")
        assert f"sending SIGKILL to process {victim_pid}" in earlyoom_log, earlyoom_log
        assert f"sending SIGKILL to process {protected_pid}" not in earlyoom_log, earlyoom_log
        machine.wait_until_fails(f"{user} is-active --quiet pressure-victim.service", timeout=10)
        machine.succeed(f"{user} is-active --quiet pressure-observer.service")
        machine.succeed(f"{user} show pressure-victim.service > /run/real-pressure/victim-unit.txt")
        machine.succeed("systemctl show earlyoom.service > /run/real-pressure/earlyoom-before-stop.txt")
        machine.succeed("systemctl stop earlyoom.service")
        machine.wait_until_succeeds("test -s /run/real-pressure/transition.json", timeout=5)
        machine.wait_until_fails("systemctl is-active --quiet pressure-transition.service", timeout=5)
        time.sleep(2)
    finally:
        machine.execute("cat /proc/uptime > /run/real-pressure/probe-end-uptime.txt; cat /proc/vmstat > /run/real-pressure/vmstat-after.txt")
        machine.execute("systemctl show pressure-io.service > /run/real-pressure/io-before-stop.txt")
        machine.execute("systemctl show pressure-sampler.service > /run/real-pressure/sampler-before-stop.txt")
        machine.execute(f"{user} show pressure-observer.service > /run/real-pressure/observer-before-stop.txt")
        machine.execute("systemctl show pressure-transition.service > /run/real-pressure/controller-before-stop.txt")
        machine.execute("systemctl stop earlyoom.service pressure-io.service pressure-sampler.service pressure-transition.service")
        machine.execute("systemctl show pressure-io.service > /run/real-pressure/io-after-stop.txt")
        machine.execute(f"{user} stop pressure-victim.service pressure-observer.service")
        for unit in ("pressure-io.service", "pressure-sampler.service", "pressure-transition.service", "earlyoom.service"):
            machine.execute(f"systemctl show {unit} > /run/real-pressure/{unit}.txt")
        machine.execute(f"{user} show pressure-observer.service > /run/real-pressure/pressure-observer.service.txt")
        machine.execute("journalctl -u earlyoom.service -u pressure-io.service -u pressure-transition.service --no-pager > /run/real-pressure/journal.txt")
        machine.execute("journalctl -k --no-pager > /run/real-pressure/kernel.txt")
        machine.copy_from_machine("/run/real-pressure", "pressure")
    captured = machine.out_dir / "pressure" / "real-pressure"
    samples = [json.loads(line) for line in (captured / "samples.jsonl").read_text().splitlines()]
    transition = json.loads((captured / "transition.json").read_text())
    assert transition["status"] in ("budget_raised", "skipped_victim_exit"), transition
    helper_files = {"pressure-io.service": "io-before-stop.txt", "pressure-sampler.service": "sampler-before-stop.txt", "pressure-transition.service": "controller-before-stop.txt", "earlyoom.service": "earlyoom-before-stop.txt", "pressure-observer.service": "observer-before-stop.txt"}
    for unit, filename in helper_files.items():
        properties = dict(line.split("=", 1) for line in (captured / filename).read_text().splitlines() if "=" in line)
        gate_helpers["validate_helper"](unit, properties)
    assert len(samples) > 10, len(samples)
    def psi_full(text):
        return float(text.split("full avg10=")[1].split()[0])
    def mem_value(text, key):
        return int(next(line.split()[1] for line in text.splitlines() if line.startswith(key + ":")))
    qualifying = [s for s in samples if s["victim_alive"] is True and s["capture_seconds"] < 1 and mem_value(s["meminfo"], "MemAvailable") / mem_value(s["meminfo"], "MemTotal") <= .05 and mem_value(s["meminfo"], "SwapFree") / mem_value(s["meminfo"], "SwapTotal") <= .05 and psi_full(s["pressure/memory"]) >= 10]
    decision = gate_helpers["daemon_decision"]((captured / "earlyoom.jsonl").read_text(), victim_pid)
    assert qualifying or decision, "no explicit pre-exit production kill-gate evidence"
    near_gate = qualifying if qualifying else [s for s in samples if s["victim_alive"] is True and s["capture_seconds"] < 1 and abs(s["monotonic"] - decision["decision_monotonic_us"] / 1_000_000) < 1]
    assert near_gate, "no independent pre-exit counters near daemon decision"
    assert any(psi_full(s["pressure/io"]) > 0 for s in near_gate), "no real IO overlap at gate"
    assert any(int(s["tool"]["memory.swap.current"] or 0) > 0 for s in samples), "victim did not use real swap"
    status = (captured / "victim-unit.txt").read_text()
    assert "ExecMainStatus=9" in status and "Result=signal" in status, status
    if qualifying:
        first_gate = qualifying[0]["monotonic"]
        exited = [s["monotonic"] for s in samples if s["victim_alive"] is False and s["monotonic"] >= first_gate]
        assert exited, "no observed victim exit after real gate"
        gate_to_exit = exited[0] - first_gate
        gate_source, exit_observer = "independent_sample", "independent_sample"
    else:
        gate_to_exit = decision["gate_to_exit_seconds"]
        gate_source, exit_observer = "daemon_decision", decision["gate_to_exit_observer"]
    assert gate_to_exit < 30, gate_to_exit
    def oom_kills(sample):
        return int(next(line.split()[1] for line in sample["vmstat"].splitlines() if line.startswith("oom_kill ")))
    before = (captured / "vmstat-before.txt").read_text()
    after = (captured / "vmstat-after.txt").read_text()
    assert oom_kills({"vmstat": after}) == oom_kills({"vmstat": before}), "guest kernel OOM superseded earlyoom"
    assert elapsed < 95, elapsed
    latency = [json.loads(line)["monotonic"] for line in (captured / "latency.jsonl").read_text().splitlines()]
    pressure_start = float((captured / "go").read_text().strip())
    assert latency[0] <= pressure_start, "protected probe was not ready before pressure"
    probe_end = float((captured / "probe-end-uptime.txt").read_text().split()[0])
    gaps = sorted([b - a for a, b in zip(latency, latency[1:])] + [max(0, probe_end - latency[-1])])
    assert latency[-1] - latency[0] >= 2, "no protected latency coverage"
    assert all(s["tool"]["memory.current"] is not None and s["interactive"]["memory.current"] is not None for s in near_gate), "missing actual PID-derived cgroups"
    assert gaps[-1] < 5, gaps[-1]
    print(json.dumps({"synthetic_pressure": False, "actual_signal": "SIGKILL", "elapsed_seconds": elapsed, "gate_to_exit_seconds": gate_to_exit, "primary_gate_source": gate_source, "exit_observer": exit_observer, "samples": len(samples), "qualifying_samples": len(qualifying), "protected_probe_max_gap_seconds": gaps[-1], "protected_probe_p95_seconds": gaps[int(len(gaps)*.95)], "live_K2": "unverified", "K3": "unverified"}))
  '';
}
