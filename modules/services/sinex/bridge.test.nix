{ lib, inputs, ... }:
{
  name = "services-sinex-delayed-runtime";
  modules = [
    { imports = [ (inputs.self + "/hosts/sinnix-prime") ]; }
    {
      sinnix.services.sinex = {
        enable = lib.mkForce true;
        autoStart = lib.mkForce false;
        prepareHost = lib.mkForce true;
        provisionDatabase = lib.mkForce true;
      };
    }
  ];
  assertions =
    config:
    let
      candidateRuntimeServices = [
        "postgresql"
        "postgresql-setup"
        "sinex-schema-apply"
        "nats"
        "sinex-nats-bootstrap"
        "sinex-blob-init"
        "sinex-tls-init"
        "sinex-ingestd"
        "sinex-gateway"
        "sinex-kitty-setup"
      ]
      ++ (config.sinex._generatedUnits or [ ])
      ++ lib.optionals (lib.attrByPath [ "services" "sinex" "nodes" "document" "enable" ] false config) [
        "sinex-document-scan"
      ];
      runtimeServices = lib.unique (
        builtins.filter (name: builtins.hasAttr name config.systemd.services) candidateRuntimeServices
      );
      # restartableRuntimeServices = long-running notify-style services only.
      # Generated source-workers tagged service_policy=invoked_on_demand are
      # oneshots (Restart=no); excluding them by their runtime shape avoids
      # depending on catalog metadata that the test doesn't import.
      restartableRuntimeServices = lib.unique (
        builtins.filter
          (
            name:
            builtins.hasAttr name config.systemd.services
            && lib.attrByPath [ "systemd" "services" name "serviceConfig" "Restart" ] null config != "no"
          )
          (
            [
              "sinex-ingestd"
              "sinex-gateway"
            ]
            ++ (config.sinex._generatedUnits or [ ])
          )
      );
      packageNames = map (pkg: pkg.name or "") config.environment.systemPackages;
      serviceWantedBy = name: lib.attrByPath [ "systemd" "services" name "wantedBy" ] [ ] config;
      serviceRestartIfChanged =
        name: lib.attrByPath [ "systemd" "services" name "restartIfChanged" ] true config;
      serviceRestartMode =
        name: lib.attrByPath [ "systemd" "services" name "serviceConfig" "Restart" ] null config;
      serviceRestartSec =
        name: lib.attrByPath [ "systemd" "services" name "serviceConfig" "RestartSec" ] null config;
      serviceConfig = name: lib.attrByPath [ "systemd" "services" name "serviceConfig" ] { } config;
      serviceUnitConfig = name: lib.attrByPath [ "systemd" "services" name "unitConfig" ] { } config;
      targetWantedBy = name: lib.attrByPath [ "systemd" "targets" name "wantedBy" ] [ ] config;
      targetUnit = name: lib.attrByPath [ "systemd" "targets" name ] { } config;
      targetUnitConfig = name: lib.attrByPath [ "systemd" "targets" name "unitConfig" ] { } config;
      runtimeWants = lib.attrByPath [ "systemd" "targets" "sinex-runtime" "wants" ] [ ] config;
      runtimeTimerWantedBy = lib.attrByPath [ "systemd" "timers" "sinex-runtime" "wantedBy" ] [ ] config;
      runtimeTimer = lib.attrByPath [ "systemd" "timers" "sinex-runtime" "timerConfig" ] { } config;
      maintenanceTimerWantedBy = name: lib.attrByPath [ "systemd" "timers" name "wantedBy" ] [ ] config;
      maintenanceTimerUnitConfig =
        name: lib.attrByPath [ "systemd" "timers" name "unitConfig" ] { } config;
      maintenanceTimerConfig = name: lib.attrByPath [ "systemd" "timers" name "timerConfig" ] { } config;
      maintenanceServiceConfig =
        name: lib.attrByPath [ "systemd" "services" name "serviceConfig" ] { } config;
      sinexMaintenanceTimers = [
        "sinex-document-scan"
      ];
      absentLegacyBlobMaintenanceUnits = [
        "sinex-blob-init"
        "sinex-blob-fsck"
        "sinex-blob-gc"
      ];
      sinexHealth = config.sinnix.services.sinex.health;
      healthPolicy = builtins.fromJSON config.environment.etc."sinnix/health-policy.json".text;
      healthServiceNames = map (check: check.name) healthPolicy.services;
      sinexHealthChecks = builtins.filter (check: check.name == "sinex") healthPolicy.services;
      natsService = config.systemd.services.nats.serviceConfig;
      postgresService = config.systemd.services.postgresql.serviceConfig;
      cappedSubstrateUnits = [
        "nats"
        "postgresql"
      ];
      sinexRuntimeAppServices = builtins.filter (
        name: !(builtins.elem name cappedSubstrateUnits)
      ) runtimeServices;
      sinexRuntimeRoot = "/var/lib/sinex";
      persistedSystemDirs = config.sinnix.persistence.system.directories;
      postgresqlUnitConfig = serviceUnitConfig "postgresql";
      sinexFilesystem = config.services.sinex.nodes.filesystem;
      sinexAutomata = config.services.sinex.nodes.automata;
      preflightEnabled = lib.attrByPath [
        "services"
        "sinex"
        "lifecycle"
        "preflight"
        "enable"
      ] false config;
    in
    [
      {
        assertion = !(builtins.elem "multi-user.target" (targetWantedBy "postgresql"));
        message = "Sinex PostgreSQL target must not install into multi-user.target";
      }
      {
        assertion = builtins.all (
          name: !(builtins.elem "multi-user.target" (serviceWantedBy name))
        ) runtimeServices;
        message = "Sinex runtime services that exist on the host must not install into multi-user.target";
      }
      {
        assertion = builtins.all (name: serviceRestartIfChanged name == false) runtimeServices;
        message = "Sinex runtime services must not restart during desktop activation";
      }
      {
        assertion = builtins.all (
          name:
          let
            service = serviceConfig name;
          in
          (!(service ? MemoryMax) || service.MemoryMax == null)
          && (!(service ? CPUQuota) || service.CPUQuota == null)
        ) sinexRuntimeAppServices;
        message = "Sinex runtime app daemons must not keep upstream MemoryMax/CPUQuota caps";
      }
      {
        assertion = builtins.all (
          name:
          let
            service = serviceConfig name;
          in
          (!(service ? MemoryMax) || service.MemoryMax == null)
          && (!(service ? CPUQuota) || service.CPUQuota == null)
        ) restartableRuntimeServices;
        message = "Long-running Sinex runtime daemons must not keep hard caps from old upstream defaults";
      }
      {
        assertion = builtins.all (
          name:
          let
            sec = serviceRestartSec name;
            # Upstream's services.sinex.runtime.restartPolicy.backoffSec is
            # typed as positive int and emits a number; legacy mkForce
            # overrides emitted "30s". Accept either form.
            secOK = sec == 30 || sec == "30s";
          in
          serviceRestartMode name == "on-failure"
          && secOK
          && (serviceUnitConfig name).StartLimitIntervalSec == 600
          && (serviceUnitConfig name).StartLimitBurst == 3
        ) restartableRuntimeServices;
        message = "Long-running Sinex runtime services must use bounded on-failure restart";
      }
      {
        assertion = builtins.elem "postgresql.target" runtimeWants;
        message = "sinex-runtime.target must pull in postgresql.target";
      }
      {
        assertion = !preflightEnabled && !(builtins.elem "sinex-preflight.service" runtimeWants);
        message = "Sinex production preflight must stay manual instead of running during desktop activation";
      }
      {
        assertion = builtins.all (name: builtins.elem "${name}.service" runtimeWants) runtimeServices;
        message = "sinex-runtime.target must pull in the stripped Sinex runtime services that exist on the host";
      }
      {
        assertion = builtins.any (name: lib.hasPrefix "sinexctl-" name) packageNames;
        message = "Sinex should expose sinexctl, not the aggregate runtime package, on interactive PATH";
      }
      {
        assertion =
          !(builtins.any (
            name: builtins.match "sinex-[0-9].*" name != null || lib.hasPrefix "xtask" name
          ) packageNames);
        message = "Sinex aggregate/runtime packages must not leak a bare global xtask into interactive PATH";
      }
      {
        assertion = runtimeTimer.OnActiveSec == "5min";
        message = "sinex-runtime.timer must delay relative to timer activation, not only boot time";
      }
      {
        assertion =
          if config.sinnix.services.sinex.autoStart then
            runtimeTimerWantedBy == [ "timers.target" ]
          else
            runtimeTimerWantedBy == [ ];
        message = "Sinex delayed runtime timer must respect the host auto-start policy";
      }
      {
        assertion =
          (targetUnitConfig "sinex-runtime").X-OnlyManualStart == true
          && (targetUnit "sinex-runtime").description == "Delayed automatic Sinex runtime";
        message = "sinex-runtime.target must keep the activation guard while describing timer-based auto-start";
      }
      {
        assertion = builtins.all (
          name:
          if config.sinnix.services.sinex.autoStart then
            maintenanceTimerWantedBy name == [ "sinex-runtime.target" ]
          else
            maintenanceTimerWantedBy name == [ ]
        ) sinexMaintenanceTimers;
        message = "Sinex maintenance timers must respect the host delayed-runtime auto-start policy";
      }
      {
        assertion = builtins.all (
          name: (maintenanceTimerUnitConfig name).PartOf == [ "sinex-runtime.target" ]
        ) sinexMaintenanceTimers;
        message = "Sinex maintenance timers must stop with the runtime target";
      }
      {
        assertion = builtins.all (
          name: (maintenanceTimerConfig name).Persistent == false
        ) sinexMaintenanceTimers;
        message = "Sinex maintenance timers must not catch up missed work immediately";
      }
      {
        assertion = builtins.all (
          name:
          let
            service = maintenanceServiceConfig name;
          in
          serviceRestartIfChanged name == false
          && (
            service.TimeoutStopSec == "15s" || service.TimeoutStopSec == 90 || service.TimeoutStopSec == "90s"
          )
          && (!(service ? Slice) || service.Slice == null)
          && (!(service ? Nice) || service.Nice == null)
          && (!(service ? CPUWeight) || service.CPUWeight == null)
          && (!(service ? IOWeight) || service.IOWeight == null)
          && (!(service ? IOSchedulingClass) || service.IOSchedulingClass == null)
          && (!(service ? ExecCondition) || service.ExecCondition == null)
        ) sinexMaintenanceTimers;
        message = "Sinex maintenance services must use plain systemd policy";
      }
      {
        assertion = builtins.all (
          name:
          !(builtins.hasAttr name config.systemd.timers) && !(builtins.hasAttr name config.systemd.services)
        ) absentLegacyBlobMaintenanceUnits;
        message = "Sinnix must not synthesize empty legacy blob maintenance units when upstream does not define them";
      }
      {
        assertion =
          if config.sinnix.services.sinex.autoStart then
            sinexHealth != null
            && sinexHealth.restartable == false
            && builtins.elem "sinex" healthServiceNames
            && sinexHealthChecks != [ ]
            && (builtins.head sinexHealthChecks).restartable == false
          else
            sinexHealth == null && !(builtins.elem "sinex" healthServiceNames) && sinexHealthChecks == [ ];
        message = "Sinex health policy must respect whether the runtime auto-starts";
      }
      {
        assertion =
          config.services.nats.settings.jetstream.max_file == "32G"
          && !(natsService ? MemoryHigh)
          && !(natsService ? MemoryMax)
          && natsService.Nice == 5
          && natsService.IOWeight == 50
          && !(natsService ? IOReadBandwidthMax)
          && !(natsService ? IOWriteBandwidthMax);
        message = "NATS must keep storage sizing with only soft workstation scheduler bias";
      }
      {
        assertion = natsService.KillSignal == "SIGTERM" && natsService.TimeoutStopSec == "90s";
        message = "NATS must have bounded but production-sized graceful shutdown time";
      }
      {
        assertion =
          !(postgresService ? MemoryHigh)
          && !(postgresService ? MemoryMax)
          && postgresService.Nice == 5
          && postgresService.IOWeight == 50
          && !(postgresService ? IOReadBandwidthMax)
          && !(postgresService ? IOWriteBandwidthMax);
        message = "PostgreSQL must carry only soft workstation scheduler bias";
      }
      {
        assertion =
          config.services.postgresql.dataDir == "${sinexRuntimeRoot}/postgresql/18"
          && config.services.sinex.stateRoot == "${sinexRuntimeRoot}/state"
          && config.users.users.sinex.home == "${sinexRuntimeRoot}/home"
          && config.users.users.sinex.homeMode == "0711"
          && !(config.system.activationScripts ? sinexHomeTraverse)
          && builtins.elem sinexRuntimeRoot postgresqlUnitConfig.RequiresMountsFor;
        message = "Sinex production hot state and home must live under the runtime state root";
      }
      {
        assertion =
          !(builtins.elem "/var/lib/postgresql" persistedSystemDirs)
          && !(builtins.elem "/var/lib/sinex" persistedSystemDirs);
        message = "Sinex/PostgreSQL hot state must not be bind-mounted from /persist";
      }
      {
        assertion = builtins.all (name: builtins.elem name sinexFilesystem.ignoredDirectoryNames) [
          ".btrfs"
          ".claude"
          ".cache"
          ".direnv"
          ".git"
          ".hg"
          ".jj"
          ".sinex"
          ".svn"
          ".Trash-1000"
          "__pycache__"
          "asciinema"
          "kitty-scrollback"
          "node_modules"
          "target"
        ];
        message = "Sinex bridge must preserve upstream and workstation filesystem ignore defaults";
      }
      {
        assertion =
          sinexAutomata.canonicalizer.profile == "heavy" && sinexAutomata.healthAggregator.profile == "heavy";
        message = "Sinex bridge must own workstation automata profile defaults";
      }
    ];
}
