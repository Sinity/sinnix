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
              sinnix.services.sinnixd.enable = true;
              sinnix.services.sinnixd.agentRunner = "/realm/project/sinnix/native-runner";
              home-manager.users.sinity.systemd.user.services.sinnixd.Unit.ConditionPathExists =
                "/realm/project/sinnix/.agentctl/project.toml";
            };
          testScript = ''
            start_all()
            machine.wait_for_unit("multi-user.target")
            uid = machine.succeed("id -u sinity").strip()
            as_user = f"XDG_RUNTIME_DIR=/run/user/{uid} runuser -u sinity --"

            machine.succeed("loginctl enable-linger sinity")
            machine.wait_for_unit(f"user@{uid}.service")
            machine.succeed("mkdir -p /realm/project/sinnix/modules /realm/project/sinnix/.agentctl /realm/project/polylogue/polylogue /realm/project/polylogue/.agentctl /realm/project/unregistered/modules /realm/project/unregistered/.agentctl")
            machine.succeed("printf '{}' > /realm/project/sinnix/flake.nix && printf '{}' > /realm/project/polylogue/pyproject.toml && printf '{}' > /realm/project/unregistered/flake.nix")
            machine.succeed("cat > /realm/project/sinnix/.agentctl/project.toml <<'EOF'\nschema = 1\n\n[project]\nid = \"sinnix\"\ndisplay_name = \"Sinnix\"\nroot_markers = [\"flake.nix\", \"modules\"]\n\n[environment]\nkind = \"fixture\"\ncommand = [\"/run/current-system/sw/bin/env\"]\ninherit = []\nunset = []\n\n[operations.descendants]\ndescription = \"Run a parent and child\"\nexec = [\"/realm/project/sinnix/parent.sh\"]\npool = \"normal\"\nresult = \"exit\"\ncache = \"none\"\nexclusive_keys = []\nEOF")
            machine.succeed("cat > /realm/project/polylogue/.agentctl/project.toml <<'EOF'\nschema = 1\n\n[project]\nid = \"polylogue\"\ndisplay_name = \"Polylogue\"\nroot_markers = [\"pyproject.toml\", \"polylogue\"]\n\n[environment]\nkind = \"plain\"\ncommand = [\"/run/current-system/sw/bin/env\"]\ninherit = []\nunset = []\n\n[owner_adapters.polylogue_archive]\nnamespace = \"polylogue.archive\"\nowner = \"polylogue-archive\"\nauthority = \"owner\"\nlifecycle = \"read_only\"\nprotocol_versions = [1]\nsource_scoped = true\nsource_ref = \"sinnix://polylogue/archive\"\nexec = [\"polylogue-agentctl-adapter\"]\ndocumentation = \"Bounded Polylogue archive status.\"\nEOF")
            machine.succeed("cat > /realm/project/unregistered/.agentctl/project.toml <<'EOF'\nschema = 1\n\n[project]\nid = \"unregistered\"\ndisplay_name = \"Unregistered\"\nroot_markers = [\"flake.nix\", \"modules\"]\n\n[environment]\nkind = \"fixture\"\ncommand = [\"/run/current-system/sw/bin/env\"]\ninherit = []\nunset = []\nEOF")
            machine.succeed("cat > /realm/project/sinnix/parent.sh <<'EOF'\n#!/bin/sh\necho $$ > /home/sinity/.local/state/sinnixd-parent.pid\nsleep 30 &\necho $! > /home/sinity/.local/state/sinnixd-child.pid\nwait\nEOF\nchmod 755 /realm/project/sinnix/parent.sh")
            machine.succeed("cat > /realm/project/sinnix/native-runner <<'EOF'\n#!/bin/sh\nset -eu\nlast=\nprompt=\nwhile [ $# -gt 0 ]; do\n  case $1 in\n    --last-file) last=$2; shift 2 ;;\n    --prompt-file) prompt=$2; shift 2 ;;\n    *) shift ;;\n  esac\ndone\ntest -f \"$prompt\"\nprintf 'native-agent-result' > \"$last\"\nprintf 'native-agent-log\\n'\nEOF\nchmod 755 /realm/project/sinnix/native-runner\ngit -C /realm/project/sinnix init --quiet\ngit -C /realm/project/sinnix add .\ngit -C /realm/project/sinnix -c user.name=Fixture -c user.email=fixture@example.test commit --quiet -m fixture\nchown -R sinity:users /realm/project")
            machine.succeed(f"{as_user} systemctl --user restart sinnixd.service")
            machine.wait_until_succeeds(f"{as_user} systemctl --user is-active --quiet sinnixd.service")
            machine.succeed(f"timeout 5 sh -c 'until test -S /run/user/{uid}/sinnixd.sock; do sleep 0.1; done'")
            machine.succeed(f"{as_user} agentctl project list | jq -e '.ok and ([.payload.value.projects[].id] | sort == [\"polylogue\", \"sinnix\"])' >/dev/null")
            machine.succeed(f"{as_user} agentctl project get polylogue | jq -e '.ok and .payload.value.id == \"polylogue\" and (.payload.value.owner_adapters | length == 1) and .payload.value.owner_adapters[0].namespace == \"polylogue.archive\" and .payload.value.owner_adapters[0].owner == \"polylogue-archive\" and .payload.value.owner_adapters[0].source_scoped and .payload.value.owner_adapters[0].source_ref == \"sinnix://polylogue/archive\"' >/dev/null")
            machine.succeed(f"{as_user} agentctl status | jq -e '.ok and ([.payload.value.owners[] | select(.namespace == \"polylogue.archive\" and .owner == \"polylogue-archive\" and .source_scoped)] | length == 1)' >/dev/null")
            job_id = machine.succeed(f"{as_user} agentctl job start sinnix descendants | jq -r '.payload.value.job_id'").strip()
            machine.wait_until_succeeds("test -s /home/sinity/.local/state/sinnixd-parent.pid && test -s /home/sinity/.local/state/sinnixd-child.pid")
            parent = machine.succeed("cat /home/sinity/.local/state/sinnixd-parent.pid").strip()
            child = machine.succeed("cat /home/sinity/.local/state/sinnixd-child.pid").strip()
            cancellation_started = int(machine.succeed("date +%s").strip())
            machine.succeed(f"{as_user} agentctl job cancel {job_id} | jq -e '.ok and .payload.value.cancel_requested' >/dev/null")
            machine.succeed(f"XDG_RUNTIME_DIR=/run/user/{uid} timeout 5 runuser -u sinity -- agentctl job wait {job_id} --timeout-seconds 3 | jq -e '.ok and (.payload.value.wait_timed_out != true) and .payload.value.state.terminal and .payload.value.state.phase == \"cancelled\"' >/dev/null")
            machine.succeed(f"timeout 3 sh -c 'until ! test -e /proc/{parent} && ! test -e /proc/{child}; do sleep 0.1; done'")
            assert int(machine.succeed("date +%s").strip()) - cancellation_started < 5
            shell_id = machine.succeed(f"{as_user} agentctl shell --project sinnix --checkout default --cwd . --timeout-seconds 60 -- /bin/sh -c 'printf shell-fixture' | jq -r '.payload.value.job_id'").strip()
            machine.succeed(f"{as_user} agentctl job wait {shell_id} --timeout-seconds 3 | jq -e '.ok and .payload.value.state.terminal and .payload.value.state.phase == \"succeeded\"' >/dev/null")
            machine.succeed(f"{as_user} agentctl job logs {shell_id} | jq -e '.ok and (.payload.value.content | contains(\"shell-fixture\"))' >/dev/null")
            machine.succeed("printf 'fixture prompt' > /realm/project/sinnix/prompt.md && chown sinity:users /realm/project/sinnix/prompt.md")
            agent_id = machine.succeed(f"{as_user} agentctl agent --project sinnix --checkout default --prompt-file /realm/project/sinnix/prompt.md --backend codex --model fixture --effort high --timeout-seconds 60 | jq -r '.payload.value.job_id'").strip()
            machine.succeed(f"{as_user} agentctl job wait {agent_id} --timeout-seconds 3 | jq -e '.ok and .payload.value.state.terminal and .payload.value.state.phase == \"succeeded\"' >/dev/null")
            machine.succeed(f"{as_user} agentctl job result {agent_id} | jq -e '.ok and .payload.value.content == \"native-agent-result\"' >/dev/null")
            machine.succeed(f"test ! -e /home/sinity/.local/state/sinnixd/inputs/{agent_id}.prompt && test ! -e /home/sinity/.local/state/sinnixd/inputs/{agent_id}.json")
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
