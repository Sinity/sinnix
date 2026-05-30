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
      # NOTE(2026-05-28): upstream module no longer uses xdg.configFile for
      # polylogue.toml — the daemon writes it at runtime via its own config path.
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
      {
        assertion = daemonService.ExecStart != null;
        message = "Polylogue daemon must have an ExecStart"
          + "(either via source symlink or inline text)";
      }
      (expect.textContains daemonExecStart "/bin/polylogued run"
        "Polylogue daemon unit must invoke polylogued run"
      )
      # No standalone browser-capture unit — the daemon owns it in-process.
      {
        assertion = !(builtins.hasAttr "polylogue-browser-capture" hm.systemd.user.services);
        message = "Standalone browser-capture service must not exist when polylogued owns the receiver";
      }
      (expect.attrPathEq daemonService [
        "Restart"
      ] "on-failure" "Polylogue daemon must restart on failure")
      # NOTE(2026-05-28): Memory/I/O guardrails and hardening now owned by
      # upstream polylogue HM module; removed service.* override surface.
      # NOTE(2026-05-28): CPU/IO/Memory guardrails owned by upstream module.
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
          assertion =
            config.sinnix.runtime.surfaces.polylogued.unit == "polylogued.service"
            && config.sinnix.runtime.surfaces.polylogued.observe.enable;
          message = "Polylogue daemon must be present in observability inventory when autostarted";
        }
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
          assertion = !(config.sinnix.runtime.surfaces ? polylogued);
          message = "Polylogue daemon autoStart=false must remove live-service observability metadata";
        }
        {
          assertion = hm.systemd.user.services.polylogued.Install.WantedBy == [ ];
          message = "Polylogue daemon autoStart=false must remove default user-session installation";
        }
      ];
  })
]
