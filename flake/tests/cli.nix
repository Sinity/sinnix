# CLI feature runtime checks: Polylogue CLI wrapper and task-tracking
# (taskwarrior/timewarrior) integration.
#
# cli-polylogue-runtime sits in the default `checks` tier: it evaluates the
# cli.polylogue feature module through the full sinnix config tree and only
# smoke-tests `--help` output with a minimal coreutils/gnugrep closure.
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

      cliCoreRuntimeSpec = mkFeatureTest {
        name = "cli-core-runtime";
        feature = "sinnix.features.cli.core.enable";
        assertions = _config: [ ];
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
      # Provably fails when: the rendered ssh config stops isolating the
      # GitHub key from the agent (verified by removing IdentityAgent = none
      # from modules/features/cli/core.nix), or the wildcard host stops
      # setting AddKeysToAgent=false.
      cliCoreRuntime = mkHmRuntimeCheck system {
        name = "cli-core-runtime-check";
        spec = cliCoreRuntimeSpec;
        nativeBuildInputs = [ pkgs.openssh.out ];
        homeFiles = [ ".ssh/config" ];
        script = ''
          ssh_config="$HOME/.ssh/config"
          ssh -G -F "$ssh_config" github.com > "$TMPDIR/github-ssh-config"
          grep -qx 'batchmode yes' "$TMPDIR/github-ssh-config"
          grep -qx 'identityagent none' "$TMPDIR/github-ssh-config"
          grep -qx "identityfile $HOME/.ssh/id_ed25519" "$TMPDIR/github-ssh-config"
          grep -qx 'identitiesonly yes' "$TMPDIR/github-ssh-config"

          # The wildcard prevents unrelated hosts from importing keys into
          # gpg-agent as well.
          ssh -G -F "$ssh_config" example.org > "$TMPDIR/default-ssh-config"
          grep -qx 'addkeystoagent false' "$TMPDIR/default-ssh-config"
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
        cli-core-runtime = cliCoreRuntime;
      };

      checks = {
        cli-polylogue-runtime = cliPolylogueRuntime;
      };

      checks = {
        cli-task-tracking-runtime = cliTaskTrackingRuntime;
      };
    };
}
