# Claude/Codex hook parity: the rows docs/agent-hook-parity.md records as
# "Enforced" on both clients are checked against the two real hook sources
# (dots/claude/managed-settings.json and the generated Codex hooks), not
# restated as a list of expected names here. Both clients name the generated
# `sinnix-polylogue-hook` adapter; its configured root is checked below.
#
# Provably fails when: a `sinnix-polylogue-hook <Event>` lane present in Claude's
# settings is dropped from the generated Codex hooks (verified by removing
# the PostToolUse entry from modules/features/dev/agents/hooks.nix), when a
# writer loses the canonical primary sidecar destination, or when either
# client loses the pre-compaction handoff or the shared hook coverage.
{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      sentinelDataDir = "/tmp/sinnix-polylogue-parity-sentinel";
      enrichDumpSource = ../../scripts/sinnix-enrich-dump;
      codexHooks = import ../../modules/features/dev/agents/hooks.nix {
        inherit pkgs;
        dotsRoot = inputs.self + "/dots";
      };
      claudeHooks = ../../dots/claude/managed-settings.json;
      polylogueHook = inputs.polylogue.packages.${system}.default;
      polylogueHookBin = import ../../modules/features/dev/agents/polylogue-hook.nix {
        inherit (pkgs) lib;
        inherit pkgs;
        dataDir = sentinelDataDir;
        inherit polylogueHook;
      };
    in
    {
      checks.agent-hook-parity =
        pkgs.runCommand "agent-hook-parity-check"
          {
            inherit
              codexHooks
              claudeHooks
              enrichDumpSource
              polylogueHook
              polylogueHookBin
              sentinelDataDir
              ;
            nativeBuildInputs = [
              pkgs.coreutils
              pkgs.jq
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
                    | any(.value[]?.hooks[]?.command; startswith("sinnix-polylogue-hook " + $event))
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

            # Every actual Polylogue writer declaration must use the same
            # generated executable and provider-specific payload shape.
            writer_rows() {
              jq -r '
                .hooks
                | to_entries[]
                | .key as $event
                | .value[]?.hooks[]?.command
                | select(type == "string" and startswith("sinnix-polylogue-hook "))
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

            # This custom-root assertion is separate from command comparison.
            # A default-root wrapper or an unconfigured packaged writer must
            # fail even when both payloads agree.
            require_text "$sentinelDataDir/hooks" "$polylogueHookBin/bin/sinnix-polylogue-hook" configured-hook-root
            reject_text '/realm/state/polylogue' "$polylogueHookBin/bin/sinnix-polylogue-hook" default-hook-root
            reject_text '/home/sinity/.local/share/polylogue' "$polylogueHookBin/bin/sinnix-polylogue-hook" legacy-hook-root

            # Standalone enrichment must fail before assembling or mutating
            # any output when its archive-root contract is not configured.
            if env -u POLYLOGUE_ARCHIVE_ROOT "${pkgs.bash}/bin/bash" "$enrichDumpSource" \
              >/dev/null 2>missing-enrich-root.stderr; then
              echo 'enrichment dump accepted a missing Polylogue archive root' >&2
              exit 1
            fi
            require_text POLYLOGUE_ARCHIVE_ROOT missing-enrich-root.stderr missing-enrich-root-diagnostic

            # Fresh-writer smoke: isolate every ambient resolution input and
            # trace file access. The explicit primary spool must receive the
            # event while archive/XDG fallback paths and the real legacy roots
            # remain untouched.
            smoke_root="$TMPDIR/polylogue-hook-smoke"
            primary="$sentinelDataDir/hooks"
            archive="$smoke_root/archive"
            legacy="$smoke_root/legacy-home"
            mkdir -p "$smoke_root/home" "$smoke_root/xdg" "$archive" "$legacy"
            trace="$smoke_root/access.trace"
            printf '%s' '{"session_id":"parity-smoke","source":"codex","turn_id":"turn-1"}' \
              | HOME="$smoke_root/home" \
                XDG_DATA_HOME="$smoke_root/xdg" \
                POLYLOGUE_ARCHIVE_ROOT="$archive" \
                strace -f -e trace=file -o "$trace" \
                "$polylogueHookBin/bin/sinnix-polylogue-hook" UserPromptSubmit \
                  --provider codex
            test -n "$(find "$primary" -type f -print -quit)"
            record="$(find "$primary" -type f -name 'codex-parity-smoke.jsonl' -print -quit)"
            test -n "$record"
            jq -e '.event_type == "UserPromptSubmit" and .provider == "codex" and .payload.session_id == "parity-smoke"' "$record" >/dev/null \
              || { echo "wrapper did not preserve event/provider payload in $record" >&2; exit 1; }
            require_text 'UserPromptSubmit' "$trace" forwarded-event
            require_text '--provider' "$trace" forwarded-provider-flag
            require_text 'codex' "$trace" forwarded-provider
            require_text "$primary" "$trace" trailing-sidecar-destination
            test -z "$(find "$archive" "$legacy" "$smoke_root/home" "$smoke_root/xdg" -mindepth 1 -print -quit)" \
              || { echo 'isolated Polylogue hook smoke wrote an ambient root' >&2; exit 1; }
            reject_text '/realm/state/polylogue' "$trace" live-hook-root
            reject_text '/home/sinity/.local/share/polylogue' "$trace" default-hook-root
            reject_text '/realm/db/polylogue' "$trace" legacy-hook-root

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
