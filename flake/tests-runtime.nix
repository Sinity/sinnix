# Runtime/VM/host check perSystem block.
#
# Runtime/PTY/VM/host-build checks that depend on a Linux host and real tooling.
# The old co-located assertion-spec layer was removed because it mostly
# duplicated declarative config instead of exercising behavior.
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      scriptRegistry = import ./scripts.nix { inherit inputs pkgs; };
      sinnixObserve = scriptRegistry.packageSet.sinnix-observe;
      testLib = import ./test-lib.nix { inherit inputs lib; };
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
          (_: {
            sinnix.features.dev.shell.enable = true;
            sinnix.features.dev.mcp-servers.enable = true;
          })
        ];
        assertions =
          config:
          let
            hm = config.home-manager.users.${config.sinnix.user.name};
            activationText = hm.home.activation.claudeSymlink.data or "";
          in
          [
            {
              assertion = !(hm.xdg.configFile ? "claude/settings.json");
              message = "Claude settings.json must not be managed through Home Manager xdg.configFile.";
            }
            {
              assertion = lib.hasInfix "${config.sinnix.paths.dotsRoot}/claude/settings.json" activationText;
              message = "Claude settings.json must be linked directly to dots during activation.";
            }
          ];
      };
      agentToolsFixture = {
        spec = devAgentToolsRuntimeSpec;
        nativeBuildInputs = [
          pkgs.coreutils
          pkgs.expect
          pkgs.findutils
          pkgs.gnugrep
          pkgs.jq
          pkgs.python3
          pkgs.zsh
        ];
        homeFiles = [
          ".gemini/settings.json"
          ".local/bin/claude-full"
          ".local/bin/claude-lean"
          ".local/bin/claude-browser"
          ".local/bin/claude-deepseek"
          ".local/bin/claude-local"
          ".local/bin/codex"
          ".local/bin/codex-lean"
          ".local/bin/codex-full"
          ".local/bin/codex-browser"
          ".local/bin/codex-deepseek"
          ".local/bin/codex-local"
          ".local/bin/gemini"
          ".local/bin/codebase-memory-mcp"
          ".local/bin/serena"
          ".local/bin/serena-hooks"
          ".local/bin/bd-prime-if-present"
          ".local/bin/mcp-firecrawl"
          ".local/bin/mcp-chrome-devtools"
          ".local/bin/mcp-chrome-devtools-private"
          ".local/bin/mcp-chrome-devtools-private-visible"
          ".local/bin/mcp-polylogue"
          ".local/bin/mcp-sinex"
          ".local/bin/sinnix-mcp-sweep"
          ".local/bin/sinnix-agent-status"
          ".local/bin/sinnix-chrome-control"
          ".local/bin/sinnix-hypr-control"
          ".local/bin/sinnix-keyboard-control"
          ".local/bin/sinnix-kitty-control"
          ".local/bin/sinnix-screenshot-control"
        ];
        xdgConfigFiles = [
          "claude/mcp.json"
          "claude/mcp-lean.json"
          "claude/mcp-browser.json"
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
        '';
      };
      agentToolsRuntimeConfig = (evalTestSpec system devAgentToolsRuntimeSpec).config;
      agentToolsCodexConfigSource =
        agentToolsRuntimeConfig.sinnix.features.dev.mcp-servers.codexConfigSource;
      agentToolsCodexFullConfigSource =
        agentToolsRuntimeConfig.sinnix.features.dev.mcp-servers.codexFullConfigSource;
      agentToolsCodexLeanConfigSource =
        agentToolsRuntimeConfig.sinnix.features.dev.mcp-servers.codexLeanConfigSource;
      agentToolsCodexEvidenceConfigSource =
        agentToolsRuntimeConfig.sinnix.features.dev.mcp-servers.codexEvidenceConfigSource;
      agentToolsCodexBrowserConfigSource =
        agentToolsRuntimeConfig.sinnix.features.dev.mcp-servers.codexBrowserConfigSource;
      agentToolsCodexDeepseekConfigSource =
        agentToolsRuntimeConfig.sinnix.features.dev.mcp-servers.codexDeepseekConfigSource;
      agentToolsCodexLocalConfigSource =
        agentToolsRuntimeConfig.sinnix.features.dev.mcp-servers.codexLocalConfigSource;
      agentToolsCodexHooksSource =
        agentToolsRuntimeConfig.sinnix.features.dev.mcp-servers.codexHooksSource;
      backupRuntimeEval = evalTestSpec system {
        name = "backup-borg-hook-runtime";
        modules = [
          mountTmpfsRoots
          baseTestConfig
          (_: {
            networking.hostName = "backup-runtime";
          })
        ];
        assertions = _config: [ ];
      };
      rewriteBackupHook =
        hook: replacements:
        builtins.replaceStrings (map (replacement: replacement.from) replacements) (map (
          replacement: replacement.to
        ) replacements) hook;
      realmBorgDrainScript =
        rewriteBackupHook backupRuntimeEval.config.systemd.services.borgbackup-job-realm.script
          [
            {
              from = "/outer-realm/backup/borg-realm-v2";
              to = "$TMPDIR/repos/borg-realm-v2";
            }
            {
              from = "/persist/root/.cache/borg-drain";
              to = "$TMPDIR/state/borg-drain";
            }
            {
              from = "/persist/root/.cache/borg";
              to = "$TMPDIR/state/borg-cache";
            }
            {
              from = "/run/lock/sinnix-borg.lock";
              to = "$TMPDIR/state/sinnix-borg.lock";
            }
            {
              from = "install -d -m 0700 -o root -g root";
              to = "install -d -m 0700";
            }
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
      persistBorgDrainScript =
        rewriteBackupHook backupRuntimeEval.config.systemd.services.borgbackup-job-persist.script
          [
            {
              from = "/outer-realm/backup/borg-persist-v1";
              to = "$TMPDIR/repos/borg-persist-v1";
            }
            {
              from = "/persist/root/.cache/borg-drain";
              to = "$TMPDIR/state/borg-drain";
            }
            {
              from = "/persist/root/.cache/borg";
              to = "$TMPDIR/state/borg-cache";
            }
            {
              from = "/run/lock/sinnix-borg.lock";
              to = "$TMPDIR/state/sinnix-borg.lock";
            }
            {
              from = "install -d -m 0700 -o root -g root";
              to = "install -d -m 0700";
            }
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
      missingRealmBorgDrainScript =
        rewriteBackupHook backupRuntimeEval.config.systemd.services.borgbackup-job-realm.script
          [
            {
              from = "/outer-realm/backup/borg-realm-v2";
              to = "$TMPDIR/repos/borg-realm-v2";
            }
            {
              from = "/persist/root/.cache/borg-drain";
              to = "$TMPDIR/state/borg-drain";
            }
            {
              from = "/persist/root/.cache/borg";
              to = "$TMPDIR/state/borg-cache";
            }
            {
              from = "/run/lock/sinnix-borg.lock";
              to = "$TMPDIR/state/sinnix-borg.lock";
            }
            {
              from = "install -d -m 0700 -o root -g root";
              to = "install -d -m 0700";
            }
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
              sinnix.features.desktop = {
                activitywatch.enable = false;
                agentVerifyTimer.enable = false;
                audio.enable = false;
                audioCapture.enable = false;
                base.enable = false;
                browser.enable = false;
                "common-apps".enable = false;
                gaming.enable = false;
                hyprland.enable = false;
                hyprlandAnimations.enable = false;
                media.enable = false;
                mime.enable = false;
                noctalia.enable = false;
                storage.enable = false;
                terminal.enable = false;
                theming.enable = false;
                ui.enable = false;
              };
              sinnix.services.polylogue.enable = true;
            };
          testScript = ''
            start_all()
            machine.wait_for_unit("multi-user.target")

            uid = machine.succeed("id -u sinity").strip()
            as_user = f"XDG_RUNTIME_DIR=/run/user/{uid} runuser -u sinity --"

            machine.succeed("loginctl enable-linger sinity")
            machine.wait_for_unit(f"user@{uid}.service")
            machine.wait_for_unit("polylogued.service", "sinity")

            machine.succeed(f"{as_user} systemctl --user is-active --quiet polylogued.service")
            machine.fail(f"{as_user} systemctl --user cat polylogue-run.service")
            machine.fail(f"{as_user} systemctl --user cat polylogue-run.timer")
            machine.succeed(f"{as_user} ${
              inputs.polylogue.packages.${system}.default
            }/bin/polylogued status --format json | jq -e '.daemon == \"polylogued\" and (.live.source_count >= 0)' >/dev/null")
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
              sinnix.features.desktop = {
                activitywatch.enable = false;
                agentVerifyTimer.enable = false;
                audio.enable = false;
                audioCapture.enable = false;
                base.enable = false;
                browser.enable = false;
                "common-apps".enable = false;
                gaming.enable = false;
                hyprland.enable = false;
                hyprlandAnimations.enable = false;
                media.enable = false;
                mime.enable = false;
                noctalia.enable = false;
                storage.enable = false;
                terminal.enable = false;
                theming.enable = false;
                ui.enable = false;
              };
              sinnix.services.transmission.enable = true;
            };
          testScript = ''
            start_all()
            machine.wait_for_unit("multi-user.target")
            machine.succeed("systemctl start transmission.service")
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
          pkgs.util-linux
        ];
        script = ''
          mkdir -p \
            "$TMPDIR/mock-bin" \
            "$TMPDIR/logs" \
            "$TMPDIR/bind" \
            "$TMPDIR/repos" \
            "$TMPDIR/state" \
            "$TMPDIR/state/borg-cache" \
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

          cat > "$TMPDIR/mock-bin/borg" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          printf '%s\n' "$*" >> "$TMPDIR/logs/borg.log"
          case "$1" in
            init)
              repo="''${@: -1}"
              repo_path="''${repo#file://}"
              mkdir -p "$repo_path"
              touch "$repo_path/config"
              ;;
            list)
              exit 2
              ;;
            create)
              ;;
            break-lock)
              ;;
            *)
              echo "unexpected borg command: $*" >&2
              exit 64
              ;;
          esac
          EOF

          cat > "$TMPDIR/mock-bin/btrfs" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          printf '%s\n' "$*" >> "$TMPDIR/logs/btrfs.log"
          if [ "$1" = subvolume ] && [ "$2" = delete ]; then
            rm -rf "$3"
            exit 0
          fi
          echo "unexpected btrfs command: $*" >&2
          exit 64
          EOF

          cat > "$TMPDIR/mock-bin/pgrep" <<'EOF'
          #!${pkgs.bash}/bin/bash
          exit 1
          EOF

          chmod +x \
            "$TMPDIR/mock-bin/mountpoint" \
            "$TMPDIR/mock-bin/mount" \
            "$TMPDIR/mock-bin/umount" \
            "$TMPDIR/mock-bin/borg" \
            "$TMPDIR/mock-bin/btrfs" \
            "$TMPDIR/mock-bin/pgrep"

          export PATH="$TMPDIR/mock-bin:$PATH"

          mkdir -p \
            "$TMPDIR/realm-snapshots/realm.2026-04-02T010000" \
            "$TMPDIR/realm-snapshots/realm.2026-04-02T011500" \
            "$TMPDIR/persist-snapshots/persist.2026-04-02T010000" \
            "$TMPDIR/persist-snapshots/persist.2026-04-02T011500"

          cat > "$TMPDIR/run-realm-hook.sh" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          ${realmBorgDrainScript}
          EOF

          cat > "$TMPDIR/run-persist-hook.sh" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          ${persistBorgDrainScript}
          EOF

          cat > "$TMPDIR/run-missing-realm-hook.sh" <<'EOF'
          #!${pkgs.bash}/bin/bash
          set -euo pipefail
          ${missingRealmBorgDrainScript}
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
          grep -q "create .*::realm-realm.2026-04-02T011500" "$TMPDIR/logs/borg.log"
          grep -q "create .*::persist-persist.2026-04-02T011500" "$TMPDIR/logs/borg.log"
          grep -q "subvolume delete $TMPDIR/realm-snapshots/realm.2026-04-02T010000" "$TMPDIR/logs/btrfs.log"
          grep -q "subvolume delete $TMPDIR/persist-snapshots/persist.2026-04-02T010000" "$TMPDIR/logs/btrfs.log"

          set +e
          "$TMPDIR/run-missing-realm-hook.sh" > "$TMPDIR/missing-realm.log" 2>&1
          missing_status=$?
          set -e

          test "$missing_status" -eq 0
          ! grep -q "borg create failed" "$TMPDIR/missing-realm.log"
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
              "$TMPDIR/sinex/.sinex/state"

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
            create table live_ingest_attempt (
              attempt_id text primary key,
              started_at text not null,
              updated_at text not null,
              completed_at text,
              status text not null,
              phase text not null,
              queued_file_count integer not null,
              needed_file_count integer not null,
              succeeded_file_count integer not null,
              failed_file_count integer not null,
              input_bytes integer not null,
              source_payload_read_bytes integer not null,
              cursor_fingerprint_read_bytes integer not null,
              parse_time_s real not null,
              convergence_time_s real not null,
              current_source text,
              current_path text,
              error text,
              rss_current_mb real,
              rss_peak_self_mb real,
              rss_peak_children_mb real,
              cgroup_path text,
              cgroup_memory_current_mb real,
              cgroup_memory_peak_mb real,
              cgroup_memory_swap_current_mb real
            );
            insert into live_ingest_attempt values (
              'attempt-fixture',
              '2026-05-03T12:00:00Z',
              '2026-05-03T12:00:12Z',
              '2026-05-03T12:00:12Z',
              'succeeded',
              'converged',
              3,
              2,
              2,
              0,
              4096,
              2048,
              0,
              1.5,
              0.5,
              'codex',
              '/tmp/session.jsonl',
              null,
              300.0,
              512.0,
              64.0,
              '/user.slice/user-1000.slice/user@1000.service/app.slice/polylogued.service',
              768.0,
              1024.0,
              0.0
            );
            SQL

            cat > "$TMPDIR/below-cgroup.tsv" <<'EOF'
            2026-05-03T12:00:10Z	sinex	/user.slice/user-1000.slice/user@1000.service/build.slice/sinex.scope	120.0	536870912	104857600	7.5	0.0
            2026-05-03T12:00:11Z	polylogued	/user.slice/user-1000.slice/user@1000.service/app.slice/polylogued.service	30.0	268435456	20971520	1.5	0.0
            EOF
            cat > "$TMPDIR/below-process.tsv" <<'EOF'
            2026-05-03T12:00:10Z	1001	cargo	S	/user.slice/user-1000.slice/user@1000.service/build.slice/sinex.scope	104857600	536870912	120.0	cargo check --workspace /realm/project/sinex
            2026-05-03T12:00:11Z	1002	polylogued	S	/user.slice/user-1000.slice/user@1000.service/app.slice/polylogued.service	20971520	268435456	30.0	polylogued run --host 127.0.0.1 --port 8765
            EOF

            SINEX_ROOT="$TMPDIR/sinex" \
            SINNIX_OBSERVE_POLYLOGUE_DB="$TMPDIR/polylogue.db" \
            SINNIX_OBSERVE_BELOW_CGROUP_TSV="$TMPDIR/below-cgroup.tsv" \
            SINNIX_OBSERVE_BELOW_PROCESS_TSV="$TMPDIR/below-process.tsv" \
              ${sinnixObserve}/bin/sinnix-observe \
                --offline --format json --since '1 day ago' --duration '1 day' --limit 5 \
                > "$TMPDIR/report.json"

            jq -e '
              .schema == "sinnix-observe-v1" and
              (.workload_rows | any(.source == "sinex.xtask" and .project == "sinex" and (.gaps | index("sinex.invocation.lacks_cgroup")))) and
              (.workload_rows | any(.source == "polylogue.live_attempt" and .project == "polylogue" and .unit == "polylogued.service" and .metrics.source_payload_read_bytes == 2048)) and
              (.workload_rows | any(.source == "below.process" and .project == "sinex")) and
              (.workload_rows | any(.source == "below.process" and .project == "polylogue")) and
              (.gaps_summary."sinex.invocation.lacks_io_bytes" >= 1)
            ' "$TMPDIR/report.json" >/dev/null

            SINEX_ROOT="$TMPDIR/sinex" \
            SINNIX_OBSERVE_POLYLOGUE_DB="$TMPDIR/polylogue.db" \
            SINNIX_OBSERVE_BELOW_CGROUP_TSV="$TMPDIR/below-cgroup.tsv" \
            SINNIX_OBSERVE_BELOW_PROCESS_TSV="$TMPDIR/below-process.tsv" \
              ${sinnixObserve}/bin/sinnix-observe \
                --offline --format human --since '1 day ago' --duration '1 day' --limit 5 \
                > "$TMPDIR/report.txt"

            grep -q '== workload rows ==' "$TMPDIR/report.txt"
            grep -q 'sinex.invocation.lacks_cgroup' "$TMPDIR/report.txt"
            grep -q 'polylogue live ingest' "$TMPDIR/report.txt"

            touch "$out"
          '';
      terminalCaptureRuntime =
        pkgs.runCommand "sinnix-terminal-capture-runtime-check"
          {
            nativeBuildInputs = [
              pkgs.asciinema
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
                pkgs.asciinema
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
              pkgs.asciinema
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
          setup = agentToolsFixture.setup + ''
            mkdir -p "$HOME/.codex"
            cp ${agentToolsCodexConfigSource} "$HOME/.codex/config.toml"
            cp ${agentToolsCodexFullConfigSource} "$HOME/.codex/full.config.toml"
            cp ${agentToolsCodexLeanConfigSource} "$HOME/.codex/lean.config.toml"
            cp ${agentToolsCodexEvidenceConfigSource} "$HOME/.codex/evidence.config.toml"
            cp ${agentToolsCodexBrowserConfigSource} "$HOME/.codex/browser.config.toml"
            cp ${agentToolsCodexDeepseekConfigSource} "$HOME/.codex/deepseek.config.toml"
            cp ${agentToolsCodexLocalConfigSource} "$HOME/.codex/local.config.toml"
            cp ${agentToolsCodexHooksSource} "$HOME/.codex/hooks.json"
            chmod 644 "$HOME/.codex/config.toml"
            chmod 644 "$HOME/.codex/full.config.toml"
            chmod 644 "$HOME/.codex/lean.config.toml"
            chmod 644 "$HOME/.codex/evidence.config.toml"
            chmod 644 "$HOME/.codex/browser.config.toml"
            chmod 644 "$HOME/.codex/deepseek.config.toml"
            chmod 644 "$HOME/.codex/local.config.toml"
            chmod 644 "$HOME/.codex/hooks.json"
          '';
          script = ''
            trap 'echo "dev-agent-tools-runtime failed at line $LINENO" >&2' ERR

            test -f "$HOME/.codex/config.toml"
            test ! -L "$HOME/.codex/config.toml"
            test ! -L "$HOME/.codex/hooks.json"
            test -f "$HOME/.gemini/settings.json"
            test -L "$HOME/.config/claude/mcp.json"

            for wrapper in \
              "$HOME/.local/bin/claude-full" \
              "$HOME/.local/bin/claude-lean" \
              "$HOME/.local/bin/claude-browser" \
              "$HOME/.local/bin/claude-deepseek" \
              "$HOME/.local/bin/claude-local" \
              "$HOME/.local/bin/codex" \
              "$HOME/.local/bin/codex-lean" \
              "$HOME/.local/bin/codex-browser" \
              "$HOME/.local/bin/codex-deepseek" \
              "$HOME/.local/bin/codex-local" \
              "$HOME/.local/bin/gemini" \
              "$HOME/.local/bin/codebase-memory-mcp" \
              "$HOME/.local/bin/serena" \
              "$HOME/.local/bin/serena-hooks" \
              "$HOME/.local/bin/bd-prime-if-present"; do
              test -x "$wrapper"
              bash -n "$wrapper"
            done

            jq -e '
              (has("mcpServers") | not) and
              .alwaysThinkingEnabled == true and
              .skipDangerousModePermissionPrompt == true and
              ([.hooks.SessionStart[].hooks[].command]
                | any(contains("SINNIX_CLAUDE_PROFILE") and contains("serena-hooks activate --client=claude-code"))) and
              ([.hooks.SessionStart[].hooks[].command]
                | any(contains("sessionstart-sinex-recall.sh"))) and
              ([.hooks.Stop[].hooks[].command]
                | any(contains("SINNIX_CLAUDE_PROFILE") and contains("serena-hooks cleanup --client=claude-code")))
            ' ${inputs.self}/dots/claude/settings.json >/dev/null

            jq -e '
              .mcpServers as $m |
              ($m | has("github") and has("context7")) and
              ($m | has("polylogue") and has("lynchpin")) and
              ($m | has("serena") and has("codebase-memory-mcp")) and
              ($m | has("chrome-devtools") | not) and
              ($m.polylogue.args == ["--role", "write"])
            ' "$HOME/.config/claude/mcp.json" >/dev/null

            jq -e '
              .mcpServers as $m |
              ($m | has("github") and has("context7") and has("polylogue")) and
              ($m | has("lynchpin") | not) and
              ($m | has("serena") | not) and
              ($m | has("codebase-memory-mcp") | not) and
              ($m | has("chrome-devtools") | not) and
              ($m.polylogue.args == ["--role", "read"])
            ' "$HOME/.config/claude/mcp-lean.json" >/dev/null

            jq -e '
              .mcpServers as $m |
              ($m | has("github") and has("context7")) and
              ($m | has("polylogue") and has("lynchpin")) and
              ($m | has("serena") and has("codebase-memory-mcp")) and
              ($m | has("chrome-devtools")) and
              ($m | has("chrome-devtools-private")) and
              ($m | has("chrome-devtools-private-visible")) and
              ($m.polylogue.args == ["--role", "write"])
            ' "$HOME/.config/claude/mcp-browser.json" >/dev/null

            python3 - <<'PYCODE'
            import pathlib, tomllib

            def keys(path):
                return set(tomllib.loads(path.read_text()).get('mcp_servers', {}))

            def assert_has(name, actual, required, forbidden=()):
                missing = set(required) - actual
                unexpected = set(forbidden) & actual
                assert not missing, f"{name} missing {sorted(missing)}"
                assert not unexpected, f"{name} unexpectedly has {sorted(unexpected)}"

            config = tomllib.loads(pathlib.Path.home().joinpath('.codex/config.toml').read_text())
            assert config['approval_policy'] == 'never'
            assert config['sandbox_mode'] == 'danger-full-access'
            assert 'mcp_servers' not in config
            assert config['features']['hooks'] is True

            full = keys(pathlib.Path.home().joinpath('.codex/full.config.toml'))
            lean = keys(pathlib.Path.home().joinpath('.codex/lean.config.toml'))
            evidence = keys(pathlib.Path.home().joinpath('.codex/evidence.config.toml'))
            browser = keys(pathlib.Path.home().joinpath('.codex/browser.config.toml'))
            assert_has('full', full, {'github', 'context7', 'polylogue', 'lynchpin', 'serena', 'codebase-memory-mcp'}, {'chrome-devtools'})
            assert_has('lean', lean, {'github', 'context7', 'polylogue'}, {'lynchpin', 'serena', 'codebase-memory-mcp', 'chrome-devtools'})
            assert_has('evidence', evidence, {'github', 'context7', 'polylogue', 'lynchpin'}, {'serena', 'codebase-memory-mcp', 'chrome-devtools'})
            assert_has('browser', browser, {'github', 'context7', 'polylogue', 'lynchpin', 'serena', 'codebase-memory-mcp', 'chrome-devtools', 'chrome-devtools-private', 'chrome-devtools-private-visible'})

            # Alternate-backend profiles must layer a provider override while
            # retaining the full MCP surface; model names remain ordinary config.
            deepseek_path = pathlib.Path.home().joinpath('.codex/deepseek.config.toml')
            deepseek = tomllib.loads(deepseek_path.read_text())
            assert deepseek['model_provider'] == 'deepseek'
            assert deepseek['model_providers']['deepseek']['env_key']
            assert keys(deepseek_path) == full
            local_path = pathlib.Path.home().joinpath('.codex/local.config.toml')
            local = tomllib.loads(local_path.read_text())
            assert local['model_provider'] == 'local'
            assert local['model_providers']['local']['base_url'].startswith('http://127.0.0.1:')
            assert keys(local_path) == full
            for path_name, expected_role in [
                ('full.config.toml', 'write'),
                ('evidence.config.toml', 'write'),
                ('browser.config.toml', 'write'),
                ('lean.config.toml', 'read'),
            ]:
                data = tomllib.loads(pathlib.Path.home().joinpath('.codex', path_name).read_text())
                assert data['mcp_servers']['polylogue']['args'] == ['--role', expected_role]
            PYCODE

            jq -e '
              .mcpServers as $m |
              ($m | has("github") and has("context7")) and
              ($m | has("polylogue") and has("lynchpin")) and
              ($m | has("serena") and has("codebase-memory-mcp")) and
              ($m | has("chrome-devtools") | not) and
              ($m.polylogue.args == ["--role", "write"])
            ' "$HOME/.gemini/settings.json" >/dev/null

            jq -e '
              [.hooks.SessionStart[].hooks[].command]
              | any(contains("SINNIX_CODEX_PROFILE") and contains("serena-hooks activate --client=codex"))
            ' "$HOME/.codex/hooks.json" >/dev/null
            jq -e '
              [.hooks.SessionStart[].hooks[].command] | index("bd-prime-if-present")
            ' "$HOME/.codex/hooks.json" >/dev/null
            jq -e '
              [.hooks.SessionStart[].hooks[].command] | index("sessionstart-sinex-recall")
            ' "$HOME/.codex/hooks.json" >/dev/null


            grep -Fq 'MCP_CONFIG="$HOME/.config/claude/mcp.json"' "$HOME/.local/bin/claude-full"
            grep -Fq 'export SINNIX_CLAUDE_PROFILE=lean' "$HOME/.local/bin/claude-lean"
            grep -Fq 'MCP_CONFIG="$HOME/.config/claude/mcp-lean.json"' "$HOME/.local/bin/claude-lean"
            grep -Fq 'MCP_CONFIG="$HOME/.config/claude/mcp-browser.json"' "$HOME/.local/bin/claude-browser"
            # DeepSeek/local variants use the full (default) MCP profile.
            grep -Fq 'MCP_CONFIG="$HOME/.config/claude/mcp.json"' "$HOME/.local/bin/claude-deepseek"
            grep -Fq 'MCP_CONFIG="$HOME/.config/claude/mcp.json"' "$HOME/.local/bin/claude-local"
            grep -Fq 'https://api.deepseek.com/anthropic' "$HOME/.local/bin/claude-deepseek"
            grep -Fq 'ANTHROPIC_BASE_URL="http://127.0.0.1:4000"' "$HOME/.local/bin/claude-local"
            grep -Fq 'codex_args=(--profile full)' "$HOME/.local/bin/codex"
            grep -Fq 'export SINNIX_CODEX_PROFILE=lean' "$HOME/.local/bin/codex-lean"
            grep -Fq 'codex_args=(--profile lean)' "$HOME/.local/bin/codex-lean"
            grep -Fq 'codex_args=(--profile full)' "$HOME/.local/bin/codex-full"
            grep -Fq 'codex_args=(--profile browser)' "$HOME/.local/bin/codex-browser"
            grep -Fq 'codex_args=(--profile deepseek)' "$HOME/.local/bin/codex-deepseek"
            grep -Fq 'codex_args=(--profile local)' "$HOME/.local/bin/codex-local"

            # All agent wrappers must bootstrap from npm packages without
            # launching through buildFHSEnv/bubblewrap.
            for wrapper in \
              "$HOME/.local/bin/claude-full" \
              "$HOME/.local/bin/codex" \
              "$HOME/.local/bin/gemini"; do
              if grep -Fq 'agent-fhs' "$wrapper"; then
                echo "$wrapper still launches through agent-fhs" >&2
                exit 1
              fi
              grep -Fq 'launch.sh' "$wrapper"
              grep -Fq 'run_agent_scoped "$STATE/launch.sh"' "$wrapper"
            done
            if grep -R 'MemoryHigh\|MemoryMax\|MemorySwapMax' "$HOME/.local/bin/claude-full" "$HOME/.local/bin/codex" "$HOME/.local/bin/gemini"; then
              echo "interactive agent wrappers must not impose shared memory caps" >&2
              exit 1
            fi
            grep -Fq 'npm install -g @anthropic-ai/claude-code' "$HOME/.local/bin/claude-full"
            grep -Fq 'npm install -g @openai/codex' "$HOME/.local/bin/codex"
            grep -Fq 'npm install -g @google/gemini-cli' "$HOME/.local/bin/gemini"

            "$HOME/.local/bin/mcp-polylogue" --help | grep -q 'Start the Polylogue MCP stdio bridge'
            grep -Fq 'sinex-mcp-server' "$HOME/.local/bin/mcp-sinex"
            for helper in \
              "$HOME/.local/bin/sinnix-agent-status" \
              "$HOME/.local/bin/sinnix-chrome-control" \
              "$HOME/.local/bin/sinnix-hypr-control" \
              "$HOME/.local/bin/sinnix-keyboard-control" \
              "$HOME/.local/bin/sinnix-kitty-control" \
              "$HOME/.local/bin/sinnix-screenshot-control"; do
              test -x "$helper"
              bash -n "$helper"
            done
            grep -Fq 'private-sync-state' "$HOME/.local/bin/sinnix-chrome-control"
            grep -Fq 'SINNIX_AGENT_CHROME_LIVE_PROFILE' "$HOME/.local/bin/sinnix-chrome-control"
            grep -Fq 'private-sync-state' "$HOME/.local/bin/mcp-chrome-devtools-private"
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
        '';
      };
    in
    {
      heavyChecks = {
        backup-borg-hook-runtime = backupBorgHookRuntime;
        cli-polylogue-runtime = cliPolylogueRuntime;
        cli-task-tracking-runtime = cliTaskTrackingRuntime;
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
