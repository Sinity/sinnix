# Hyprland idle / DPMS management.
#
# The lock screen UI is provided by Noctalia (see noctalia.nix). This keeps
# hypridle owns the ordered OLED power and lock stages. Media and game
# inhibitors remain in the Hyprland rules module.
#
{ pkgs, ... }:
let
  # Record the start of a long AFK interval for the operations reducer.
  # Plain-text timestamp, not JSON -- afk-resume below is the only file the
  # reducer actually parses (sinnix_ops_reducer.cli: --anchor-events
  # defaults to %t/sinnix/afk-resume.json).
  afkStart = pkgs.writeShellScript "sinnix-ops-afk-start" ''
    set -euo pipefail
    dir="''${XDG_RUNTIME_DIR:?}/sinnix"
    mkdir -p "$dir"
    date -u +%Y-%m-%dT%H:%M:%SZ > "$dir/afk-start"
  '';
  # Record an AFK resume event for the operations reducer. Exact file paths
  # and JSON shape are load-bearing: the reducer's anchor.reduce_anchor_event
  # reads started_at/resumed_at off this file at %t/sinnix/afk-resume.json.
  afkResume = pkgs.writeShellScript "sinnix-ops-afk-resume" ''
    set -euo pipefail
    dir="''${XDG_RUNTIME_DIR:?}/sinnix"
    start="$dir/afk-start"
    event="$dir/afk-resume.json"
    if [[ ! -s "$start" ]]; then exit 0; fi
    resumed="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    started="$(<"$start")"
    tmp="$event.tmp.$$"
    printf '{"started_at":"%s","resumed_at":"%s","interval_id":"%s:%s"}\n' "$started" "$resumed" "$started" "$resumed" > "$tmp"
    mv "$tmp" "$event"
    rm -f "$start"
  '';
in
{
  services.hypridle = {
    enable = true;
    settings = {
      general = {
        after_sleep_cmd = "hyprctl dispatch dpms on";
        ignore_dbus_inhibit = false;
        lock_cmd = "noctalia msg session lock";
      };

      listener = [
        {
          timeout = 1800;
          on-timeout = "${afkStart}";
          on-resume = "${afkResume}";
        }
        {
          timeout = 420;
          on-timeout = "hyprctl dispatch dpms off";
          on-resume = "hyprctl dispatch dpms on";
        }
        {
          timeout = 1500;
          on-timeout = "noctalia msg session lock";
          on-resume = "hyprctl dispatch dpms on";
        }
      ];
    };
  };
}
