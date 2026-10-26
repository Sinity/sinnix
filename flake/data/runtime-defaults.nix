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

  # Nix evaluation and builds: low weights so they yield, a memory ceiling
  # sized for two parallel jobs on a 32 GB host, and no pressure kill. On
  # 2026-10-18 oomd killed nix-daemon itself, with every connected client,
  # at 50% pressure under the then 10G/12G ceiling. A build that outgrows
  # MemoryMax loses its largest process to the kernel instead. The daemon
  # is a system service, so its builds cannot join the user manager's agent
  # budget (below) and keep a budget of their own: 12G/16G with unbounded
  # swap let builds and agents together exceed RAM by half. Two parallel
  # builds at four cores each fit 10G; the swap allowance keeps them from
  # filling the swap the agent budget is sized against.
  buildSlicePolicy = {
    IOAccounting = true;
    CPUWeight = 20;
    IOWeight = 20;
    MemoryHigh = "10G";
    MemoryMax = "12G";
    MemorySwapMax = "4G";
  };

  # The desktop's memory, in MiB, measured 2026-10-27 under agent load
  # (resident plus swapped): Chrome 4.3 GiB (6.6 GiB with many tabs on
  # 2026-10-19), Hyprland 0.6 GiB, the noctalia shell 1.0 GiB, kitty,
  # PipeWire and the portals 0.3 GiB. That night all of it was swapped out
  # behind MemoryLow alone: low is best effort, and once the agents'
  # ceilings together exceeded RAM nothing unprotected was left to reclaim.
  # The `Min` values are a hard guarantee, never reclaimed; `Low` covers the
  # larger working set as long as anything unprotected remains.
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
    # Yielding classes use the lowest best-effort priority and low weights,
    # never the idle IO class. Under mq-deadline an idle request waits up to
    # 10 s whenever anything else is queued, and on this host something
    # always is: idle-class jobs with deadlines (a 70 GB integrity scan, the
    # speech pass, the filesystem index) ran at a few MB/s and timed out.
    background = mkClass "Maintenance that should yield to interaction" {
      Nice = 10;
      IOSchedulingClass = "best-effort";
      IOSchedulingPriority = 7;
      CPUWeight = 20;
      IOWeight = 20;
      MemoryHigh = "1G";
      MemoryMax = "3G";
    };
    # Borg holds ~3 GB of chunk index and files cache for the realm
    # repository; a 2G MemoryHigh pushed it into swap on every run.
    # No device bandwidth caps: on btrfs a capped writer can hold a
    # transaction that uncapped interactive writers then wait on.
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
      # Input and other critical system services share system.slice. Give
      # that ancestor the same target so protecting the user slice cannot
      # throttle the input route at their root-level competition.
      system = {
        IOAccounting = true;
        IODeviceLatencyTargetSec = interactiveIoLatency;
      };
      # memory.min and memory.low are limited by every ancestor. This
      # carries the desktop's guarantee (app, session and shell slices) to
      # the root hierarchy; workstation.nix repeats it on user-<uid>.slice
      # and user@<uid>.service.
      user = {
        IOAccounting = true;
        IODeviceLatencyTargetSec = interactiveIoLatency;
        # The desktop lives here, and the agents inside it carry their own
        # low weight one level down. With the default 100 the user slice
        # shared a saturated disk evenly with system services and builds,
        # and Chrome waited in iocost throttling (ioc_rqos_throttle).
        IOWeight = 400;
        MemoryMin = mib desktopMemory.totalMin;
        MemoryLow = mib desktopMemory.totalLow;
      };
      # Low weights, and per-unit memory limits from each unit's class. A
      # shared 2G ceiling here made every scheduled job reclaim against the
      # others, and IOWeight 1 on top of idle IO gave them nothing at all.
      background = {
        CPUWeight = 20;
        IOWeight = 20;
      };
      # The daemon and every build it runs live here (nix-build.slice is
      # its only child), so this weight is the builds' share at the root
      # level. It used to carry the desktop's latency target so store
      # queries were never throttled, but that also put builds level with
      # the desktop. Builds and devshells are agent work and yield to it.
      nix = {
        IOAccounting = true;
        IOWeight = 25;
      };
      nix-build = buildSlicePolicy;
      system-critical = {
        IOAccounting = true;
        IODeviceLatencyTargetSec = interactiveIoLatency;
        CPUWeight = 400;
        IOWeight = 300;
        MemoryLow = "2G";
      };
    };
    user = {
      # The agent budget. Every kind of agent work runs below this one
      # slice: interactive CLIs (agent-cli), their tool commands, MCP servers
      # and the devkit test PostgreSQL (agent-tool), and the agentctl job
      # plane with every pool (agent-ctl). Slice names encode hierarchy, so
      # an agent-* slice is a child of this one.
      #
      # Until 2026-10-27 the three were siblings of the desktop with ceilings
      # of their own (10G, 12G and 20G high), together a third more than the
      # host's RAM, and the desktop's best-effort MemoryLow was all that stood
      # between them and Chrome. That night they held 18 GiB resident and
      # 5 GiB of swap, memory pressure stalled every task 18% of the time,
      # and Chrome, Hyprland and the shell were swapped out.
      #
      # Sized so the desktop and the live services always fit beside it on
      # this 31 GiB host: desktop guarantee 6.5 (desktopMemory.totalMin) +
      # system services ~6 (Sinex PostgreSQL's 4G buffers, sinexd, the
      # critical slice) + kernel and compressed swap ~2.5 + MemoryMax 16.
      # MemoryHigh throttles the agents 2G before that. The swap allowance
      # lets cold agent pages go to zram rather than making agents re-read
      # page cache, and it is all the swap agent work can take.
      agent = {
        IOAccounting = true;
        # Below app and session (100) and the shell (400). The quota keeps a
        # third of the 24 threads out of reach whatever the weights say,
        # since an idle desktop's share is otherwise lent away.
        CPUWeight = 60;
        CPUQuota = "1600%";
        # iocost lends an idle sibling's share, so a low weight costs agents
        # nothing while the desktop is quiet and gives the desktop ~97% of
        # the disk when it is not. At 90-100 per agent slice, three of them
        # held as much weight as the whole desktop.
        IOWeight = 25;
        MemoryHigh = "14G";
        MemoryMax = "16G";
        MemorySwapMax = "6G";
        TasksMax = 16384;
      };
      # Interactive agent CLIs and their in-process subagents. Claude's Bash
      # tools, MCP servers and ad-hoc builds run in agent-tool.slice; heavy
      # declared work belongs to agent-ctl.slice.
      # 2026-09-27 an agent's `uv sync` source-built a C++ wheel here with ~25
      # parallel cc1plus at ~800 MB each; with no ceiling and CPUWeight 400
      # this slice outranked the desktop and took the host to load 74, RAM
      # exhausted and 14 GB of swap.
      agent-cli = {
        IOAccounting = true;
        # Above the tools and the job plane, so a coordinator stays
        # responsive during a wave.
        CPUWeight = 100;
        IOWeight = 100;
        # The agent processes themselves stay resident while tools and jobs
        # fill the budget (~0.6 GB for a coordinator with twenty forks; all
        # sessions together 1.9 GB on 2026-10-27).
        MemoryLow = "2G";
        # Throttle, never kill: every in-process subagent shell is a child of
        # the coordinator's Claude process in the same scope, so an oomd
        # policy here would take the session down with its runaway child.
        MemoryHigh = "6G";
        # Hard backstop only if throttling cannot hold: the kernel's
        # cgroup-local OOM then picks the largest single process, which for
        # a runaway build is the build, not a ~1 GB agent process.
        MemoryMax = "8G";
        MemorySwapMax = "2G";
        TasksMax = 8192;
      };
      # What interactive agents run: Bash tool commands, stdio MCP servers
      # and their subprocesses, moved here by claude-tool-scope (Claude
      # Code's CLAUDE_CODE_SHELL_PREFIX). A sibling of agent-cli.slice, not a
      # child, so tool memory never counts toward the agent processes'
      # MemoryHigh: on 2026-09-28 a dozen parallel verification gates held
      # the agent slice at its MemoryHigh and the kernel throttled the
      # coordinator itself for hours (sinnix-6to8). Here the tools throttle
      # each other and the supervising process stays responsive until the
      # whole budget is full.
      agent-tool = {
        IOAccounting = true;
        # Just below agent-cli.slice, so the coordinator wins CPU contention
        # against its own tools.
        CPUWeight = 90;
        IOWeight = 90;
        # Kill, not throttle, once the tools as a whole thrash. A killed tool
        # is a failed command the agent can retry; throttling at MemoryHigh
        # instead held every session's commands in reclaim and swap for half
        # an hour on 2026-10-19 (one 11.3G real-data run beside other
        # sessions' builds). oomd kills the descendant with the most reclaim,
        # which here is one command's scope; claude-tool-scope gives each
        # command its own. There is no per-command ceiling: a big command on
        # a quiet host is fine, and only contention that actually stalls the
        # slice is acted on. MemoryMax and the small swap allowance end a
        # single runaway inside this slice instead of across the budget.
        MemoryHigh = "8G";
        MemoryMax = "10G";
        MemorySwapMax = "2G";
        ManagedOOMMemoryPressure = "kill";
        ManagedOOMMemoryPressureLimit = "50%";
        ManagedOOMMemoryPressureDurationSec = "20s";
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
        # Chrome alone measured 6.6G on 2026-10-19, when 6G of MemoryLow let
        # it be swapped out (3 GB) and video stuttered. The guarantee covers
        # Chrome's resident core (the launcher claims desktopMemory.chromeMin
        # of it for the browser unit); Low covers the rest while the agents
        # still hold anything reclaimable.
        MemoryMin = mib desktopMemory.appMin;
        MemoryLow = mib desktopMemory.appLow;
      };
      session = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 300;
        IODeviceLatencyTargetSec = interactiveIoLatency;
        # Hyprland (its unit claims desktopMemory.compositorMin), kitty,
        # PipeWire and the portals: 0.9 GiB together on 2026-10-27, when
        # Hyprland's 0.6 GiB was mostly swapped out. The 2026-09 figure of
        # 7 GB included agent sessions that now start in agent-cli.slice.
        MemoryMin = mib desktopMemory.sessionMin;
        MemoryLow = mib desktopMemory.sessionLow;
      };
      # systemd creates this dash-hierarchy parent for desktop-shell.slice.
      # Carry the shell policy to its competition with the other user slices.
      desktop = {
        IOAccounting = true;
        IODeviceLatencyTargetSec = interactiveIoLatency;
        CPUWeight = 400;
        IOWeight = 300;
        MemoryMin = mib desktopMemory.shellMin;
        MemoryLow = mib desktopMemory.shellLow;
      };
      # The noctalia shell: 1.0 GiB on 2026-10-27, 0.7 GiB of it swapped out.
      desktop-shell = {
        IOAccounting = true;
        IODeviceLatencyTargetSec = interactiveIoLatency;
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
        # The job plane is the agents' main workload during a wave; at 10 it
        # starved behind an idle desktop and the coordinator's own polls.
        CPUWeight = 90;
        IOWeight = 100;
        MemoryHigh = "12G";
        MemoryMax = "14G";
        # Bounded swap for the plane as a whole. With none, a job at its
        # ceiling could only drop page cache (6 TiB of re-reads over one
        # 11-day uptime). A job's own cold pages are the cheaper thing to
        # page.
        MemorySwapMax = "5G";
      };
      agent-ctl-work = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 100;
      };
      # Each pueue task is a transient service in one of these slices. The
      # plane and the agent pool are never oomd victims; the pytest leaf
      # pools and bulk are killed at their own pressure. Pools are admitted
      # by width and adaptive headroom (which reads every ancestor's limits,
      # the budget's included), not by free-RAM probes. Each pool may swap a
      # little of its own memory; MemoryMax still ends a runaway, and the
      # plane's MemorySwapMax bounds the total.
      agent-ctl-agent = {
        IOAccounting = true;
        CPUWeight = 400;
        IOWeight = 300;
        # Worker count, not this ceiling, is the lever: see agent.parallel in
        # modules/services/agentctl.nix.
        MemoryHigh = "8G";
        MemorySwapMax = "1G";
      };

      # Slice names encode hierarchy, so this is not just the `pytest` pool: it
      # is also the PARENT of agent-ctl-pytest-heavy and agent-ctl-pytest-quick.
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
      # core-bound. 12G is the whole plane: a corpus run beside a busy agent
      # pool is throttled by the plane, not given more of the host.
      #
      # No ManagedOOMMemoryPressure here, unlike the leaves. A parent's memory
      # PSI is the AGGREGATE of its children, so pressure generated by a busy
      # sibling was attributed to this scope and killed the longest-running
      # task in it: that is how a 1h54m corpus run died at 93% while the quick
      # pool was live (2026-09-14). The correct response to sibling
      # oversubscription is throttling; a genuine runaway is still bounded by
      # MemoryMax and by each leaf's own pressure policy.
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
      # The corpus gate (`verify_all`). Same envelope as its parent: this pool
      # is the reason the parent is 12G, and nothing else may run beside it at
      # full width. The 50%/30s pressure kill stays -- it was never the defect.
      # A scope whose ceiling exceeds its working set by 1.2x does not reclaim,
      # so it does not generate sustained memory PSI; the previous kill was a
      # 6G ceiling under a 10 GiB working set, not a policy that is too eager.
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
      # Bulk work yields to interactive readers and fails within its memory
      # budget. MemoryHigh sits below MemoryMax so an oversized job reclaims
      # and swaps its own pages before the hard cap; equal limits with no swap
      # made bulk drop and re-read its page cache instead (4.86 TiB of
      # refaults in one uptime), and an 80M read cap made each re-read slow.
      # Cargo builds peak at 5-8 GiB each; the cargo cap admits two across
      # pools, and this slice holds them up to the plane's ceiling. At 8G/10G
      # two concurrent checks reclaimed against each other until oomd killed
      # one after 53 minutes (2026-10-25).
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
        # Focused Cargo test builds peak at 2-6 GiB each and the pool runs
        # three; the plane's own ceiling bounds normal and bulk together.
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
      # One benchmark or measurement at a time. Its numbers are only valid on
      # a quiet host, so it runs throttled by nothing but its own ceiling: no
      # pressure kill, ordinary weights.
      agent-ctl-measure = {
        IOAccounting = true;
        CPUWeight = 100;
        IOWeight = 100;
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
