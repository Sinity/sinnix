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
            grep -Fx $'PreToolUse\tclaude-code' claude-writers
            grep -Fx $'PostToolUse\tclaude-code' claude-writers
            grep -Fx $'SessionStart\tclaude-code' claude-writers
            grep -Fx $'Stop\tclaude-code' claude-writers
            grep -Fx $'UserPromptSubmit\tclaude-code' claude-writers
            grep -Fx $'PreToolUse\tcodex' codex-writers
            grep -Fx $'PostToolUse\tcodex' codex-writers
            grep -Fx $'SessionStart\tcodex' codex-writers
            grep -Fx $'Stop\tcodex' codex-writers
            grep -Fx $'UserPromptSubmit\tcodex' codex-writers

            # This custom-root assertion is separate from command comparison.
            # A default-root wrapper or an unconfigured packaged writer must
            # fail even when both payloads agree.
            grep -F -- "$sentinelDataDir/hooks" "$polylogueHookBin/bin/sinnix-polylogue-hook"
            if grep -F -e '/realm/state/polylogue' -e '/home/sinity/.local/share/polylogue' "$polylogueHookBin/bin/sinnix-polylogue-hook"; then
              echo 'generated Polylogue hook wrapper contains a default or legacy root' >&2
              exit 1
            fi

            # Fresh-writer smoke: isolate every ambient resolution input and
            # trace file access. The explicit primary spool must receive the
            # event while archive/XDG fallback paths and the real legacy roots
            # remain untouched.
            smoke_root="$TMPDIR/polylogue-hook-smoke"
            primary="$smoke_root/primary-hooks"
            archive="$smoke_root/archive"
            legacy="$smoke_root/legacy-home"
            mkdir -p "$smoke_root/home" "$smoke_root/xdg" "$primary" "$archive" "$legacy"
            trace="$smoke_root/access.trace"
            printf '%s' '{"session_id":"parity-smoke","source":"codex","turn_id":"turn-1"}' \
              | HOME="$smoke_root/home" \
                XDG_DATA_HOME="$smoke_root/xdg" \
                POLYLOGUE_ARCHIVE_ROOT="$archive" \
                strace -f -e trace=file -o "$trace" \
                "$polylogueHook/bin/polylogue-hook" UserPromptSubmit \
                  --provider codex --sidecar-dir "$primary"
            test -n "$(find "$primary" -type f -print -quit)"
            grep -R -F 'parity-smoke' "$primary" >/dev/null
            test -z "$(find "$archive" "$legacy" "$smoke_root/home" "$smoke_root/xdg" -type f -print -quit)"
            if grep -F -e '/realm/state/polylogue' -e '/home/sinity/.local/share/polylogue' -e '/realm/db/polylogue' "$trace"; then
              echo 'isolated Polylogue hook smoke accessed a live or legacy root' >&2
              exit 1
            fi

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
