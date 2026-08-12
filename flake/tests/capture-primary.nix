# PRIMARY-selection capture lane: static service-shape checks plus a
# runtime fixture that exercises the real generated watch script (fake
# wl-paste / hyprctl, real sinnix-capture writer) for text, binary,
# no-content-dedup (unlike clipboard), and debounce-burst-collapse
# behavior.
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      scriptRegistry = import ../scripts.nix { inherit inputs pkgs; };
      captureCli = scriptRegistry.packageSet.sinnix-capture;
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
      surface = evaluated.config.sinnix.runtime.surfaces.capture-primary;
      execStart = unit.Service.ExecStart;
      unitJson = builtins.toJSON {
        Unit = unit.Unit;
        Service = unit.Service;
      };
      surfaceJson = builtins.toJSON surface;

      primaryWatchRuntime =
        pkgs.runCommand "sinnix-capture-primary-runtime-check"
          {
            nativeBuildInputs = [
              pkgs.coreutils
              pkgs.findutils
              pkgs.gnugrep
              pkgs.gawk
              pkgs.jq
              pkgs.python3
            ];
          }
          ''
            watch_bin="$(printf '%s\n' ${lib.escapeShellArg execStart} | tr ' ' '\n' | grep 'sinnix-capture-primary-watch$')"
            test -x "$watch_bin"

            mkdir -p "$TMPDIR/bin" "$TMPDIR/captures" "$TMPDIR/state" "$TMPDIR/fixture"

            cat > "$TMPDIR/bin/wl-paste" <<'EOF_WLPASTE'
            #!/usr/bin/env bash
            set -euo pipefail
            # Drop the leading --primary flag the real wl-clipboard CLI
            # accepts; this fixture doesn't distinguish selections.
            args=()
            for a in "$@"; do
              [ "$a" = "--primary" ] && continue
              args+=("$a")
            done
            if [ "''${args[0]:-}" = "--list-types" ]; then
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

            export PATH="$TMPDIR/bin:${captureCli}/bin:${pkgs.jq}/bin:${pkgs.coreutils}/bin:${pkgs.gawk}/bin:$PATH"
            export SINNIX_CAPTURE_ROOT="$TMPDIR/captures"
            export SINNIX_CAPTURE_PRIMARY_STATE_DIR="$TMPDIR/state"
            # Keep the fixture fast: real debounce default is 400ms.
            export SINNIX_CAPTURE_PRIMARY_DEBOUNCE_MS=20
            export FIXTURE_DIR="$TMPDIR/fixture"

            index_file="$TMPDIR/captures/primary/primary-index.jsonl"

            # ── Text capture ────────────────────────────────────────────
            printf 'text/plain;charset=utf-8\n' > "$FIXTURE_DIR/types"
            printf 'first selection' > "$FIXTURE_DIR/content"
            printf '{"class": "kitty", "title": "test terminal"}' > "$FIXTURE_DIR/activewindow.json"
            "$watch_bin"

            test "$(wc -l < "$index_file")" -eq 1

            envelope_file="$(find "$TMPDIR/captures/primary" -maxdepth 1 -name 'primary-*.jsonl' | head -n1)"
            jq -e '
              .schema == "sinnix-capture-v1" and
              .lane == "primary" and
              .payload.category == "text" and
              .payload.mime == "text/plain;charset=utf-8" and
              .payload.text == "first selection" and
              .payload.source_window.class == "kitty" and
              .payload.source_window.title == "test terminal" and
              .raw_ref == null
            ' "$envelope_file" >/dev/null

            # ── No content-based dedup: firing again with the *same*
            # content must still capture (unlike the clipboard lane) ────
            "$watch_bin"
            test "$(wc -l < "$index_file")" -eq 2
            jq -e '.payload.text == "first selection"' <(tail -n1 "$envelope_file") >/dev/null

            # ── Debounce collapses a same-selection re-fire burst into
            # one capture of the settled content ───────────────────────
            #
            # Rather than racing two real backgrounded invocations against
            # wall-clock timing (flaky under nix-build's variable CPU
            # scheduling), deterministically exercise the two branches the
            # real burst-collapse relies on:
            #
            # 1. An invocation that gets superseded during its debounce
            #    sleep (something else re-stamps the trigger file before
            #    it wakes) must exit silently -- no envelope written.
            # 2. A subsequent invocation that nothing else touches during
            #    its own sleep must capture the settled content normally.
            SINNIX_CAPTURE_PRIMARY_DEBOUNCE_MS=200
            export SINNIX_CAPTURE_PRIMARY_DEBOUNCE_MS
            printf 'burst step one (should be superseded)' > "$FIXTURE_DIR/content"
            "$watch_bin" &
            superseded_pid=$!
            # Give the backgrounded invocation time to read its content
            # snapshot and stamp the trigger file (fast: a handful of
            # subprocess spawns), well before its 200ms debounce sleep
            # elapses -- then simulate "a newer selection-change fired
            # during the sleep" by re-stamping the trigger file ourselves.
            sleep 0.05
            printf 'test-superseding-marker' > "$TMPDIR/state/last-trigger"
            wait "$superseded_pid"

            test "$(wc -l < "$index_file")" -eq 2

            SINNIX_CAPTURE_PRIMARY_DEBOUNCE_MS=20
            export SINNIX_CAPTURE_PRIMARY_DEBOUNCE_MS
            printf 'burst step two settled' > "$FIXTURE_DIR/content"
            "$watch_bin"

            test "$(wc -l < "$index_file")" -eq 3
            jq -e '.payload.text == "burst step two settled"' <(tail -n1 "$envelope_file") >/dev/null

            # ── Binary capture ──────────────────────────────────────────
            printf 'image/png\n' > "$FIXTURE_DIR/types"
            printf 'not-a-real-png-but-binary-enough' > "$FIXTURE_DIR/content"
            "$watch_bin"

            test "$(wc -l < "$index_file")" -eq 4

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
      checks.capture-primary-static =
        pkgs.runCommand "capture-primary-static-check"
          {
            nativeBuildInputs = [ pkgs.jq ];
          }
          ''
            cat > unit.json <<'EOF_UNIT'
            ${unitJson}
            EOF_UNIT
            cat > surface.json <<'EOF_SURFACE'
            ${surfaceJson}
            EOF_SURFACE
            jq -e '
              # ExecStart may render as a plain string or a single-element
              # array depending on the systemd option type's merge/apply
              # behavior -- normalize before substring checks.
              (.Service.ExecStart | if type == "array" then join(" ") else . end) as $execStart |
              ($execStart | contains("wl-paste --primary --watch")) and
              ($execStart | contains("sinnix-capture-primary-watch")) and
              (.Service.Environment | any(startswith("SINNIX_CAPTURE_ROOT="))) and
              (.Service.Environment | any(startswith("SINNIX_CAPTURE_PRIMARY_STATE_DIR="))) and
              (.Service.Environment | any(startswith("SINNIX_CAPTURE_PRIMARY_DEBOUNCE_MS="))) and
              (.Service.ReadWritePaths | length) == 3 and
              .Unit.After == ["graphical-session.target"] and
              .Unit.PartOf == ["graphical-session.target"]
            ' unit.json >/dev/null
            jq -e '
              .resourceClass == "capture-runtime" and
              .kind == "capture" and
              .manager == "user" and
              (.captures[0].eventDriven) and
              .captures[0].staleAfterSeconds == 604800 and
              .observe.enable and
              .observe.restartable
            ' surface.json >/dev/null
            touch "$out"
          '';

      heavyChecks = {
        capture-primary-runtime = primaryWatchRuntime;
      };
    };
}
