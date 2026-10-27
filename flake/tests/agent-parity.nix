# Claude/Codex hook parity: the hooks both clients must run are checked
# against the two real hook sources (dots/claude/managed-settings.json and the
# generated Codex hooks), not restated as a list of expected names here.
# Both clients invoke the live rewrite's hook (`polylogue hook EVENT`,
# with `--harness codex` for Codex), which writes the hook spool of the live
# archive and brings the session-start brief.
#
# Provably fails when: a `polylogue hook <Event>` lane present in
# Claude's settings is dropped from the generated Codex hooks, when a writer
# bakes a sidecar path, when a hook invocation stops appending a spool line
# naming its harness, event and session, or when either client loses the
# pre-compaction handoff or shared hook coverage.
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
      repoRoot = inputs.self;
      codexHooks = import ../../modules/features/dev/agents/hooks.nix {
        inherit pkgs;
        dotsRoot = inputs.self + "/dots";
      };
      claudeHooks = ../../dots/claude/managed-settings.json;
      polylogueHook = inputs.polylogue-rewrite.packages.${system}.polylogue;
      testLib = import ../test-lib.nix { inherit inputs lib; };
      inherit (testLib)
        evalTestSpec
        mkServiceTest
        ;
      polylogueSpec = mkServiceTest {
        name = "polylogue-agent-hook-parity";
        service = "polylogue";
        extraModules = [
          (_: {
            sinnix.services.polylogue.liveRoot = sentinelDataDir;
          })
        ];
        assertions = _config: [ ];
      };
      polylogueEvaluated = evalTestSpec system polylogueSpec;
      polylogueCli = polylogueEvaluated.config.system.build.polylogueCli;
    in
    {
      checks.agent-hook-parity =
        pkgs.runCommand "agent-hook-parity-check"
          {
            inherit
              claudeHooks
              codexHooks
              polylogueCli
              polylogueHook
              repoRoot
              sentinelDataDir
              ;
            nativeBuildInputs = [
              pkgs.coreutils
              pkgs.gnugrep
              pkgs.jq
              pkgs.ripgrep
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

            test -x "$polylogueHook/bin/polylogue" || {
              echo "polylogue is not an executable in $polylogueHook" >&2
              exit 1
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
                    | any(.value[]?.hooks[]?.command; startswith("polylogue hook " + $event))
                  ))
                | map(.key)
                | sort[]
              ' "$1"
            }
            lanes "$claudeHooks" > claude-lanes
            lanes "$codexHooks" > codex-lanes
            test -s claude-lanes || {
              echo "Claude settings declare no polylogue hook lane at all" >&2
              exit 1
            }
            missing="$(comm -23 claude-lanes codex-lanes)"
            if [ -n "$missing" ]; then
              echo "Codex hooks are missing Polylogue capture lanes Claude has: $missing" >&2
              exit 1
            fi

            # Every Polylogue hook declaration names its event and, for a
            # harness other than Claude Code, `--harness NAME`, and nothing
            # else: the anchored capture rejects any trailing flag.
            writer_rows() {
              jq -r '
                .hooks
                | to_entries[]
                | .key as $event
                | .value[]?.hooks[]?.command
                | select(type == "string" and startswith("polylogue hook "))
                | capture("^polylogue hook (?<event>[^ ]+)( --harness (?<harness>[^ ]+))?$")
                | select(.event == $event)
                | [$event, (.harness // "claude-code")]
                | @tsv
              ' "$1"
            }
            writer_rows "$claudeHooks" | sort > claude-writers
            writer_rows "$codexHooks" | sort > codex-writers
            test -s claude-writers || {
              echo "Claude settings declare no polylogue hook row" >&2
              exit 1
            }
            test -s codex-writers || {
              echo "generated Codex hooks declare no polylogue hook row" >&2
              exit 1
            }
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

            # The hook command resolves to the same wrapper the daemon runs.
            require_text "$sentinelDataDir/data" "$polylogueCli/bin/polylogue" live-data-home
            require_text "$sentinelDataDir/state" "$polylogueCli/bin/polylogue" live-state-home

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

            require_text 'polylogue hook Stop' "$claudeHooks" claude-command-name
            require_text 'polylogue hook Stop --harness codex' "$codexHooks" codex-command-name

            # Hook smoke: run the rewrite's hook for both harnesses with no
            # daemon. It fails open (no context) and appends one spool line
            # per event under XDG_STATE_HOME, naming the harness's origin,
            # the event and the session.
            smoke_root="$TMPDIR/polylogue-hook-smoke"
            mkdir -p "$smoke_root/home" "$smoke_root/xdg-data" "$smoke_root/xdg-state"
            for call in "UserPromptSubmit codex parity-codex" "Stop claude-code parity-claude"; do
              set -- $call
              printf '{"session_id":"%s","cwd":"/nonexistent","prompt":"hello"}' "$3" \
                | env HOME="$smoke_root/home" \
                  XDG_DATA_HOME="$smoke_root/xdg-data" \
                  XDG_STATE_HOME="$smoke_root/xdg-state" \
                  "$polylogueHook/bin/polylogue" hook "$1" --harness "$2" > "$smoke_root/$1.out"
              test ! -s "$smoke_root/$1.out" || {
                echo "the $1 hook answered without a daemon" >&2
                cat "$smoke_root/$1.out" >&2
                exit 1
              }
            done
            lines="$(find "$smoke_root/xdg-state/polylogue/hooks" -type f -name '*.ndjson' 2>/dev/null)"
            require_line() {
              if [ -z "$lines" ] || ! jq -se --arg p "$1" --arg e "$2" --arg s "$3" \
                'any(.[]; .provider == $p and .event == $e and .session_id == $s)' \
                $lines >/dev/null; then
                echo "no hook spool line for $1/$2/$3" >&2
                find "$smoke_root" -type f -print -exec cat {} \; >&2
                exit 1
              fi
            }
            require_line codex UserPromptSubmit parity-codex
            require_line claude-code Stop parity-claude
            test -z "$(find "$smoke_root/home" "$smoke_root/xdg-data" -mindepth 1 -print -quit)" \
              || { echo 'the hook wrote outside its spool' >&2; exit 1; }

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
