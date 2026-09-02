# QEMU NixOS VM integration checks (below, polylogue daemon, transmission).
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
  runtimeDefaults = import ../data/runtime-defaults.nix { inherit lib; };
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
              virtualisation.memorySize = 4096;
              systemd.user.slices = lib.mapAttrs (_: sliceConfig: {
                inherit sliceConfig;
              }) runtimeDefaults.slices.user;
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
              sinnix.services.sinnixd.projectRoots = [
                "/realm/project/sinnix"
                "/realm/project/polylogue"
              ];
              home-manager.users.sinity.systemd.user.services.sinnixd.Unit.ConditionPathExists =
                "/realm/project/sinnix/.agentctl/project.toml";
            };
          testScript = ''
            import json

            start_all()
            machine.wait_for_unit("multi-user.target")
            uid = machine.succeed("id -u sinity").strip()
            as_user = f"XDG_RUNTIME_DIR=/run/user/{uid} runuser -u sinity --"
            pressure_clear = "awk '$1 == \"full\" { sub(\"avg10=\", \"\", $2); exit !($2 < 0.2) }' /proc/pressure/memory && awk '$1 == \"full\" { sub(\"avg10=\", \"\", $2); exit !($2 < 5.0) }' /proc/pressure/io"

            machine.succeed("loginctl enable-linger sinity")
            machine.wait_for_unit(f"user@{uid}.service")
            machine.succeed("mkdir -p /realm/project/sinnix/modules /realm/project/sinnix/.agentctl /realm/project/polylogue/polylogue /realm/project/polylogue/.agentctl /realm/project/unregistered/modules /realm/project/unregistered/.agentctl")
            machine.succeed("printf '{}' > /realm/project/sinnix/flake.nix && printf '{}' > /realm/project/polylogue/pyproject.toml && printf '{}' > /realm/project/unregistered/flake.nix")
            machine.succeed("cat > /realm/project/sinnix/.agentctl/project.toml <<'EOF'\nschema = 1\n\n[project]\nid = \"sinnix\"\ndisplay_name = \"Sinnix\"\nroot_markers = [\"flake.nix\", \"modules\"]\n\n[environment]\nkind = \"fixture\"\ncommand = [\"/run/current-system/sw/bin/env\"]\npreflight = [\"true\"]\ninherit = []\nunset = []\n\n[operations.descendants]\ndescription = \"Run a parent and child\"\nexec = [\"/realm/project/sinnix/parent.sh\"]\npool = \"normal\"\nresult = \"exit\"\ncache = \"none\"\nexclusive_keys = []\nestimate_memory_bytes = 67108864\nEOF")
            machine.succeed("cat >> /realm/project/sinnix/.agentctl/project.toml <<'EOF'\n\n[operations.cpu_stress]\ndescription = \"Exercise idle CPU scheduling through the real job route\"\nexec = [\"/realm/project/sinnix/cpu-stress.py\", \"2\", \"/home/sinity/.local/state/sinnixd-managed-cpu\"]\npool = \"normal\"\nresult = \"exit\"\ncache = \"none\"\nexclusive_keys = []\nestimate_memory_bytes = 67108864\n\n[operations.cpu_contended]\ndescription = \"Exercise contended CPU scheduling through the real job route\"\nexec = [\"/realm/project/sinnix/cpu-stress.py\", \"4\", \"/home/sinity/.local/state/sinnixd-managed-contended-cpu\", \"/home/sinity/.local/state/sinnixd-managed-ready\", \"/home/sinity/.local/state/sinnixd-cpu-go\"]\npool = \"normal\"\nresult = \"exit\"\ncache = \"none\"\nexclusive_keys = []\nestimate_memory_bytes = 67108864\n\n[operations.memory_stress]\ndescription = \"Exercise memory admission through the real job route\"\nexec = [\"/realm/project/sinnix/memory-stress.py\", \"1536\", \"5\"]\npool = \"normal\"\nresult = \"exit\"\ncache = \"none\"\nexclusive_keys = []\nestimate_memory_bytes = 1610612736\nEOF")
            machine.succeed("cat > /realm/project/polylogue/.agentctl/project.toml <<'EOF'\nschema = 1\n\n[project]\nid = \"polylogue\"\ndisplay_name = \"Polylogue\"\nroot_markers = [\"pyproject.toml\", \"polylogue\"]\n\n[environment]\nkind = \"plain\"\ncommand = [\"/run/current-system/sw/bin/env\"]\ninherit = []\nunset = []\n\n[owner_adapters.polylogue_archive]\nnamespace = \"polylogue.archive\"\nowner = \"polylogue-archive\"\nauthority = \"owner\"\nlifecycle = \"read_only\"\nprotocol_versions = [1]\nsource_scoped = true\nsource_ref = \"sinnix://polylogue/archive\"\nexec = [\"polylogue-agentctl-adapter\"]\ndocumentation = \"Bounded Polylogue archive status.\"\nEOF")
            machine.succeed("cat > /realm/project/unregistered/.agentctl/project.toml <<'EOF'\nschema = 1\n\n[project]\nid = \"unregistered\"\ndisplay_name = \"Unregistered\"\nroot_markers = [\"flake.nix\", \"modules\"]\n\n[environment]\nkind = \"fixture\"\ncommand = [\"/run/current-system/sw/bin/env\"]\ninherit = []\nunset = []\nEOF")
            machine.succeed("cat > /realm/project/sinnix/parent.sh <<'EOF'\n#!/bin/sh\necho $$ > /home/sinity/.local/state/sinnixd-parent.pid\nsleep 30 &\necho $! > /home/sinity/.local/state/sinnixd-child.pid\nwait\nEOF\nchmod 755 /realm/project/sinnix/parent.sh")
            machine.succeed("cat > /realm/project/sinnix/cpu-stress.py <<'EOF'\n#!${pkgs.python3}/bin/python3\nfrom pathlib import Path\nimport sys\nimport time\n\nif len(sys.argv) == 5:\n    Path(sys.argv[3]).touch()\n    while not Path(sys.argv[4]).exists():\n        time.sleep(0.01)\nstarted = time.process_time_ns()\ndeadline = time.monotonic() + int(sys.argv[1])\nwhile time.monotonic() < deadline:\n    pass\nPath(sys.argv[2]).write_text(str(time.process_time_ns() - started))\nEOF\nchmod 755 /realm/project/sinnix/cpu-stress.py")
            machine.succeed("cat > /realm/project/sinnix/memory-stress.py <<'EOF'\n#!${pkgs.python3}/bin/python3\nimport sys\nimport time\n\nallocation = bytearray(int(sys.argv[1]) * 1024 * 1024)\nfor offset in range(0, len(allocation), 4096):\n    allocation[offset] = 1\ntime.sleep(int(sys.argv[2]))\nEOF\nchmod 755 /realm/project/sinnix/memory-stress.py")
            machine.succeed("cat > /realm/project/sinnix/native-runner <<'EOF'\n#!/bin/sh\nset -eu\nlast=\nprompt=\nwhile [ $# -gt 0 ]; do\n  case $1 in\n    --last-file) last=$2; shift 2 ;;\n    --prompt-file) prompt=$2; shift 2 ;;\n    *) shift ;;\n  esac\ndone\ntest -f \"$prompt\"\nprintf 'native-agent-result' > \"$last\"\nprintf 'native-agent-log\\n'\nEOF\nchmod 755 /realm/project/sinnix/native-runner\ngit -C /realm/project/sinnix init --quiet\ngit -C /realm/project/sinnix add .\ngit -C /realm/project/sinnix -c user.name=Fixture -c user.email=fixture@example.test commit --quiet -m fixture\nchown -R sinity:users /realm/project")
            machine.succeed(f"{as_user} systemctl --user restart sinnixd.service")
            machine.wait_until_succeeds(f"{as_user} systemctl --user is-active --quiet sinnixd.service")
            machine.succeed(f"timeout 5 sh -c 'until test -S /run/user/{uid}/sinnixd.sock; do sleep 0.1; done'")
            machine.succeed(f"{as_user} systemctl --user cat sinnixd.slice | grep -qx CPUWeight=10")
            machine.succeed("test $(cat /sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/cpu.weight) -eq 100")
            machine.succeed(f"{as_user} agentctl project list | jq -e '.ok and ([.payload.value.projects[].id] | sort == [\"polylogue\", \"sinnix\"])' >/dev/null")
            # The descriptor still carries a retired [owner_adapters] table; the
            # loader must ignore it rather than take the project out of service.
            machine.succeed(f"{as_user} agentctl project get polylogue | jq -e '.ok and .payload.value.id == \"polylogue\" and (.payload.value | has(\"owner_adapters\") | not)' >/dev/null")
            machine.succeed(f"{as_user} agentctl status | jq -e '.ok and ([.payload.value.owners[] | select(.source_scoped)] | length == 0)' >/dev/null")
            job_id = machine.succeed(f"{as_user} agentctl job start sinnix descendants | jq -r '.payload.value.job_id'").strip()
            machine.wait_until_succeeds("test -s /home/sinity/.local/state/sinnixd-parent.pid && test -s /home/sinity/.local/state/sinnixd-child.pid")
            parent = machine.succeed("cat /home/sinity/.local/state/sinnixd-parent.pid").strip()
            child = machine.succeed("cat /home/sinity/.local/state/sinnixd-child.pid").strip()
            machine.succeed("test $(cat /sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/sinnixd.slice/cpu.weight) -eq 10")
            machine.succeed(f"{as_user} systemctl --user show sinnixd-job-{job_id}.service -P ControlGroup | grep -q '/sinnixd-work.slice/sinnixd-work-normal.slice/'")
            cancellation_started = int(machine.succeed("date +%s").strip())
            machine.succeed(f"{as_user} agentctl job cancel {job_id} | jq -e '.ok and .payload.value.cancel_requested' >/dev/null")
            machine.succeed(f"XDG_RUNTIME_DIR=/run/user/{uid} timeout 5 runuser -u sinity -- agentctl job wait {job_id} --timeout-seconds 3 | jq -e '.ok and (.payload.value.wait_timed_out != true) and .payload.value.state.terminal and .payload.value.state.phase == \"cancelled\"' >/dev/null")
            machine.succeed(f"timeout 3 sh -c 'until ! test -e /proc/{parent} && ! test -e /proc/{child}; do sleep 0.1; done'")
            assert int(machine.succeed("date +%s").strip()) - cancellation_started < 5
            shell_id = machine.succeed(f"{as_user} agentctl shell --project sinnix --checkout default --cwd . --timeout-seconds 60 -- /bin/sh -c 'printf shell-fixture' | jq -r '.payload.value.job_id'").strip()
            machine.succeed(f"{as_user} agentctl job wait {shell_id} --timeout-seconds 3 | jq -e '.ok and .payload.value.state.terminal and .payload.value.state.phase == \"succeeded\"' >/dev/null")
            machine.succeed(f"{as_user} agentctl job logs {shell_id} | jq -e '.ok and (.payload.value.content | contains(\"shell-fixture\"))' >/dev/null")
            machine.succeed("printf 'fixture prompt' > /realm/project/sinnix/prompt.md && chown sinity:users /realm/project/sinnix/prompt.md")
            machine.wait_until_succeeds(pressure_clear)
            agent_response = machine.succeed(f"{as_user} agentctl agent --project sinnix --checkout default --prompt-file /realm/project/sinnix/prompt.md --backend codex --model fixture --effort high --timeout-seconds 60 || true")
            agent_data = json.loads(agent_response)
            assert agent_data.get("ok") is True, agent_data
            agent_id = agent_data["payload"]["value"]["job_id"]
            machine.succeed(f"{as_user} agentctl job wait {agent_id} --timeout-seconds 30 | jq -e '.ok and .payload.value.state.terminal and .payload.value.state.phase == \"succeeded\"' >/dev/null")
            machine.succeed(f"{as_user} agentctl job result {agent_id} | jq -e '.ok and .payload.value.content == \"native-agent-result\"' >/dev/null")
            machine.succeed(f"test ! -e /home/sinity/.local/state/sinnixd/inputs/{agent_id}.prompt && test ! -e /home/sinity/.local/state/sinnixd/inputs/{agent_id}.json")

            machine.wait_until_succeeds(pressure_clear)
            idle_id = machine.succeed(f"{as_user} agentctl job start sinnix cpu_stress | jq -r '.payload.value.job_id'").strip()
            machine.succeed(f"{as_user} agentctl job wait {idle_id} --timeout-seconds 60 | jq -e '.ok and .payload.value.state.phase == \"succeeded\"' >/dev/null")
            idle_cpu = int(machine.succeed("cat /home/sinity/.local/state/sinnixd-managed-cpu").strip())
            assert idle_cpu > 1000000000, idle_cpu

            contended_id = machine.succeed(f"{as_user} agentctl job start sinnix cpu_contended | jq -r '.payload.value.job_id'").strip()
            machine.wait_until_succeeds("test -e /home/sinity/.local/state/sinnixd-managed-ready")
            machine.succeed(f"{as_user} systemd-run --user --quiet --unit=interactive-stress.service --slice=app.slice /realm/project/sinnix/cpu-stress.py 4 /home/sinity/.local/state/sinnixd-interactive-cpu /home/sinity/.local/state/sinnixd-interactive-ready /home/sinity/.local/state/sinnixd-cpu-go")
            machine.wait_until_succeeds("test -e /home/sinity/.local/state/sinnixd-interactive-ready")
            machine.succeed("touch /home/sinity/.local/state/sinnixd-cpu-go && chown sinity:users /home/sinity/.local/state/sinnixd-cpu-go")
            machine.succeed(f"{as_user} agentctl job wait {contended_id} --timeout-seconds 15 | jq -e '.ok and .payload.value.state.phase == \"succeeded\"' >/dev/null")
            machine.wait_until_succeeds(f"! {as_user} systemctl --user is-active --quiet interactive-stress.service")
            work_cpu = int(machine.succeed("cat /home/sinity/.local/state/sinnixd-managed-contended-cpu").strip())
            interactive_cpu = int(machine.succeed("cat /home/sinity/.local/state/sinnixd-interactive-cpu").strip())
            assert work_cpu > 0, work_cpu
            assert interactive_cpu > work_cpu * 3, (interactive_cpu, work_cpu)

            machine.wait_until_succeeds(pressure_clear)
            first_memory_id = machine.succeed(f"{as_user} agentctl job start sinnix memory_stress | jq -r '.payload.value.job_id'").strip()
            machine.wait_until_succeeds(f"test $({as_user} systemctl --user show sinnixd-job-{first_memory_id}.service -P MemoryCurrent) -gt 1073741824")
            machine.succeed(f"{as_user} systemd-run --user --quiet --unit=interactive-memory.service --slice=app.slice /realm/project/sinnix/memory-stress.py 1024 10")
            machine.wait_until_succeeds(f"test $({as_user} systemctl --user show interactive-memory.service -P MemoryCurrent) -gt 805306368")
            second_memory_id = machine.succeed(f"{as_user} agentctl job start sinnix memory_stress | jq -r '.payload.value.job_id'").strip()
            machine.wait_until_succeeds(f"{as_user} agentctl job get {second_memory_id} | jq -e '.payload.value.state.phase == \"queued\" and (.payload.value.state.admission.blocked_by | index(\"host-memory\"))' >/dev/null")
            machine.succeed(f"{as_user} agentctl job wait {first_memory_id} --timeout-seconds 10 | jq -e '.ok and .payload.value.state.phase == \"succeeded\"' >/dev/null")
            machine.succeed(f"{as_user} agentctl job wait {second_memory_id} --timeout-seconds 15 | jq -e '.ok and .payload.value.state.phase == \"succeeded\"' >/dev/null")
            machine.wait_until_succeeds(f"! {as_user} systemctl --user is-active --quiet interactive-memory.service")
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
