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

      checks.xiaomi-witness-owner-lock =
        let
          unit = host.systemd.user.services.sinnix-xiaomi-witness;
          recovery =
            (builtins.fromTOML (builtins.readFile ../../.agentctl/project.toml))
            .operations.xiaomi_witness_backfill;
          lock = "${unit.environment.XIAOMI_WITNESS_STATE}/sync.lock";
        in
        assert inputs.nixpkgs.lib.hasInfix "flock --exclusive ${lock} " unit.serviceConfig.ExecStart;
        assert builtins.elemAt recovery.exec 2 == lock;
        assert builtins.elemAt recovery.exec 0 == "flock";
        assert builtins.elemAt recovery.exec 1 == "--exclusive";
        assert builtins.elem "XIAOMI_WITNESS_WINDOW_DAYS=35" recovery.exec;
        pkgs.runCommand "xiaomi-witness-owner-lock" { } "touch $out";

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
