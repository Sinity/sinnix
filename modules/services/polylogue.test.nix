{
  lib,
  mkServiceTest,
  expect,
  hmFor,
  ...
}:
mkServiceTest {
  name = "services-polylogue";
  service = "polylogue";
  assertions =
    config:
    let
      hm = hmFor config;
      unit = hm.systemd.user.services."polylogue-run".Unit or { };
      service = hm.systemd.user.services."polylogue-run".Service or { };
      daemonUnit = hm.systemd.user.services.polylogued.Unit or { };
      daemonService = hm.systemd.user.services.polylogued.Service or { };
      browserCaptureExists = builtins.hasAttr "polylogue-browser-capture" hm.systemd.user.services;
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
      daemonExecStart =
        let
          raw = daemonService.ExecStart or [ ];
        in
        if builtins.isList raw then builtins.concatStringsSep " " raw else raw;
    in
    [
      (expect.hmUserServiceExists hm "polylogue-run" "Polylogue user service must exist")
      (expect.hmUserServiceExists hm "polylogued" "Polylogue daemon user service must exist")
      (expect.hmUserTimerExists hm "polylogue-run" "Polylogue user timer must exist")
      (expect.textContains execStart "/bin/polylogue --plain run acquire parse materialize render index"
        "Polylogue catch-up service must run archive/product stages without unattended site publication"
      )
      {
        assertion =
          builtins.match ".*sinnix-maintenance-gate.*polylogue-run\\.service.*" service.ExecCondition != null;
        message = "Polylogue catch-up must use only the explicit maintenance-overlap gate";
      }
      (expect.textContains daemonExecStart "/bin/polylogued run --host 127.0.0.1 --port 8765"
        "Polylogue daemon must run the watcher/browser-capture command with the local receiver port"
      )
      {
        assertion = !(builtins.elem "polylogue-run.service" (daemonUnit.Wants or [ ]));
        message = "Polylogue daemon must not start durable catch-up immediately";
      }
      {
        assertion = !(lib.hasInfix "--no-browser-capture" daemonExecStart);
        message = "Polylogue daemon must own browser capture by default";
      }
      {
        assertion = !browserCaptureExists;
        message = "Standalone browser-capture service must be opt-in when polylogued owns the receiver";
      }
      (expect.attrPathEq unit [
        "X-SwitchMethod"
      ] "keep-old" "Polylogue catch-up must not run inline during Home Manager switches")
      (expect.attrPathEq service [
        "TimeoutStartSec"
      ] "30min" "Polylogue catch-up must keep a bounded but realistic timeout")
      (expect.attrPathEq daemonService [
        "Restart"
      ] "on-failure" "Polylogue daemon must restart on failure")
      (expect.attrPathEq service [
        "MemoryHigh"
      ] "8G" "Polylogue ingestion must retain a headroom-oriented memory high watermark")
      (expect.attrPathEq daemonService [
        "MemoryMax"
      ] "4G" "Polylogue daemon must keep a runaway-only memory limit")
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
