# Runtime/VM/host check perSystem block.
#
# Extracted from the legacy `flake/tests.nix` monolith so that fast assertion
# specs (now co-located `*.test.nix` files) stay separate from the heavyweight
# runtime/PTY/VM/host-build checks that depend on a Linux host and real
# tooling. flake-parts merges this perSystem block with the spec block in
# `flake/tests.nix`.
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      testLib = import ./test-lib.nix { inherit inputs lib; };
      checkTiers = import ./check-tiers.nix { inherit lib; };
      inherit (testLib)
        baseTestConfig
        evalTestSpec
        mountTmpfsRoots
        mkFeatureTest
        mkHmRuntimeCheck
        mkRuntimeCheck
        mkVmCheck
        mkHostBuildCheck
        ;
      repoFixtureRoot = builtins.path {
        path = ../.;
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
      devGitRuntimeSpec = mkFeatureTest {
        name = "dev-git-runtime";
        feature = "sinnix.features.dev.git.enable";
        assertions = _config: [ ];
      };
      devLanguagesRuntimeSpec = mkFeatureTest {
        name = "dev-languages-runtime";
        feature = "sinnix.features.dev.languages.enable";
        assertions = _config: [ ];
      };
      devAgentToolsRuntimeSpec = mkFeatureTest {
        name = "dev-agent-tools-runtime";
        feature = "sinnix.features.dev.agentTools.enable";
        extraModules = [
          (
            { ... }:
            {
              sinnix.features.dev.shell.enable = true;
              sinnix.features.dev.mcp-servers.enable = true;
            }
          )
        ];
        assertions = _config: [ ];
      };
      agentToolsFixture = {
        spec = devAgentToolsRuntimeSpec;
        nativeBuildInputs = [
          pkgs.coreutils
          pkgs.expect
          pkgs.findutils
          pkgs.gnugrep
          pkgs.jq
          pkgs.zsh
        ];
        homeFiles = [
          ".codex/config.toml"
          ".gemini/settings.json"
          ".local/bin/forge"
          ".local/bin/mcp-firecrawl"
          ".local/bin/mcp-playwright"
          ".local/bin/mcp-polylogue"
          "forge/.forge.toml"
          "forge/.mcp.json"
          "forge/skills"
        ];
        xdgConfigFiles = [
          "claude/settings.json"
        ];
        useHmZshrc = true;
        zshrcPreamble = ''
          autoload -Uz compinit
          compinit
        '';
        setup = ''
          export PATH="$HOME/.local/bin:${
            lib.makeBinPath [
              pkgs.coreutils
              pkgs.findutils
              pkgs.gnugrep
              pkgs.jq
              pkgs.zsh
            ]
          }:$PATH"
          export SHELL="${pkgs.zsh}/bin/zsh"
          export TERM="xterm-kitty"
          export TERM_PROGRAM="kitty"
          export TERM_PROGRAM_VERSION="test"
          export ZDOTDIR="$HOME"

          mkdir -p \
            "$HOME/forge/agents" \
            "$HOME/forge/commands" \
            "$HOME/forge/logs/requests" \
            "$HOME/forge/snapshots"

          cat > "$HOME/forge/.credentials.json" <<'EOF'
          []
          EOF
        '';
      };
      backupRuntimeEval = evalTestSpec system {
        name = "backup-borg-hook-runtime";
        modules = [
          mountTmpfsRoots
          baseTestConfig
          (
            { ... }:
            {
              networking.hostName = "backup-runtime";
            }
          )
        ];
        assertions = _config: [ ];
      };
      rewriteBackupHook =
        hook: replacements:
        builtins.replaceStrings (map (replacement: replacement.from) replacements) (map (
          replacement: replacement.to
        ) replacements) hook;
      realmBorgPreHook =
        rewriteBackupHook backupRuntimeEval.config.services.borgbackup.jobs.realm.preHook
          [
            {
              from = "${pkgs.util-linux}/bin/mountpoint";
              to = "$TMPDIR/mock-bin/mountpoint";
            }
            {
              from = "${pkgs.util-linux}/bin/umount";
              to = "$TMPDIR/mock-bin/umount";
            }
            {
              from = "${pkgs.util-linux}/bin/mount";
              to = "$TMPDIR/mock-bin/mount";
            }
            {
              from = "/realm/.btrfs/snapshot";
              to = "$TMPDIR/realm-snapshots";
            }
            {
              from = "/run/borgbackup-snapshot-inputs/realm";
              to = "$TMPDIR/bind/realm";
            }
          ];
      persistBorgPreHook =
        rewriteBackupHook backupRuntimeEval.config.services.borgbackup.jobs.persist.preHook
          [
            {
              from = "${pkgs.util-linux}/bin/mountpoint";
              to = "$TMPDIR/mock-bin/mountpoint";
            }
            {
              from = "${pkgs.util-linux}/bin/umount";
              to = "$TMPDIR/mock-bin/umount";
            }
            {
              from = "${pkgs.util-linux}/bin/mount";
              to = "$TMPDIR/mock-bin/mount";
            }
            {
              from = "/persist/.btrfs/snapshot";
              to = "$TMPDIR/persist-snapshots";
            }
            {
              from = "/run/borgbackup-snapshot-inputs/persist";
              to = "$TMPDIR/bind/persist";
            }
          ];
      missingRealmBorgPreHook =
        rewriteBackupHook backupRuntimeEval.config.services.borgbackup.jobs.realm.preHook
          [
            {
              from = "${pkgs.util-linux}/bin/mountpoint";
              to = "$TMPDIR/mock-bin/mountpoint";
            }
            {
              from = "${pkgs.util-linux}/bin/umount";
              to = "$TMPDIR/mock-bin/umount";
            }
            {
              from = "${pkgs.util-linux}/bin/mount";
              to = "$TMPDIR/mock-bin/mount";
            }
            {
              from = "/realm/.btrfs/snapshot";
              to = "$TMPDIR/realm-empty";
            }
            {
              from = "/run/borgbackup-snapshot-inputs/realm";
              to = "$TMPDIR/bind/realm-empty";
            }
          ];

      hostBuildChecks = lib.optionalAttrs (system == "x86_64-linux") {
        host-sinnix-prime-build = mkHostBuildCheck system {
          name = "sinnix-prime";
          modules = [
            { imports = [ ../hosts/sinnix-prime ]; }
          ];
        };
        host-sinnix-ethereal-build = mkHostBuildCheck system {
          name = "sinnix-ethereal";
          modules = [
            inputs.disko.nixosModules.disko
            { imports = [ ../hosts/sinnix-ethereal ]; }
          ];
        };
      };
      vmChecks = lib.optionalAttrs pkgs.stdenv.hostPlatform.isLinux {
        below-vm = mkVmCheck system {
          name = "below-vm";
          nodes.machine = {
            sinnix.services.below.enable = true;
          };
          testScript = ''
            start_all()
            machine.wait_for_unit("multi-user.target")
            machine.wait_for_unit("below.service")
            machine.succeed("test \"$(systemctl show below.service -P SubState)\" = running")
            machine.wait_until_succeeds("test -d /var/log/below/store")
            machine.wait_until_succeeds("find /var/log/below/store -type f | grep -q .")
          '';
        };
        polylogue-vm = mkVmCheck system {
          name = "polylogue-vm";
          nodes.machine =
            { pkgs, ... }:
            {
              environment.systemPackages = [ pkgs.jq ];
              sinnix.services.polylogue.enable = true;
            };
          testScript = ''
            start_all()
            machine.wait_for_unit("multi-user.target")

            uid = machine.succeed("id -u sinity").strip()
            as_user = f"XDG_RUNTIME_DIR=/run/user/{uid} runuser -u sinity --"

            machine.succeed("loginctl enable-linger sinity")
            machine.wait_for_unit(f"user@{uid}.service")
            machine.wait_for_unit("polylogue-run.timer", "sinity")

            machine.succeed(f"{as_user} systemctl --user start polylogue-run.service")
            machine.wait_until_succeeds(f"{as_user} systemctl --user show polylogue-run.service -P Result | grep -qx success")

            machine.wait_until_succeeds(f"{as_user} test -s /home/sinity/.local/share/polylogue/polylogue.db")
            machine.wait_until_succeeds(
                f"""{as_user} sh -lc 'find "$HOME/.local/share/polylogue/runs" -type f | grep -q .'"""
            )
            machine.succeed(
                f"""{as_user} sh -lc 'latest_run=$(ls -1t "$HOME/.local/share/polylogue/runs"/run-*.json | head -n 1); jq -e ".run_id != null and .duration_ms >= 0 and .counts.acquire_errors >= 0" "$latest_run" >/dev/null'"""
            )
          '';
        };
        sentinel-vm = mkVmCheck system {
          name = "sentinel-vm";
          nodes.machine =
            { pkgs, ... }:
            {
              environment.systemPackages = [ pkgs.jq ];
              sinnix.services.sentinel = {
                enable = true;
                enableCorrectiveActions = false;
                enableNotifications = false;
                intervalSec = 5;
              };
              systemd.tmpfiles.rules = [
                "d /persist/.btrfs/snapshot 0755 root root -"
              ];
            };
          testScript = ''
            start_all()
            machine.wait_for_unit("multi-user.target")
            machine.wait_for_unit("sinnix-sentinel.timer")

            machine.succeed("systemctl start sinnix-sentinel.service")
            machine.succeed("test \"$(systemctl show sinnix-sentinel.service -P Result)\" = success")

            machine.wait_until_succeeds("test -s /run/sinnix/health.json")
            machine.succeed("test -d /var/log/sinnix-sentinel")
            machine.succeed("test -d /var/lib/sinnix-sentinel")
            machine.succeed("test -s /var/log/sinnix-sentinel/events.jsonl")

            machine.succeed("jq -e '(.summary.ok + .summary.warn + .summary.fail) >= 1 and any(.checks[]; .category == \"services\")' /run/sinnix/health.json >/dev/null")
            machine.succeed("head -n 1 /var/log/sinnix-sentinel/events.jsonl | jq -e '.source == \"sinnix-sentinel\"' >/dev/null")
          '';
        };
        transmission-vm = mkVmCheck system {
          name = "transmission-vm";
          nodes.machine =
            { pkgs, ... }:
            {
              environment.systemPackages = [
                pkgs.curl
                pkgs.jq
              ];
              sinnix.services.transmission.enable = true;
            };
          testScript = ''
            start_all()
            machine.wait_for_unit("multi-user.target")
            machine.wait_for_unit("transmission.service")
            machine.wait_until_succeeds("test -d /neo-outer-realm/inbox")

            machine.wait_until_succeeds("curl -sS -D /tmp/transmission.headers -o /tmp/transmission.body http://127.0.0.1:9091/transmission/rpc || true; grep -q '409 Conflict' /tmp/transmission.headers")
            machine.succeed('session_id=$(awk -F": " \'/X-Transmission-Session-Id/ {print $2}\' /tmp/transmission.headers | tr -d "\\r"); test -n "$session_id"')
          '';
        };
      };
      backupBorgHookRuntime = mkRuntimeCheck system {
        name = "backup-borg-hook-runtime-check";
        nativeBuildInputs = [
          pkgs.bash
          pkgs.coreutils
          pkgs.findutils
          pkgs.gnugrep
        ];
        script = ''
          mkdir -p \
            "$TMPDIR/mock-bin" \
            "$TMPDIR/logs" \
            "$TMPDIR/bind" \
            "$TMPDIR/realm-snapshots" \
            "$TMPDIR/persist-snapshots" \
            "$TMPDIR/realm-empty"

          cat > "$TMPDIR/mock-bin/mountpoint" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          path="''${@: -1}"
          if [ -e "$path/.mounted" ]; then
            exit 0
          fi
          exit 1
          EOF

          cat > "$TMPDIR/mock-bin/mount" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          source_path="''${@: -2:1}"
          target_path="''${@: -1}"
          mkdir -p "$target_path"
          touch "$target_path/.mounted"
          printf '%s => %s\n' "$source_path" "$target_path" >> "$TMPDIR/logs/mount.log"
          EOF

          cat > "$TMPDIR/mock-bin/umount" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          target_path="$1"
          rm -f "$target_path/.mounted"
          printf '%s\n' "$target_path" >> "$TMPDIR/logs/umount.log"
          EOF

          chmod +x "$TMPDIR/mock-bin/mountpoint" "$TMPDIR/mock-bin/mount" "$TMPDIR/mock-bin/umount"

          mkdir -p \
            "$TMPDIR/realm-snapshots/realm.2026-04-02T010000" \
            "$TMPDIR/realm-snapshots/realm.2026-04-02T011500" \
            "$TMPDIR/persist-snapshots/persist.2026-04-02T010000" \
            "$TMPDIR/persist-snapshots/persist.2026-04-02T011500"

          cat > "$TMPDIR/run-realm-hook.sh" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          ${realmBorgPreHook}
          EOF

          cat > "$TMPDIR/run-persist-hook.sh" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          ${persistBorgPreHook}
          EOF

          cat > "$TMPDIR/run-missing-realm-hook.sh" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          ${missingRealmBorgPreHook}
          EOF

          chmod +x \
            "$TMPDIR/run-realm-hook.sh" \
            "$TMPDIR/run-persist-hook.sh" \
            "$TMPDIR/run-missing-realm-hook.sh"

          "$TMPDIR/run-realm-hook.sh"
          "$TMPDIR/run-persist-hook.sh"

          grep -q "$TMPDIR/realm-snapshots/realm.2026-04-02T011500 => $TMPDIR/bind/realm" "$TMPDIR/logs/mount.log"
          grep -q "$TMPDIR/persist-snapshots/persist.2026-04-02T011500 => $TMPDIR/bind/persist" "$TMPDIR/logs/mount.log"
          grep -q "$TMPDIR/bind/realm" "$TMPDIR/logs/umount.log"
          grep -q "$TMPDIR/bind/persist" "$TMPDIR/logs/umount.log"

          set +e
          "$TMPDIR/run-missing-realm-hook.sh" > "$TMPDIR/missing-realm.log" 2>&1
          missing_status=$?
          set -e

          test "$missing_status" -eq 1
          grep -q "No realm snapshot found" "$TMPDIR/missing-realm.log"
        '';
      };
      sinnixObserveRuntime =
        pkgs.runCommand "sinnix-observe-runtime-check"
          {
            nativeBuildInputs = [
              pkgs.coreutils
              pkgs.gnugrep
              pkgs.jq
              pkgs.python3
              pkgs.sqlite
            ];
          }
          ''
            export HOME="$TMPDIR/home"
            mkdir -p \
              "$HOME" \
              "$TMPDIR/sinex/.sinex/state" \
              "$TMPDIR/polylogue-runs"

            sqlite3 "$TMPDIR/sinex/.sinex/state/xtask-history.db" <<'SQL'
            create table invocations (
              id integer primary key,
              command text not null,
              subcommand text,
              started_at text not null,
              finished_at text,
              duration_secs real,
              status text not null,
              cwd text not null,
              pid integer,
              scope_key text,
              launch_mode text,
              is_background integer,
              process_cpu_usage_avg real,
              process_memory_usage_max_mb real,
              process_count_max integer,
              resource_sample_count integer,
              shared_nix_build_slice_memory_usage_max_mb real,
              shared_background_slice_memory_usage_max_mb real
            );
            insert into invocations values (
              42,
              'check',
              null,
              '2026-05-03T12:00:00Z',
              '2026-05-03T12:00:25Z',
              25.0,
              'success',
              '/realm/project/sinex',
              null,
              'scope-fixture',
              'foreground',
              0,
              180.0,
              512.0,
              12,
              4,
              128.0,
              2048.0
            );
            SQL

            sqlite3 "$TMPDIR/polylogue.db" <<'SQL'
            create table runs (
              run_id text primary key,
              timestamp text not null,
              plan_snapshot text,
              counts_json text,
              drift_json text,
              indexed integer,
              duration_ms integer
            );
            insert into runs values (
              'run-fixture',
              '1777809600',
              null,
              '{"conversations":2,"messages":77,"acquired":1,"rendered":2}',
              '{}',
              1,
              12345
            );
            SQL

            cat > "$TMPDIR/polylogue-runs/run-1777809600-run-fixture.json" <<'JSON'
            {
              "run_id": "run-fixture",
              "timestamp": 1777809600,
              "duration_ms": 12345,
              "counts": {
                "conversations": 2,
                "messages": 77,
                "rendered": 2
              }
            }
            JSON

            cat > "$TMPDIR/below-cgroup.tsv" <<'EOF'
            2026-05-03T12:00:10Z	sinex	/user.slice/user-1000.slice/user@1000.service/build.slice/sinex.scope	120.0	536870912	104857600	7.5	0.0
            2026-05-03T12:00:11Z	polylogue	/user.slice/user-1000.slice/user@1000.service/background.slice/polylogue.scope	30.0	268435456	20971520	1.5	0.0
            EOF
            cat > "$TMPDIR/below-process.tsv" <<'EOF'
            2026-05-03T12:00:10Z	1001	cargo	S	/user.slice/user-1000.slice/user@1000.service/build.slice/sinex.scope	104857600	536870912	120.0	cargo check --workspace /realm/project/sinex
            2026-05-03T12:00:11Z	1002	polylogue	S	/user.slice/user-1000.slice/user@1000.service/background.slice/polylogue.scope	20971520	268435456	30.0	polylogue --plain run acquire parse materialize render index
            EOF

            SINEX_ROOT="$TMPDIR/sinex" \
            SINNIX_OBSERVE_POLYLOGUE_DB="$TMPDIR/polylogue.db" \
            SINNIX_OBSERVE_POLYLOGUE_RUNS_DIR="$TMPDIR/polylogue-runs" \
            SINNIX_OBSERVE_BELOW_CGROUP_TSV="$TMPDIR/below-cgroup.tsv" \
            SINNIX_OBSERVE_BELOW_PROCESS_TSV="$TMPDIR/below-process.tsv" \
              ${pkgs.python3}/bin/python3 ${../scripts/sinnix-observe} \
                --offline --format json --since '1 day ago' --duration '1 day' --limit 5 \
                > "$TMPDIR/report.json"

            jq -e '
              .schema == "sinnix-observe-v1" and
              (.workload_rows | any(.source == "sinex.xtask" and .project == "sinex" and (.gaps | index("sinex.invocation.lacks_cgroup")))) and
              (.workload_rows | any(.source == "polylogue.run" and .project == "polylogue" and (.gaps | index("polylogue.run.lacks_cgroup")))) and
              (.workload_rows | any(.source == "below.process" and .project == "sinex")) and
              (.workload_rows | any(.source == "below.process" and .project == "polylogue")) and
              (.gaps_summary."sinex.invocation.lacks_io_bytes" >= 1) and
              (.gaps_summary."polylogue.run.lacks_psi_window" >= 1)
            ' "$TMPDIR/report.json" >/dev/null

            SINEX_ROOT="$TMPDIR/sinex" \
            SINNIX_OBSERVE_POLYLOGUE_DB="$TMPDIR/polylogue.db" \
            SINNIX_OBSERVE_POLYLOGUE_RUNS_DIR="$TMPDIR/polylogue-runs" \
            SINNIX_OBSERVE_BELOW_CGROUP_TSV="$TMPDIR/below-cgroup.tsv" \
            SINNIX_OBSERVE_BELOW_PROCESS_TSV="$TMPDIR/below-process.tsv" \
              ${pkgs.python3}/bin/python3 ${../scripts/sinnix-observe} \
                --offline --format human --since '1 day ago' --duration '1 day' --limit 5 \
                > "$TMPDIR/report.txt"

            grep -q '== workload rows ==' "$TMPDIR/report.txt"
            grep -q 'sinex.invocation.lacks_cgroup' "$TMPDIR/report.txt"
            grep -q 'polylogue.run.lacks_cgroup' "$TMPDIR/report.txt"

            touch "$out"
          '';
      terminalCaptureRuntime =
        pkgs.runCommand "sinnix-terminal-capture-runtime-check"
          {
            nativeBuildInputs = [
              pkgs.asciinema_3
              pkgs.coreutils
              pkgs.findutils
              pkgs.gnugrep
              pkgs.jq
              pkgs.util-linux
              pkgs.zsh
            ];
          }
          ''
            export HOME="$TMPDIR/home"
            export PATH="${
              lib.makeBinPath [
                pkgs.asciinema_3
                pkgs.coreutils
                pkgs.findutils
                pkgs.gnugrep
                pkgs.jq
                pkgs.util-linux
                pkgs.zsh
              ]
            }:$PATH"
            mkdir -p "$HOME" "$TMPDIR/captures"

            cat > "$TMPDIR/fake-shell.zsh" <<'EOF'
            #!${pkgs.zsh}/bin/zsh
            set -eu
            source ${../scripts/sinnix-terminal-capture-hooks.zsh}
            print -r -- "terminal-capture-ready"
            true
            exit 0
            EOF
            chmod +x "$TMPDIR/fake-shell.zsh"

            transcript="$TMPDIR/terminal-capture-runtime.typescript"

            script -qfec "env \
              EPOCHREALTIME='1773285652,647035000' \
              HOME='$HOME' \
              HOSTNAME='terminal-capture-test' \
              KITTY_PID='4242' \
              SHELL='$TMPDIR/fake-shell.zsh' \
              SINNIX_CAPTURE_CAST_FILE='$TMPDIR/poison.cast' \
              SINNIX_CAPTURE_EVENTS_FILE='$TMPDIR/poison.events.jsonl' \
              SINNIX_CAPTURE_ROOT='$TMPDIR/captures' \
              SINNIX_CAPTURE_SESSION_ID='poison-session' \
              TERM='xterm-kitty' \
              USER='tester' \
              ${pkgs.bash}/bin/bash ${../scripts/sinnix-captured-shell}" "$transcript"

            grep -q "terminal-capture-ready" "$transcript"

            session_json="$(find "$TMPDIR/captures" -type f -name session.json | sed -n '1p')"
            events_json="$(find "$TMPDIR/captures" -type f -name events.jsonl | sed -n '1p')"
            cast_file="$(find "$TMPDIR/captures" -type f -name session.cast | sed -n '1p')"

            test -n "$session_json"
            test -n "$events_json"
            test -n "$cast_file"

            session_dir="$(dirname "$session_json")"
            session_id="$(basename "$session_dir")"
            month_dir="$(dirname "$session_dir")"
            day_dir="$(basename "$month_dir")"
            year_month_dir="$(dirname "$month_dir")"
            month_name="$(basename "$year_month_dir")"
            year_name="$(basename "$(dirname "$year_month_dir")")"

            test "$day_dir" != "$session_id"
            [[ "$year_name" =~ ^[0-9]{4}$ ]]
            [[ "$month_name" =~ ^[0-9]{2}$ ]]
            [[ "$day_dir" =~ ^[0-9]{2}$ ]]
            test "$cast_file" = "$session_dir/session.cast"
            test "$events_json" = "$session_dir/events.jsonl"
            test -z "$(find "$TMPDIR/captures" -maxdepth 1 -type f | sed -n '1p')"
            test -z "$(find "$TMPDIR/captures" -type f -name '*.cast.meta' | sed -n '1p')"

            jq -e '
              .schema == "terminal-session-v1" and
              .session_id == $session_id and
              (.started_at_ms | type) == "number" and
              (.command_count | type) == "number" and
              .command_count >= 1 and
              .event_count >= 4 and
              .cast_path == $cast_path and
              .events_path == $events_path and
              .host == "terminal-capture-test" and
              .terminal == "kitty" and
              .exit_reason == "shell_exit" and
              .cleanup_escalated == false and
              .recorder_exit_code == 0 and
              (.session_id | test(",") | not) and
              .session_id != "poison-session" and
              .cast_path != $poison_cast and
              .events_path != $poison_events
            ' \
              --arg session_id "$session_id" \
              --arg cast_path "$cast_file" \
              --arg events_path "$events_json" \
              --arg poison_cast "$TMPDIR/poison.cast" \
              --arg poison_events "$TMPDIR/poison.events.jsonl" \
              "$session_json" >/dev/null

            jq -s -e '
              length >= 4 and
              .[0].type == "session_start" and
              .[-1].type == "session_end" and
              ([.[] | select(.type == "command_start")] | length) >= 1 and
              all(.[]; .session_id != "poison-session")
            ' "$events_json" >/dev/null

            touch "$out"
          '';
      terminalCaptureRuntimeFailure =
        pkgs.runCommand "sinnix-terminal-capture-runtime-failure-check"
          {
            nativeBuildInputs = [
              pkgs.asciinema_3
              pkgs.coreutils
              pkgs.findutils
              pkgs.gnugrep
              pkgs.jq
              pkgs.util-linux
              pkgs.zsh
            ];
          }
          ''
            export HOME="$TMPDIR/home"
            mkdir -p "$HOME" "$TMPDIR/captures" "$TMPDIR/bin"

            cat > "$TMPDIR/bin/asciinema" <<'EOF'
            #!${pkgs.bash}/bin/bash
            set -euo pipefail

            command_path=""
            output_path=""

            while (($#)); do
              case "$1" in
                rec)
                  shift
                  ;;
                --command)
                  command_path="$2"
                  shift 2
                  ;;
                --*)
                  if (($# >= 2)) && [[ "$2" != --* ]]; then
                    shift 2
                  else
                    shift
                  fi
                  ;;
                *)
                  output_path="$1"
                  shift
                  ;;
              esac
            done

            test -n "$command_path"
            test -n "$output_path"
            mkdir -p "$(dirname "$output_path")"
            printf '{"version": 3, "width": 80, "height": 24, "timestamp": 0}\n' > "$output_path"
            "$command_path"
            exit 42
            EOF
            chmod +x "$TMPDIR/bin/asciinema"

            cat > "$TMPDIR/fake-shell.zsh" <<'EOF'
            #!${pkgs.zsh}/bin/zsh
            set -eu
            source ${../scripts/sinnix-terminal-capture-hooks.zsh}
            print -r -- "terminal-capture-ready"
            true
            exit 0
            EOF
            chmod +x "$TMPDIR/fake-shell.zsh"

            export PATH="$TMPDIR/bin:${
              lib.makeBinPath [
                pkgs.coreutils
                pkgs.findutils
                pkgs.gnugrep
                pkgs.jq
                pkgs.util-linux
                pkgs.zsh
              ]
            }:$PATH"

            transcript="$TMPDIR/terminal-capture-runtime-failure.typescript"

            set +e
            script -qfec "env \
              EPOCHREALTIME='1773285652,647035000' \
              HOME='$HOME' \
              HOSTNAME='terminal-capture-test' \
              KITTY_PID='4242' \
              SHELL='$TMPDIR/fake-shell.zsh' \
              SINNIX_CAPTURE_ROOT='$TMPDIR/captures' \
              TERM='xterm-kitty' \
              USER='tester' \
              ${pkgs.bash}/bin/bash ${../scripts/sinnix-captured-shell}" "$transcript"
            status=$?
            set -e

            test "$status" -eq 42
            grep -q "terminal-capture-ready" "$transcript"

            session_json="$(find "$TMPDIR/captures" -type f -name session.json | sed -n '1p')"
            events_json="$(find "$TMPDIR/captures" -type f -name events.jsonl | sed -n '1p')"
            cast_file="$(find "$TMPDIR/captures" -type f -name session.cast | sed -n '1p')"

            test -n "$session_json"
            test -n "$events_json"
            test -n "$cast_file"
            test -z "$(find "$TMPDIR/captures" -maxdepth 1 -type f | sed -n '1p')"
            test -z "$(find "$TMPDIR/captures" -type f -name '*.cast.meta' | sed -n '1p')"

            jq -e '
              .schema == "terminal-session-v1" and
              (.started_at_ms | type) == "number" and
              .exit_reason == "shell_exit" and
              .exit_code == 0 and
              .recorder_exit_code == 42 and
              .cleanup_escalated == false and
              .command_count >= 1 and
              .event_count >= 4 and
              (.session_id | test(",") | not)
            ' "$session_json" >/dev/null

            jq -s -e '
              length >= 4 and
              .[0].type == "session_start" and
              .[-1].type == "session_end"
            ' "$events_json" >/dev/null

            touch "$out"
          '';
      devAgentToolsRuntime = mkHmRuntimeCheck system (
        agentToolsFixture
        // {
          name = "dev-agent-tools-runtime-check";
          nativeBuildInputs = builtins.filter (pkg: pkg != pkgs.expect) agentToolsFixture.nativeBuildInputs;
          script = ''
            test -L "$HOME/.codex/config.toml"
            test -L "$(readlink "$HOME/.codex/config.toml")"
            test -L "$HOME/.gemini/settings.json"
            test -L "$(readlink "$HOME/.gemini/settings.json")"
            test -L "$HOME/.config/claude/settings.json"
            test -L "$(readlink "$HOME/.config/claude/settings.json")"
            test -L "$HOME/forge/.forge.toml"
            test -L "$(readlink "$HOME/forge/.forge.toml")"

            cp ${lib.escapeShellArg (toString (repoFixtureRoot + "/dots/forge/.forge.toml"))} \
              "$TMPDIR/forge.toml"
            rm "$HOME/forge/.forge.toml"
            cp "$TMPDIR/forge.toml" "$HOME/forge/.forge.toml"

            "$HOME/.local/bin/forge" --version | grep -q '^forge '
            "$HOME/.local/bin/forge" config get model | grep -qx 'gpt-5.5'
            "$HOME/.local/bin/mcp-polylogue" --help | grep -q 'Start the Polylogue MCP stdio bridge'
            "$HOME/.local/bin/mcp-playwright" --help | grep -q 'Usage: Playwright MCP'

            "$HOME/.local/bin/forge" config path | grep -qx "$HOME/forge/.forge.toml"
            test -d "$HOME/forge/agents"
            test -d "$HOME/forge/logs/requests"
            test -d "$HOME/forge/snapshots"
            test -f "$HOME/forge/.forge_history"

            jq -e '
              .mcpServers.context7.url == "https://mcp.context7.com/mcp" and
              .mcpServers.firecrawl.command == "mcp-firecrawl" and
              .mcpServers.playwright.command == "mcp-playwright" and
              .mcpServers.playwright.args == ["--headless"] and
              .mcpServers.polylogue.command == "mcp-polylogue"
            ' "$HOME/forge/.mcp.json" >/dev/null

            ${pkgs.zsh}/bin/zsh -ic '[[ -n "$_FORGE_PLUGIN_LOADED" ]]'
            ${pkgs.zsh}/bin/zsh -ic '[[ -n "$_FORGE_THEME_LOADED" ]]'
            ${pkgs.zsh}/bin/zsh -ic '[[ "$_FORGE_BIN" == "$HOME/.local/bin/forge" ]]'
            ${pkgs.zsh}/bin/zsh -ic 'bindkey -M viins "^M" | grep -q "forge-accept-line"'
            ${pkgs.zsh}/bin/zsh -ic 'bindkey -M viins "^J" | grep -q "forge-accept-line"'
            ${pkgs.zsh}/bin/zsh -ic 'bindkey -M viins "^I" | grep -q "forge-completion"'
          '';
        }
      );
      cliPolylogueRuntime = mkHmRuntimeCheck system {
        name = "cli-polylogue-runtime-check";
        spec = cliPolylogueRuntimeSpec;
        nativeBuildInputs = [
          pkgs.coreutils
          pkgs.gnugrep
        ];
        script = ''
          polylogue --help | grep -q '^Usage: polylogue'
          polylogue schema list --help | grep -q 'List available schema packages'
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
      devGitRuntime = mkHmRuntimeCheck system {
        name = "dev-git-runtime-check";
        spec = devGitRuntimeSpec;
        nativeBuildInputs = [
          pkgs.delta
          pkgs.git
          pkgs.gnugrep
        ];
        homeFiles = [ ".config/git/ignore_global" ];
        xdgConfigFiles = [ "git/config" ];
        script = ''
          git config --global --get init.defaultBranch | grep -qx 'master'
          git config --global --get merge.conflictStyle | grep -qx 'zdiff3'
          git config --global --get pull.rebase | grep -qx 'true'
          git config --global --get rerere.enabled | grep -qx 'true'
          git config --global --get credential.https://github.com.helper | grep -q '/run/agenix/github-token'
          grep -q '^AGENTS.md$' "$HOME/.config/git/ignore_global"
          delta --version >/dev/null
        '';
      };
      devLanguagesRuntime = mkHmRuntimeCheck system {
        name = "dev-languages-runtime-check";
        spec = devLanguagesRuntimeSpec;
        nativeBuildInputs = [
          pkgs.coreutils
          pkgs.gnugrep
        ];
        script = ''
          python --version >/dev/null
          node --version >/dev/null
          sqlite3 --version >/dev/null
          gh --version >/dev/null
          forge --version | grep -q '^forge '
        '';
      };
      devAgentToolsPty = mkHmRuntimeCheck system (
        agentToolsFixture
        // {
          name = "dev-agent-tools-pty-check";
          script = ''
            cat > "$TMPDIR/forge-pty.expect" <<'EOF'
            log_user 1
            log_file -noappend "$env(TMPDIR)/forge-pty.log"
            set timeout 20

            spawn env HOME=$env(HOME) PATH=$env(PATH) SHELL=$env(SHELL) TERM=$env(TERM) TERM_PROGRAM=$env(TERM_PROGRAM) TERM_PROGRAM_VERSION=$env(TERM_PROGRAM_VERSION) ZDOTDIR=$env(ZDOTDIR) ${pkgs.zsh}/bin/zsh -i
            after 3000
            send_user "forge-pty: shell spawned\n"
            send "print READY\r"
            expect {
              -re {READY} {}
              timeout { exit 1 }
            }

            send_user "forge-pty: sending :env\n"
            send ":env\r"
            expect {
              -re {TOOL CONFIGURATION} {}
              timeout { exit 1 }
            }
            expect {
              -re {debug requests} {}
              timeout { exit 1 }
            }

            send "exit\r"
            expect eof
            EOF

            TMPDIR="$TMPDIR" ${pkgs.expect}/bin/expect -f "$TMPDIR/forge-pty.expect"
            ${pkgs.gnugrep}/bin/grep -q 'TOOL CONFIGURATION' "$TMPDIR/forge-pty.log"
            ${pkgs.gnugrep}/bin/grep -q 'debug requests' "$TMPDIR/forge-pty.log"
          '';
        }
      );
    in
    {
      heavyChecks = {
        backup-borg-hook-runtime = backupBorgHookRuntime;
        cli-polylogue-runtime = cliPolylogueRuntime;
        cli-task-tracking-runtime = cliTaskTrackingRuntime;
        dev-agent-tools-pty = devAgentToolsPty;
        dev-agent-tools-runtime = devAgentToolsRuntime;
        dev-git-runtime = devGitRuntime;
        dev-languages-runtime = devLanguagesRuntime;
        sinnix-observe-runtime = sinnixObserveRuntime;
        terminal-capture-runtime = terminalCaptureRuntime;
        terminal-capture-runtime-failure = terminalCaptureRuntimeFailure;
      }
      // vmChecks
      // hostBuildChecks;
    };
}
