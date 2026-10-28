# Contracts over the machine's own configuration. Checks that inspect
# sinnix-prime read `inputs.self.nixosConfigurations.sinnix-prime`, so the
# tier evaluates the real configuration once rather than rebuilding it.
#
# Test fixtures force module assertions on synthetic configurations; this
# check forces every one on the configuration that is actually deployed,
# which otherwise first meets them in the heavy host build or at switch.
{ inputs, ... }:
{
  perSystem =
    { pkgs, ... }:
    let
      host = inputs.self.nixosConfigurations.sinnix-prime.config;
      failures = builtins.filter (entry: !entry.assertion) host.assertions;
      journalSource = host.systemd.services.ensure-journal-source;
    in
    {
      # Check the rendered host policy as well as the registry contract in
      # agent-resource-policy: a renderer or profile override must not silently
      # drop monitoring or enroll the desktop/coordinator as kill candidates.
      checks.workstation-oom-policy =
        let
          inherit (inputs.nixpkgs) lib;
          slices = host.systemd.user.units;
          plane = slices."agent-ctl.slice".text;
          tools = slices."agent-tool.slice".text;
          earlyoomArgs = host.systemd.services.earlyoom.environment.EARLYOOM_ARGS;
          unmonitored =
            text:
            !(lib.hasInfix "ManagedOOMMemoryPressure=kill" text) && !(lib.hasInfix "ManagedOOMSwap=kill" text);
        in
        assert lib.all (line: lib.hasInfix line plane) [
          "ManagedOOMMemoryPressure=kill"
          "ManagedOOMMemoryPressureLimit=40%"
          "ManagedOOMMemoryPressureDurationSec=15s"
          "ManagedOOMSwap=kill"
        ];
        assert lib.hasInfix "ManagedOOMSwap=kill" tools;
        assert lib.all (name: unmonitored slices."${name}.slice".text) [
          "agent"
          "agent-cli"
          "app"
          "session"
          "desktop"
          "desktop-shell"
        ];
        assert !host.systemd.oomd.enableRootSlice;
        assert !host.systemd.oomd.enableSystemSlice;
        assert !host.systemd.oomd.enableUserSlices;
        # earlyoom exits at startup on -m above 99; an out-of-range value
        # crash-looped the service on 2026-10-27 while this check passed.
        assert host.services.earlyoom.freeMemThreshold <= 99;
        assert lib.all (arg: lib.hasInfix arg earlyoomArgs) [
          "-m5"
          "-s10"
          "--mem-psi-min 10"
        ];
        pkgs.runCommand "workstation-oom-policy-check" { } "touch $out";

      checks.cargo-cache =
        let
          unit = host.systemd.services.sinnix-cargo-cache;
          alternate =
            (inputs.self.nixosConfigurations.sinnix-prime.extendModules {
              modules = [ ({ lib, ... }: { sinnix.paths.realmRoot = lib.mkForce "/fixture-realm"; }) ];
            }).config;
          selectorFor =
            config:
            builtins.head (
              builtins.filter (
                package: package.name == "sinnix-cargo-target"
              ) config.home-manager.users.${config.sinnix.user.name}.home.packages
            );
        in
        assert unit.environment.CARGO_CACHE_ROOT == "/realm/state/cache/cargo";
        assert
          alternate.systemd.services.sinnix-cargo-cache.environment.CARGO_CACHE_ROOT
          == "/fixture-realm/state/cache/cargo";
        assert unit.serviceConfig.Type == "oneshot";
        assert builtins.elem "/realm" unit.unitConfig.RequiresMountsFor;
        pkgs.runCommand "cargo-cache-check"
          {
            nativeBuildInputs = [
              pkgs.python3
              pkgs.bash
              pkgs.coreutils
              pkgs.git
              pkgs.util-linux
              (selectorFor host)
            ];
            provision = pkgs.writeText "cargo-cache-provision" unit.script;
          }
          ''
            python ${./cargo_cache.py} "$provision" ${../../scripts/sinnix-cargo-target} ${../../scripts/sinnix-direnvrc}
            explicit="$TMPDIR/explicit-target"
            test "$(CARGO_TARGET_DIR="$explicit" sinnix-cargo-target)" = "$explicit"
            test ! -e "$explicit"
            if env -u CARGO_TARGET_DIR ${selectorFor alternate}/bin/sinnix-cargo-target >target.out 2>target.err; then
              echo "unprovisioned alternate root was accepted" >&2
              exit 1
            fi
            test "$(cat target.err)" = "Cargo cache subvolume is not provisioned: /fixture-realm/state/cache/cargo"
            touch "$out"
          '';

      checks.transmission-sparsify =
        let
          unit = host.systemd.services.transmission-sparsify;
        in
        assert unit.serviceConfig.RuntimeDirectory == "transmission-sparsify";
        assert unit.serviceConfig.RuntimeDirectoryMode == "0700";
        pkgs.runCommand "transmission-sparsify-state-check"
          {
            nativeBuildInputs = [
              pkgs.python3
              pkgs.bash
              pkgs.coreutils
            ];
            startScript = pkgs.writeText "transmission-sparsify-start" unit.script;
            stopScript = pkgs.writeText "transmission-sparsify-stop" unit.postStop;
          }
          ''
            python ${./transmission_sparsify.py} "$startScript" "$stopScript"
            touch "$out"
          '';

      checks.journal-source =
        assert builtins.elem "realm.mount" journalSource.requires;
        assert builtins.elem "realm.mount" journalSource.after;
        assert builtins.elem "var-log-journal.mount" journalSource.requiredBy;
        assert builtins.elem "var-log-journal.mount" journalSource.before;
        assert journalSource.unitConfig.DefaultDependencies == false;
        assert host.fileSystems."/var/log/journal".device == "/realm/state/journal";
        assert host.services.journald.settings.Journal.SystemMaxFiles == 10000;
        assert host.services.journald.settings.Journal.SystemMaxUse == "100G";
        assert host.services.journald.settings.Journal.MaxRetentionSec == "365day";
        pkgs.runCommand "journal-source-check"
          {
            nativeBuildInputs = [
              pkgs.python3
              pkgs.bash
            ];
            sourceScript = pkgs.writeText "journal-source-script" journalSource.script;
          }
          ''
            python ${./journal_source.py} "$sourceScript"
            touch "$out"
          '';

      checks.ai-control-cli =
        pkgs.runCommand "ai-control-cli"
          {
            nativeBuildInputs = [
              pkgs.python3
              pkgs.bash
              pkgs.jq
              pkgs.gnugrep
              pkgs.gawk
              pkgs.gnused
              pkgs.coreutils
            ];
          }
          ''
            python ${./ai_control_cli.py} ${../../scripts/sinnix-ai}
            touch "$out"
          '';

      checks.xiaomi-cloud-owner-lock =
        let
          unit = host.systemd.user.services.sinnix-capture-xiaomi-cloud;
          recovery =
            (builtins.fromTOML (builtins.readFile ../../.agentctl/project.toml))
            .operations.xiaomi_cloud_backfill;
          lock = "${unit.environment.XIAOMI_CLOUD_STATE}/sync.lock";
        in
        assert inputs.nixpkgs.lib.hasInfix "flock --exclusive ${lock} " unit.serviceConfig.ExecStart;
        assert builtins.elemAt recovery.exec 2 == lock;
        assert builtins.elemAt recovery.exec 0 == "flock";
        assert builtins.elemAt recovery.exec 1 == "--exclusive";
        assert builtins.elem "XIAOMI_CLOUD_WINDOW_DAYS=35" recovery.exec;
        pkgs.runCommand "xiaomi-cloud-owner-lock" { } "touch $out";

      checks.hub-http-boundary =
        let
          service = host.home-manager.users.${host.sinnix.user.name}.systemd.user.services.sinnix-hub;
          command = builtins.head service.Service.ExecStart;
          resolverCommand = service.Service.ExecStartPre;
          resolver = builtins.appendContext (builtins.head (inputs.nixpkgs.lib.splitString " " resolverCommand)) (
            builtins.getContext resolverCommand
          );
          caddyfile = builtins.appendContext (builtins.elemAt (builtins.match ".*--config ([^ ]+) .*" command) 0) (
            builtins.getContext command
          );
        in
        pkgs.runCommand "hub-http-boundary"
          {
            nativeBuildInputs = [
              pkgs.python3
              pkgs.caddy
            ];
            inherit caddyfile resolver;
            reportPort = toString host.sinnix.services.hub.reportsPort;
          }
          ''
            python ${./hub_http_boundary.py} "$caddyfile" "$resolver" "$reportPort"
            touch "$out"
          '';

      checks.sinnix-prime-assertions =
        if failures == [ ] then
          pkgs.runCommand "sinnix-prime-assertions" { } ''
            touch "$out"
          ''
        else
          throw "sinnix-prime fails ${toString (builtins.length failures)} assertion(s):\n${
            inputs.nixpkgs.lib.concatMapStringsSep "\n" (entry: "  - ${entry.message}") failures
          }";
    };
}
