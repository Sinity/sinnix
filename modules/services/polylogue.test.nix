{ mkServiceTest, expect, hmFor, ... }:
mkServiceTest {
  name = "services-polylogue";
  service = "polylogue";
  assertions =
    config:
    let
      hm = hmFor config;
      unit = hm.systemd.user.services."polylogue-run".Unit or { };
      service = hm.systemd.user.services."polylogue-run".Service or { };
      browserCapture = hm.systemd.user.services."polylogue-browser-capture".Service or { };
      timer = hm.systemd.user.timers."polylogue-run".Timer or { };
      execStart =
        let
          raw = service.ExecStart or [ ];
        in
        if builtins.isList raw then builtins.concatStringsSep " " raw else raw;
      browserCaptureExecStart =
        let
          raw = browserCapture.ExecStart or [ ];
        in
        if builtins.isList raw then builtins.concatStringsSep " " raw else raw;
    in
    [
      (expect.hmUserServiceExists hm "polylogue-run" "Polylogue user service must exist")
      (expect.hmUserServiceExists hm "polylogue-browser-capture"
        "Polylogue browser capture receiver must exist"
      )
      (expect.hmUserTimerExists hm "polylogue-run" "Polylogue user timer must exist")
      (expect.textContains execStart "/bin/polylogue --plain run acquire parse materialize render index"
        "Polylogue catch-up service must run archive/product stages without unattended site publication"
      )
      {
        assertion = !(service ? ExecCondition);
        message = "Polylogue catch-up must not hide pipeline pressure behind an arbitrary start gate";
      }
      (expect.textContains browserCaptureExecStart
        "/bin/polylogued browser-capture serve --host 127.0.0.1 --port 8765"
        "Polylogue browser capture receiver must run local-only on the default extension port"
      )
      (expect.attrPathEq unit [
        "X-SwitchMethod"
      ] "keep-old" "Polylogue catch-up must not run inline during Home Manager switches")
      (expect.attrPathEq service [
        "TimeoutStartSec"
      ] "30min" "Polylogue catch-up must keep a bounded but realistic timeout")
      (expect.attrPathEq browserCapture [
        "Restart"
      ] "on-failure" "Polylogue browser capture receiver must restart on failure")
      (expect.attrPathEq service [
        "MemoryHigh"
      ] "8G" "Polylogue ingestion must retain a headroom-oriented memory high watermark")
      (expect.attrPathEq browserCapture [
        "MemoryMax"
      ] "512M" "Polylogue browser capture receiver must keep a tight memory limit")
      (expect.attrPathEq service [
        "MemoryMax"
      ] "16G" "Polylogue ingestion must retain a runaway-only hard memory limit")
      (expect.attrPathEq service [
        "IOWeight"
      ] 1 "Polylogue ingestion must run at minimum cgroup I/O weight")
      {
        assertion = !(service ? IOReadBandwidthMax) && !(service ? IOWriteBandwidthMax);
        message = "Polylogue ingestion must not use hard per-device I/O bandwidth caps";
      }
      (expect.attrPathEq timer [
        "OnStartupSec"
      ] "30min" "Polylogue timer must not run archive catch-up during interactive boot")
      (expect.attrPathEq timer [
        "OnUnitInactiveSec"
      ] "1h" "Polylogue timer must be paced after durable catch-up completion, not realtime ingestion")
      (expect.attrPathEq timer [
        "Persistent"
      ] false "Polylogue timer must not catch up missed runs immediately after boot")
    ];
}
