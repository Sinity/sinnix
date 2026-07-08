# CLI feature runtime checks: Polylogue CLI wrapper and task-tracking
# (taskwarrior/timewarrior) integration.
#
# cli-polylogue-runtime is promoted into the default `checks` tier
# (sinnix-7bu): it evaluates the cli.polylogue feature module through the
# full sinnix config tree and only smoke-tests `--help` output with a
# minimal coreutils/gnugrep closure — cheap relative to the PTY/VM/host-build
# checks that stay in heavyChecks.
#
# Split out of the former flake/tests-runtime.nix monolith (sinnix-7bu).
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      testLib = import ../test-lib.nix { inherit inputs lib; };
      inherit (testLib)
        mkFeatureTest
        mkHmRuntimeCheck
        ;

      repoFixtureRoot = builtins.path {
        path = ../../.;
        name = "sinnix-runtime-fixture-root";
      };

      cliPolylogueRuntimeSpec = mkFeatureTest {
        name = "cli-polylogue-runtime";
        feature = "sinnix.features.cli.polylogue.enable";
        assertions = _config: [ ];
      };
      cliTaskTrackingRuntimeSpec = mkFeatureTest {
        name = "cli-task-tracking-runtime";
        feature = "sinnix.features.cli.task-tracking.enable";
        extraModules = [
          (
            { config, ... }:
            {
              home-manager.users.${config.sinnix.user.name}.programs.zsh.enable = true;
            }
          )
        ];
        assertions = _config: [ ];
      };

      cliPolylogueRuntime = mkHmRuntimeCheck system {
        name = "cli-polylogue-runtime-check";
        spec = cliPolylogueRuntimeSpec;
        nativeBuildInputs = [
          pkgs.coreutils
          pkgs.gnugrep
        ];
        script = ''
          polylogue --help | grep -q '^Usage: polylogue'
          polylogue find --help | grep -q 'Search the archive'
          polylogue config --help | grep -q 'Show resolved Polylogue configuration'
          polylogue-python - <<'EOF'
          import sys
          print(sys.executable)
          EOF
        '';
      };
      cliTaskTrackingRuntime = mkHmRuntimeCheck system {
        name = "cli-task-tracking-runtime-check";
        spec = cliTaskTrackingRuntimeSpec;
        nativeBuildInputs = [
          pkgs.coreutils
          pkgs.gnugrep
          pkgs.jq
          pkgs.taskwarrior3
          pkgs.timewarrior
          pkgs.zsh
        ];
        fixtureAssets = [
          {
            source = repoFixtureRoot + "/dots/taskwarrior/taskrc";
            target = ".config/task/taskrc";
            rewrites = [
              {
                from = "/realm/project/sinnix";
                to = toString repoFixtureRoot;
              }
            ];
          }
          {
            source = repoFixtureRoot + "/dots/timewarrior/timewarrior.cfg";
            target = ".config/timewarrior/timewarrior.cfg";
            rewrites = [
              {
                from = "/realm/project/sinnix";
                to = toString repoFixtureRoot;
              }
            ];
          }
          {
            source = repoFixtureRoot + "/dots/timewarrior/extensions";
            target = ".config/timewarrior/extensions";
            recursive = true;
          }
        ];
        rewriteFiles = [
          {
            target = ".zshrc";
            rewrites = [
              {
                from = "/realm/project/sinnix";
                to = toString repoFixtureRoot;
              }
            ];
          }
        ];
        useHmZshrc = true;
        setup = ''
          export PATH="${
            lib.makeBinPath [
              pkgs.coreutils
              pkgs.gnugrep
              pkgs.jq
              pkgs.taskwarrior3
              pkgs.timewarrior
              pkgs.zsh
            ]
          }:$PATH"
          mkdir -p \
            "$HOME/.config/task" \
            "$HOME/.config/timewarrior/extensions" \
            "$HOME/.task" \
            "$HOME/.local/share/timewarrior"
        '';
        script = ''
            task diagnostics > "$TMPDIR/task.diagnostics"
            grep -q "$HOME/.config/task/taskrc" "$TMPDIR/task.diagnostics"
            grep -q '${repoFixtureRoot}/dots/taskwarrior/hooks' "$TMPDIR/task.diagnostics"

            timew diagnostics > "$TMPDIR/timew.diagnostics"
            grep -q "$HOME/.config/timewarrior/timewarrior.cfg" "$TMPDIR/timew.diagnostics"
            grep -q "$HOME/.local/share/timewarrior" "$TMPDIR/timew.diagnostics"
            grep -q "$HOME/.config/timewarrior/extensions" "$TMPDIR/timew.diagnostics"

          AGENT_NAME=codex AGENT_SESSION_ID=test-session ${pkgs.zsh}/bin/zsh -ic '
            alias ta | grep -q "task add"
            alias twstart | grep -q "timew start"
            type agent_project >/dev/null
            [[ "$(agent_project)" == "agent.codex.test-session" ]]
            type atr >/dev/null
          '
        '';
      };
    in
    {
      checks = {
        cli-polylogue-runtime = cliPolylogueRuntime;
      };

      heavyChecks = {
        cli-task-tracking-runtime = cliTaskTrackingRuntime;
      };
    };
}
