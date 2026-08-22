# QEMU NixOS VM integration checks (below, polylogue daemon, transmission).
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
            machine.succeed(f"{as_user} ${
              inputs.polylogue.packages.${system}.default
            }/bin/polylogued status --format json | jq -e '.daemon == \"polylogued\" and (.live.source_count >= 0)' >/dev/null")
          '';
        };
        sinnixd-vm = mkVmCheck system {
          name = "sinnixd-vm";
          nodes.machine =
            { pkgs, ... }:
            {
              environment.systemPackages = [ pkgs.jq ];
              sinnix.features.desktop = {
                activitywatch.enable = false;
                audio.enable = false;
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
              sinnix.paths.projectRoot = "/realm/project/fixture";
              sinnix.services.sinnixd.enable = true;
            };
          testScript = ''
            start_all()
            machine.wait_for_unit("multi-user.target")
            uid = machine.succeed("id -u sinity").strip()
            as_user = f"XDG_RUNTIME_DIR=/run/user/{uid} runuser -u sinity --"

            machine.succeed("loginctl enable-linger sinity")
            machine.wait_for_unit(f"user@{uid}.service")
            machine.succeed("mkdir -p /realm/project/fixture/modules /realm/project/fixture/.agentctl")
            machine.succeed("printf '{}' > /realm/project/fixture/flake.nix")
            machine.succeed("cat > /realm/project/fixture/.agentctl/project.toml <<'EOF'\nschema = 1\n\n[project]\nid = \"fixture\"\ndisplay_name = \"Fixture\"\nroot_markers = [\"flake.nix\", \"modules\"]\n\n[environment]\nkind = \"fixture\"\ncommand = [\"/run/current-system/sw/bin/env\"]\ninherit = []\nunset = []\n\n[operations.descendants]\ndescription = \"Run a parent and child\"\nexec = [\"/realm/project/fixture/parent.sh\"]\npool = \"normal\"\nresult = \"exit\"\ncache = \"none\"\nexclusive_keys = []\nEOF")
            machine.succeed("cat > /realm/project/fixture/parent.sh <<'EOF'\n#!/bin/sh\necho $$ > /home/sinity/.local/state/sinnixd-parent.pid\nsleep 30 &\necho $! > /home/sinity/.local/state/sinnixd-child.pid\nwait\nEOF\nchmod 755 /realm/project/fixture/parent.sh\nchown -R sinity:users /realm/project/fixture")
            machine.succeed(f"{as_user} systemctl --user restart sinnixd.service")
            machine.wait_until_succeeds(f"{as_user} systemctl --user is-active --quiet sinnixd.service")
            job_id = machine.succeed(f"{as_user} agentctl job start fixture descendants | jq -r '.payload.value.job_id'").strip()
            machine.wait_until_succeeds("test -s /home/sinity/.local/state/sinnixd-parent.pid && test -s /home/sinity/.local/state/sinnixd-child.pid")
            parent = machine.succeed("cat /home/sinity/.local/state/sinnixd-parent.pid").strip()
            child = machine.succeed("cat /home/sinity/.local/state/sinnixd-child.pid").strip()
            machine.succeed(f"{as_user} agentctl job cancel {job_id} | jq -e '.ok and .payload.value.cancel_requested' >/dev/null")
            machine.succeed(f"{as_user} agentctl job wait {job_id} | jq -e '.ok and ((.payload.value.state.phase == \"succeeded\" and .payload.value.state.systemd.Result == \"success\") or (.payload.value.state.phase == \"cancelled\" and (.payload.value.state.cancellation.invocation_id? | type == \"string\")))' >/dev/null")
            machine.wait_until_succeeds(f"! test -e /proc/{parent} && ! test -e /proc/{child}")
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
