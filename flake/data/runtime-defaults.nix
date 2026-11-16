{ lib }:
let
  mkClass = description: serviceConfig: {
    inherit description serviceConfig;
  };

  # The workstation's IOCost initializer owns every physical block device.
  # IOLatency shares incompatible blkcg delay state with IOCost, so these
  # policies use relative weights rather than simultaneous latency targets.

  # Two four-core builds fit the 10G ceiling with bounded swap and low weights;
  # pressure killing would terminate nix-daemon and every connected client.
  buildSlicePolicy = {
    IOAccounting = true;
    CPUWeight = 20;
    IOWeight = 20;
    MemoryHigh = "10G";
    MemoryMax = "12G";
    MemorySwapMax = "4G";
  };

  # Desktop memory is in MiB: Min protects memory from reclaim; Low protects
  # the larger working set while unprotected memory remains.
  desktopMemory = rec {
    chromeMin = 3072;
    appMin = 4096;
    appLow = 8192;
    compositorMin = 768;
    sessionMin = 1536;
    sessionLow = 3072;
    shellMin = 1024;
    shellLow = 1024;
    totalMin = appMin + sessionMin + shellMin;
    totalLow = appLow + sessionLow + shellLow;
  };
  # Protect the user services that process live session data, in MiB.
  userLiveLow = 3072;
  mib = value: "${toString value}M";

  surfaceType = surface: if surface.manager == "user" then "user" else surface.kind;

  normalizeSurface =
    surface:
    let
      normalized = {
        manager = "system";
        kind = lib.last (lib.splitString "." surface.unit);
        resourceClass = "ordinary";
        notifyOnFailure = false;
        operatorRestart = false;
        expectedDown = null;
        captures = [ ];
        activation = {
          mode = "direct";
          publicEndpoint = null;
          backendEndpoint = null;
          idleTimeout = null;
          exclusiveResource = null;
        };
        workload = {
          class = "unclassified";
          rationale = "";
          processMatchers = [ ];
          earlyoomAvoid = false;
        };
        resources = { };
      }
      // surface;
    in
    normalized
    // {
      effectiveResources = lib.filterAttrs (_: value: value != null) normalized.resources;
    };

  effectiveSurface =
    resourceClasses: surface:
    let
      normalized = normalizeSurface surface;
      classResources = resourceClasses.${normalized.resourceClass}.serviceConfig or { };
    in
    normalized
    // {
      effectiveResources =
        classResources // lib.filterAttrs (_: value: value != null) normalized.resources;
    };

  # One lane, normalized for the inventory. Split out of captureRows so the
  # shared capture fields are preserved for both surface-owned and standalone
  # lanes. captureRows adds the declared producer binding without guessing
  # a unit for standalone data.
  captureRow =
    capture:
    {
      inherit (capture) name path;
    }
    // lib.optionalAttrs ((capture.producerProgressPath or null) != null) {
      inherit (capture) producerProgressPath;
    }
    // lib.optionalAttrs ((capture.cadenceSeconds or null) != null) {
      expectedCadenceSeconds = capture.cadenceSeconds;
    }
    // lib.optionalAttrs (capture.eventDriven or false) {
      expectedCadence = "event-driven";
    }
    // lib.optionalAttrs ((capture.staleAfterSeconds or null) != null) {
      expectedStaleAfterSeconds = capture.staleAfterSeconds;
    }
    // lib.optionalAttrs ((capture.requiredPayloadFields or [ ]) != [ ]) {
      inherit (capture) requiredPayloadFields;
    }
    // lib.optionalAttrs ((capture.livenessProbe or null) != null) {
      inherit (capture) livenessProbe;
    };

  captureRows =
    surfaces: standalone:
    (lib.concatLists (
      lib.mapAttrsToList (
        name: surface:
        map (
          capture:
          (captureRow capture)
          // {
            producer = {
              surface = name;
              inherit (surface) unit manager;
            };
          }
        ) surface.captures
      ) (lib.mapAttrs (_: normalizeSurface) surfaces)
    ))
    ++ map (capture: (captureRow capture) // { producer = null; }) standalone;

  observedServiceRows =
    surfaces:
    lib.mapAttrsToList
      (name: surface: {
        inherit name;
        inherit (surface)
          kind
          manager
          resourceClass
          unit
          ;
        workload = surface.workload;
        type = surfaceType surface;
        inherit (surface) operatorRestart expectedDown;
        activationMode = surface.activation.mode;
      })
      (
        lib.filterAttrs (_: surface: surface.notifyOnFailure) (lib.mapAttrs (_: normalizeSurface) surfaces)
      );
in
rec {
  # Read by the Chrome launcher and the Hyprland unit, which claim their
  # share of the desktop guarantee on their own units.
  inherit desktopMemory;

  # Global earlyoom is only the last-resort floor. Per-scope cgroups own
  # workload containment; this process-name fallback protects only surfaces
  # needed to keep or recover the graphical/login session. Agents, language
  # runtimes, browsers, and generic shells deliberately remain eligible.
  # Single base list: earlyoomPatternFor extends exactly this with the
  # processMatchers of surfaces that opt in via workload.earlyoomAvoid.
  # Entries match unanchored against /proc/<pid>/comm (15 chars max, hence
  # the truncated xdg-desktop-po): keep entries <=15 chars, and only for
  # processes that can exist on our hosts.
  earlyoomEmergencyAvoidBase = [
    "systemd"
    "systemd-logind"
    "dbus-daemon"
    "sshd"
    "agetty"
    "uwsm"
    "start-hyprland"
    "Hyprland"
    "Xwayland"
    "noctalia"
    "xdg-desktop-po"
    "pipewire"
    "wireplumber"
    "kitty"
    "below"
    "nix-daemon"
  ];
  earlyoomEmergencyAvoidPattern = "(${lib.concatStringsSep "|" earlyoomEmergencyAvoidBase})";

  classes = {
    ordinary = mkClass "Services without shared resource overrides" { };
    critical = mkClass "Services needed to observe or regain control" {
      Slice = "system-critical.slice";
      Nice = -5;
      IOSchedulingClass = "best-effort";
      IOSchedulingPriority = 0;
    };
    # Use low best-effort priority: idle IO can delay scheduled jobs indefinitely.
    background = mkClass "Maintenance that should yield to interaction" {
      Nice = 10;
      IOSchedulingClass = "best-effort";
      IOSchedulingPriority = 7;
      CPUWeight = 20;
      IOWeight = 20;
      MemoryHigh = "1G";
      MemoryMax = "3G";
    };
    # Borg needs about 3 GB for caches; no bandwidth caps, because a capped
    # btrfs writer can hold a transaction that interactive writers wait on.
    backup = mkClass "Snapshot and backup jobs" {
      Slice = "background.slice";
      Nice = 10;
      IOSchedulingClass = "best-effort";
      IOSchedulingPriority = 7;
      CPUWeight = 20;
      IOWeight = 20;
      MemoryHigh = "4G";
      MemoryMax = "8G";
    };
    # Live services and the desktop share priority; bulk work uses a lower class.
    live = mkClass "The live record and its database" {
      Slice = "live.slice";
    };
    capture = mkClass "Long-running capture daemons" {
      Nice = 10;
      IOSchedulingClass = "best-effort";
      IOSchedulingPriority = 7;
      IOWeight = 20;
      MemoryHigh = "6G";
      MemoryMax = "8G";
    };
  };

  slices = {
    system = {
      # Input and other critical system services share this accounted ancestor.
      system = {
        IOAccounting = true;
      };
      # The live class's system units (Sinex PostgreSQL, sinexd, NATS, the
      # journald capture). Equal to user.slice for the disk; see the live
      # class.
      live = {
        IOAccounting = true;
        CPUWeight = 400;
        IOWeight = 400;
        # PostgreSQL memory protection also requires protection on this ancestor.
        MemoryLow = "6G";
      };
      # memory.min and memory.low are limited by every ancestor. This
      # carries the desktop's guarantee (app, session and shell slices) to
      # the root hierarchy; workstation.nix repeats it on user-<uid>.slice
      # and user@<uid>.service.
      user = {
        IOAccounting = true;
        # Give the desktop equal disk weight with live system services.
        IOWeight = 400;
        MemoryMin = mib desktopMemory.totalMin;
        # The user manager's live slice is protected only within this.
        MemoryLow = mib (desktopMemory.totalLow + userLiveLow);
      };
      # Individual units set memory limits; the shared slice yields IO.
      background = {
        CPUWeight = 20;
        IOWeight = 20;
      };
      # The daemon and every build it runs live here (nix-build.slice is
      # its only child), so this weight is the builds' share at the root
      # level. Builds and devshells are agent work and yield to the desktop.
      nix = {
        IOAccounting = true;
        IOWeight = 25;
      };
      nix-build = buildSlicePolicy;
      system-critical = {
        IOAccounting = true;
        CPUWeight = 400;
        IOWeight = 300;
        MemoryLow = "2G";
      };
    };
    user = {
      # Agent slices share a budget alongside the protected desktop, live
      # services and kernel; MemoryHigh is 3G below MemoryMax.
      agent = {
        IOAccounting = true;
        # Below app and session (100) and the shell (400). The quota equals
        # all 16 threads, so only the weights hold agents back from the
        # desktop.
        CPUWeight = 60;
        CPUQuota = "1600%";
        # IOCost lends idle shares while favoring the desktop under contention.
        IOWeight = 25;
        # At 20G/22G the host hit a global OOM twice on 2026-11-02 (03:25,
        # 03:50): agents near their ceiling beside live and rehearsal
        # PostgreSQL and the desktop left the kernel nothing, and it killed a
        # build's rustc from outside any agent slice. 19G leaves the desktop's
        # 6.5G guarantee, live services (5-9G) and the kernel their share, so
        # agent work is throttled or killed inside this slice first. Swap
        # stays small: agents are reclaimed or killed, never paged to the QLC
        # NVMe.
        #
        # 19G was sized against 31 GiB. Since 2026-11-09 PostgreSQL's shared
        # buffers hold 4.5 GiB of that as huge pages, which no cgroup is
        # charged for and reclaim cannot touch. On 2026-11-16 the budget
        # stood at 12.3G anonymous plus its 2G of swap, far below 16G, while
        # the host had 17.4G anonymous, 9.5G in zram and 2.2G of page cache
        # in total: this slice kept 0.6G of page cache and spent 98% of the
        # time stalled re-reading its own binaries, at under 1% memory
        # pressure, so neither oomd nor earlyoom acted for half an hour.
        # What the host can give agents beside huge pages (4.5G), kernel
        # slab and page tables (2.6G), the zram store (3-4G when full), the
        # desktop and the live services is about 12.5G, page cache included.
        # The ceiling sits below that so agents meet their own limit, where
        # the stall counts as this budget's memory pressure and the job
        # plane's oomd policy ends it. More swap lets idle sessions compress
        # (about 3:1) instead of pinning RAM.
        MemoryHigh = "10G";
        MemoryMax = "12G";
        MemorySwapMax = "4G";
        TasksMax = 16384;
      };
      # Interactive agents run here; their tools and declared jobs use sibling slices.
      agent-cli = {
        IOAccounting = true;
        # Above the tools and the job plane, so a coordinator stays
        # responsive during a wave.
        CPUWeight = 100;
        IOWeight = 100;
        # The agent processes themselves stay resident while tools and jobs
        # fill the budget (~0.6 GB for a coordinator with twenty forks; all
        # sessions together 1.9 GB on 2026-10-27; fourteen sessions held
        # 5.1G resident and 1.5G swapped on 2026-11-16). The protection
        # covers the sessions in use, so reclaim at the budget's MemoryHigh
        # lands on jobs and tools first.
        MemoryLow = "5G";
        # Throttle, never kill: every in-process subagent shell is a child of
        # the coordinator's Claude process in the same scope, so an oomd
        # policy here would take the session down with its runaway child.
        # At 6G, fourteen sessions sat on the limit with 0.16G of page cache
        # between them and every keystroke re-read the CLI from disk.
        MemoryHigh = "8G";
        # Hard backstop only if throttling cannot hold: the kernel's
        # cgroup-local OOM then picks the largest single process, which for
        # a runaway build is the build, not a ~1 GB agent process.
        MemoryMax = "10G";
        MemorySwapMax = "4G";
        TasksMax = 8192;
      };
      # Tool commands and MCP servers use a sibling slice, so their memory
      # does not count against agent-cli.slice MemoryHigh.
      agent-tool = {
        IOAccounting = true;
        # Just below agent-cli.slice, so the coordinator wins CPU contention
        # against its own tools.
        CPUWeight = 90;
        IOWeight = 90;
        # Pressure killing selects a command scope; the ceiling and swap limit
        # bound total tool memory.
        MemoryHigh = "8G";
        MemoryMax = "10G";
        MemorySwapMax = "2G";
        ManagedOOMMemoryPressure = "kill";
        ManagedOOMMemoryPressureLimit = "50%";
        ManagedOOMMemoryPressureDurationSec = "20s";
        # Global swap exhaustion can precede this slice's pressure threshold.
        # Offer command scopes (not coordinator sessions) to oomd's swap ranking.
        ManagedOOMSwap = "kill";
        TasksMax = 8192;
      };
      # The live class's user units (the session producer, Polylogue's live
      # daemon): equal to the desktop slices (300) for the disk, far above
      # agent (25); see the live class.
      live = {
        IOAccounting = true;
        CPUWeight = 200;
        IOWeight = 300;
        MemoryLow = mib userLiveLow;
      };
      app = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 300;
        # Chrome claims part of this guaranteed memory; Low protects the rest
        # while unprotected memory remains. IO weights do not guarantee latency.
        MemoryMin = mib desktopMemory.appMin;
        MemoryLow = mib desktopMemory.appLow;
      };
      session = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 300;
        # Hyprland (claiming desktopMemory.compositorMin), kitty, PipeWire and
        # the portals need about 0.9 GiB together.
        MemoryMin = mib desktopMemory.sessionMin;
        MemoryLow = mib desktopMemory.sessionLow;
      };
      # systemd creates this dash-hierarchy parent for desktop-shell.slice.
      # Carry the shell policy to its competition with the other user slices.
      desktop = {
        IOAccounting = true;
        CPUWeight = 400;
        IOWeight = 300;
        MemoryMin = mib desktopMemory.shellMin;
        MemoryLow = mib desktopMemory.shellLow;
      };
      # The shell has its own memory protection.
      desktop-shell = {
        IOAccounting = true;
        CPUWeight = 400;
        IOWeight = 300;
        MemoryMin = mib desktopMemory.shellMin;
        MemoryLow = mib desktopMemory.shellLow;
      };
      backup = {
        IOAccounting = true;
        CPUWeight = 20;
        IOWeight = 20;
        MemoryHigh = "8G";
        MemoryMax = "12G";
      };
      background = {
        IOAccounting = true;
        CPUWeight = 20;
        IOWeight = 20;
      };
      # The agentctl job plane: pueued (agent-ctl-work.slice) and every pool
      # slice below it. Its own ceiling leaves the agent CLIs' and tools'
      # share of the budget; the budget, not this slice, bounds it against
      # the desktop.
      agent-ctl = {
        IOAccounting = true;
        # Give queued work enough CPU to make progress alongside the desktop.
        CPUWeight = 90;
        IOWeight = 100;
        # Builds, up to four by pool width (normal 1, bulk 1, compile 2).
        # Peak memory per job since 2026-11-01, page cache included: Polylogue
        # focused p50 3.6G p90 5.5G, Sinex focused/exec p90 6.8-6.9G, compile
        # and Clippy p90 2.0-3.4G, so four typical builds would sum to ~13G,
        # which the host does not have beside the sessions: the plane holds
        # two typical builds or one large one, and a third is throttled and
        # then ended by the oomd policy below instead of stalling the host.
        # The plane sits 2G below the agent budget.
        MemoryHigh = "8G";
        MemoryMax = "10G";
        # Bounded swap for the plane as a whole. With none, a job at its
        # ceiling could only drop page cache (6 TiB of re-reads over one
        # 11-day uptime). A job's own cold pages are the cheaper thing to
        # page. Within the budget's own 2G.
        MemorySwapMax = "2G";
        # MemoryHigh can hold the plane in reclaim indefinitely below MemoryMax.
        # Monitor the whole plane so every pool contributes eligible job units.
        # 40% full PSI means all runnable work is stalled for two fifths of
        # the sampling window; 15s above it tolerates short allocation bursts
        # but sacrifices the job with most reclaim before minutes of thrash.
        # Only descendants are selected, so pueued and job units are candidates;
        # agent-cli and the desktop are outside this tree. Do not monitor agent.
        ManagedOOMMemoryPressure = "kill";
        ManagedOOMMemoryPressureLimit = "40%";
        ManagedOOMMemoryPressureDurationSec = "15s";
        # At oomd's global RAM/swap threshold (SwapUsedLimit, default 90%),
        # rank eligible descendants by swap use, even without local pressure.
        # oomd requires a victim to use >5% of total swap; small jobs may be
        # ineligible, so earlyoom remains the global stalled-host fallback.
        ManagedOOMSwap = "kill";
      };
      agent-ctl-work = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 100;
      };
      # Pueue tasks run in pool slices; the parent monitors their combined
      # pressure and limits total swap. Pool widths limit concurrent tasks.
      agent-ctl-agent = {
        IOAccounting = true;
        CPUWeight = 400;
        IOWeight = 300;
        # Worker count, not this ceiling, is the lever: see agent.parallel in
        # modules/services/agentctl.nix.
        MemoryHigh = "8G";
        MemorySwapMax = "1G";
      };

      # Codex workers (`codex` operation): many light processes, ~136 MB
      # resident each, that spend most of their time waiting on builds in
      # other pools. Width, not this ceiling, is the lever.
      agent-ctl-codex = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 100;
        MemoryHigh = "8G";
        MemoryMax = "10G";
        MemorySwapMax = "1G";
      };

      # Four test workers at about 2263 MiB each plus a 1 GiB master need 10 GiB;
      # 12G high adds 20% margin shared by pytest, heavy and quick pools.
      agent-ctl-pytest = {
        IOAccounting = true;
        # Tests are the wave's critical path; agent processes mostly wait on
        # the API, so the test pools outrank them.
        CPUWeight = 200;
        IOWeight = 200;
        MemoryHigh = "12G";
        MemoryMax = "14G";
        MemorySwapMax = "2G";
      };
      # Full corpus tests share the parent ceiling and have pressure monitoring.
      agent-ctl-pytest-heavy = {
        IOAccounting = true;
        CPUWeight = 200;
        IOWeight = 200;
        MemoryHigh = "12G";
        MemoryMax = "14G";
        MemorySwapMax = "2G";
        ManagedOOMMemoryPressure = "kill";
        ManagedOOMMemoryPressureLimit = "50%";
        ManagedOOMMemoryPressureDurationSec = "30s";
      };
      # Short, bounded pytest selections (one file, one worker's focused
      # check): a separate pool so they never queue behind the corpus.
      # The ceiling is shared by every running quick job. Keep it above their
      # measured combined peak so memory.high does not create sustained reclaim
      # that triggers oomd for healthy focused runs. The 12G parent arbitrates
      # this pool against concurrent heavy tests.
      agent-ctl-pytest-quick = {
        IOAccounting = true;
        CPUWeight = 200;
        IOWeight = 200;
        MemoryHigh = "9G";
        MemoryMax = "10G";
        MemorySwapMax = "1G";
        ManagedOOMMemoryPressure = "kill";
        ManagedOOMMemoryPressureLimit = "50%";
        ManagedOOMMemoryPressureDurationSec = "30s";
      };
      # Bulk work yields to interactive reads; separate high and max limits
      # allow reclaim and swap before reaching the hard ceiling.
      agent-ctl-bulk = {
        IOAccounting = true;
        CPUWeight = 20;
        IOWeight = 10;
        MemoryHigh = "12G";
        MemoryMax = "14G";
        MemorySwapMax = "2G";
        ManagedOOMMemoryPressure = "kill";
        ManagedOOMMemoryPressureLimit = "50%";
        ManagedOOMMemoryPressureDurationSec = "30s";
      };
      agent-ctl-normal = {
        IOAccounting = true;
        CPUWeight = 50;
        IOWeight = 50;
        # Focused Cargo test builds peak at 2-7 GiB each and the pool runs
        # one; the plane's own ceiling bounds normal and bulk together.
        MemoryHigh = "12G";
        MemoryMax = "14G";
        MemorySwapMax = "2G";
      };
      agent-ctl-interactive = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 100;
        MemoryHigh = "2G";
        MemoryMax = "4G";
        MemorySwapMax = "512M";
      };
      # The gateway's shell lanes share this parent by slice-name hierarchy.
      # It hosts no pool; it measures both lanes and stays above the wider
      # child so it never binds either alone.
      agent-ctl-shell = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 100;
        MemoryHigh = "12G";
        MemorySwapMax = "2G";
      };
      # Quick reads (rg, sed, git status) come first for CPU and IO; a runaway
      # one is killed at its own ceiling, never paging the desktop.
      agent-ctl-shell-quick = {
        IOAccounting = true;
        CPUWeight = 200;
        IOWeight = 200;
        MemoryHigh = "3G";
        MemoryMax = "4G";
        MemorySwapMax = "512M";
      };
      # Agent CLIs launched from ChatGPT: 2-3 GiB each, like agent-ctl-agent
      # workers, and like them throttled rather than killed.
      agent-ctl-shell-long = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 100;
        MemoryHigh = "10G";
        MemorySwapMax = "2G";
      };
      # Offloads and copies: the lowest I/O weight in the plane, so builds
      # and interactive reads keep the disk while a copy runs.
      agent-ctl-background = {
        IOAccounting = true;
        CPUWeight = 10;
        IOWeight = 5;
        MemoryHigh = "4G";
        MemoryMax = "6G";
        MemorySwapMax = "512M";
      };
      # Two type and lint checks at 3-4 GiB each fit in 8G; their metadata
      # writes take priority over test builds.
      agent-ctl-compile = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 100;
        MemoryHigh = "8G";
        MemoryMax = "10G";
        MemorySwapMax = "1G";
      };
      # One benchmark or measurement at a time. Its numbers are only valid on
      # a quiet host, so it runs throttled by nothing but its own ceiling: no
      # pressure kill, ordinary weights.
      agent-ctl-measure = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 100;
        # No MemoryLow: under recursive protection a child's low is bounded by
        # its ancestors', and the user manager's 15G is claimed in full by
        # the desktop and live slices, so it would be inert. agentctl marks
        # measurement units as the OOM killers' last choice instead.
        MemoryHigh = "12G";
        MemoryMax = "14G";
        MemorySwapMax = "2G";
      };
      # One full workstation build (`sinnix:build_system`); evaluation runs
      # here, the derivations in the Nix daemon.
      agent-ctl-system-build = {
        IOAccounting = true;
        CPUWeight = 20;
        IOWeight = 10;
        MemoryHigh = "8G";
        MemoryMax = "10G";
        MemorySwapMax = "2G";
      };
      # The switch commands place their evaluation scope here.
      nix-build = buildSlicePolicy;
    };
  };

  # An agent CLI puts its outermost process in agent-cli.slice unless it is
  # already inside a declared accounting boundary. These are those
  # boundaries: agent-cli.slice is the interactive plane, and agent-ctl.slice
  # is the whole job plane — the coordinator, every pool slice, and the
  # per-task scope that carries a lane's MemoryMax and its cancellation reap.
  # Naming the outer slice rather than each pool keeps a new pool from
  # launching an agent that escapes its own budget. An agent started from a
  # tool command (agent-tool.slice) moves to agent-cli.slice like one started
  # from a terminal.
  agentContainedSlices = [
    "agent-cli.slice"
    "agent-ctl.slice"
  ];
  # Shell `case` pattern matched against /proc/self/cgroup. The separators
  # are load-bearing: "agent-ctl-agent.slice" begins with "agent-ctl"
  # without being agent-ctl.slice.
  agentContainedCasePattern = lib.concatMapStringsSep "|" (
    slice: ''*"/${slice}/"*''
  ) agentContainedSlices;

  baseSurfaces = {
    sshd = {
      unit = "sshd.service";
      resourceClass = "critical";
    };
    nix-gc = {
      unit = "nix-gc.service";
      resourceClass = "background";
    };
  };

  earlyoomPatternFor =
    surfaces:
    let
      protectedMatchers = lib.concatLists (
        lib.mapAttrsToList (
          _: surface:
          if surface.workload.earlyoomAvoid or false then surface.workload.processMatchers or [ ] else [ ]
        ) surfaces
      );
    in
    "(${lib.concatStringsSep "|" (lib.unique (earlyoomEmergencyAvoidBase ++ protectedMatchers))})";

  mkInventory =
    {
      hostname ? "",
      units ? baseSurfaces,
      mounts ? [ ],
      captures ? [ ],
    }:
    {
      schema = "sinnix-runtime-inventory-v2";
      inherit hostname slices;
      earlyoomEmergencyAvoidPattern = earlyoomPatternFor (lib.mapAttrs (_: normalizeSurface) units);
      units = lib.mapAttrs (_: effectiveSurface classes) units;
      inherit mounts;
      observedServices = observedServiceRows units;
      captures = captureRows units captures;
    };
}
