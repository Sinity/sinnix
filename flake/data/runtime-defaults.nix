{ lib }:
let
  mkClass = description: serviceConfig: {
    inherit description serviceConfig;
  };

  # Protect interactive reads on both the store/home SSD and Realm NVMe.
  # io.latency only arbitrates siblings, so the root user slice and the
  # desktop parent must carry this policy as well as app/session children.
  interactiveIoLatency = [
    "/nix 20ms"
    "/realm 20ms"
  ];

  buildSlicePolicy = {
    IOAccounting = true;
    CPUWeight = 5;
    IOWeight = 2;
    MemoryHigh = "10G";
    MemoryMax = "12G";
    ManagedOOMMemoryPressure = "kill";
    ManagedOOMMemoryPressureLimit = "50%";
    ManagedOOMMemoryPressureDurationSec = "30s";
  };

  surfaceType = surface: if surface.manager == "user" then "user" else surface.kind;

  normalizeSurface =
    surface:
    let
      normalized = {
        manager = "system";
        kind = "service";
        resourceClass = "ordinary";
        observe = {
          enable = false;
          restartable = false;
        };
        acknowledged = {
          down = false;
          reason = "";
          since = "";
          ref = "";
        };
        captures = [ ];
        activation = {
          mode = "direct";
          publicEndpoint = null;
          backendEndpoint = null;
          idleTimeout = null;
          exclusiveResource = null;
          dependsOn = [ ];
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
      data =
        capture.data or {
          class = "canonical";
          inputs = [ ];
          source = null;
          preservation = "indefinite";
          fidelity = "source";
          backup = "inherited";
        };
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
        restartable = surface.observe.restartable;
        activationMode = surface.activation.mode;
        acknowledged = surface.acknowledged;
      })
      (
        lib.filterAttrs (_: surface: surface.observe.enable) (lib.mapAttrs (_: normalizeSurface) surfaces)
      );
in
rec {
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
    background = mkClass "Maintenance that should yield to interaction" {
      Nice = 10;
      IOSchedulingClass = "idle";
      CPUWeight = 5;
      IOWeight = 5;
      MemoryHigh = "1G";
      MemoryMax = "3G";
    };
    backup = mkClass "Snapshot and backup jobs" {
      Slice = "background.slice";
      Nice = 10;
      CPUSchedulingPolicy = "idle";
      IOSchedulingClass = "idle";
      CPUWeight = 20;
      IOWeight = 20;
      MemoryHigh = "2G";
      MemoryMax = "4G";
      IOReadBandwidthMax = [
        "/persist 40M"
        "/realm 80M"
        "/outer-realm 40M"
      ];
      IOWriteBandwidthMax = [
        "/persist 20M"
        "/realm 40M"
        "/outer-realm 40M"
      ];
    };
    capture = mkClass "Long-running capture daemons" {
      Nice = 10;
      IOSchedulingClass = "idle";
      IOWeight = 10;
      MemoryHigh = "6G";
      MemoryMax = "8G";
    };
  };

  slices = {
    system = {
      # memory.low protection is limited by every ancestor. This carries the
      # user-manager app/session/shell allocations to the root hierarchy.
      user = {
        IOAccounting = true;
        IODeviceLatencyTargetSec = interactiveIoLatency;
        MemoryLow = "11776M";
      };
      background = {
        CPUWeight = 3;
        IOWeight = 1;
        MemoryHigh = "2G";
        MemoryMax = "4G";
        # PSI-scoped oomd: kill sacrificial work at cgroup granularity when
        # ITS OWN memory pressure stalls it, rather than letting global
        # earlyoom pick victims. 50%/30s (not the 10%/5s defaults) so only a
        # genuinely wedged scope dies, not a busy one.
        ManagedOOMMemoryPressure = "kill";
        ManagedOOMMemoryPressureLimit = "50%";
        ManagedOOMMemoryPressureDurationSec = "30s";
      };
      nix-build = {
        CPUWeight = 5;
        IOWeight = 2;
        # Store restores bypass build concurrency. Bound their device traffic
        # as well as memory; scratch and the store share this device.
        IOReadBandwidthMax = "/nix 80M";
        IOWriteBandwidthMax = "/nix 40M";
        # Daemon builds run outside the AgentCTL work budget. Bound this
        # additional working set so concurrent jobs leave desktop headroom.
        MemoryHigh = "10G";
        MemoryMax = "12G";
        # PSI-scoped oomd: kill sacrificial work at cgroup granularity when
        # ITS OWN memory pressure stalls it, rather than letting global
        # earlyoom pick victims. 50%/30s (not the 10%/5s defaults) so only a
        # genuinely wedged scope dies, not a busy one.
        ManagedOOMMemoryPressure = "kill";
        ManagedOOMMemoryPressureLimit = "50%";
        ManagedOOMMemoryPressureDurationSec = "30s";
      };
      system-critical = {
        IOAccounting = true;
        CPUWeight = 400;
        IOWeight = 300;
        MemoryLow = "2G";
      };
      # System-manager counterparts of the user-side job plane below, for
      # system units that participate in it. The memory ceiling stays on the
      # user side alone: their heavy phases execute as pueue tasks there, and
      # a second MemoryHigh here would double the plane's declared budget.
      agentctl = {
        IOAccounting = true;
        CPUWeight = 10;
        IOWeight = 10;
      };
      agentctl-work = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 100;
      };
    };
    user = {
      # Interactive agent CLIs and their in-process subagents. Claude's Bash
      # tools, MCP servers and ad-hoc builds run in agenttool.slice; heavy
      # declared work belongs to agentctl.slice and keeps its own budget.
      # 2026-09-27 an agent's `uv sync` source-built a C++ wheel here with ~25
      # parallel cc1plus at ~800 MB each; with no ceiling and CPUWeight 400
      # this slice outranked the desktop and took the host to load 74, RAM
      # exhausted and 14 GB of swap.
      agent = {
        IOAccounting = true;
        # Below app/session (100) so the desktop wins contention, above the
        # agentctl job plane (90) so a coordinator stays responsive during a
        # wave. The quota keeps 8 of 24 cores out of reach whatever the
        # weights say, since an idle desktop's share is otherwise lent away.
        CPUWeight = 95;
        CPUQuota = "1600%";
        IOWeight = 100;
        # The agent processes themselves stay resident (measured ~0.6 GB for
        # a coordinator with twenty forks).
        MemoryLow = "3G";
        # Throttle, never kill: every in-process subagent shell is a child of
        # the coordinator's Claude process in the same scope, so an oomd
        # policy here would take the session down with its runaway child.
        # 10G leaves the desktop reservation (app 6G + session 5G +
        # desktop-shell 512M) and the job plane room on a 31 GB host.
        MemoryHigh = "10G";
        # Hard backstop only if throttling cannot hold: the kernel's
        # cgroup-local OOM then picks the largest single process, which for
        # a runaway build is the build, not a ~1 GB agent process.
        MemoryMax = "14G";
        MemorySwapMax = "2G";
        TasksMax = 8192;
      };
      # What interactive agents run: Bash tool commands, stdio MCP servers
      # and their subprocesses, moved here by claude-tool-scope (Claude
      # Code's CLAUDE_CODE_SHELL_PREFIX). A sibling of agent.slice, not a
      # child, so tool memory never counts toward the agent processes'
      # MemoryHigh: on 2026-09-28 a dozen parallel verification gates held
      # agent.slice at its MemoryHigh and the kernel throttled the
      # coordinator itself for hours (sinnix-6to8). Here the tools throttle
      # each other and the supervising process stays responsive.
      agenttool = {
        IOAccounting = true;
        # Just below agent.slice, so the coordinator wins CPU contention
        # against its own tools.
        CPUWeight = 90;
        CPUQuota = "1600%";
        IOWeight = 90;
        # Throttle, never kill: a killed tool is a failed command the agent
        # can retry, but MemoryMax is the backstop against a runaway build.
        MemoryHigh = "12G";
        MemoryMax = "16G";
        MemorySwapMax = "4G";
        TasksMax = 8192;
      };
      app = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 300;
        # Weights share bandwidth only while both sides issue IO; a latency
        # target throttles batch whenever the desktop's own requests wait,
        # which is what swap-in feels like under six lanes.
        IODeviceLatencyTargetSec = interactiveIoLatency;
        # Batch under agentctl.slice grows into swap; the desktop's working
        # set must not be what gets reclaimed to make room for it.
        MemoryLow = "6G";
      };
      session = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 300;
        # Weights share bandwidth only while both sides issue IO; a latency
        # target throttles batch whenever the desktop's own requests wait,
        # which is what swap-in feels like under six lanes.
        IODeviceLatencyTargetSec = interactiveIoLatency;
        # The interactive part of session.slice, measured 2026-09-02 21:30 at
        # 7 GB current. Its 23 GB peak is Claude-session subagents running
        # pytest, which belong in the work slice, not behind this guarantee.
        MemoryLow = "5G";
      };
      # systemd creates this dash-hierarchy parent for desktop-shell.slice.
      # Carry the shell policy to its competition with the other user slices.
      desktop = {
        IOAccounting = true;
        IODeviceLatencyTargetSec = interactiveIoLatency;
        CPUWeight = 400;
        IOWeight = 300;
        MemoryLow = "512M";
      };
      desktop-shell = {
        IOAccounting = true;
        IODeviceLatencyTargetSec = interactiveIoLatency;
        CPUWeight = 400;
        IOWeight = 300;
        MemoryLow = "512M";
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
        CPUWeight = 3;
        IOWeight = 1;
        MemoryHigh = "2G";
        MemoryMax = "4G";
        # PSI-scoped oomd: kill sacrificial work at cgroup granularity when
        # ITS OWN memory pressure stalls it, rather than letting global
        # earlyoom pick victims. 50%/30s (not the 10%/5s defaults) so only a
        # genuinely wedged scope dies, not a busy one.
        ManagedOOMMemoryPressure = "kill";
        ManagedOOMMemoryPressureLimit = "50%";
        ManagedOOMMemoryPressureDurationSec = "30s";
      };
      # Slice names encode hierarchy. This outer slice is the direct sibling
      # of app.slice and session.slice, so its weights govern host contention.
      agentctl = {
        IOAccounting = true;
        # The job plane is the machine's main workload during a wave; at 10 it
        # starved behind an idle desktop and the coordinator's own polls.
        CPUWeight = 90;
        IOWeight = 100;
        # Bound the aggregate job plane, not only its individual pools.
        # Desktop reservations are reclaim protection, not a substitute for
        # a hard limit on background allocations.
        MemoryHigh = "20G";
        MemoryMax = "20G";
        MemorySwapMax = "0";
      };
      agentctl-work = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 100;
      };
      # Each pueue task is a transient service in one of these slices. The
      # outer agentctl.slice and the agent pool are never oomd or swap
      # victims; the pytest leaf pools and bulk are killed at their own pressure. The
      # reservations are fixed against the workstation's 32 GiB physical
      # memory: app 6 GiB, session 5 GiB, desktop shell 512 MiB, and the
      # remaining job plane is admitted by pool rather than free-RAM probes.
      # Zero swap is deliberate for test/build pools: a hostile child must be
      # killed at its own MemoryMax instead of making the desktop page.
      agentctl-agent = {
        IOAccounting = true;
        CPUWeight = 400;
        IOWeight = 300;
        # Held at 8G: with pytest-heavy's 12G it fills the 20G work plane
        # (flake/tests/agent-tools.nix). Worker count, not this ceiling, is
        # the lever: see agent.parallel in modules/services/agentctl.nix.
        MemoryHigh = "8G";
        MemorySwapMax = "0";
      };
      # The agents a landing owns. Same envelope as the agent pool: they are
      # the same kind of process, held apart only so the queue can pause new
      # worker dispatch without stalling a landing.
      # Parent of agentctl-land-agent, by the same name hierarchy that makes
      # agentctl-pytest a parent. It hosts no pool of its own, but it was
      # undeclared and so inherited the plane with no accounting and no
      # ceiling: invisible to cgroup sampling and unbounded below the plane's
      # 20G. Declared here at accounting plus a ceiling that stays above its
      # only child (4G), so it measures the landing without binding it.
      agentctl-land = {
        IOAccounting = true;
        CPUWeight = 400;
        IOWeight = 300;
        MemoryHigh = "6G";
        MemorySwapMax = "0";
      };
      agentctl-land-agent = {
        IOAccounting = true;
        CPUWeight = 400;
        IOWeight = 300;
        MemoryHigh = "4G";
        MemorySwapMax = "0";
      };
      # Slice names encode hierarchy, so this is not just the `pytest` pool: it
      # is also the PARENT of agentctl-pytest-heavy and agentctl-pytest-quick.
      # Its ceiling is what the three pools share, and it is the only one that
      # binds them collectively -- raising a child alone changes nothing.
      #
      # Sized from the measured corpus working set rather than a guess: one
      # xdist worker peaks at 2263 MiB (two independent methods agreeing within
      # 1%; a slot receipt showed 2290 MiB private / 2352 MiB PSS for a managed
      # 4293-test process). Four workers plus the collecting master is
      # 4 * 2263 MiB + ~1 GiB = 10.05 GiB. The build slices show what headroom
      # a working set needs to run without reclaim at all: 18.4-18.6 GiB peak
      # under a 22G ceiling (1.18x) took zero high events. 10.05 GiB * 1.2 is
      # 12.1 GiB, so 12G high / 14G max, and the corpus is sized for four
      # workers -- 4 of 24 cores, because this corpus is memory-bound, not
      # core-bound.
      #
      # 12G is also exactly what the plane can give beside a saturated agent
      # pool: 12G + 8G = the plane's own 20G MemoryHigh. A concurrent quick run
      # therefore pushes this slice past its ceiling on purpose, and the
      # corpus, as the critical path, is what the throttle protects.
      #
      # No ManagedOOMMemoryPressure here, unlike the leaves. A parent's memory
      # PSI is the AGGREGATE of its children, so pressure generated by a busy
      # sibling was attributed to this scope and killed the longest-running
      # task in it: that is how a 1h54m corpus run died at 93% while the quick
      # pool was live (2026-09-14). The correct response to sibling
      # oversubscription is throttling; a genuine runaway is still bounded by
      # MemoryMax and by each leaf's own pressure policy.
      agentctl-pytest = {
        IOAccounting = true;
        # Tests are the wave's critical path; agent processes mostly wait on
        # the API, so the test pools outrank them.
        CPUWeight = 200;
        IOWeight = 200;
        MemoryHigh = "12G";
        MemoryMax = "14G";
        MemorySwapMax = "0";
      };
      # The corpus gate (`verify_all`). Same envelope as its parent: this pool
      # is the reason the parent is 12G, and nothing else may run beside it at
      # full width. The 50%/30s pressure kill stays -- it was never the defect.
      # A scope whose ceiling exceeds its working set by 1.2x does not reclaim,
      # so it does not generate sustained memory PSI; the previous kill was a
      # 6G ceiling under a 10 GiB working set, not a policy that is too eager.
      agentctl-pytest-heavy = {
        IOAccounting = true;
        CPUWeight = 200;
        IOWeight = 200;
        MemoryHigh = "12G";
        MemoryMax = "14G";
        MemorySwapMax = "0";
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
      agentctl-pytest-quick = {
        IOAccounting = true;
        CPUWeight = 200;
        IOWeight = 200;
        MemoryHigh = "9G";
        MemoryMax = "10G";
        MemorySwapMax = "0";
        ManagedOOMMemoryPressure = "kill";
        ManagedOOMMemoryPressureLimit = "50%";
        ManagedOOMMemoryPressureDurationSec = "30s";
      };
      # Bulk work yields to interactive readers and fails within its memory
      # budget. Keeping the soft and hard limits equal avoids prolonged
      # memory.high reclaim before an oversized workload reaches its cap.
      agentctl-bulk = {
        IOAccounting = true;
        CPUWeight = 20;
        IOWeight = 10;
        # IOWeight arbitrates contention through io.cost but does not cap
        # throughput. Share a device ceiling across concurrent bulk jobs,
        # matching the backup class; stricter operation budgets still apply.
        IOReadBandwidthMax = [
          "/realm 80M"
          "/nix 80M"
        ];
        IOWriteBandwidthMax = [
          "/realm 40M"
          "/nix 40M"
        ];
        MemoryHigh = "10G";
        MemoryMax = "10G";
        MemorySwapMax = "0";
        ManagedOOMMemoryPressure = "kill";
        ManagedOOMMemoryPressureLimit = "50%";
        ManagedOOMMemoryPressureDurationSec = "30s";
      };
      agentctl-normal = {
        IOAccounting = true;
        CPUWeight = 50;
        IOWeight = 50;
        # Three concurrent Polylogue verify_quick jobs (parallel gates, ~2-2.6G
        # each) held the old 5G line on 2026-09-28 at 88% full memory
        # pressure, so each ran slower than two unthrottled ones would.
        MemoryHigh = "9G";
        MemoryMax = "10G";
        MemorySwapMax = "0";
      };
      agentctl-interactive = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 100;
        MemoryHigh = "2G";
        MemoryMax = "4G";
        MemorySwapMax = "0";
      };
      # The gateway's shell lanes share this parent by slice-name hierarchy.
      # It hosts no pool; it measures both lanes and stays above the wider
      # child so it never binds either alone.
      agentctl-shell = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 100;
        MemoryHigh = "12G";
        MemorySwapMax = "0";
      };
      # Quick reads (rg, sed, git status) come first for CPU and IO; a runaway
      # one is killed at its own ceiling, never paging the desktop.
      agentctl-shell-quick = {
        IOAccounting = true;
        CPUWeight = 200;
        IOWeight = 200;
        MemoryHigh = "3G";
        MemoryMax = "4G";
        MemorySwapMax = "0";
      };
      # Agent CLIs launched from ChatGPT: 2-3 GiB each, like agentctl-agent
      # workers, and like them throttled rather than killed.
      agentctl-shell-long = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 100;
        MemoryHigh = "10G";
        MemorySwapMax = "0";
      };
      build = buildSlicePolicy;
      nix-build = buildSlicePolicy;
    };
  };

  # An agent CLI puts its outermost process in agent.slice unless it is
  # already inside a declared accounting boundary. These are those
  # boundaries: agent.slice is the interactive plane, and agentctl.slice is the
  # whole job plane — the coordinator, every pool slice, and the per-task
  # scope that carries a lane's MemoryMax and its cancellation reap. Naming
  # the outer slice rather than each pool keeps a new pool from launching an
  # agent that escapes its own budget.
  agentContainedSlices = [
    "agent.slice"
    "agentctl.slice"
  ];
  # Shell `case` pattern matched against /proc/self/cgroup. The separators
  # are load-bearing: "agentctl-agent.slice" ends in "agent.slice"
  # without being it.
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
      surfaces ? baseSurfaces,
      mounts ? [ ],
      backups ? { },
      captures ? [ ],
      dataStores ? { },
    }:
    {
      schema = "sinnix-runtime-inventory-v1";
      inherit
        hostname
        classes
        slices
        ;
      earlyoomEmergencyAvoidPattern = earlyoomPatternFor (lib.mapAttrs (_: normalizeSurface) surfaces);
      surfaces = lib.mapAttrs (_: effectiveSurface classes) surfaces;
      inherit mounts backups dataStores;
      observedServices = observedServiceRows surfaces;
      captures = captureRows surfaces captures;
    };
}
