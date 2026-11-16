# Provably fails when: the recorder stops stripping inherited SINNIX_CAPTURE_*
# state before launching the shell (verified by deleting that loop from
# scripts/sinnix-captured-shell), writes its session outside the
# year/month/day layout (verified by flattening session_dir), stops
# propagating the recorder's exit code (the -failure variant), reorders or
# loses shell events (the -interactive variant), or makes the shell wait for
# the capture directory again (the -stalled-disk variant, verified by having
# the hooks append to events.jsonl themselves).
#
# Kitty/PTY terminal-capture recorder runtime checks (asciinema wrapper +
# session/event JSON shape, including a forced-nonzero-exit variant, a real
# interactive shell, a capture side that cannot write, and the fallback when
# no session writer is reading).
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};

      captureTools = [
        pkgs.python3
        pkgs.asciinema
        pkgs.coreutils
        pkgs.findutils
        pkgs.gnugrep
        pkgs.jq
        pkgs.util-linux
        pkgs.zsh
      ];

      # session.json and events.jsonl are finished by the session writer,
      # which outlives the launcher: wait for it instead of assuming order.
      awaitSession = ''
        session_finalized() {
          local file
          file="$(find "$TMPDIR/captures" -type f -name session.json | sed -n '1p')"
          test -n "$file" && jq -e '.finished_at_ms != null and .recorder_exit_code != null' "$file" >/dev/null 2>&1
        }
        await_session() {
          local deadline=$((SECONDS + 60))
          until session_finalized; do
            if ((SECONDS >= deadline)); then
              echo "session.json was not finalized" >&2
              find "$TMPDIR/captures" -type f -exec cat {} + >&2 || true
              exit 1
            fi
            sleep 0.1
          done
        }
      '';

      # A real interactive zsh with the hooks loaded. The commands are typed
      # once the first prompt is up; the recorder discards earlier input.
      interactiveSession = ''
        export HOME="$TMPDIR/home"
        mkdir -p "$HOME/.config/sinnix" "$TMPDIR/zdotdir" "$TMPDIR/bin" "$TMPDIR/start"
        printf '%s\n' "$TMPDIR/captures" > "$HOME/.config/sinnix/terminal-capture-root"
        cat > "$TMPDIR/zdotdir/.zshrc" <<EOF
        unsetopt zle
        source ${../../scripts/sinnix-terminal-capture-hooks.zsh}
        _test_ready() { : > "$TMPDIR/shell-ready" }
        add-zsh-hook precmd _test_ready
        EOF
        ${awaitSession}
        # run_session <typed input>: the launcher's exit status is returned.
        run_session() {
          (
            until test -e "$TMPDIR/shell-ready"; do sleep 0.05; done
            printf '%s' "$1"
          ) | (
            cd "$TMPDIR/start"
            timeout 120 script -qfec "stty rows 24 cols 80; exec env \
              HOME='$HOME' \
              HOSTNAME='terminal-capture-test' \
              KITTY_PID='4242' \
              SHELL='${pkgs.zsh}/bin/zsh' \
              ZDOTDIR='$TMPDIR/zdotdir' \
              TERM='xterm-kitty' \
              USER=\"\$CAPTURE_USER\" \
              ${pkgs.bash}/bin/bash ${../../scripts}/sinnix-captured-shell" "$TMPDIR/typescript"
          )
        }
        export CAPTURE_USER=tester
        export PATH="$TMPDIR/bin:${lib.makeBinPath captureTools}:$PATH"
        typed=$'true\nfalse\nexit 0\n'
        expected_events='
          [.[].type] == ["session_start", "command_start", "command_end", "command_start", "command_end", "command_start", "session_end"] and
          [.[] | select(.type == "command_start") | .command] == ["true", "false", "exit 0"] and
          [.[] | select(.type == "command_end") | .exit_code] == [0, 1] and
          ([.[].ts_ms] | . == sort) and
          .[0].terminal == "kitty" and
          .[-1].exit_code == 0 and
          .[-1].exit_reason == "shell_exit"
        '
        expected_session='
          .schema == "terminal-session-v1" and
          .user == $capture_user and
          .command_count == 3 and
          .event_count == 7 and
          .exit_code == 0 and
          .exit_reason == "shell_exit" and
          .recorder_exit_code == 0 and
          .cleanup_escalated == false and
          (.duration_ms | type) == "number" and
          .final_cwd == $start
        '
      '';

      mkInteractiveCheck =
        name: body:
        pkgs.runCommand name { nativeBuildInputs = captureTools; } ''
          ${interactiveSession}
          ${body}
          touch "$out"
        '';

      terminalCaptureRuntime =
        pkgs.runCommand "sinnix-terminal-capture-runtime-check"
          {
            nativeBuildInputs = [
              pkgs.python3
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
                pkgs.python3
                pkgs.asciinema
                pkgs.coreutils
                pkgs.findutils
                pkgs.gnugrep
                pkgs.jq
                pkgs.util-linux
                pkgs.zsh
              ]
            }:$PATH"
            mkdir -p "$HOME/.config/sinnix" "$TMPDIR/captures"
            printf '%s\n' "$TMPDIR/captures" > "$HOME/.config/sinnix/terminal-capture-root"

            # The shell the recorder launches must not inherit any
            # SINNIX_CAPTURE_* state from whoever started it: a nested
            # capture session that trusts inherited paths writes into its
            # parent's session. The recorder strips those variables before
            # exporting its own, so an inherited marker must be gone here.
            cat > "$TMPDIR/fake-shell.zsh" <<'EOF'
            #!${pkgs.zsh}/bin/zsh
            set -eu
            source ${../../scripts/sinnix-terminal-capture-hooks.zsh}
            [[ $(umask) == *000 ]]
            touch "$TMPDIR/user-created-file"
            print -r -- "terminal-capture-ready"
            print -r -- "inherited-capture-marker: ''${SINNIX_CAPTURE_POISON:-stripped}"
            true
            exit 0
            EOF
            chmod +x "$TMPDIR/fake-shell.zsh"

            transcript="$TMPDIR/terminal-capture-runtime.typescript"
            capture_user=$'tester\001\002\003\004\005\006\007\010\011\012\013\014\015\016\017\020\021\022\023\024\025\026\027\030\031\032\033\034\035\036\037'

            script -qfec "umask 000; stty rows 24 cols 80; exec env \
              EPOCHREALTIME='1773285652,647035000' \
              HOME='$HOME' \
              HOSTNAME='terminal-capture-test' \
              KITTY_PID='4242' \
              SHELL='$TMPDIR/fake-shell.zsh' \
              SINNIX_CAPTURE_CAST_FILE='$TMPDIR/poison.cast' \
              SINNIX_CAPTURE_EVENTS_FILE='$TMPDIR/poison.events.jsonl' \
              SINNIX_CAPTURE_ROOT='$TMPDIR/retired-captures' \
              SINNIX_CAPTURE_POISON='leaked' \
              SINNIX_CAPTURE_SESSION_ID='poison-session' \
              TERM='xterm-kitty' \
              USER='$capture_user' \
              ${pkgs.bash}/bin/bash ${../../scripts}/sinnix-captured-shell" "$transcript"

            if test -e "$TMPDIR/retired-captures"; then
              echo "Recorder used the inherited retired capture root" >&2
              exit 1
            fi
            grep -q "terminal-capture-ready" "$transcript"
            grep -q "inherited-capture-marker: stripped" "$transcript"

            ${awaitSession}
            await_session
            session_json="$(find "$TMPDIR/captures" -type f -name session.json | sed -n '1p')"
            events_json="$(find "$TMPDIR/captures" -type f -name events.jsonl | sed -n '1p')"
            cast_file="$(find "$TMPDIR/captures" -type f -name session.cast | sed -n '1p')"

            test -n "$session_json"
            test -n "$events_json"
            test -n "$cast_file"
            jq -s -e '
              .[0].version == 3 and
              any(.[1:][]; .[1] == "o" and (.[2] | contains("terminal-capture-ready")))
            ' "$cast_file" >/dev/null
            test "$(stat -c %a "$TMPDIR/user-created-file")" = 666
            test "$(stat -c %a "$TMPDIR/captures")" = 700
            test -z "$(find "$TMPDIR/captures" -type f ! -perm 0600 -print -quit)"

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
              .user == $capture_user and
              .terminal == "kitty" and
              .exit_reason == "shell_exit" and
              .cleanup_escalated == false and
              .recorder_exit_code == 0 and
              (.session_id | test(",") | not) and
              .session_id != "poison-session" and
              .cast_path != $poison_cast and
              .events_path != $poison_events
            ' \
              --arg capture_user "$capture_user" \
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
              pkgs.python3
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
            bash -c "$command_path"
            exit 42
            EOF
            chmod +x "$TMPDIR/bin/asciinema"

            cat > "$TMPDIR/fake-shell.zsh" <<'EOF'
            #!${pkgs.zsh}/bin/zsh
            set -eu
            source ${../../scripts/sinnix-terminal-capture-hooks.zsh}
            print -r -- "terminal-capture-ready"
            true
            exit 0
            EOF
            chmod +x "$TMPDIR/fake-shell.zsh"

            export PATH="$TMPDIR/bin:${
              lib.makeBinPath [
                pkgs.python3
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
            script -qfec "stty rows 24 cols 80; exec env \
              EPOCHREALTIME='1773285652,647035000' \
              HOME='$HOME' \
              HOSTNAME='terminal-capture-test' \
              KITTY_PID='4242' \
              SHELL='$TMPDIR/fake-shell.zsh' \
              SINNIX_CAPTURE_ROOT='$TMPDIR/captures' \
              TERM='xterm-kitty' \
              USER='tester' \
              ${pkgs.bash}/bin/bash ${../../scripts}/sinnix-captured-shell" "$transcript"
            status=$?
            set -e

            test "$status" -eq 42
            grep -q "terminal-capture-ready" "$transcript"

            ${awaitSession}
            await_session
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
    in
    {
      checks = {
        terminal-capture-buffered-writer =
          pkgs.runCommand "terminal-capture-buffered-writer"
            {
              nativeBuildInputs = [
                pkgs.python3
                pkgs.asciinema
                pkgs.util-linux
              ];
            }
            ''
              export HOME="$TMPDIR/home"
              mkdir -p "$HOME"
              python3 ${../../pkgs/sinnix-terminal-capture/tests/stalled-writer.py} \
                ${../../scripts/sinnix-terminal-capture-writer}
              touch "$out"
            '';
        terminal-capture-runtime = terminalCaptureRuntime;
        # Events arrive in the order the shell produced them, and all of
        # them, the session end included, are on disk after the terminal
        # has closed.
        terminal-capture-interactive = mkInteractiveCheck "sinnix-terminal-capture-interactive-check" ''
          run_session "$typed"
          await_session
          session_dir="$(dirname "$(find "$TMPDIR/captures" -type f -name session.json)")"
          jq -s -e "$expected_events" "$session_dir/events.jsonl" >/dev/null
          jq -e --arg capture_user "$CAPTURE_USER" --arg start "$TMPDIR/start" "$expected_session" \
            "$session_dir/session.json" >/dev/null
          test "$(find "$TMPDIR/captures" -type f | sort | sed 's|.*/||' | tr '\n' ' ')" = "events.jsonl session.cast session.json "
          test -z "$(find "$TMPDIR/captures" -type f ! -perm 0600 -print -quit)"
        '';
        # The capture side cannot write: its first repository query turns
        # events.jsonl into a FIFO nobody reads, so the session writer
        # blocks opening it. The shell must still start, run its commands
        # and exit, and everything must arrive once the FIFO is read.
        terminal-capture-stalled-disk = mkInteractiveCheck "sinnix-terminal-capture-stalled-disk-check" ''
          mkdir "$TMPDIR/start/.git"
          cat > "$TMPDIR/bin/git" <<EOF
          #!${pkgs.bash}/bin/bash
          session_json="\$(find "$TMPDIR/captures" -type f -name session.json | sed -n '1p')"
          events="\$(dirname "\$session_json")/events.jsonl"
          test -p "\$events" || mkfifo "\$events"
          exit 1
          EOF
          chmod +x "$TMPDIR/bin/git"

          started=$SECONDS
          run_session "$typed"
          elapsed=$((SECONDS - started))
          echo "shell started, ran its commands and exited in about $elapsed s while the capture side was blocked"
          test "$elapsed" -le 20

          session_json="$(find "$TMPDIR/captures" -type f -name session.json)"
          events_fifo="$(dirname "$session_json")/events.jsonl"
          blocked='.exit_reason == "recorder_starting" and .event_count == 0 and .finished_at_ms == null'
          test -p "$events_fifo"
          jq -e "$blocked" "$session_json" >/dev/null
          sleep 2
          jq -e "$blocked" "$session_json" >/dev/null

          timeout 60 cat "$events_fifo" > "$TMPDIR/released-events.jsonl"
          await_session
          jq -s -e "$expected_events" "$TMPDIR/released-events.jsonl" >/dev/null
          jq -e --arg capture_user "$CAPTURE_USER" --arg start "$TMPDIR/start" "$expected_session" \
            "$session_json" >/dev/null
          echo "all 7 events and the final session.json arrived after the block was released"
        '';
        # No session writer is reading (it cannot start): the shell and the
        # launcher write the files themselves, as before the pipe existed.
        terminal-capture-fallback = mkInteractiveCheck "sinnix-terminal-capture-fallback-check" ''
          printf '#!${pkgs.bash}/bin/bash\nexit 1\n' > "$TMPDIR/bin/setsid"
          chmod +x "$TMPDIR/bin/setsid"
          export CAPTURE_USER=$'tester\001\037"\\'
          run_session "$typed"
          session_dir="$(dirname "$(find "$TMPDIR/captures" -type f -name session.json)")"
          jq -s -e "$expected_events" "$session_dir/events.jsonl" >/dev/null
          jq -e --arg capture_user "$CAPTURE_USER" --arg start "$TMPDIR/start" "$expected_session" \
            "$session_dir/session.json" >/dev/null
          test "$(stat -c %a "$TMPDIR/captures")" = 700
          test -z "$(find "$TMPDIR/captures" -type f ! -perm 0600 -print -quit)"
        '';
        terminal-capture-runtime-failure = terminalCaptureRuntimeFailure;
      };
    };
}
