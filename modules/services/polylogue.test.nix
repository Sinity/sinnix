{
  lib,
  mkServiceTest,
  expect,
  hmFor,
  ...
}:
let
  commonAssertions =
    config:
    let
      hm = hmFor config;
      daemonService = hm.systemd.user.services.polylogued.Service or { };
      browserCaptureExists = builtins.hasAttr "polylogue-browser-capture" hm.systemd.user.services;
      daemonExecStart =
        let
          raw = daemonService.ExecStart or [ ];
        in
        if builtins.isList raw then builtins.concatStringsSep " " raw else raw;
    in
    [
      (expect.hmUserServiceExists hm "polylogued" "Polylogue daemon user service must exist")
      {
        assertion = !(builtins.hasAttr "polylogue-run" hm.systemd.user.services);
        message = "Polylogue must not install a separate batch catch-up writer service";
      }
      {
        assertion = !(builtins.hasAttr "polylogue-run" hm.systemd.user.timers);
        message = "Polylogue must not install a batch catch-up timer";
      }
      (expect.textContains daemonExecStart "/bin/polylogued run --host 127.0.0.1 --port 8765"
        "Polylogue daemon must run the watcher/browser-capture command with the local receiver port"
      )
      {
        assertion = !(lib.hasInfix "--no-browser-capture" daemonExecStart);
        message = "Polylogue daemon must own browser capture by default";
      }
      {
        assertion = !browserCaptureExists;
        message = "Standalone browser-capture service must be opt-in when polylogued owns the receiver";
      }
      (expect.attrPathEq daemonService [
        "Restart"
      ] "on-failure" "Polylogue daemon must restart on failure")
      {
        assertion = !(daemonService ? MemoryHigh) && !(daemonService ? MemoryMax);
        message = "Polylogue daemon must not carry local cgroup memory guardrails";
      }
      {
        assertion = !(daemonService ? IOReadIOPSMax) && !(daemonService ? IOReadBandwidthMax);
        message = "Polylogue daemon must not carry local I/O caps";
      }
      {
        assertion = !(daemonService ? CPUWeight);
        message = "Polylogue daemon must not carry a local CPU cgroup weight";
      }
      {
        assertion =
          daemonService.Nice == 10
          && daemonService.IOSchedulingClass == "idle"
          && daemonService.IOWeight == 10;
        message = "Polylogue daemon must run as a systemd-managed background I/O workload";
      }
    ];
in
[
  (mkServiceTest {
    name = "services-polylogue";
    service = "polylogue";
    assertions =
      config:
      let
        hm = hmFor config;
      in
      commonAssertions config
      ++ [
        {
          assertion = hm.systemd.user.services.polylogued.Install.WantedBy == [ "default.target" ];
          message = "Polylogue daemon must start automatically by default";
        }
      ];
  })
  (mkServiceTest {
    name = "services-polylogue-manual-start";
    service = "polylogue";
    extraModules = [
      {
        sinnix.services.polylogue.daemon.autoStart = false;
      }
    ];
    assertions =
      config:
      let
        hm = hmFor config;
      in
      commonAssertions config
      ++ [
        {
          assertion = hm.systemd.user.services.polylogued.Install.WantedBy == [ ];
          message = "Polylogue daemon autoStart=false must remove default user-session installation";
        }
      ];
  })
]
