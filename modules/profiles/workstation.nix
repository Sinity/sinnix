# Interactive workstation profile.
#
# Coarse aggregate for a desktop/interactive host (sinnix-prime). Sets
# `sinnix.machine.isDesktop = true` and owns the resource-governance stack
# that keeps desktop-critical processes protected while build/background
# workloads are explicitly placed into lower-weight slices by
# `sinnix-scope`: systemd slices, earlyoom policy, io.cost init, RAPL power
# caps, and the interactive memory sysctls.
#
# Mirrors modules/profiles/cloud.nix's shape (enable-gated aggregate a host
# opts into) rather than scattering `isDesktop` conditionals across modules.
{
  lib,
  config,
  pkgs,
  ...
}:
let
  cfg = config.sinnix.profiles.workstation;
  runtimeInventory = config.sinnix.runtime.inventory;
  panicLogCapture = pkgs.writeShellApplication {
    name = "panic-log-capture";
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
        # Skip loop devices
        echo "$dev" | grep -q "^loop" && continue
        # Skip if no queue/scheduler
        [ -f "$dev_path/queue/scheduler" ] || continue

        major_minor=$(cat "$dev_path/dev")

        # NVMe uses 'none' by default which disables queue-based IO scheduling.
        # Switch to mq-deadline so cgroup IOWeight can actually take effect.
        scheduler=$(cat "$dev_path/queue/scheduler")
        if echo "$scheduler" | grep -q "\[none\]"; then
          echo "mq-deadline" > "$dev_path/queue/scheduler" || true
        fi

        # Activate iocost cost model — auto-calibrates from device latency.
        # This makes IOWeight proportional and work-conserving rather than nominal.
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
  options.sinnix.profiles.workstation.enable = lib.mkEnableOption "Interactive workstation profile";

  config = lib.mkIf cfg.enable {
    sinnix.machine.isDesktop = lib.mkForce true;

    # Tiered swap posture (2026-07-10, resolves sinnix-mys under the
    # operator axiom "things getting killed >> thrash"): zram is the fast
    # first tier that absorbs allocation bursts at RAM speed, the NVMe
    # swapfile (hosts/sinnix-prime/storage.nix, priority 10) is the overflow
    # tier for sustained pressure. An 8 GiB zram device costs ~20 MiB until
    # used and ~1 byte per ~3 bytes of cold anon it holds (zstd); the
    # earlier "compressed RAM hides pressure" objection is now covered by
    # instrumentation instead of prohibition — machine-telemetry samples
    # zram mm_stat, per-device swap occupancy, PSI, and refaults, so a
    # thrash regression is visible within hours. The 2026-07-09 kill storm
    # (17 rustc SIGTERMs with 7.5 GiB of swap idle) is the failure mode this
    # exists to end: bursts must have somewhere fast to go.
    zramSwap = {
      enable = true;
      algorithm = "zstd";
      # 8G -> 12G (2026-07-10, same night): the first real stress test — 88
      # concurrent test-binary links — filled the 8G tier completely at a
      # measured 3.6:1 ratio (6.9G data in 1.9G RAM, zero kills, ~1% memory
      # PSI) and spilled correctly to the NVMe file. 12G costs ~3.3G
      # resident when full at that ratio and widens the burst absorber; do
      # not go past ~12G on 32G RAM without a zram residue-reset hygiene
      # (dead post-build pages park compressed until faulted or reset —
      # sinnix-mys follow-up) because the incompressible worst case
      # approaches 1:1. Disksize change applies to /dev/zram0 on reboot;
      # a live switch cannot resize an active swap device.
      memoryMax = 12 * 1024 * 1024 * 1024;
      priority = 100;
    };

    systemd.settings.Manager.StatusUnitFormat = "name";

    boot.kernel.sysctl = {
      # Keep process (anon) memory resident; reclaim file cache before swapping,
      # and start reclaim early enough that interactive work sees real free
      # pages instead of relying on last-second cache eviction.
      # Diagnosed 2026-06-07: swappiness=60 + vfs_cache_pressure=50 made the box
      # hoard ~18 GiB page cache while paging ~17 GiB of anon to swap (incl.
      # ~9 GiB to the disk swapfile) despite ~20 GiB available RAM. swappiness=1
      # + vfs_cache_pressure=100 inverted that path. The 2026-06-29 agent/build
      # failure mode was different: truly-free pages were low, zram was full,
      # and new rustc processes needed multi-GiB allocations immediately.
      # Maintain a concrete free-page reserve (min_free_kbytes +
      # watermark_scale_factor) so "available" memory does not depend on
      # painful last-second reclaim.
      #
      # Re-diagnosed 2026-07-09: swappiness=0 left the 4 GiB disk swapfile
      # completely unused (0B, even mid-OOM-kill) while earlyoom repeatedly
      # killed short-lived rustc bursts (~6-7 GiB RSS for 30-60s, single
      # large-crate compiles, not sustained growth) with several GiB of idle
      # swap sitting right there. A brief burst is exactly the case swap
      # should absorb without triggering the 2026-06-07 thrashing pattern
      # (that was *sustained* 17 GiB anon pressure, a different shape). Bumped
      # to a small nonzero value so the kernel prefers swapping a transient
      # spike over an immediate earlyoom kill, without going back to the
      # heavy-swap-hoarding regime that caused the original diagnosis.
      "vm.swappiness" = 10;
      "vm.page-cluster" = 0;
      # 2026-07-10: returned 1000 -> 100 (kernel default) per sinnix-mys.
      # The 2026-06-07 diagnosis actually credited vfs=100 for the fix; 1000
      # was an overshoot that, together with the (now removed) 2-minute
      # drop_caches timer, kept dentries/inodes permanently cold — PID1 alone
      # re-read ~390 GiB/day of unit fragments and mmap'd libraries. Burst
      # headroom is owned by min_free_kbytes + watermark_scale_factor below,
      # not by suppressing the VFS caches.
      "vm.vfs_cache_pressure" = 100;
      "vm.min_free_kbytes" = 1048576;
      "vm.watermark_scale_factor" = 200;
      # Keep Btrfs/NVMe writeback from accumulating multi-GiB dirty bursts.
      # The Crucial P3 /realm drive has shown 30s NVMe command timeouts under
      # mixed build/database writeback; bounded dirty bytes push back earlier
      # and make stalls shorter and more attributable.
      "vm.dirty_background_bytes" = 64 * 1024 * 1024;
      "vm.dirty_bytes" = 256 * 1024 * 1024;

      # Rebuild and Home Manager activation reload a large user unit/D-Bus
      # surface in bursts. Keep inotify capacity high enough that dbus-broker
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

    systemd.services.panic-log-capture = {
      description = "Capture previous-boot kernel panic/oops logs from pstore";
      wantedBy = [ "multi-user.target" ];
      after = [ "local-fs.target" ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        ExecStart = "${panicLogCapture}/bin/panic-log-capture";
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

    # There is deliberately NO periodic cache-drop machinery here. The former
    # sinnix-cache-trim timer ran `sync; echo 3 > drop_caches` every 2 minutes
    # whenever reclaimable cache exceeded 4 GiB. Measured on 2026-07-09/10
    # (machine-telemetry metric_sample): 8-14 MILLION file workingset
    # refaults per hour and ~3.5 TiB/day of block reads (polylogued 1.3T,
    # PID1 ~0.4T re-faulting mmap'd libs/units, machine-telemetry 0.4T) —
    # the trim manufactured the very pressure it claimed to relieve, since
    # MemAvailable already counts reclaimable cache as available. Removed
    # per the operator-approved posture decision (sinnix-mys); kernel LRU
    # reclaim is the cache bound.
    services.earlyoom = {
      enable = true;
      enableNotifications = true;
      # earlyoom acts only when BOTH memory and swap are below threshold.
      # Keep the memory gate tied to real MemAvailable pressure. earlyoom
      # v1.9 computes this percentage against "user mem total"
      # (MemAvailable + AnonPages), which is ~26 GiB on sinnix-prime under
      # current desktop load; 5% is about 1.3 GiB of MemAvailable headroom.
      # Demoted 5 -> 3 (sinnix-3gb, 2026-07-10): with PSI-scoped oomd now
      # killing wedged sacrificial slices (runtime-defaults.nix) and the
      # zram+NVMe swap tiers absorbing bursts, earlyoom is the emergency
      # floor for true exhaustion, not the first responder. History says the
      # first responder role was actively harmful: zero kernel OOMs ever
      # recorded, while earlyoom itself generated the outages (186 kills on
      # 2026-06-30, a 79-process kitten cascade on 07-04, 17 rustc kills on
      # 07-09).
      freeMemThreshold = 3;
      # Re-diagnosed 2026-07-10: 100 was set after the 2026-06-30 desktop
      # stall (314 MiB MemAvailable with swap still empty -- the old ~10%
      # swap gate suppressed the emergency kill until the compositor was
      # already wedged). At the time swap lived on the root SATA SSD, so
      # letting swap fill up meant fighting for I/O with everything else on
      # that disk -- waiting for it to help was actively harmful. freeSwap
      # Threshold=100 made the swap condition a no-op (any nonzero swap
      # usage satisfies "below 100% free"), so earlyoom fires the instant
      # MemAvailable alone dips under freeMemThreshold, regardless of how
      # much swap capacity sits idle.
      #
      # Since the swapfile moved to /realm (NVMe, hosts/sinnix-prime/
      # storage.nix) and vm.swappiness went 0 -> 10, that tradeoff no
      # longer holds: swap I/O is fast and doesn't contend with anything
      # wear-sensitive or latency-critical. Confirmed live the same night
      # a fresh rustc burst got SIGTERM'd with swap at 97.6% free (465 MiB
      # of 8 GiB used) -- the swap capacity that should have absorbed the
      # spike was sitting idle because the gate never gave it a chance.
      # Loosened to 50: lets a burst use up to ~4 GiB of swap before
      # earlyoom panics (a real grace window, unlike 100), while still
      # acting well before swap is anywhere near exhausted (unlike the old
      # ~10% default that caused the June wedge).
      freeSwapThreshold = 50;
      extraArgs = [
        # No --prefer regex (removed 2026-07-10, sinnix-3gb): victim steering
        # was an arms race of same-day threshold rewrites, and at the -m3
        # floor earlyoom only fires at true exhaustion where oom_score-based
        # choice is appropriate. Slice-scoped oomd now handles the "kill the
        # runaway build, not the desktop" case at cgroup granularity.
        #
        # Protect interactive surfaces. Coding agents (`claude`, `codex`, and
        # their node/python runtime/MCP children) are interactive work and are
        # avoided like the desktop apps so launching one never evicts another.
        # Also avoid Nix activation/control-plane processes and local dev
        # daemons; they are coordination surfaces, not bulk memory consumers.
        "--avoid"
        "(systemd|systemd-logind|dbus-daemon|dbus-broker|dbus-broker-launch|sshd|agetty|Hyprland|Xwayland|noctalia|quickshell|xdg-desktop-portal|pipewire|wireplumber|foot|kitty|zsh|bash|sudo|doas|below|weechat|asciinema|aw-server|chrome|chromium|firefox|electron|claude|codex|node|python|serena|polylogue|lynchpin|sinexd|postgres|nats-server|nix|nix-daemon)"
      ];
    };

    systemd.services.earlyoom = {
      wants = [ "swap.target" ];
      after = [ "swap.target" ];
    };

    # systemd-oomd is the first-line kill policy (sinnix-3gb, 2026-07-10):
    # sacrificial slices (build/nix-build/background, both scopes) carry
    # ManagedOOMMemoryPressure=kill at 50%/30s in runtime-defaults.nix, so a
    # wedged build dies as a cgroup while the desktop and agents never
    # qualify. The earlier false-positive history was the 10%/5s defaults
    # (killed Codex 2026-05-07) — the 50%/30s gate only fires on scopes that
    # are genuinely stalled on their own memory. earlyoom remains the global
    # emergency floor at -m3.
    systemd.oomd.enable = true;

    # Devshell/agent scratch belongs on /realm NVMe, not the RAM-backed /tmp
    # tmpfs. `nix develop` creates its per-shell TMPDIR (nix-shell.XXXXXX)
    # under the ambient TMPDIR, and heavy test suites (lynchpin pytest duckdb
    # fixtures) write GiBs there; every shell gets a fresh dir, so per-tool
    # retention (e.g. pytest's keep-last-3) never prunes across sessions.
    # 2026-07-09: 345 accumulated dirs pinned 5.8 GiB of the 6 GiB /tmp tmpfs
    # as unreclaimable shmem and drove that evening's earlyoom storm
    # (sinnix-7yd). Pointing the session TMPDIR at NVMe keeps /tmp tmpfs for
    # small system churn while shell/test scratch lands on wear-tolerant
    # storage with age-based cleanup (the `7d` field below; NVMe contents
    # also survive reboots, unlike tmpfs, hence the aging is load-bearing).
    environment.sessionVariables.TMPDIR = "/realm/tmp/shell";
    systemd.tmpfiles.rules = [ "d /realm/tmp/shell 1777 root root 7d" ];

    # nix.slice has no explicit unit here: it exists only as the implicit
    # dash-hierarchy parent of nix-build.slice (systemd creates parent slices
    # automatically), and it has exactly one child, so giving it its own
    # CPUWeight/IOWeight (previously byte-identical to nix-build.slice's) had
    # no sibling to compete against and did nothing.
    systemd.slices = lib.mapAttrs (_: sliceConfig: {
      inherit sliceConfig;
    }) runtimeInventory.slices.system;

    systemd.user.slices = lib.mapAttrs (_: sliceConfig: {
      inherit sliceConfig;
    }) runtimeInventory.slices.user;
  };
}
