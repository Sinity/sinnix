# QEMU NixOS VM integration checks (below, polylogue daemon, transmission).
#
# Split out of the former flake/tests-runtime.nix monolith (sinnix-7bu).
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      testLib = import ../test-lib.nix { inherit inputs lib; };
      inherit (testLib) mkVmCheck;

      vmChecks = lib.optionalAttrs pkgs.stdenv.hostPlatform.isLinux {
        below-vm = mkVmCheck system {
          name = "below-vm";
          nodes.machine = {
            sinnix.services.below.enable = true;
          };
          testScript = ''
            start_all()
            machine.wait_for_unit("multi-user.target")
            machine.wait_for_unit("below.service")
            machine.succeed("test \"$(systemctl show below.service -P SubState)\" = running")
            machine.wait_until_succeeds("test -d /var/log/below/store")
            machine.wait_until_succeeds("find /var/log/below/store -type f | grep -q .")
          '';
        };
        polylogue-vm = mkVmCheck system {
          name = "polylogue-vm";
          nodes.machine =
            { pkgs, ... }:
            {
              environment.systemPackages = [ pkgs.jq ];
              sinnix.features.desktop = {
                activitywatch.enable = false;
                agentVerifyTimer.enable = false;
                audio.enable = false;
                audioCapture.enable = false;
                base.enable = false;
                browser.enable = false;
                "common-apps".enable = false;
                gaming.enable = false;
                hyprland.enable = false;
                hyprlandAnimations.enable = false;
                media.enable = false;
                mime.enable = false;
                noctalia.enable = false;
                storage.enable = false;
                terminal.enable = false;
                theming.enable = false;
                ui.enable = false;
              };
              sinnix.services.polylogue.enable = true;
            };
          testScript = ''
            start_all()
            machine.wait_for_unit("multi-user.target")

            uid = machine.succeed("id -u sinity").strip()
            as_user = f"XDG_RUNTIME_DIR=/run/user/{uid} runuser -u sinity --"

            machine.succeed("loginctl enable-linger sinity")
            machine.wait_for_unit(f"user@{uid}.service")
            machine.wait_for_unit("polylogued.service", "sinity")

            machine.succeed(f"{as_user} systemctl --user is-active --quiet polylogued.service")
            machine.fail(f"{as_user} systemctl --user cat polylogue-run.service")
            machine.fail(f"{as_user} systemctl --user cat polylogue-run.timer")
            machine.succeed(f"{as_user} ${
              inputs.polylogue.packages.${system}.default
            }/bin/polylogued status --format json | jq -e '.daemon == \"polylogued\" and (.live.source_count >= 0)' >/dev/null")
          '';
        };
        transmission-vm = mkVmCheck system {
          name = "transmission-vm";
          nodes.machine =
            { pkgs, ... }:
            {
              environment.systemPackages = [
                pkgs.curl
                pkgs.jq
              ];
              sinnix.features.desktop = {
                activitywatch.enable = false;
                agentVerifyTimer.enable = false;
                audio.enable = false;
                audioCapture.enable = false;
                base.enable = false;
                browser.enable = false;
                "common-apps".enable = false;
                gaming.enable = false;
                hyprland.enable = false;
                hyprlandAnimations.enable = false;
                media.enable = false;
                mime.enable = false;
                noctalia.enable = false;
                storage.enable = false;
                terminal.enable = false;
                theming.enable = false;
                ui.enable = false;
              };
              sinnix.services.transmission.enable = true;
            };
          testScript = ''
            start_all()
            machine.wait_for_unit("multi-user.target")
            machine.succeed("systemctl start transmission.service")
            machine.wait_for_unit("transmission.service")
            machine.wait_until_succeeds("test -d /neo-outer-realm/inbox")

            machine.wait_until_succeeds("curl -sS -D /tmp/transmission.headers -o /tmp/transmission.body http://127.0.0.1:9091/transmission/rpc || true; grep -q '409 Conflict' /tmp/transmission.headers")
            machine.succeed('session_id=$(awk -F": " \'/X-Transmission-Session-Id/ {print $2}\' /tmp/transmission.headers | tr -d "\\r"); test -n "$session_id"')
          '';
        };
      };
    in
    {
      heavyChecks = vmChecks;
    };
}
