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

  # The desktop's guarantee in MiB (MemoryMin: never reclaimed). Measured
  # 2026-11-02..16: app.slice p50 3.9G p95 4.6G, session 0.9-1.5G, the shell
  # 1.0G. Beyond its guarantee the desktop competes with unprotected memory,
  # which is almost all agent work.
  desktopMemory = rec {
    chromeMin = 3072;
    appMin = 4096;
    compositorMin = 768;
    sessionMin = 1536;
    shellMin = 1024;
    totalMin = appMin + sessionMin + shellMin;
  };

  # The host's memory budget, in MiB (docs/resource-control.md). Every line
  # outside agent work is memory the kernel keeps for its owner (MemoryMin,
  # or MemoryLow sized to the owner's working set); agent work's hard
  # ceiling is what remains. Agents therefore meet their own ceiling before
  # the host runs out, and anything that grows past its line is paid for by
  # reclaiming and then killing agent work, never the desktop or a service.
  hostMemory = rec {
    # MemTotal on sinnix-prime.
    ram = 31923;
    # Kernel memory no cgroup is charged for (slab, vmalloc, stacks, about
    # 1.3 GiB) and the free-page watermarks (min_free_kbytes 256 MiB).
    kernel = 2048;
    # The zram store (workstation.nix): 9 GiB of swapped pages from every
    # cgroup, compressed about 3:1, held in RAM.
    zram = 3072;
    desktop = desktopMemory.totalMin;
    # The huge-page reservation for shared buffers (bridge.nix: 2,202 pages,
    # 4.3 GiB, charged to the unit) plus 1.2 GiB of backends and cache.
    postgresql = 5632;
    sinexd = 1024;
    nats = 128;
    journaldCapture = 128;
    # The Polylogue daemon (1.5 GiB) and the session producer.
    polylogue = 1536;
    sessionProducer = 256;
    userLive = polylogue + sessionProducer;
    systemLive = postgresql + sinexd + nats + journaldCapture;
    # Other system daemons (system.slice, 0.9 GiB median) and recovery tools.
    systemServices = 1024;
    systemCritical = 256;
    # The user capture producers and ActivityWatch (0.3 GiB together).
    captureProducers = 512;
    protected =
      desktop + systemLive + userLive + systemServices + systemCritical + captureProducers;
    agents = ram - kernel - zram - protected;
  };
  # The ceiling actually set on agent.slice, rounded down from the remainder.
  agentMemory = rec {
    max = 9216;
    # Interactive sessions: protected up to their measured p95 (3.0 GiB).
    cliLow = 3072;
    cliHigh = 6144;
    cliMax = 7168;
    toolMax = 5120;
    # The job plane: room for the largest single job (a Sinnix check peaks
    # at 6.1-6.4G, a Sinex focused build at 6.9G); the sessions' protection,
    # not this ceiling, keeps them resident when the plane and the sessions
    # together reach the agent ceiling.
    planeMax = 8192;
  };
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
  # Read by the live units' resources (bridge.nix, polylogue.nix). Agent
  # work's ceiling never exceeds what the budget leaves it.
  memoryBudget =
    assert lib.assertMsg (
      agentMemory.max <= hostMemory.agents
      && agentMemory.cliMax <= agentMemory.max
      && agentMemory.planeMax <= agentMemory.max
      && agentMemory.toolMax <= agentMemory.max
    ) "agent memory ceilings exceed what the host memory budget leaves for agent work";
    hostMemory;

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
        MemoryLow = mib memoryBudget.systemServices;
      };
      # The live class's system units (Sinex PostgreSQL, sinexd, NATS, the
      # journald capture). Equal to user.slice for the disk; see the live
      # class.
      live = {
        IOAccounting = true;
        CPUWeight = 400;
        IOWeight = 400;
        # memory.low is limited by every ancestor, so the live units' own
        # protection counts only up to this slice's.
        MemoryLow = mib memoryBudget.systemLive;
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
        # The user manager's live and capture slices are protected only
        # within this. With memory_recursiveprot, protection a child does not
        # use passes to its siblings, agent work included, so this equals
        # the budget lines below it and nothing more: at 14G (a soft Low of
        # 12G for the desktop) agent work inherited most of the slack and the
        # kernel reclaimed Chrome beside it.
        MemoryLow = mib (desktopMemory.totalMin + memoryBudget.userLive + memoryBudget.captureProducers);
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
        MemoryLow = mib memoryBudget.systemCritical;
      };
    };
    user = {
      # The agent budget: every kind of agent work runs below this one slice
      # (interactive CLIs, their tool commands and MCP servers, and the
      # agentctl job plane). Its MemoryMax is the remainder of the host
      # budget (memoryBudget above, docs/resource-control.md), so agent work
      # meets this ceiling before the host runs short: reclaim and the
      # out-of-memory killer then act inside this slice, where the victim is
      # the job or tool with the highest OOM score (agentctl sets 900 on job
      # units, claude-tool-scope 800 on tool commands, the CLIs 300).
      # Only the CLIs have a MemoryHigh. On this slice, the job plane and the
      # tool slice a MemoryHigh held runaway allocators throttled for
      # minutes without ever reaching the ceiling, while oomd's pressure
      # rule killed bystanders that were being reclaimed (a build, another
      # session's tool command). At a MemoryMax the kernel reclaims and
      # swaps first and then kills the largest of the highest-scored
      # processes at once.
      agent = {
        IOAccounting = true;
        # Below app and session (100) and the shell (400). The quota equals
        # all 16 threads, so only the weights hold agents back from the
        # desktop.
        CPUWeight = 60;
        CPUQuota = "1600%";
        # IOCost lends idle shares while favoring the desktop under contention.
        IOWeight = 25;
        MemoryMax = mib agentMemory.max;
        # Idle sessions compress into zram (about 3:1) instead of pinning RAM;
        # 4G of swapped agent pages hold about 1.3G of the zram store.
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
        # The sessions' measured p95 (all sessions, 3.0G) stays resident, so
        # reclaim inside the budget lands on jobs and tools first.
        MemoryLow = mib agentMemory.cliLow;
        # Throttle, never kill: every in-process subagent shell is a child of
        # the coordinator's Claude process in the same scope, so an oomd
        # policy here would take the session down with its runaway child.
        # The band between Low and High keeps page cache for the CLIs
        # themselves, so a keystroke never re-reads the CLI from disk.
        MemoryHigh = mib agentMemory.cliHigh;
        # Hard backstop only if throttling cannot hold: the kernel's
        # cgroup-local OOM then picks the largest single process, which for
        # a runaway build is the build, not a ~1 GB agent process.
        MemoryMax = mib agentMemory.cliMax;
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
        # The ceiling ends a runaway command (the largest at score 800); the
        # pressure rule ends sustained thrash among many commands.
        MemoryMax = mib agentMemory.toolMax;
        MemorySwapMax = "2G";
        ManagedOOMMemoryPressure = "kill";
        ManagedOOMMemoryPressureLimit = "50%";
        ManagedOOMMemoryPressureDurationSec = "20s";
        # At oomd's global swap threshold, offer command scopes (not
        # coordinator sessions) to its swap ranking.
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
        MemoryLow = mib memoryBudget.userLive;
      };
      app = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 300;
        # Chrome claims part of this guaranteed memory. IO weights do not
        # guarantee latency.
        MemoryMin = mib desktopMemory.appMin;
      };
      session = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 300;
        # Hyprland (claiming desktopMemory.compositorMin), kitty, PipeWire and
        # the portals need about 0.9 GiB together.
        MemoryMin = mib desktopMemory.sessionMin;
      };
      # systemd creates this dash-hierarchy parent for desktop-shell.slice.
      # Carry the shell policy to its competition with the other user slices.
      desktop = {
        IOAccounting = true;
        CPUWeight = 400;
        IOWeight = 300;
        MemoryMin = mib desktopMemory.shellMin;
      };
      # The shell has its own memory protection.
      desktop-shell = {
        IOAccounting = true;
        CPUWeight = 400;
        IOWeight = 300;
        MemoryMin = mib desktopMemory.shellMin;
      };
      backup = {
        IOAccounting = true;
        CPUWeight = 20;
        IOWeight = 20;
        MemoryHigh = "8G";
        MemoryMax = "12G";
      };
      # The user capture producers and ActivityWatch. Their working set is
      # protected; the ceiling, six times what they use together, ends a
      # leak or a bulk job started here instead of in the job plane.
      background = {
        IOAccounting = true;
        CPUWeight = 20;
        IOWeight = 20;
        MemoryLow = mib memoryBudget.captureProducers;
        MemoryMax = "3G";
      };
      # The agentctl job plane: pueued (agent-ctl-work.slice) and every pool
      # slice below it, in what the sessions leave of the agent budget.
      # Peak memory per job, page cache included: Polylogue focused p50 3.6G
      # p90 5.5G, Sinex focused p90 6.9G, Sinnix check 6.1-6.4G, compile and
      # Clippy 2.0-3.4G. The plane holds one large job, or one test build
      # beside one type check; beyond that the kernel ends the largest job at
      # the ceiling, and the owner sees "out of memory" (docs/agentctl.md).
      agent-ctl = {
        IOAccounting = true;
        # Give queued work enough CPU to make progress alongside the desktop.
        CPUWeight = 90;
        IOWeight = 100;
        MemoryMax = mib agentMemory.planeMax;
        # A job's own cold pages are cheaper to page than its page cache is to
        # re-read.
        MemorySwapMax = "2G";
        # Sustained reclaim among several jobs below the ceiling: monitor the
        # whole plane so every pool contributes eligible job units. 40% full
        # PSI means all runnable work is stalled for two fifths of
        # the sampling window; 15s above it tolerates short allocation bursts
        # but sacrifices the job with most reclaim before minutes of thrash.
        # Only descendants are selected, so pueued and job units are candidates;
        # agent-cli and the desktop are outside this tree.
        ManagedOOMMemoryPressure = "kill";
        ManagedOOMMemoryPressureLimit = "40%";
        ManagedOOMMemoryPressureDurationSec = "15s";
        # At oomd's global swap threshold (workstation.nix), rank eligible
        # descendants by swap use, even without local pressure.
        ManagedOOMSwap = "kill";
      };
      agent-ctl-work = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 100;
      };
      # Pueue tasks run in pool slices under the plane's ceiling. A pool sets
      # its own memory limit only where it is tighter than the plane's.
      agent-ctl-agent = {
        IOAccounting = true;
        CPUWeight = 400;
        IOWeight = 300;
        MemorySwapMax = "1G";
      };
      # Codex workers (`codex` operation): light processes, ~136 MB resident
      # each, that spend most of their time waiting on builds in other pools.
      agent-ctl-codex = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 100;
        MemoryHigh = "3G";
        MemoryMax = "4G";
        MemorySwapMax = "1G";
      };
      # The parent of the pytest-heavy and pytest-quick pools as well, by
      # slice-name hierarchy.
      agent-ctl-pytest = {
        IOAccounting = true;
        # Tests are the wave's critical path; agent processes mostly wait on
        # the API, so the test pools outrank them.
        CPUWeight = 200;
        IOWeight = 200;
        MemorySwapMax = "2G";
      };
      # The corpus gate: one xdist worker peaks at 2.3 GiB, so the plane holds
      # two workers and the collecting process.
      agent-ctl-pytest-heavy = {
        IOAccounting = true;
        CPUWeight = 200;
        IOWeight = 200;
        MemorySwapMax = "2G";
        ManagedOOMMemoryPressure = "kill";
        ManagedOOMMemoryPressureLimit = "50%";
        ManagedOOMMemoryPressureDurationSec = "30s";
      };
      # Short, bounded pytest selections (one file, one worker's focused
      # check): a separate pool so they never queue behind the corpus.
      agent-ctl-pytest-quick = {
        IOAccounting = true;
        CPUWeight = 200;
        IOWeight = 200;
        MemoryHigh = "4G";
        MemoryMax = "5G";
        MemorySwapMax = "1G";
        ManagedOOMMemoryPressure = "kill";
        ManagedOOMMemoryPressureLimit = "50%";
        ManagedOOMMemoryPressureDurationSec = "30s";
      };
      # Bulk work yields to interactive reads.
      agent-ctl-bulk = {
        IOAccounting = true;
        CPUWeight = 20;
        IOWeight = 10;
        MemorySwapMax = "2G";
        ManagedOOMMemoryPressure = "kill";
        ManagedOOMMemoryPressureLimit = "50%";
        ManagedOOMMemoryPressureDurationSec = "30s";
      };
      # Focused Cargo test builds, 2-7 GiB each.
      agent-ctl-normal = {
        IOAccounting = true;
        CPUWeight = 50;
        IOWeight = 50;
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
      # It hosts no pool; it measures both lanes.
      agent-ctl-shell = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 100;
        MemorySwapMax = "2G";
      };
      # Quick reads (rg, sed, git status) come first for CPU and IO; a runaway
      # one is killed at its own ceiling.
      agent-ctl-shell-quick = {
        IOAccounting = true;
        CPUWeight = 200;
        IOWeight = 200;
        MemoryHigh = "3G";
        MemoryMax = "4G";
        MemorySwapMax = "512M";
      };
      # Agent CLIs launched from ChatGPT: 2-3 GiB each, like agent-ctl-agent
      # workers.
      agent-ctl-shell-long = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 100;
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
      # Rust type and lint checks, 3-4 GiB each; their metadata writes take
      # priority over test builds.
      agent-ctl-compile = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 100;
        MemorySwapMax = "1G";
      };
      # One benchmark or measurement at a time. Its numbers are only valid on
      # a quiet host, so it runs throttled by nothing but the plane: no
      # pressure kill, ordinary weights. agentctl marks measurement units as
      # the OOM killers' last choice.
      agent-ctl-measure = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 100;
        MemorySwapMax = "2G";
      };
      # One full workstation build (`sinnix:build_system`); evaluation runs
      # here, the derivations in the Nix daemon.
      agent-ctl-system-build = {
        IOAccounting = true;
        CPUWeight = 20;
        IOWeight = 10;
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
