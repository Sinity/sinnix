# Continuous Wayland PRIMARY-selection capture lane
#
# `wl-paste --primary --watch` runs one long-lived user service that
# invokes a small event script on every PRIMARY-selection change (the
# X11-style "select-to-copy" buffer, distinct from the normal clipboard --
# populated by highlighting text, no explicit copy action, traditionally
# pasted with middle-click).
#
# Unlike the clipboard lane (capture-clipboard.nix), this lane does NOT
# de-duplicate consecutive identical content: PRIMARY changes on every new
# selection during ordinary reading, and that volume/repetition is itself
# the signal (what the operator was reading/re-reading), not noise to
# suppress.
#
# It DOES debounce, though, for a different reason than dedup: empirically
# (2026-08-12, live session, `wl-paste --primary --watch` against both a
# keyboard-driven Shift+Right selection-extend and address-bar text
# selection) a single logical selection action fires the watch command
# repeatedly in rapid succession -- e.g. 4 keypresses produced 7 fire
# events within ~40ms, several with byte-identical trailing content as the
# selection settled. The protocol/toolkit re-offers the selection on every
# internal extend step, not just once at gesture-end. A short debounce
# (see `debounceMs`) collapses each such burst into one capture of the
# settled selection, without touching the no-dedup policy above (a burst
# collapsing to one write is not content-based dedup -- two genuinely
# separate selections a few seconds apart still both get captured).
#
# The debounce is implemented per-invocation (no long-lived coordinator):
# each fire snapshots the current PRIMARY content immediately (cheap -- a
# single wl-paste read), stamps a monotonic trigger id, sleeps
# `debounceMs`, then checks whether a newer trigger id was stamped during
# the sleep. Only the invocation that is still the latest at wake-up does
# the expensive part (source-window attribution + sinnix-capture write).
#
# Content handling reuses the clipboard lane's MIME-preference and
# binary/text classification logic verbatim (PRIMARY is almost always
# plain text, but can carry the same rich formats an explicit copy would).
#
# Privacy note: same posture as every other capture lane -- this captures
# the operator's own selections to their own local lake; sensitivity is
# handled at consumption time, not capture time.
{
  mkServiceModule,
  lib,
  pkgs,
  config,
  helpers,
  ...
}@args:
let
  username = config.sinnix.user.name;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  captureCli = scriptPkgs.sinnix-capture;

  laneDir = "${config.sinnix.paths.capturesRoot}/primary";
  blobDir = "${laneDir}/blobs";
  stateDir = "${config.sinnix.paths.stateRoot}/sinnix-capture-primary";

  primaryWatch = pkgs.writeShellApplication {
    name = "sinnix-capture-primary-watch";
    runtimeInputs = [
      pkgs.wl-clipboard
      pkgs.hyprland
      pkgs.jq
      pkgs.coreutils
      captureCli
    ];
    text = ''
      set -euo pipefail

      # Read from environment (set on the systemd unit below) rather than
      # baking a path in at build time -- keeps this script runnable
      # standalone against a fixture capture root (see flake/tests).
      capture_root="''${SINNIX_CAPTURE_ROOT:?SINNIX_CAPTURE_ROOT must be set}"
      state_dir="''${SINNIX_CAPTURE_PRIMARY_STATE_DIR:?SINNIX_CAPTURE_PRIMARY_STATE_DIR must be set}"
      debounce_ms="''${SINNIX_CAPTURE_PRIMARY_DEBOUNCE_MS:?SINNIX_CAPTURE_PRIMARY_DEBOUNCE_MS must be set}"
      lane_dir="$capture_root/primary"
      blob_dir="$lane_dir/blobs"
      trigger_file="$state_dir/last-trigger"

      mkdir -p "$lane_dir" "$blob_dir" "$state_dir"

      # MIME preference order -- identical to the clipboard lane (see
      # capture-clipboard.nix): known binary (image) formats first, then
      # file-manager copies (uri-list), then plain-text variants.
      pick_mime() {
        local offered="$1" candidate
        for candidate in \
          image/png image/jpeg image/gif image/bmp image/tiff image/webp \
          text/uri-list \
          "text/plain;charset=utf-8" text/plain STRING UTF8_STRING; do
          if grep -qxF "$candidate" <<<"$offered"; then
            printf '%s' "$candidate"
            return 0
          fi
        done
        head -n1 <<<"$offered"
      }

      is_binary_mime() {
        case "$1" in
          image/*|application/octet-stream) return 0 ;;
          *) return 1 ;;
        esac
      }

      offered_types="$(wl-paste --primary --list-types 2>/dev/null || true)"
      if [ -z "$offered_types" ]; then
        # No PRIMARY selection right now (nothing highlighted, or it was
        # just cleared) -- nothing to capture.
        exit 0
      fi

      mime="$(pick_mime "$offered_types")"

      tmp_content="$(mktemp)"
      trap 'rm -f "$tmp_content"' EXIT
      if ! wl-paste --primary --no-newline --type "$mime" >"$tmp_content" 2>/dev/null; then
        exit 0
      fi

      size="$(stat -c%s "$tmp_content")"
      if [ "$size" -eq 0 ]; then
        exit 0
      fi

      # Debounce (see module header): stamp a monotonic trigger id, sleep,
      # then only proceed if we're still the most recent trigger. This
      # collapses same-selection re-fire bursts without doing any
      # content-based dedup -- two distinct selections that happen to
      # contain the same text still both get captured, because each is
      # its own debounce window.
      trigger_id="$(date +%s%N)"
      printf '%s' "$trigger_id" >"$trigger_file"
      sleep "$(awk -v ms="$debounce_ms" 'BEGIN { printf "%.3f", ms / 1000 }')"
      latest_trigger="$(cat "$trigger_file" 2>/dev/null || true)"
      if [ "$latest_trigger" != "$trigger_id" ]; then
        # A newer selection-change fired during our debounce window --
        # that invocation will do the capture once it settles.
        exit 0
      fi

      window_json="$(hyprctl activewindow -j 2>/dev/null || echo null)"
      source_window="$(jq -c '
        if type == "object" then {class: (.class // null), title: (.title // null)}
        else {class: null, title: null}
        end
      ' <<<"$window_json")"

      raw_ref=""
      if is_binary_mime "$mime"; then
        sha256="$(sha256sum "$tmp_content" | cut -d' ' -f1)"
        shard="''${sha256:0:2}"
        blob_shard_dir="$blob_dir/$shard"
        mkdir -p "$blob_shard_dir"
        blob_path="$blob_shard_dir/$sha256"
        if [ ! -e "$blob_path" ]; then
          cp "$tmp_content" "$blob_path"
          chmod 0600 "$blob_path"
        fi
        raw_ref="$blob_path"
        payload="$(jq -n \
          --arg mime "$mime" \
          --arg sha256 "$sha256" \
          --argjson size "$size" \
          --argjson source_window "$source_window" \
          '{category: "binary", mime: $mime, sha256: $sha256, size: $size, source_window: $source_window}')"
      else
        payload="$(jq -n \
          --arg mime "$mime" \
          --rawfile text "$tmp_content" \
          --argjson size "$size" \
          --argjson source_window "$source_window" \
          '{category: "text", mime: $mime, text: $text, size: $size, source_window: $source_window}')"
      fi

      write_args=(write --capture-root "$capture_root" --lane primary --payload "$payload")
      if [ -n "$raw_ref" ]; then
        write_args+=(--raw-ref "$raw_ref")
      fi
      exec sinnix-capture "''${write_args[@]}"
    '';
  };
in
mkServiceModule {
  name = "capture-primary";
  description = "Continuous Wayland PRIMARY-selection capture lane (wl-paste --primary --watch -> sinnix-capture)";
  extraOptions = {
    debounceMs = lib.mkOption {
      type = lib.types.ints.positive;
      default = 400;
      description = ''
        Milliseconds to wait after a PRIMARY-selection change before
        capturing, collapsing the multi-fire bursts a single selection
        gesture produces (see module header for the empirical basis) into
        one write of the settled selection.
      '';
    };
  };
  surface = {
    unit = "sinnix-capture-primary.service";
    manager = "user";
    kind = "capture";
    resourceClass = "capture-runtime";
    captures = [
      {
        name = "primary";
        path = laneDir;
        eventDriven = true;
        # PRIMARY-selection activity depends entirely on whether the
        # operator is doing text-heavy reading/selecting -- genuinely
        # intermittent, same as the clipboard and mpris lanes. Matches
        # their week-long budget (capture-registry.nix / capture-mpris.nix).
        staleAfterSeconds = 604800;
      }
    ];
    observe = {
      enable = true;
      restartable = true;
    };
  };
  configFn =
    { cfg, ... }:
    {
      systemd.tmpfiles.rules = [
        "d ${laneDir} 0700 ${username} users -"
        "d ${blobDir} 0700 ${username} users -"
        "d ${stateDir} 0700 ${username} users -"
      ];

      home-manager.users.${username} = {
        systemd.user.services.sinnix-capture-primary = {
          Unit = {
            Description = "Wayland PRIMARY-selection capture lane";
            After = [ "graphical-session.target" ];
            PartOf = [ "graphical-session.target" ];
          };
          Service = (
            lib.sinnix.mkRuntimeServiceConfig {
              runtimeInventory = config.sinnix.runtime.inventory;
              unit = "sinnix-capture-primary.service";
              overrides = {
                Type = "simple";
                ExecStart = "${pkgs.wl-clipboard}/bin/wl-paste --primary --watch ${primaryWatch}/bin/sinnix-capture-primary-watch";
                Restart = "on-failure";
                RestartSec = "5s";
                Environment = [
                  "SINNIX_CAPTURE_ROOT=${config.sinnix.paths.capturesRoot}"
                  "SINNIX_CAPTURE_PRIMARY_STATE_DIR=${stateDir}"
                  "SINNIX_CAPTURE_PRIMARY_DEBOUNCE_MS=${toString cfg.debounceMs}"
                ];
                NoNewPrivileges = true;
                ProtectSystem = "strict";
                ProtectHome = "read-only";
                ReadWritePaths = [
                  laneDir
                  blobDir
                  stateDir
                ];
                UMask = "0077";
              };
            }
          );
          Install.WantedBy = [ "graphical-session.target" ];
        };
      };
    };
} args
