# agent-tool-command against a real user manager: an agent's tool commands
# share one unit under agent-tool.slice, each in its own leaf cgroup, and the
# unit ends with the agent. The cgroup moves and the unit's lifetime are what
# is under test, so this needs a booted systemd, not a sandbox.
{ inputs, ... }:
{
  perSystem =
    { system, sinnixScriptRegistry, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      agentToolCommand = sinnixScriptRegistry.packageSet.agent-tool-command;
      cgroupProbe = pkgs.writeShellScript "cgroup-probe" ''
        cat /proc/self/cgroup
      '';
      # A stand-in for the agent process: it runs tool commands the way an
      # agent does and then stays alive, as the agent's unit.
      agent = pkgs.writeShellScript "fixture-agent" ''
        set -u
        export PATH=/run/current-system/sw/bin:$PATH SHELL=${pkgs.bash}/bin/bash
        out="$XDG_RUNTIME_DIR/atc"
        mkdir -p "$out"
        cd "$out"
        run=agent-tool-command
        # Two first commands race to start the unit.
        $run 'cat /proc/self/cgroup > race1' &
        $run 'cat /proc/self/cgroup > race2' &
        wait
        for i in 1 2 3; do
          $run "cat /proc/self/cgroup > seq$i"
        done
        bash -c 'echo $$ > pid.outer; exec agent-tool-command "echo \$\$ > pid.inner"'
        $run 'exit 7'
        echo $? > status
        $run -- bash -c 'cat /proc/self/cgroup > argv'
        $run 'polylogue internal hook PreToolUse' > hook-command
        $run '/etc/fixture/dots/claude/hooks/probe' > hook-file
        $run 'cat /proc/self/oom_score_adj > oom; echo "$AGENT_TOOL_COMMAND_PID $$" > marker'
        $run 'echo $$ > long.pid; exec sleep 600' &
        ZDOTDIR=/etc/fixture-zsh ${pkgs.zsh}/bin/zsh -lc 'cat /proc/self/cgroup > zsh-login'
        touch ready
        exec sleep infinity
      '';
      # An agent whose commands cannot reach the user manager.
      agentWithoutManager = pkgs.writeShellScript "fixture-agent-without-manager" ''
        set -u
        export PATH=/run/current-system/sw/bin:$PATH SHELL=${pkgs.bash}/bin/bash
        out="$XDG_RUNTIME_DIR/atc-without-manager"
        mkdir -p "$out/runtime"
        cd "$out"
        XDG_RUNTIME_DIR="$out/runtime" agent-tool-command 'cat /proc/self/cgroup > command; exit 5'
        echo $? > status
        XDG_RUNTIME_DIR="$out/runtime" ZDOTDIR=/etc/fixture-zsh ${pkgs.zsh}/bin/zsh -lc 'cat /proc/self/cgroup > zsh-login'
        touch ready
      '';
    in
    {
      heavyChecks.agent-tool-command-vm = pkgs.testers.runNixOSTest {
        name = "agent-tool-command";
        nodes.machine = {
          virtualisation.memorySize = 1024;
          virtualisation.cores = 2;
          users.users.fixture = {
            isNormalUser = true;
            uid = 1000;
            linger = true;
          };
          environment.systemPackages = [
            agentToolCommand
            pkgs.zsh
            (pkgs.writeShellScriptBin "polylogue" ''
              exec ${cgroupProbe}
            '')
          ];
          environment.etc."fixture/dots/claude/hooks/probe".source = cgroupProbe;
          environment.etc."fixture-zsh/.zshenv".text = ''
            source ${../../dots/zsh/agent-tool-scope.zsh}
          '';
        };
        testScript = ''
          import re

          start_all()
          machine.wait_for_unit("multi-user.target")
          machine.wait_for_unit("user@1000.service")
          as_user = "runuser -u fixture -- env XDG_RUNTIME_DIR=/run/user/1000"
          user = f"{as_user} systemctl --user"
          out = "/run/user/1000/atc"
          root = "/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service"
          unit = "agent-tool-fixture-agent.service"
          unit_cgroup = f"{root}/agent.slice/agent-tool.slice/{unit}"
          leaf = re.compile(rf"^0::/user\.slice/user-1000\.slice/user@1000\.service/agent\.slice/agent-tool\.slice/{re.escape(unit)}/cmd-\d+$")

          def read(path):
              return machine.succeed(f"cat {path}").strip()

          def launch(name, program):
              # The outer unit only starts the scope; the agent itself is a
              # scope under agent-cli.slice, as a real one is.
              machine.succeed(
                  f"{as_user} systemd-run --user --quiet --collect --unit={name}-launcher -- "
                  f"${pkgs.systemd}/bin/systemd-run --user --scope --quiet --collect "
                  f"--unit={name} --slice=agent-cli.slice -- {program}"
              )

          with subtest("a command outside agent-cli.slice stays where it is"):
              here = machine.succeed(f"{as_user} agent-tool-command 'cat /proc/self/cgroup'").strip()
              assert "/agent-tool.slice/" not in here, here
              assert machine.succeed(f"{user} list-units --no-legend 'agent-tool-*'").strip() == ""

          with subtest("an agent's commands share one unit, one leaf cgroup each"):
              launch("fixture-agent", "${agent}")
              machine.wait_until_succeeds(f"test -e {out}/ready", timeout=60)
              for name in ("race1", "race2", "seq1", "seq2", "seq3", "argv", "zsh-login"):
                  assert leaf.match(read(f"{out}/{name}")), (name, read(f"{out}/{name}"))
              leaves = {read(f"{out}/{name}") for name in ("race1", "race2", "seq1", "seq2", "seq3", "argv")}
              assert len(leaves) == 6, leaves
              units = machine.succeed(f"{user} list-units --no-legend --plain 'agent-tool-*'").split()
              assert units[0] == unit and units.count(unit) == 1, units
              assert machine.succeed(f"{user} list-units --no-legend --plain 'run-*.scope'").strip() == ""
              journal = machine.succeed("journalctl _UID=1000 -o cat --no-pager")
              assert journal.count("Started Agent tool commands.") == 1, journal
              assert "Started Agent tool command." not in journal, journal

          with subtest("a command keeps its PID, status, OOM rank and mark"):
              assert read(f"{out}/pid.outer") == read(f"{out}/pid.inner")
              assert read(f"{out}/status") == "7"
              assert read(f"{out}/oom") == "800"
              mark, pid = read(f"{out}/marker").split()
              assert mark == pid, (mark, pid)

          with subtest("hooks stay in the agent's unit"):
              for name in ("hook-command", "hook-file"):
                  assert read(f"{out}/{name}").endswith("/agent-cli.slice/fixture-agent.scope"), read(f"{out}/{name}")

          with subtest("each leaf has the memory controller and finished ones are removed"):
              long_pid = read(f"{out}/long.pid")
              machine.succeed(f"test -e {unit_cgroup}/cmd-{long_pid}/memory.oom.group")
              assert read(f"{unit_cgroup}/cgroup.procs") == ""
              machine.wait_until_succeeds(
                  f"test \"$(ls -d {unit_cgroup}/cmd-* | tr '\\n' ' ')\" = '{unit_cgroup}/cmd-{long_pid} '",
                  timeout=90,
              )

          with subtest("the unit and its commands end with the agent"):
              machine.succeed(f"kill -0 {long_pid}")
              machine.succeed(f"{user} kill --kill-whom=all fixture-agent.scope")
              machine.wait_until_fails(f"{user} is-active --quiet {unit}", timeout=30)
              machine.wait_until_fails(f"kill -0 {long_pid}", timeout=30)
              machine.wait_until_fails(f"test -e {unit_cgroup}", timeout=30)

          with subtest("without the user manager a command runs where it stands"):
              launch("fixture-agent-without-manager", "${agentWithoutManager}")
              lone = "/run/user/1000/atc-without-manager"
              machine.wait_until_succeeds(f"test -e {lone}/ready", timeout=60)
              assert read(f"{lone}/status") == "5"
              for name in ("command", "zsh-login"):
                  assert read(f"{lone}/{name}").endswith("/agent-cli.slice/fixture-agent-without-manager.scope"), read(f"{lone}/{name}")
              assert machine.succeed(f"{user} list-units --no-legend 'agent-tool-*'").strip() == ""
        '';
      };
    };
}
