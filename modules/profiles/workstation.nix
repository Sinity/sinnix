# Interactive workstation profile.
#
# Applied automatically to desktop hosts. It owns the resource-governance stack
# that keeps desktop-critical processes protected while declared services and
# AgentCTL jobs receive their own resource policy: systemd slices, earlyoom
# policy, io.cost init, RAPL power
# caps, the interactive memory sysctls, and the bounded stop timeout that
# keeps one wedged session unit from owning the whole reboot.
{
  lib,
  config,
  pkgs,
  helpers,
  ...
}:
let
  runtimeInventory = config.sinnix.runtime.inventory;
  primaryUserUid = toString config.users.users.${config.sinnix.user.name}.uid;
  # The desktop's guarantee is only as large as every ancestor's, so the
  # user slice's values are repeated on the per-user slice and manager.
  interactiveMemoryMin = runtimeInventory.slices.system.user.MemoryMin;
  interactiveMemoryLow = runtimeInventory.slices.system.user.MemoryLow;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  userTmpRoot = "/realm/tmp/work";
  earlyoomAvoidPattern = runtimeInventory.earlyoomEmergencyAvoidPattern;
  forbiddenEarlyoomAvoidTokens = [
    "bash"
    "chrome"
    "chromium"
    "claude"
    "codex"
    "electron"
    "firefox"
    "node"
    "python"
    "zsh"
  ];
  panicLogCapture = pkgs.writeShellApplication {
    name = "sinnix-capture-panic-log";
    runtimeInputs = [ pkgs.coreutils ];
    text = ''
      set -eu

      out=/var/log/panic
      mkdir -p "$out"

      if [ -d /sys/fs/pstore ]; then
        for f in /sys/fs/pstore/*; do
          [ -e "$f" ] || continue
          cp -a "$f" "$out/$(date -u +%Y%m%dT%H%M%SZ)-$(basename "$f")" || true
        done
      fi
    '';
  };
  iocostInit = pkgs.writeShellApplication {
    name = "sinnix-iocost-init";
    runtimeInputs = [
      pkgs.coreutils
      pkgs.gnugrep
    ];
    text = ''
      set -eu

      # io.cost makes IOWeight declarations in the cgroup hierarchy actually
      # effective on NVMe drives. Without it, the kernel ignores IOWeight for
      # any device running the 'none' (passthrough) scheduler — which is the
      # NVMe default — so every IOWeight config in the slice tree is silently
      # discarded. Setting the scheduler to mq-deadline lets the block layer
      # mediate between cgroups, and ctrl=auto calibrates the cost model from
      # the device's actual latency characteristics.
      for dev_path in /sys/block/*/; do
        dev=$(basename "$dev_path")
        echo "$dev" | grep -q "^loop" && continue
        [ -f "$dev_path/queue/scheduler" ] || continue

        major_minor=$(cat "$dev_path/dev")

        scheduler=$(cat "$dev_path/queue/scheduler")
        if echo "$scheduler" | grep -q "\[none\]"; then
          echo "mq-deadline" > "$dev_path/queue/scheduler" || true
        fi

        # Auto-calibrate the cost model from device latency, making IOWeight
        # proportional and work-conserving rather than nominal.
        printf '%s enable=1 ctrl=auto\n' "$major_minor" > /sys/fs/cgroup/io.cost.qos || true
      done
    '';
  };
  applyCpuPowerLimits = pkgs.writeShellApplication {
    name = "sinnix-apply-cpu-power-limits";
    runtimeInputs = [
      pkgs.coreutils
      pkgs.gnugrep
    ];
    text = ''
      set -eu

      package=
      for candidate in /sys/class/powercap/intel-rapl:*; do
        [ -f "$candidate/name" ] || continue
        if grep -qx 'package-0' "$candidate/name"; then
          package="$candidate"
          break
        fi
      done

      [ -n "$package" ] || exit 0

      # Keep the desktop thermal envelope below the i7-13700K's package
      # critical threshold during sustained compile and media workloads.
      printf '%s\n' 95000000 >"$package/constraint_0_power_limit_uw"
      printf '%s\n' 150000000 >"$package/constraint_1_power_limit_uw"
    '';
  };
in
{
  config = lib.mkIf config.sinnix.machine.isDesktop (
    lib.mkMerge [
      (lib.sinnix.mkScheduledJob
        {
          inherit config;
          unitName = "sinnix-tmp-sweep";
          description = "Remove unheld recognized scratch directories";
        }
        {
          # Root can observe non-dumpable holders. The program drops to the
          # declared owner before removal; no privileged deletion is allowed.
          manager = "system";
          user = "root";
          resourceClass = "background";
          execStart = "${scriptPkgs.sinnix-tmp-sweep}/bin/sinnix-tmp-sweep --owner ${lib.escapeShellArg config.sinnix.user.name}";
          environment.TMPDIR = userTmpRoot;
          unit.unitConfig.RequiresMountsFor = [ userTmpRoot ];
          serviceConfig = {
            TimeoutStartSec = "5min";
            NoNewPrivileges = true;
            CapabilityBoundingSet = [
              "CAP_DAC_READ_SEARCH"
              "CAP_SYS_PTRACE"
              "CAP_SETUID"
              "CAP_SETGID"
            ];
            ProtectSystem = "strict";
            ProtectHome = "read-only";
            ReadWritePaths = [
              userTmpRoot
              "/tmp"
            ];
          };
          timer = {
            # Nix scratch uses holder checks; PID-qualified producer scratch
            # also requires a dead allocator and a 24-hour age floor.
            #
            # Persistent catches an elapse missed while logged out.
            intervalSec = 900;
            persistent = true;
            description = "Periodic owned scratch sweep";
          };
        }
      )
      {
        assertions = [
          {
            assertion = lib.all (
              token: !(lib.hasInfix token earlyoomAvoidPattern)
            ) forbiddenEarlyoomAvoidTokens;
            message = "earlyoom must not exempt agents, browsers, language runtimes, or generic shells";
          }
          {
            assertion = lib.hasInfix "start-hyprland" earlyoomAvoidPattern;
            message = "earlyoom must protect the lowercase Hyprland session launcher used by UWSM";
          }
        ];

        # zram is the only swap. An NVMe swapfile overflow tier was removed on
        # 2026-10-27: on 10-27 00:05 agent work filled zram plus 4 GiB of it on
        # the QLC /realm drive, and paging there held IO-full PSI at 74% for
        # the whole host. Overcommit beyond zram is killed, not paged to disk.
        # Telemetry samples zram/PSI/refaults so a thrash regression stays visible.
        zramSwap = {
          enable = true;
          algorithm = "zstd";
          # 12 GiB, sized from a measured 3.6:1 compression ratio under real
          # load; do not raise further without a zram residue-reset hygiene step
          # (incompressible worst case approaches 1:1). Disksize changes apply
          # to /dev/zram0 only on reboot, not on a live switch.
          memoryMax = 12 * 1024 * 1024 * 1024;
          priority = 100;
        };

        systemd.settings.Manager.StatusUnitFormat = "name";

        # No polkit password dialogs for wheel on unit management and power
        # actions: wheel already has NOPASSWD sudo, so the prompt is friction with
        # no security boundary behind it. Deliberately scoped to systemd1 and
        # login1 rather than a blanket YES, so genuinely unusual actions (disk
        # reformat via udisks, etc.) still surface.
        security.polkit.extraConfig = ''
          polkit.addRule(function(action, subject) {
            if (!subject.isInGroup("wheel")) return undefined;
            if (action.id.indexOf("org.freedesktop.systemd1.") === 0) {
              return polkit.Result.YES;
            }
            if (action.id.indexOf("org.freedesktop.login1.") === 0) {
              return polkit.Result.YES;
            }
            return undefined;
          });
        '';

        boot.kernel.sysctl = {
          # zram is the first swap tier, so swapping a cold anonymous page costs
          # a compression, not a disk write. At swappiness 10 the kernel evicted
          # file cache instead and re-read it: over one 11-day uptime file
          # refaults reached 16.6 TiB against 1.4 TiB of swap-ins.
          # The free-page reserve is a small fixed floor against allocation
          # bursts; a 1 GiB reserve with a 2% watermark gap kept ~2 GB idle on a
          # 32 GB host that was swapping.
          "vm.swappiness" = 100;
          "vm.page-cluster" = 0;
          # Kernel default; do not raise. At 1000 dentries/inodes stay permanently
          # cold and PID1 alone re-reads hundreds of GiB/day of unit fragments.
          "vm.vfs_cache_pressure" = 100;
          "vm.min_free_kbytes" = 262144;
          "vm.watermark_scale_factor" = 50;
          # Keep Btrfs writeback from accumulating multi-GiB dirty bursts. The
          # slow drive is bounded on its own (a per-device limit in the host's
          # storage configuration); this global limit is the sum every disk
          # shares, so it is set high enough that one drive's backlog does not
          # pause writers to the others.
          "vm.dirty_background_bytes" = 128 * 1024 * 1024;
          "vm.dirty_bytes" = 1024 * 1024 * 1024;

          # Rebuild and Home Manager activation reload a large user unit/D-Bus
          # surface in bursts. Keep inotify capacity high enough that the bus daemon
          # and the user manager can attach their watches instead of timing out
          # during switch activation.
          "fs.inotify.max_user_watches" = 2097152;
          "fs.inotify.max_user_instances" = 65536;
          "fs.inotify.max_queued_events" = 262144;

          # Preserve crash diagnostics without turning ordinary hung-task reports
          # into automatic workstation reboots.
          "kernel.hung_task_panic" = 0;
          "kernel.hung_task_timeout_secs" = 120;
          "kernel.panic" = 60;
          "kernel.oops_all_cpu_backtrace" = 1;
          "kernel.hardlockup_all_cpu_backtrace" = 1;
          "kernel.softlockup_all_cpu_backtrace" = 1;
        };

        boot.kernelModules = [ "ramoops" ];
        boot.kernelParams = [
          "ramoops.record_size=262144"
          "ramoops.console_size=262144"
          "ramoops.ftrace_size=131072"
          "ramoops.dump_oops=1"
        ];

        systemd.services.sinnix-capture-panic-log = {
          description = "Capture previous-boot kernel panic/oops logs from pstore";
          wantedBy = [ "multi-user.target" ];
          after = [ "local-fs.target" ];
          serviceConfig = {
            Type = "oneshot";
            RemainAfterExit = true;
            ExecStart = "${panicLogCapture}/bin/sinnix-capture-panic-log";
          };
        };

        systemd.services.sinnix-iocost-init = {
          description = "Activate io.cost on all block devices so IOWeight is honoured";
          wantedBy = [ "sysinit.target" ];
          before = [ "sysinit.target" ];
          unitConfig.DefaultDependencies = false;
          serviceConfig = {
            Type = "oneshot";
            RemainAfterExit = true;
            ExecStart = "${iocostInit}/bin/sinnix-iocost-init";
          };
        };

        systemd.services.sinnix-cpu-power-limits = {
          description = "Apply sane Intel CPU package power limits";
          wantedBy = [ "multi-user.target" ];
          after = [ "multi-user.target" ];
          serviceConfig = {
            Type = "oneshot";
            RemainAfterExit = true;
            ExecStart = "${applyCpuPowerLimits}/bin/sinnix-apply-cpu-power-limits";
          };
        };

        # No periodic cache-drop machinery: kernel LRU reclaim is the cache bound,
        # and a drop_caches timer manufactures the pressure it claims to relieve
        # since MemAvailable already counts reclaimable cache.
        services.earlyoom = {
          enable = true;
          enableNotifications = true;
          # Last resort when swap is nearly full AND the host stalls. MemAvailable
          # includes reclaimable cache, so -m3 could veto kills with RAM and zram
          # full while memory.high held jobs in reclaim below every hard limit.
          # -m5 keeps a real memory gate. -m99 (2026-10-27) let a full swap
          # alone trigger kills: on 2026-10-28 03:36 earlyoom killed with 40%
          # of RAM available, because cold pages filled zram while the host
          # stalled on IO. Thrash inside the agent budget is oomd's job
          # (agent-ctl and agent-tool kill on memory pressure and on swap).
          # Scoped oomd targets job/tool descendants; this global fallback
          # also covers pressure outside those trees and swap-ineligible jobs.
          freeMemThreshold = 5;
          # SIGTERM below 10% free swap (~1.2 GiB of 12 GiB zram), SIGKILL
          # below the default half (5%) if SIGTERM cannot recover the host.
          freeSwapThreshold = 10;
          extraArgs = [
            # No --prefer regex: at the stalled-swap floor oom_score ranks victims,
            # and slice-scoped oomd handles "kill the runaway build, not the
            # desktop" at cgroup granularity. Only recovery-critical surfaces are
            # avoided — agents stay eligible victims, since process-name avoidance
            # is not a containment boundary (per-scope MemoryHigh/Max is).
            "--avoid"
            earlyoomAvoidPattern
            # At the near-full-swap emergency floor, full-memory PSI
            # above 10 already makes the graphical session unreliable.
            "--mem-psi-min"
            "10"
          ];
        };

        systemd.services.earlyoom = {
          wants = [ "swap.target" ];
          after = [ "swap.target" ];
        };

        # systemd-oomd is the first-line kill policy. Only sacrificial job/tool
        # trees opt into pressure/swap monitoring in runtime-defaults.nix;
        # coordinator and desktop trees stay outside their candidate sets.
        # earlyoom covers global near-full swap with actual memory stalls.
        systemd.oomd.enable = true;

        # Devshell/agent scratch belongs on /realm NVMe, not the RAM-backed /tmp
        # tmpfs: `nix develop` uses `nix-shell.*` and `nix-develop-*` scratch
        # directories and can leave them after a normal exit. On the
        # 6 GiB /tmp tmpfs that population reaches ENOSPC, which truncates
        # heredocs and gives EMFILE in unrelated processes. The scratch root is
        # private to the operator (0700) rather than a shared 1777 tree, so the
        # sweeper below can decide ownership from the filesystem.
        #
        # Login sessions and the systemd user manager both use this scratch
        # root. System services keep the default /tmp.
        environment.sessionVariables.TMPDIR = userTmpRoot;
        systemd.user.settings.Manager.DefaultEnvironment = "TMPDIR=${userTmpRoot}";
        # The root is declared once in core.nix. Claude Code's separate
        # CLAUDE_CODE_TMPDIR points to this same location.

        systemd.slices =
          (lib.mapAttrs (_: sliceConfig: {
            inherit sliceConfig;
          }) runtimeInventory.slices.system)
          // {
            "user-${primaryUserUid}".sliceConfig = {
              MemoryMin = interactiveMemoryMin;
              MemoryLow = interactiveMemoryLow;
            };
          };

        # This native systemd instance owns the whole desktop and job plane.
        # A drop-in updates its resources without replacing the template or
        # restarting the user manager during activation.
        systemd.units."user@${primaryUserUid}.service" = {
          overrideStrategy = "asDropin";
          # The service builder also injects environment settings. This native
          # drop-in sets only resource policy and activation flags.
          text = ''
            [Service]
            MemoryMin=${interactiveMemoryMin}
            MemoryLow=${interactiveMemoryLow}
            X-RestartIfChanged=false
            X-StopIfChanged=false
          '';
        };

        systemd.user.slices = lib.mapAttrs (_: sliceConfig: {
          inherit sliceConfig;
        }) runtimeInventory.slices.user;

        # Shutdown cost of the graphical session is bounded here, once, for every
        # user unit — Sinnix-owned or not.
        #
        # The tty1 login parks `systemctl --user start --wait
        # wayland-session-envelope@hyprland-uwsm.desktop.target` inside
        # session-1.scope (uwsm's signal-handler.sh, which on SIGTERM stops that
        # target and then waits on the same pid). logind stops the session scope
        # BEFORE the user manager — user@1000.service is ordered
        # Before=session-1.scope, and ordering reverses on stop — so the scope's
        # stop job completes only once the envelope target, and therefore every
        # graphical-session member, has gone inactive. One member that ignores
        # SIGTERM holds the target for its full stop timeout while the session
        # scope burns an identical timeout in parallel, and logind offers no
        # per-scope knob to cap a transient session scope: it inherits the manager
        # default. Bounding that default is the only lever that reaches the whole
        # chain.
        #
        # Measured, not theorised: the 2026-08-14 reboot cost 91s of dead time
        # because a single wedged screen recorder sat in graphical-session.target
        # for the full 90s default. That unit is gone, but the exposure was never
        # specific to it — 44 of the 47 user services running on this host carry
        # the 90s default, so any one of them can reproduce the stall.
        #
        # 15s is Sinnix's established shutdown-debris cap for ordinary services,
        # and Borg jobs.
        # A session helper still alive 15s after SIGTERM is wedged; the choice is
        # not between a clean exit and a kill, it is between killing it now and
        # killing it 75s later. This is only the *default*, so per-unit
        # TimeoutStopSec still wins in either direction — the three user services
        # that already declare their own keep them (uwsm's wayland-wm@ at 10s,
        # nm-applet and at-spi at 5s) — and the system manager's own 90s default
        # is deliberately left alone, since daemons with real flush work sit
        # outside this chain.
        systemd.user.settings.Manager.DefaultTimeoutStopSec = "15s";
      }
    ]
  );
}
