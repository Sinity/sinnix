# Claude/Codex hook parity: the rows docs/agent-hook-parity.md records as
# "Enforced" on both clients are checked against the two real hook sources
# (dots/claude/managed-settings.json and the generated Codex hooks), not
# restated as a list of expected names here.
#
# Provably fails when: a `polylogue-hook <Event>` lane present in Claude's
# settings is dropped from the generated Codex hooks (verified by removing
# the PostToolUse entry from modules/features/dev/agents/hooks.nix), or when
# either client loses the pre-compaction handoff or the orphan sweep.
{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      codexHooks = import ../../modules/features/dev/agents/hooks.nix {
        inherit pkgs;
        dotsRoot = inputs.self + "/dots";
      };
      claudeHooks = ../../dots/claude/managed-settings.json;
    in
    {
      checks.agent-hook-parity =
        pkgs.runCommand "agent-hook-parity-check"
          {
            inherit codexHooks claudeHooks;
            nativeBuildInputs = [ pkgs.jq ];
          }
          ''
            # The evidence lanes: every lifecycle event on which a client
            # ships a session to Polylogue. Codex must cover at least what
            # Claude does, or half the estate's agent history stops being
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

            # The two cross-client commands the parity matrix records as
            # enforced on both sides. Each lives in its own source file, so
            # this is an agreement between two files rather than an echo of
            # one.
            for command in sinnix-context-handoff "sinnix-mcp-sweep --orphans-only"; do
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
