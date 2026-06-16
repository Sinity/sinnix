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
        "sinexd"
        "sinex-ingestd"
        "sinex-gateway"
        "sinex-kitty-setup"
      ]
      ++ (config.sinex._generatedUnits or [ ])
      ++
        lib.optionals (lib.attrByPath [ "services" "sinex" "sources" "document" "enable" ] false config)
          [
            "sinex-document-scan"
          ];
      runtimeServices = lib.unique (
        builtins.filter (name: builtins.hasAttr name config.systemd.services) candidateRuntimeServices
      );
      # restartableRuntimeServices = long-running notify-style services only.
      # Generated source services tagged service_policy=invoked_on_demand are
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
              "sinexd"
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
      serviceStopIfChanged =
        name: lib.attrByPath [ "systemd" "services" name "stopIfChanged" ] true config;
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
      sinexSurface = config.sinnix.runtime.surfaces.sinex-runtime;
      runtimeInventory = builtins.fromJSON config.environment.etc."sinnix/runtime-inventory.json".text;
      observedServiceNames = map (check: check.name) runtimeInventory.observedServices;
      expectedObservedSinexNames = [
        "sinex-runtime"
        "sinexd"
        "nats"
        "postgresql"
      ];
      sinexObservedServices = builtins.filter (
        check: builtins.elem check.name expectedObservedSinexNames
      ) runtimeInventory.observedServices;
      observedByName =
        name: builtins.head (builtins.filter (check: check.name == name) runtimeInventory.observedServices);
      natsService = config.systemd.services.nats.serviceConfig;
      natsStreams = config.services.sinex.nats.bootstrapStreams.streams;
      natsStreamByName = name: builtins.head (builtins.filter (stream: stream.name == name) natsStreams);
      postgresService = config.systemd.services.postgresql.serviceConfig;
      sinexdService = config.systemd.services.sinexd.serviceConfig;
      sinexPostgresDumpUnit = config.systemd.services.sinex-postgres-dump;
      sinexPostgresDumpService = sinexPostgresDumpUnit.serviceConfig;
      sinexPostgresDumpTimer = config.systemd.timers.sinex-postgres-dump.timerConfig;
      substrateUnits = [
        "nats"
        "postgresql"
      ];
      sinexRuntimeAppServices = builtins.filter (
        name: !(builtins.elem name substrateUnits)
      ) runtimeServices;
      # Post-sinexd-collapse: automata run inside the unified sinexd daemon,
      # not as standalone services. The sinexd unit carries the memory guardrails.
      boundedAutomataServices = [ "sinexd" ];
      sinexRuntimeRoot = "/var/lib/sinex";
      sinexPostgresDumpRoot = "/persist/backup/sinex-postgres";
      persistedSystemDirs = config.sinnix.persistence.system.directories;
      postgresqlUnitConfig = serviceUnitConfig "postgresql";
      sinexFilesystem = config.services.sinex.sources.filesystem;
      preflightEnabled = lib.attrByPath [
        "services"
        "sinex"
        "lifecycle"
        "preflight"
        "enable"
      ] false config;
      serviceWants = name: lib.attrByPath [ "systemd" "services" name "wants" ] [ ] config;
      serviceAfter = name: lib.attrByPath [ "systemd" "services" name "after" ] [ ] config;
      serviceBefore = name: lib.attrByPath [ "systemd" "services" name "before" ] [ ] config;
      targetAccessServices = [
        "sinex-browser-target-access"
        "sinex-desktop-target-access"
        "sinex-document-target-access"
        "sinex-terminal-target-access"
      ];
      generatedSourceServices = builtins.filter (name: lib.hasPrefix "sinex-source-" name) (
        config.sinex._generatedUnits or [ ]
      );
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
        assertion = builtins.all (name: serviceStopIfChanged name == false) restartableRuntimeServices;
        message = "Long-running Sinex runtime services must not stop during desktop activation";
      }
      {
        assertion =
          builtins.elem "SINEX_DB_MAX_CONNECTIONS=32" sinexdService.Environment
          && builtins.elem "SINEX_DB_MIN_CONNECTIONS=4" sinexdService.Environment;
        message = "sinexd DB pool must be bounded below the upstream 100-connection default";
      }
      {
        assertion = builtins.all (
          name:
          let
            service = serviceConfig name;
          in
          service ? MemoryHigh
          && service.MemoryHigh != null
          && (!(service ? CPUQuota) || service.CPUQuota == null)
        ) boundedAutomataServices;
        message = "Sinex heavy automata (sinexd) must keep upstream memory guardrails";
      }
      {
        assertion = builtins.all (
          name:
          let
            service = serviceConfig name;
          in
          (!(service ? CPUQuota) || service.CPUQuota == null)
        ) restartableRuntimeServices;
        message = "Long-running Sinex runtime daemons must not keep CPU hard caps";
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
        assertion = builtins.elem "SINEX_EVENT_ENGINE_REJECT_INITIAL_REPLAY=false" sinexdService.Environment;
        message = "Sinnix Sinex runtime must explicitly allow raw-stream recovery replay when the event_engine durable is missing";
      }
      {
        assertion = builtins.elem "SINEX_EVENT_ENGINE_STARTUP_CATCH_UP_MAX_CONCURRENT=1" sinexdService.Environment;
        message = "Sinnix Sinex runtime must serialize startup catch-up to reduce interactive I/O pressure";
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
          && (targetUnitConfig "sinex-runtime").X-RestartIfChanged == false
          && (targetUnitConfig "sinex-runtime").X-StopIfChanged == false
          && (targetUnit "sinex-runtime").description == "Delayed automatic Sinex runtime";
        message = "sinex-runtime.target must keep the activation guard while describing timer-based auto-start";
      }
      {
        assertion = builtins.all (
          name: maintenanceTimerWantedBy name == [ "sinex-runtime.target" ]
        ) sinexMaintenanceTimers;
        message = "Sinex maintenance timers must attach to the runtime target even when delayed auto-start is disabled";
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
          !(builtins.hasAttr name config.systemd.timers) && !(builtins.hasAttr name config.systemd.services)
        ) absentLegacyBlobMaintenanceUnits;
        message = "Sinnix must not synthesize empty legacy blob maintenance units when upstream does not define them";
      }
      {
        assertion =
          config.services.sinex.storage.blob.autoInit == false
          && !(builtins.elem "sinex-blob-init.service" (serviceWants "sinex-ingestd"))
          && !(builtins.elem "sinex-blob-init.service" (serviceAfter "sinex-ingestd"))
          && !(builtins.elem "sinex-blob-init.service" (serviceWants "sinex-gateway"))
          && !(builtins.elem "sinex-blob-init.service" (serviceAfter "sinex-gateway"));
        message = "Sinex CAS runtime must not reference absent legacy blob-init units";
      }
      {
        assertion = builtins.all (
          name: !(builtins.elem "sinex-preflight.service" (serviceBefore name))
        ) targetAccessServices;
        message = "Sinex target-access helpers must not order against disabled preflight";
      }
      {
        assertion =
          if config.sinnix.services.sinex.autoStart then
            sinexSurface.observe.enable
            && sinexSurface.observe.restartable == false
            && builtins.all (name: builtins.elem name observedServiceNames) expectedObservedSinexNames
            && sinexObservedServices != [ ]
            && builtins.all (
              check: check.restartable == false && check.manager == "system"
            ) sinexObservedServices
            && (observedByName "sinex-runtime").kind == "target"
            && (observedByName "sinex-runtime").resourceClass == "capture-runtime"
            && (observedByName "sinexd").kind == "service"
            && (observedByName "sinexd").resourceClass == "capture-runtime"
            && (observedByName "nats").kind == "service"
            && (observedByName "nats").resourceClass == "capture-substrate"
            && (observedByName "postgresql").kind == "service"
            && (observedByName "postgresql").resourceClass == "capture-substrate"
          else
            !sinexSurface.observe.enable
            && builtins.all (name: !(builtins.elem name observedServiceNames)) expectedObservedSinexNames
            && sinexObservedServices == [ ];
        message = "Sinex observability inventory must respect whether the runtime auto-starts";
      }
      {
        assertion = (natsStreamByName "SINEX_RAW_EVENTS").maxBytes == null;
        message = "Sinex raw event stream bootstrap must not shrink the live production cap";
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
        assertion =
          sinexPostgresDumpService.User == "postgres"
          && sinexPostgresDumpService.Group == "postgres"
          && builtins.elem "postgresql.target" sinexPostgresDumpUnit.requires
          && builtins.elem "persist.mount" sinexPostgresDumpUnit.requires
          && builtins.elem sinexRuntimeRoot sinexPostgresDumpUnit.unitConfig.RequiresMountsFor
          && builtins.elem sinexPostgresDumpRoot sinexPostgresDumpUnit.unitConfig.RequiresMountsFor;
        message = "Sinex pg_dump backup must run as postgres with backup-maintenance scheduling and required mounts";
      }
      {
        assertion =
          builtins.elem "d ${sinexPostgresDumpRoot} 0700 postgres postgres -" config.systemd.tmpfiles.rules
          && builtins.any (pkg: lib.hasPrefix "gawk-" (pkg.name or "")) sinexPostgresDumpUnit.path;
        message = "Sinex pg_dump backup must dump sinex_prod with the agenix password and retain the newest dumps";
      }
      {
        assertion =
          config.systemd.timers.sinex-postgres-dump.wantedBy == [ "timers.target" ]
          && sinexPostgresDumpTimer.Persistent == false;
        message = "Sinex pg_dump backup timer must be scheduled without catch-up storms";
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
    ];
}
