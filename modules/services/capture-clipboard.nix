# Continuous Wayland clipboard capture lane
#
# `wl-paste --watch` runs one long-lived user service (this host's
# compositor is Hyprland/wlroots) that invokes a small event script on
# every clipboard selection change. The event script:
#
# - Picks the most specific offered MIME type (images before uri-list
#   before plain-text variants).
# - Classifies it text (goes inline in the envelope payload) or binary
#   (content-hashed with sha256 and written once to a content-addressed
#   blob store under the lane directory; the envelope carries only
#   mime/sha256/size plus a `raw_ref` pointer to the blob).
# - De-duplicates consecutive identical clipboard content. wl-paste
#   --watch fires on every selection-change protocol event, not only on
#   content changes -- this host also runs wl-clip-persist (clipboard
#   persistence across window close, see desktop/base.nix), whose
#   re-offers are exactly the kind of no-op re-selection this would
#   otherwise double-write.
# - Attributes the source window via `hyprctl activewindow -j`.
# - Appends one sinnix-capture-v1 envelope via `sinnix-capture write`.
#
# This lane captures everything copied, secrets included, by design:
# sensitivity is handled at consumption time. Do not add redaction here.
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

  laneDir = "${config.sinnix.paths.activityRoot}/clipboard";
  blobDir = "${laneDir}/blobs";
  stateDir = "${config.sinnix.paths.stateRoot}/cursors/capture-clipboard";

  clipboardWatch = pkgs.writeShellApplication {
    name = "sinnix-capture-clipboard-watch";
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
      state_dir="''${SINNIX_CAPTURE_CLIPBOARD_STATE_DIR:?SINNIX_CAPTURE_CLIPBOARD_STATE_DIR must be set}"
      lane_dir="$capture_root/clipboard"
      blob_dir="$lane_dir/blobs"
      last_hash_file="$state_dir/last-selection"

      # wl-paste --watch supplies the new selection on stdin. Drain it before
      # making any nested clipboard request, otherwise the selection owner can
      # block forever writing a large selection while this handler waits for a
      # second transfer from that same owner.
      watch_input="$(mktemp)"
      tmp_content="$(mktemp)"
      trap 'rm -f "$watch_input" "$tmp_content"' EXIT
      cat >"$watch_input"

      mkdir -p "$lane_dir" "$blob_dir" "$state_dir"

      # MIME preference order: known binary (image) formats first, then
      # file-manager copies (uri-list), then plain-text variants. Falls
      # back to whatever wl-paste offered first for anything unrecognized
      # (app-specific rich-text/custom formats included) -- captured as
      # text unless it matches a binary pattern below.
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

      offered_types="$(wl-paste --list-types 2>/dev/null || true)"
      if [ -z "$offered_types" ]; then
        # Clipboard cleared / nothing offered right now -- nothing to capture.
        exit 0
      fi

      mime="$(pick_mime "$offered_types")"

      if ! wl-paste --no-newline --type "$mime" >"$tmp_content" 2>/dev/null; then
        exit 0
      fi

      size="$(stat -c%s "$tmp_content")"
      if [ "$size" -eq 0 ]; then
        exit 0
      fi

      sha256="$(sha256sum "$tmp_content" | cut -d' ' -f1)"

      # De-duplicate consecutive identical clipboard content (see module
      # header). Only the most recent selection is tracked -- this is a
      # linear stream, not a history dedup.
      dedupe_key="$mime:$sha256"
      if [ -f "$last_hash_file" ] && [ "$(cat "$last_hash_file")" = "$dedupe_key" ]; then
        exit 0
      fi
      printf '%s' "$dedupe_key" >"$last_hash_file"

      window_json="$(hyprctl activewindow -j 2>/dev/null || echo null)"
      source_window="$(jq -c '
        if type == "object" then {class: (.class // null), title: (.title // null)}
        else {class: null, title: null}
        end
      ' <<<"$window_json")"

      raw_ref=""
      if is_binary_mime "$mime"; then
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

      write_args=(write --capture-root "$capture_root" --lane clipboard)
      if [ -n "$raw_ref" ]; then
        write_args+=(--raw-ref "$raw_ref")
      fi
      printf '%s' "$payload" | exec sinnix-capture "''${write_args[@]}"
    '';
  };
in
mkServiceModule {
  name = "capture-clipboard";
  description = "Continuous Wayland clipboard capture lane (wl-paste --watch -> sinnix-capture)";
  surface = {
    unit = "sinnix-capture-clipboard.service";
    manager = "user";
    resourceClass = "capture-runtime";
    captures = [
      {
        name = "clipboard";
        path = laneDir;
        eventDriven = true;
        # Genuinely bursty/idle-tolerant: an operator can go a full week
        # without copying anything new (travel, laptop-only stretches).
        staleAfterSeconds = 604800;
      }
    ];
    observe = {
      enable = true;
      restartable = true;
    };
  };
  configFn =
    { ... }:
    {
      systemd.tmpfiles.rules = [
        "d ${laneDir} 0700 ${username} users -"
        "d ${blobDir} 0700 ${username} users -"
        "d ${stateDir} 0700 ${username} users -"
      ];

      home-manager.users.${username} = {
        systemd.user.services.sinnix-capture-clipboard = {
          Unit = {
            Description = "Wayland clipboard capture lane";
            After = [ "graphical-session.target" ];
            PartOf = [ "graphical-session.target" ];
          };
          Service = (
            lib.sinnix.mkRuntimeServiceConfig {
              runtimeInventory = config.sinnix.runtime.inventory;
              unit = "sinnix-capture-clipboard.service";
              overrides = {
                Type = "simple";
                ExecStart = "${pkgs.wl-clipboard}/bin/wl-paste --watch ${clipboardWatch}/bin/sinnix-capture-clipboard-watch";
                Restart = "on-failure";
                RestartSec = "5s";
                Environment = [
                  "SINNIX_CAPTURE_ROOT=${config.sinnix.paths.activityRoot}"
                  "SINNIX_CAPTURE_CLIPBOARD_STATE_DIR=${stateDir}"
                  # The session exports TMPDIR=/realm/tmp/shell, which is
                  # read-only inside this unit's ProtectSystem=strict
                  # namespace, so every mktemp fails and the lane silently
                  # captures nothing. Pin tmp inside the sandbox instead.
                  "TMPDIR=/tmp"
                ];
                PrivateTmp = true;
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
