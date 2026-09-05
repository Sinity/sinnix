# Provably fails when: the lane's directory moves out from under the capture
# root the unit is given, the unit loses write access to the lane the runtime
# inventory advertises for it, or the generated watch script stops reading the
# PRIMARY buffer, stops writing an envelope, stops spilling binary payloads to
# a blob, or starts de-duplicating consecutive identical selections (which is
# the clipboard lane's policy, not this one's).
#
# PRIMARY-selection capture lane: static service-shape checks (unit
# ExecStart/Environment/ReadWritePaths, runtime surface metadata) plus a
# runtime fixture that exercises the real generated watch script (fake
# wl-paste / hyprctl, real sinnix-capture writer).
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    {
      system,
      sinnixScriptRegistry,
      ...
    }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      captureCli = sinnixScriptRegistry.packageSet.sinnix-capture;
      testLib = import ../test-lib.nix { inherit inputs lib; };
      inherit (testLib) evalTestSpec mkServiceTest;

      spec = mkServiceTest {
        name = "capture-primary";
        service = "capture-primary";
        assertions = _: [ ];
      };
      evaluated = evalTestSpec system spec;
      hm = evaluated.config.home-manager.users.${evaluated.config.sinnix.user.name};
      unit = hm.systemd.user.services.sinnix-capture-primary;
      execStart = unit.Service.ExecStart;
      unitJson = builtins.toJSON {
        Unit = unit.Unit;
        Service = unit.Service;
      };
      capturesJson = builtins.toJSON evaluated.config.sinnix.runtime.inventory.captures;

      primaryWatchRuntime =
        pkgs.runCommand "sinnix-capture-primary-runtime-check"
          {
            nativeBuildInputs = [
              pkgs.coreutils
              pkgs.findutils
              pkgs.gnugrep
              pkgs.jq
            ];
          }
          ''
            watch_bin="$(printf '%s\n' ${lib.escapeShellArg execStart} | tr ' ' '\n' | grep 'sinnix-capture-primary-watch$')"
            test -x "$watch_bin"

            mkdir -p "$TMPDIR/bin" "$TMPDIR/captures" "$TMPDIR/state" "$TMPDIR/fixture"

            # writeShellApplication bakes `export PATH=<real store paths>` as
            # the script's first statement, which shadows this fixture's fake
            # wl-paste/hyprctl with the real binaries -- in the build sandbox
            # the real wl-paste degrades to a silent no-op and the check can
            # never pass. Run a copy with exactly that one line stripped: the
            # capture logic under test is byte-identical, and every tool the
            # baked PATH provided is supplied by the fixture PATH below.
            watch="$TMPDIR/watch"
            cp "$watch_bin" "$watch"
            test "$(grep -c '^export PATH=' "$watch")" -eq 1
            sed -i '/^export PATH=/d' "$watch"
            chmod +x "$watch"

            # Serves the PRIMARY buffer only when asked for it: a lane that
            # dropped --primary would read the clipboard instead, which is a
            # different buffer with different content and a lane of its own.
            cat > "$TMPDIR/bin/wl-paste" <<'EOF_WLPASTE'
            #!/usr/bin/env bash
            set -euo pipefail
            if [ "''${1:-}" != "--primary" ]; then
              printf 'clipboard-buffer-not-primary'
              exit 0
            fi
            shift
            if [ "''${1:-}" = "--list-types" ]; then
              cat "$FIXTURE_DIR/types"
              exit 0
            fi
            cat "$FIXTURE_DIR/content"
            EOF_WLPASTE
            chmod +x "$TMPDIR/bin/wl-paste"

            cat > "$TMPDIR/bin/hyprctl" <<'EOF_HYPRCTL'
            #!/usr/bin/env bash
            set -euo pipefail
            if [ "''${1:-}" = "activewindow" ]; then
              cat "$FIXTURE_DIR/activewindow.json"
              exit 0
            fi
            echo '{}'
            EOF_HYPRCTL
            chmod +x "$TMPDIR/bin/hyprctl"
            # No /usr/bin/env in the build sandbox: an unpatched fake shebang
            # fails execve, the watch script treats the failure as "nothing
            # offered", and the run degrades to a silent no-op.
            patchShebangs "$TMPDIR/bin"

            export PATH="$TMPDIR/bin:${captureCli}/bin:${pkgs.jq}/bin:${pkgs.coreutils}/bin:$PATH"
            export SINNIX_CAPTURE_ROOT="$TMPDIR/captures"
            export SINNIX_CAPTURE_PRIMARY_STATE_DIR="$TMPDIR/state"
            # Collapse the settle window so one fixture invocation writes
            # synchronously; the debounce arbitration itself is covered by
            # pkgs/sinnix-capture/tests/test_selection.py.
            export SINNIX_CAPTURE_PRIMARY_DEBOUNCE_MS=0
            export FIXTURE_DIR="$TMPDIR/fixture"

            # ── Text capture ────────────────────────────────────────────
            printf 'text/plain;charset=utf-8\n' > "$FIXTURE_DIR/types"
            printf 'highlighted while reading' > "$FIXTURE_DIR/content"
            printf '{"class": "firefox", "title": "test page"}' > "$FIXTURE_DIR/activewindow.json"
            "$watch"

            index_file="$TMPDIR/captures/primary/primary-index.jsonl"
            test "$(wc -l < "$index_file")" -eq 1

            envelope_file="$(find "$TMPDIR/captures/primary" -maxdepth 1 -name 'primary-2*.jsonl' | head -n1)"
            jq -e '
              .schema == "sinnix-capture-v1" and
              .lane == "primary" and
              .payload.category == "text" and
              .payload.mime == "text/plain;charset=utf-8" and
              .payload.text == "highlighted while reading" and
              .payload.source_window.class == "firefox" and
              .payload.source_window.title == "test page" and
              .raw_ref == null
            ' "$envelope_file" >/dev/null

            # ── Re-reading the same text is signal, not noise ───────────
            # The clipboard lane drops a consecutive duplicate; this lane
            # must record it.
            "$watch"
            test "$(wc -l < "$index_file")" -eq 2

            # ── Binary capture ─────────────────────────────────────────
            printf 'image/png\n' > "$FIXTURE_DIR/types"
            printf 'not-a-real-png-but-binary-enough' > "$FIXTURE_DIR/content"
            "$watch"

            test "$(wc -l < "$index_file")" -eq 3

            sha256="$(sha256sum "$FIXTURE_DIR/content" | cut -d' ' -f1)"
            jq -e --arg sha256 "$sha256" '
              .payload.category == "binary" and
              .payload.mime == "image/png" and
              .payload.sha256 == $sha256 and
              (.payload | has("text") | not) and
              .raw_ref != null and
              (.raw_ref | endswith($sha256))
            ' <(tail -n1 "$envelope_file") >/dev/null

            blob_path="$(jq -r '.raw_ref' <(tail -n1 "$envelope_file"))"
            test -f "$blob_path"
            diff "$blob_path" "$FIXTURE_DIR/content"

            touch "$out"
          '';
    in
    {
      checks.capture-primary-runtime = primaryWatchRuntime;

      checks.capture-primary-static =
        pkgs.runCommand "capture-primary-static-check"
          {
            nativeBuildInputs = [ pkgs.jq ];
          }
          ''
            cat > unit.json <<'EOF_UNIT'
            ${unitJson}
            EOF_UNIT
            cat > captures.json <<'EOF_CAPTURES'
            ${capturesJson}
            EOF_CAPTURES
            jq -e '
              # ExecStart may render as a plain string or a single-element
              # array depending on the systemd option merge/apply behavior
              # -- normalize before substring checks.
              (.Service.ExecStart | if type == "array" then join(" ") else . end) as $execStart |
              ($execStart | contains("wl-paste --primary --watch")) and
              ($execStart | contains("sinnix-capture-primary-watch")) and
              .Unit.After == ["graphical-session.target"] and
              .Unit.PartOf == ["graphical-session.target"]
            ' unit.json >/dev/null
            # The lane the sentinel watches and the directory the unit is
            # actually allowed to write must be the same place: a lane
            # advertised at a path no unit writes is a silent capture gap.
            # Neither side is restated as a literal here.
            jq -e --slurpfile captures captures.json --arg lane "primary" '
              (.Service.Environment
                | map(select(startswith("SINNIX_CAPTURE_ROOT=")))
                | first
                | ltrimstr("SINNIX_CAPTURE_ROOT=")) as $root |
              ($captures[0] | map(select(.name == $lane)) | first) as $capture |
              $root != null and
              $capture != null and
              ($capture.path | startswith($root + "/")) and
              (.Service.ReadWritePaths | any($capture.path | startswith(.)))
            ' unit.json >/dev/null
            touch "$out"
          '';
    };
}
