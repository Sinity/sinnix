# Clipboard capture lane: static service-shape checks plus a runtime
# fixture that exercises the real generated watch script (fake wl-paste /
# hyprctl, real sinnix-capture writer) for text, binary/dedup, and
# consecutive-duplicate behavior.
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
        name = "capture-clipboard";
        service = "capture-clipboard";
        assertions = _: [ ];
      };
      evaluated = evalTestSpec system spec;
      hm = evaluated.config.home-manager.users.${evaluated.config.sinnix.user.name};
      unit = hm.systemd.user.services.sinnix-capture-clipboard;
      surface = evaluated.config.sinnix.runtime.surfaces.capture-clipboard;
      execStart = unit.Service.ExecStart;
      unitJson = builtins.toJSON {
        Unit = unit.Unit;
        Service = unit.Service;
      };
      surfaceJson = builtins.toJSON surface;

      clipboardWatchRuntime =
        pkgs.runCommand "sinnix-capture-clipboard-runtime-check"
          {
            nativeBuildInputs = [
              pkgs.coreutils
              pkgs.findutils
              pkgs.gnugrep
              pkgs.jq
              pkgs.python3
            ];
          }
          ''
            watch_bin="$(printf '%s\n' ${lib.escapeShellArg execStart} | tr ' ' '\n' | grep 'sinnix-capture-clipboard-watch$')"
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

            cat > "$TMPDIR/bin/wl-paste" <<'EOF_WLPASTE'
            #!/usr/bin/env bash
            set -euo pipefail
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
            # fails execve, `|| true` in the watch script swallows it, and the
            # run degrades to a silent empty-types no-op.
            patchShebangs "$TMPDIR/bin"

            export PATH="$TMPDIR/bin:${captureCli}/bin:${pkgs.jq}/bin:${pkgs.coreutils}/bin:$PATH"
            export SINNIX_CAPTURE_ROOT="$TMPDIR/captures"
            export SINNIX_CAPTURE_CLIPBOARD_STATE_DIR="$TMPDIR/state"
            export FIXTURE_DIR="$TMPDIR/fixture"

            # ── Text capture ────────────────────────────────────────────
            printf 'text/plain;charset=utf-8\n' > "$FIXTURE_DIR/types"
            printf 'hello from the fixture' > "$FIXTURE_DIR/content"
            printf '{"class": "kitty", "title": "test terminal"}' > "$FIXTURE_DIR/activewindow.json"
            "$watch"

            # Firing again with the *same* content must be a silent no-op
            # (consecutive-duplicate de-dup).
            "$watch"

            index_file="$TMPDIR/captures/clipboard/clipboard-index.jsonl"
            test "$(wc -l < "$index_file")" -eq 1

            envelope_file="$(find "$TMPDIR/captures/clipboard" -maxdepth 1 -name 'clipboard-*.jsonl' | head -n1)"
            jq -e '
              .schema == "sinnix-capture-v1" and
              .lane == "clipboard" and
              .payload.category == "text" and
              .payload.mime == "text/plain;charset=utf-8" and
              .payload.text == "hello from the fixture" and
              .payload.source_window.class == "kitty" and
              .payload.source_window.title == "test terminal" and
              .raw_ref == null
            ' "$envelope_file" >/dev/null

            # ── Binary capture (new content -> not deduped away) ───────
            printf 'image/png\n' > "$FIXTURE_DIR/types"
            printf 'not-a-real-png-but-binary-enough' > "$FIXTURE_DIR/content"
            "$watch"

            test "$(wc -l < "$index_file")" -eq 2

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
      checks.capture-clipboard-static =
        pkgs.runCommand "capture-clipboard-static-check"
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
              # array depending on the systemd option merge/apply behavior
              # -- normalize before substring checks.
              (.Service.ExecStart | if type == "array" then join(" ") else . end) as $execStart |
              ($execStart | contains("wl-paste --watch")) and
              ($execStart | contains("sinnix-capture-clipboard-watch")) and
              (.Service.Environment | any(startswith("SINNIX_CAPTURE_ROOT="))) and
              (.Service.Environment | any(startswith("SINNIX_CAPTURE_CLIPBOARD_STATE_DIR="))) and
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

      checks = {
        capture-clipboard-runtime = clipboardWatchRuntime;
      };
    };
}
