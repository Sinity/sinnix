# Claude/Codex hook parity: the rows docs/agent-hook-parity.md records as
# "Enforced" on both clients are checked against the two real hook sources
# (dots/claude/managed-settings.json and the generated Codex hooks), not
# restated as a list of expected names here. Both clients invoke the installed
# upstream `polylogue-hook`; its archive root comes from generated
# `polylogue.toml`.
#
# Provably fails when: a `polylogue-hook <Event>` lane present in Claude's
# settings is dropped from the generated Codex hooks, when a writer bakes a
# sidecar path, when generated archive.root stops following dataDir, or when
# either client loses the pre-compaction handoff or shared hook coverage.
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      sentinelDataDir = "/tmp/sinnix-polylogue-parity-sentinel";
      enrichDumpSource = ../../scripts/sinnix-enrich-dump;
      repoRoot = inputs.self;
      codexHooks = import ../../modules/features/dev/agents/hooks.nix {
        inherit pkgs;
        dotsRoot = inputs.self + "/dots";
      };
      claudeHooks = ../../dots/claude/managed-settings.json;
      polylogueHook = import ../polylogue-package.nix {
        inherit inputs pkgs;
        package = inputs.polylogue.packages.${system}.default;
      };
      testLib = import ../test-lib.nix { inherit inputs lib; };
      inherit (testLib)
        evalTestSpec
        hmFor
        mkServiceTest
        ;
      polylogueSpec = mkServiceTest {
        name = "polylogue-agent-hook-parity";
        service = "polylogue";
        extraModules = [
          (_: {
            sinnix.services.polylogue.dataDir = sentinelDataDir;
          })
        ];
        assertions = _config: [ ];
      };
      polylogueEvaluated = evalTestSpec system polylogueSpec;
      polylogueConfigSource =
        (hmFor polylogueEvaluated.config).xdg.configFile."polylogue/polylogue.toml".source;
    in
    {
      checks.agent-hook-parity =
        pkgs.runCommand "agent-hook-parity-check"
          {
            inherit
              claudeHooks
              codexHooks
              enrichDumpSource
              polylogueConfigSource
              polylogueHook
              repoRoot
              sentinelDataDir
              ;
            nativeBuildInputs = [
              pkgs.coreutils
              pkgs.gnugrep
              pkgs.jq
              pkgs.ripgrep
              pkgs.strace
            ];
          }
          ''
            require_text() {
              needle="$1"
              file="$2"
              label="$3"
              if ! grep -Fq -- "$needle" "$file"; then
                echo "missing $label: $needle in $file" >&2
                exit 1
              fi
            }

            reject_text() {
              needle="$1"
              file="$2"
              label="$3"
              if grep -Fq -- "$needle" "$file"; then
                echo "forbidden $label: $needle in $file" >&2
                grep -Fn -- "$needle" "$file" >&2
                exit 1
              fi
            }

            require_row() {
              row="$1"
              file="$2"
              label="$3"
              if ! grep -Fxq -- "$row" "$file"; then
                echo "missing $label row: $row in $file" >&2
                sed -n '1,120p' "$file" >&2
                exit 1
              fi
            }

            test -x "$polylogueHook/bin/polylogue-hook"

            # The evidence lanes: every lifecycle event on which a client
            # ships a session to Polylogue. Codex must cover at least what
            # Claude does, or half the machine's agent history stops being
            # captured while the other half looks healthy.
            lanes() {
              jq -r '
                .hooks
                | to_entries
                | map(select(
                    .key as $event
                    | any(.value[]?.hooks[]?.command; startswith("polylogue-hook " + $event))
                  ))
                | map(.key)
                | sort[]
              ' "$1"
            }
            lanes "$claudeHooks" > claude-lanes
            lanes "$codexHooks" > codex-lanes
            test -s claude-lanes
            missing="$(comm -23 claude-lanes codex-lanes)"
            if [ -n "$missing" ]; then
              echo "Codex hooks are missing Polylogue capture lanes Claude has: $missing" >&2
              exit 1
            fi

            # Every actual Polylogue writer declaration must use the upstream
            # executable with event/provider arguments only. In particular,
            # the anchored provider capture rejects any trailing sidecar flag.
            writer_rows() {
              jq -r '
                .hooks
                | to_entries[]
                | .key as $event
                | .value[]?.hooks[]?.command
                | select(type == "string" and startswith("polylogue-hook "))
                | [$event, (capture(" --provider (?<provider>[^ ]+)$").provider)]
                | @tsv
              ' "$1"
            }
            writer_rows "$claudeHooks" | sort > claude-writers
            writer_rows "$codexHooks" | sort > codex-writers
            test -s claude-writers
            test -s codex-writers
            cut -f1 claude-writers > claude-writer-lanes
            cut -f1 codex-writers > codex-writer-lanes
            diff -u claude-writer-lanes codex-writer-lanes
            require_row $'PreToolUse\tclaude-code' claude-writers claude-pretool
            require_row $'PostToolUse\tclaude-code' claude-writers claude-posttool
            require_row $'SessionStart\tclaude-code' claude-writers claude-sessionstart
            require_row $'Stop\tclaude-code' claude-writers claude-stop
            require_row $'UserPromptSubmit\tclaude-code' claude-writers claude-prompt
            require_row $'PreToolUse\tcodex' codex-writers codex-pretool
            require_row $'PostToolUse\tcodex' codex-writers codex-posttool
            require_row $'SessionStart\tcodex' codex-writers codex-sessionstart
            require_row $'Stop\tcodex' codex-writers codex-stop
            require_row $'UserPromptSubmit\tcodex' codex-writers codex-prompt

            # Check the generated production config, not a test-only wrapper.
            # This is the authority consumed by a flag-less upstream hook.
            awk -v expected="root = \"$sentinelDataDir\"" '
              $0 == "[archive]" { in_archive = 1; next }
              /^\[/ { in_archive = 0 }
              in_archive && $0 == expected { found = 1 }
              END { exit(found ? 0 : 1) }
            ' "$polylogueConfigSource" || {
              echo "generated polylogue.toml does not derive archive.root from dataDir" >&2
              sed -n '1,40p' "$polylogueConfigSource" >&2
              exit 1
            }
            reject_text '/realm/state/polylogue' "$polylogueConfigSource" default-config-root
            reject_text '/home/sinity/.local/share/polylogue' "$polylogueConfigSource" legacy-config-root

            # No repository hook command may bake a sidecar path. Keep this
            # source census scoped to the actual hook declarations so this
            # assertion cannot pass because a test copied a command literal.
            sidecar_flag="--sidecar"-dir
            if rg -n --fixed-strings -- "$sidecar_flag" \
              "$repoRoot/dots/claude/managed-settings.json" \
              "$repoRoot/modules/features/dev/agents/hooks.nix"; then
              echo 'repository hook command bakes a Polylogue sidecar path' >&2
              exit 1
            fi
            test ! -e "$repoRoot/modules/features/dev/agents/polylogue-hook.nix"

            # The managed Claude file is an out-of-store dots symlink. It and
            # generated Codex config both retain the continuously installed
            # upstream command name, so landing cannot create an activation
            # interval where the named executable is absent.
            require_text 'polylogue-hook Stop --provider claude-code' "$claudeHooks" claude-command-name
            require_text 'polylogue-hook Stop --provider codex' "$codexHooks" codex-command-name

            # Standalone enrichment must fail before assembling or mutating
            # any output when its archive-root contract is not configured.
            if env -u POLYLOGUE_ARCHIVE_ROOT "${pkgs.bash}/bin/bash" "$enrichDumpSource" \
              >/dev/null 2>missing-enrich-root.stderr; then
              echo 'enrichment dump accepted a missing Polylogue archive root' >&2
              exit 1
            fi
            require_text POLYLOGUE_ARCHIVE_ROOT missing-enrich-root.stderr missing-enrich-root-diagnostic

            # Fresh-writer smoke: install the generated TOML at the same XDG
            # path Home Manager uses in production, leave POLYLOGUE_ARCHIVE_ROOT
            # unset, and execute the actual upstream hook for both providers.
            # HOME, XDG data/state, and the absent archive-root environment are
            # decoys. Only the configured archive root may receive sidecars.
            smoke_root="$TMPDIR/polylogue-hook-smoke"
            primary="$sentinelDataDir/hooks"
            config_home="$smoke_root/config"
            archive_decoy="$smoke_root/archive-decoy"
            mkdir -p "$smoke_root/home" "$config_home/polylogue" "$smoke_root/xdg-data" "$smoke_root/xdg-state" "$archive_decoy"
            cp "$polylogueConfigSource" "$config_home/polylogue/polylogue.toml"
            trace="$smoke_root/access.trace"
            printf '%s' '{"session_id":"parity-codex","source":"codex","turn_id":"turn-1"}' \
              | env -u POLYLOGUE_ARCHIVE_ROOT -u POLYLOGUE_CONFIG \
                HOME="$smoke_root/home" \
                XDG_CONFIG_HOME="$config_home" \
                XDG_DATA_HOME="$smoke_root/xdg-data" \
                XDG_STATE_HOME="$smoke_root/xdg-state" \
                strace -f -e trace=file -o "$trace" \
                "$polylogueHook/bin/polylogue-hook" UserPromptSubmit \
                  --provider codex
            printf '%s' '{"session_id":"parity-claude","source":"claude","turn_id":"turn-2"}' \
              | env -u POLYLOGUE_ARCHIVE_ROOT -u POLYLOGUE_CONFIG \
                HOME="$smoke_root/home" \
                XDG_CONFIG_HOME="$config_home" \
                XDG_DATA_HOME="$smoke_root/xdg-data" \
                XDG_STATE_HOME="$smoke_root/xdg-state" \
                strace -f -e trace=file -o "$smoke_root/claude.trace" \
                "$polylogueHook/bin/polylogue-hook" Stop \
                  --provider claude-code
            test -n "$(find "$primary" -type f -name 'codex-*.jsonl' -print -quit)"
            test -n "$(find "$primary" -type f -name 'claude-code-*.jsonl' -print -quit)"
            require_text UserPromptSubmit "$trace" codex-event
            require_text --provider "$trace" provider-flag
            require_text codex "$trace" codex-provider
            require_text Stop "$smoke_root/claude.trace" claude-event
            require_text claude-code "$smoke_root/claude.trace" claude-provider
            test -z "$(find "$archive_decoy" "$smoke_root/home" "$smoke_root/xdg-data" "$smoke_root/xdg-state" -mindepth 1 -print -quit)" \
              || { echo 'isolated Polylogue hook smoke wrote a decoy root' >&2; exit 1; }
            reject_text '/realm/state/polylogue' "$trace" live-hook-root
            reject_text '/home/sinity/.local/share/polylogue' "$trace" legacy-hook-root
            reject_text '/realm/state/polylogue' "$smoke_root/claude.trace" claude-live-hook-root
            reject_text '/home/sinity/.local/share/polylogue' "$smoke_root/claude.trace" claude-legacy-hook-root

            # The shared context handoff is configured independently for both
            # clients, so this verifies the intended cross-client agreement.
            for command in sinnix-context-handoff; do
              for file in "$claudeHooks" "$codexHooks"; do
                jq -e --arg needle "$command" '
                  [.hooks[][].hooks[]?.command] | any(contains($needle))
                ' "$file" >/dev/null || {
                  echo "Hook command '$command' is absent from $file but required on both clients" >&2
                  exit 1
                }
              done
            done
            touch "$out"
          '';
    };
}
