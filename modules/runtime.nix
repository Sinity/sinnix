# Runtime inventory registry
#
# One source of truth for Sinnix runtime units, resource classes, systemd
# slices, static slice budgets, and capture inventory.
{
  lib,
  config,
  helpers,
  pkgs,
  ...
}:
let
  cfg = config.sinnix;
  inherit (helpers.data) runtimeDefaults;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  resourceClassNames = builtins.attrNames runtimeDefaults.classes;

  # Sinnix's single failure-report path: a unit that enters `failed`
  # reports itself, so nothing has to poll it. It routes into the hub-server,
  # which owns the health sweep, rather than appending to the ledger directly:
  # one schema and one dedup state for both the OnFailure path and the sweep.
  # When they kept separate keys the same unit re-notified on every failure and
  # its recovery never paired with the outage (2026-08-14, on
  # borgbackup-status.service). `emit-failure` posts to the running hub server and
  # falls back to writing the same transition itself when the hub server is down,
  # which is exactly a moment when units fail.
  #
  # umask 0002 because this runs as root while the hub server runs as the
  # operator: both write the same two files in /run/sinnix, which is setgid
  # `users` for that reason.
  #
  # One body, two templates: a user-manager unit cannot OnFailure into a
  # system template, and only the systemctl scope differs.
  unitFailureNotify = pkgs.writeShellApplication {
    name = "sinnix-unit-failure-notify";
    runtimeInputs = [
      pkgs.systemd
      scriptPkgs.sinnix-hub-server
    ];
    text = ''
      umask 0002
      unit="$1"
      if [ "''${2:-}" = "--user" ]; then
        manager=user
        result="$(systemctl --user show "$unit" -p Result --value 2>/dev/null || true)"
      else
        manager=system
        result="$(systemctl show "$unit" -p Result --value 2>/dev/null || true)"
      fi
      sinnix-hub-server emit-failure --unit "$unit" --result "''${result:-unknown}" --manager "$manager"
    '';
  };

  units = config.sinnix.runtime.units;
  surfaceRows = lib.mapAttrsToList (name: surface: {
    inherit name;
    inherit (surface)
      kind
      manager
      resourceClass
      unit
      ;
  }) units;
  surfaceUnitKeys = map (surface: "${surface.manager}:${surface.unit}") surfaceRows;
  duplicateSurfaceUnitKeys = lib.unique (
    builtins.filter (
      key: (builtins.length (builtins.filter (candidate: candidate == key) surfaceUnitKeys)) > 1
    ) surfaceUnitKeys
  );
  mountMonitoring = [
    {
      path = cfg.paths.realmRoot;
      warnPct = 80;
      failPct = 90;
    }
    {
      # /outer-realm holds the Borg destination. Like /realm, a full
      # filesystem prevents new durable state from being written, so apply
      # the existing critical-storage headroom policy rather than the
      # high-occupancy /neo-outer-realm media policy below.
      path = cfg.paths.outerRealm;
      warnPct = 80;
      failPct = 90;
    }
    {
      # /neo-outer-realm is a bulk media archive, not a service write path:
      # nothing on it is a live database, a snapshot queue, or a backup
      # destination, so "nearly full" is its normal working state rather than
      # an incident. The /realm thresholds exist because a full /realm stalls
      # capture lanes and Postgres; neither failure mode exists here, and an
      # 80/90 pair on a 13T drive pages at 1.3T free. Give it a band that
      # actually means something: warn where a large addition could still be
      # refused, fail where writes are genuinely at risk. On 13T each point is
      # ~130G, so 97/98 is 390G/260G free -- and the warn line sits ABOVE the
      # 95% the drive already reads, because a warning that is true the moment
      # it is declared is a permanent page, not a warning.
      path = cfg.paths.neoOuterRealm;
      warnPct = 97;
      failPct = 98;
    }
  ];

  # One shape for a capture lane, used in two places: inline on a runtime
  # surface that owns its own lane, and standalone in sinnix.runtime.captures
  # for a lane whose writer is not a systemd unit at all. Those used to be the
  # same option, which forced three surfaces to put a shell script's name in a
  # field typed "systemd unit name" and carved a `kind = "capture"` hole in the
  # assertion that checks it. A lane is not a unit; now it does not have to
  # pretend to be one.
  captureLaneType = lib.types.submodule {
    options = {
      name = lib.mkOption { type = lib.types.str; };
      path = lib.mkOption { type = lib.types.str; };
      producerProgressPath = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        description = ''
          Optional producer-owned marker updated only after real output is
          committed. The health sweep can stat this one path when its bounded
          file scan cannot determine freshness.
        '';
      };
      cadenceSeconds = lib.mkOption {
        type = lib.types.nullOr lib.types.int;
        default = null;
      };
      eventDriven = lib.mkOption {
        type = lib.types.bool;
        default = false;
      };
      staleAfterSeconds = lib.mkOption {
        type = lib.types.nullOr lib.types.int;
        default = null;
        description = ''
          Absolute staleness budget in seconds, independent of
          cadenceSeconds. Event-driven lanes (eventDriven = true)
          have no numeric cadence for the health sweep's 2*cadence
          staleness check, so this is the only signal that flags
          them stale when writes stop. Lanes with a numeric
          cadenceSeconds may set this too; the health sweep flags a
          lane stale when EITHER threshold is exceeded.
        '';
      };
      livenessProbe = lib.mkOption {
        type = lib.types.nullOr (
          lib.types.submodule {
            options = {
              command = lib.mkOption {
                type = lib.types.str;
                description = ''
                  Shell snippet (run as `bash -c "$command"` under
                  `timeout`) answering "is the thing this lane
                  observes actually present and publishing?" --
                  a check on the UPSTREAM source, distinct from
                  whether the lane's own unit is active
                  (systemctl is-active is already covered
                  elsewhere and is precisely the check that
                  missed sinnix-pev0's a11y incident: the unit,
                  listeners, and bus were all healthy while the
                  AT-SPI registry root had zero children
                  published).

                  Exit-code contract the health sweep relies on:
                  0 = present, 1 = confirmed absent, anything
                  else (including a timeout's 124) = unknown.
                  A probe that cannot determine the answer must
                  exit something other than 0 or 1 -- silently
                  exiting 0 on failure is exactly the bug class
                  this option exists to catch.
                '';
              };
              timeoutSeconds = lib.mkOption {
                type = lib.types.ints.positive;
                default = 5;
                description = ''
                  Bound on the probe's runtime. The health sweep runs
                  on a 1-minute cadence against every capture
                  lane, so a hung probe must not hang the sweep;
                  a timeout is reported as unknown, never healthy.
                '';
              };
            };
          }
        );
        default = null;
        description = ''
          Optional upstream-liveness probe. Most lanes have no
          cheap probe available -- leave this null and the lane
          behaves exactly as it did before this option existed.
          staleAfterSeconds alone can only detect "no writes
          recently"; it structurally cannot distinguish a
          legitimately quiet lane from one whose upstream
          publisher never registered in the first place, so
          lanes where that distinction is cheaply checkable
          should declare a probe here instead of relying solely
          on a longer budget.
        '';
      };
      requiredPayloadFields = lib.mkOption {
        type = lib.types.listOf lib.types.str;
        default = [ ];
        example = [
          "window_class"
          "geometry.width"
        ];
        description = ''
          Dotted paths into a sinnix-capture-v1 record's `payload`
          that this lane claims to populate. The hub server's health sweep
          samples the lane's most recent records and flags the lane
          `degenerate` when a declared field is null/empty in EVERY
          sampled record -- the "alive and writing at full cadence,
          but the data is unconditionally null" failure the
          staleness check cannot see (screen-frames shipped that way
          for its whole deployed life; see sinnix-3w9n).

          Declare only fields a healthy record always carries.
          Fields that are legitimately absent sometimes (an optional
          subtitle, a nullable parent id) must NOT be listed: the
          check is deliberately all-or-nothing so a partially
          populated field is never an alarm, which means a
          sometimes-null field simply makes the check unable to
          fire. Leave empty for lanes whose captures are not
          JSONL envelopes.
        '';
      };
    };
  };

  runtimeInventory =
    runtimeDefaults.mkInventory {
      hostname = config.networking.hostName;
      inherit units;
      captures = config.sinnix.runtime.captures;
      mounts = mountMonitoring;
    }
    // {
      capture_scopes = {
        schema = "sinnix-capture-scope-v1";
        subjects = lib.mapAttrs (
          _: names:
          builtins.filter (name: builtins.elem name (map (lane: lane.name) runtimeInventory.captures)) names
        ) config.sinnix.runtime.captureSubjects;
      };
      # The archive root is configuration, not a guessed XDG sibling.
      polylogue.archiveRoot = config.sinnix.services.polylogue.dataDir;
    };
in
{
  options.sinnix.runtime.units = lib.mkOption {
    type = lib.types.attrsOf (
      lib.types.submodule (
        { name, config, ... }:
        {
          options = {
            unit = lib.mkOption {
              type = lib.types.str;
              description = "systemd unit name owned by this runtime surface.";
            };
            manager = lib.mkOption {
              type = lib.types.enum [
                "system"
                "user"
              ];
              default = "system";
              description = "systemd manager that owns the unit.";
            };
            kind = lib.mkOption {
              type = lib.types.enum [
                "service"
                "socket"
                "timer"
                "target"
                "slice"
                "scope"
              ];
              readOnly = true;
              default = lib.last (lib.splitString "." config.unit);
              description = "systemd unit type, taken from the suffix of `unit`.";
            };
            resourceClass = lib.mkOption {
              type = lib.types.enum resourceClassNames;
              default = "ordinary";
              # A class becomes real by way of serviceConfig, which only a
              # service has: mkRuntimeServiceConfig resolves a surface by its
              # `<unit>.service` name and can never reach a timer. Rejecting the
              # combination here rather than deleting the inert keys once is what
              # stops a tenth from being added.
              apply =
                value:
                lib.throwIf (config.kind == "timer" && value != "ordinary")
                  "sinnix.runtime.units.${name}: a timer has no serviceConfig, so resourceClass = \"${value}\" can never apply; declare it on the .service surface this timer triggers"
                  value;
              description = "Sinnix runtime resource class.";
            };
            resources = {
              Slice = lib.mkOption {
                type = lib.types.nullOr lib.types.str;
                default = null;
              };
              IOSchedulingClass = lib.mkOption {
                type = lib.types.nullOr lib.types.str;
                default = null;
              };
              IOSchedulingPriority = lib.mkOption {
                type = lib.types.nullOr lib.types.int;
                default = null;
              };
              MemoryHigh = lib.mkOption {
                type = lib.types.nullOr lib.types.str;
                default = null;
              };
              MemoryMax = lib.mkOption {
                type = lib.types.nullOr lib.types.str;
                default = null;
              };
              MemoryLow = lib.mkOption {
                type = lib.types.nullOr lib.types.str;
                default = null;
              };
              CPUWeight = lib.mkOption {
                type = lib.types.nullOr lib.types.int;
                default = null;
              };
              IOWeight = lib.mkOption {
                type = lib.types.nullOr lib.types.int;
                default = null;
              };
              Nice = lib.mkOption {
                type = lib.types.nullOr lib.types.int;
                default = null;
              };
              TimeoutStartSec = lib.mkOption {
                type = lib.types.nullOr lib.types.str;
                default = null;
              };
              TimeoutStopSec = lib.mkOption {
                type = lib.types.nullOr lib.types.str;
                default = null;
              };
            };
            workload = {
              class = lib.mkOption {
                type = lib.types.enum [
                  "interactive"
                  "protected"
                  "sacrificial"
                  "substrate"
                  "unclassified"
                ];
                default = "unclassified";
                description = "Workload policy class for runtime, telemetry, and pressure decisions.";
              };
              rationale = lib.mkOption {
                type = lib.types.str;
                default = "";
                description = "Reason this surface has its workload class.";
              };
              processMatchers = lib.mkOption {
                type = lib.types.listOf lib.types.str;
                default = [ ];
                description = "Bounded fallback matchers for children without their own unit identity.";
              };
              earlyoomAvoid = lib.mkOption {
                type = lib.types.bool;
                default = false;
                description = "Add this surface's processMatchers to the earlyoom emergency avoid pattern (session-recovery surfaces only).";
              };
            };
            notifyOnFailure = lib.mkOption {
              type = lib.types.bool;
              default = false;
              description = ''
                Attach the failure-notify template (OnFailure=) and list the unit in
                the inventory's observedServices, which the hub server's health
                sweep watches.
              '';
            };
            operatorRestart = lib.mkOption {
              type = lib.types.bool;
              default = false;
              description = "Whether the hub server may restart this unit on the operator's request.";
            };
            ai = lib.mkOption {
              type = lib.types.nullOr (
                lib.types.submodule {
                  options = {
                    backendKind = lib.mkOption {
                      type = lib.types.enum [
                        "native"
                        "container"
                      ];
                      default = "native";
                    };
                    browserRequests = lib.mkOption {
                      type = lib.types.enum [
                        "loopback"
                        "native-only"
                      ];
                      default = "loopback";
                      description = "Admission before socket activation: loopback browser UI or native requests only.";
                    };
                    requiresCuda = lib.mkOption {
                      type = lib.types.bool;
                      default = false;
                    };
                  };
                }
              );
              default = null;
              description = "AI backend classification carried by the owning runtime surface.";
            };
            # Without this, every fresh agent session rediscovers an intentional
            # outage as an emergency and re-reports it. It is not a mute: the
            # unit still appears, in its own section, with this text attached,
            # so a stale entry stays visible.
            expectedDown = lib.mkOption {
              type = lib.types.nullOr lib.types.nonEmptyStr;
              default = null;
              example = "Parked during the archive reindex (polylogue-reindex-2026.1, since 2026-08-14)";
              description = "Why this unit is expected to be down, with its tracking reference and date; null when it should run.";
            };
            captures = lib.mkOption {
              type = lib.types.listOf captureLaneType;
              default = [ ];
              description = "Capture outputs produced by this runtime surface.";
            };
            activation = {
              mode = lib.mkOption {
                type = lib.types.enum [
                  "direct"
                  "socket-proxy"
                ];
                default = "direct";
                description = "How this surface is activated and exposed to local clients.";
              };
              publicEndpoint = lib.mkOption {
                type = lib.types.nullOr lib.types.str;
                default = null;
                description = "Local endpoint presented to clients, if any.";
              };
              backendEndpoint = lib.mkOption {
                type = lib.types.nullOr lib.types.str;
                default = null;
                description = "Private backend endpoint behind an activation proxy, if any.";
              };
              idleTimeout = lib.mkOption {
                type = lib.types.nullOr lib.types.str;
                default = null;
                description = "Idle timeout after which an activated backend may stop.";
              };
              readinessTimeout = lib.mkOption {
                type = lib.types.nullOr lib.types.ints.positive;
                default = null;
                description = ''
                  Seconds a socket proxy blocks its own start,
                  waiting for the backend to accept a TCP connection, before
                  giving up. Bounds the queueing window for a cold-start
                  request: without it, systemd-socket-proxyd starts
                  forwarding as soon as its unit starts, not once the
                  backend actually binds, so requests arriving mid-load get
                  refused instead of parked.
                '';
              };
              exclusiveResource = lib.mkOption {
                type = lib.types.nullOr lib.types.str;
                default = null;
                description = "Resource admission key shared by mutually exclusive surfaces.";
              };
              # Long-running consumers of a socket-proxied surface MUST speak to
              # the publicEndpoint: traffic against the private backend port is
              # invisible to the proxy's idle timer, so mid-work the proxy
              # idle-exits and tears the backend (and the consumer) down with it.
              # Declaring the consumer here renders its environment override
              # automatically.
              consumers = lib.mkOption {
                type = lib.types.listOf (
                  lib.types.submodule {
                    options = {
                      unit = lib.mkOption {
                        type = lib.types.str;
                        description = "systemd service name (without .service) of the consumer.";
                      };
                      environment = lib.mkOption {
                        type = lib.types.attrsOf lib.types.str;
                        default = { };
                        description = "Environment forced onto the consumer, pointing it at publicEndpoint.";
                      };
                    };
                  }
                );
                default = [ ];
                description = "Units doing long-running work against this surface via the public endpoint.";
              };
            };
          };
        }
      )
    );
    default = { };
    description = "Enabled runtime units and their capture lanes, declared by owning modules.";
  };

  # Lanes with no owning systemd unit: a hotkey script, a shell wrapper the
  # terminal launches, an external artifact drop. They still need freshness
  # budgets, because "nothing writes this lane" is the failure that looks
  # exactly like silence -- but they are not units, and giving them a
  # `unit` field was a lie every consumer had to know about.
  options.sinnix.runtime.captures = lib.mkOption {
    type = lib.types.listOf captureLaneType;
    default = [ ];
    description = ''
      Capture lanes that no runtime surface owns. Declared here rather than as
      a surface with a synthetic unit name, so the health sweep and the inventory
      see their freshness without anything having to special-case them.
    '';
  };

  options.sinnix.runtime.captureSubjects = lib.mkOption {
    type = lib.types.attrsOf (lib.types.listOf lib.types.str);
    default = { };
    description = "Explicit capture-scope-v1 subject membership by exact runtime lane ID.";
  };

  options.sinnix.runtime.inventory = lib.mkOption {
    type = lib.types.attrs;
    readOnly = true;
    default = runtimeInventory;
    description = "Sinnix runtime units, slices and capture inventory.";
  };

  config = lib.mkMerge [
    {
      sinnix.runtime.captureSubjects = import ../flake/data/capture-subjects.nix;
      assertions = lib.mkAfter [
        {
          assertion = builtins.all (
            lane:
            builtins.length (
              builtins.filter (names: builtins.elem lane.name names) (
                builtins.attrValues config.sinnix.runtime.captureSubjects
              )
            ) == 1
          ) runtimeInventory.captures;
          message = "Each declared capture lane must belong to exactly one explicit runtime capture subject.";
        }
      ];

    }
    (lib.sinnix.mkScheduledJob
      {
        inherit config;
        unitName = "sinnix-user-manager-watchdog";
        description = "Re-execute the operator's user manager when its job queue wedges";
        surface = config.sinnix.runtime.units.user-manager-watchdog;
      }
      {
        # System manager on purpose: a wedged user manager never dispatches
        # its own timers' start jobs.
        execStart = "${scriptPkgs.sinnix-user-manager-watchdog}/bin/sinnix-user-manager-watchdog ${cfg.user.name}";
        serviceConfig.TimeoutStartSec = "120s";
        timer = {
          onBootSec = "10min";
          intervalSec = 300;
        };
      }
    )
    (lib.sinnix.mkScheduledJob
      {
        inherit config;
        unitName = "sinnix-config-drift";
        description = "Compare live state with the evaluated Sinnix configuration";
        surface = config.sinnix.runtime.units.config-drift;
      }
      {
        execStart = lib.concatStringsSep " " [
          "${scriptPkgs.sinnix-config-drift}/bin/sinnix-config-drift"
          "--manifest /etc/sinnix/config.json"
          "--output ${cfg.paths.machineRoot}/config-drift.jsonl"
          "--user-name ${cfg.user.name}"
          # The user profile's noctalia, so the merged export uses the same
          # binary and schema the running shell does. The collector runs this
          # child as cfg.user, independently of its privileged machine probes.
          "--noctalia /etc/profiles/per-user/${cfg.user.name}/bin/noctalia"
          "--noctalia-config-home /home/${cfg.user.name}/.config/noctalia"
          "--noctalia-state-home /home/${cfg.user.name}/.local/state/noctalia"
        ];
        unit = {
          after = [ "local-fs.target" ];
          wants = [ "local-fs.target" ];
        };
        timer = {
          onBootSec = "2min";
          intervalSec = 300;
          persistent = true;
        };
      }
    )
    {
      assertions =
        let
          ids = map (capture: capture.name) runtimeInventory.captures;
          paths = map (capture: capture.path) runtimeInventory.captures;
          duplicates =
            values:
            lib.unique (
              builtins.filter (
                value: builtins.length (builtins.filter (candidate: candidate == value) values) > 1
              ) values
            );
          # A class only becomes real when some module writes it onto the unit.
          # nix-gc declared `background` for months while nixpkgs owned the
          # unit and nothing applied it, so it ran at the default IOWeight of
          # 100 -- a hundred times its declared share -- and starved the jobs
          # that were correctly throttled. The timer guard above rejects one
          # shape of inert declaration; this rejects the other.
          inertResourceClasses = lib.filter (surface: surface != null) (
            lib.mapAttrsToList (
              name: surface:
              let
                unitName = lib.removeSuffix ".service" surface.unit;
                applied = config.systemd.services.${unitName}.serviceConfig or { };
                # Some classes place the unit in a slice that carries the
                # weights; others put them on the unit itself. Either way the
                # keys the class declares are the evidence that it arrived.
                declared = builtins.attrNames (
                  runtimeDefaults.classes.${surface.resourceClass}.serviceConfig or { }
                );
                # A module may drop a single key on purpose -- `omit` exists
                # for exactly that, and a hard MemoryMax is reserved for real
                # safety boundaries. The defect is a class that never arrived
                # at all, so require evidence of application, not every key.
                arrived = lib.filter (key: applied ? "${key}") declared;
              in
              if
                (surface.manager or "system") == "system"
                && surface.kind == "service"
                && surface.resourceClass != "ordinary"
                # A configuration that never builds the unit has nothing to
                # govern; the defect is a unit that exists and runs ungoverned.
                && config.systemd.services ? "${unitName}"
                && declared != [ ]
                && arrived == [ ]
              then
                "${name} (${surface.unit}, class ${surface.resourceClass})"
              else
                null
            ) units
          );
        in
        [
          {
            assertion = inertResourceClasses == [ ];
            message =
              "sinnix.runtime.units declare a resourceClass that never reaches the unit; "
              + "the owning module must write it with lib.sinnix.mkRuntimeServiceConfig: "
              + lib.concatStringsSep ", " inertResourceClasses;
          }
          {
            assertion = duplicateSurfaceUnitKeys == [ ];
            message =
              "sinnix.runtime.units must not declare duplicate manager/unit pairs: "
              + lib.concatStringsSep ", " duplicateSurfaceUnitKeys;
          }
          {
            assertion = duplicates ids == [ ];
            message = "sinnix.runtime capture lane names must be unique: ${lib.concatStringsSep ", " (duplicates ids)}";
          }
          {
            assertion = duplicates paths == [ ];
            message = "sinnix.runtime capture lane paths must be unique: ${lib.concatStringsSep ", " (duplicates paths)}";
          }
        ];

      sinnix.runtime.units = runtimeDefaults.baseSurfaces // {
        # Critical, not background: its probes have 30 s timeouts, and in the
        # background class one run took 97 s of wall time for 33 ms of CPU,
        # long enough to misjudge a healthy manager as wedged.
        user-manager-watchdog = {
          unit = "sinnix-user-manager-watchdog.service";
          resourceClass = "critical";
          notifyOnFailure = true;
        };
        # The drift probe itself is governed like everything else it audits:
        # classed, observed, and its output watched as a lane, so a silently
        # dead probe is a health verdict rather than a quiet absence.
        config-drift = {
          unit = "sinnix-config-drift.service";
          resourceClass = "background";
          notifyOnFailure = true;
          captures = [
            {
              name = "config-drift";
              path = "${cfg.paths.machineRoot}/config-drift.jsonl";
              staleAfterSeconds = 1800;
            }
          ];
        };
      };

      environment.etc."sinnix/runtime-inventory.json" = {
        text = builtins.toJSON config.sinnix.runtime.inventory;
        mode = "0444";
      };
      environment.systemPackages = [
        scriptPkgs.sinnix-config-drift
        scriptPkgs.sinnix-preflight
      ];
      # setgid: the health transition ledger and its dedup state are written by
      # the hub-server (as the operator) and, when the hub server is down, by the
      # root-run failure template. Group `users` inherited by both is what keeps
      # the second writer from locking the first out of its own state file.
      systemd.tmpfiles.rules = [
        "d /run/sinnix 2775 root users -"
        # The two shared files, made group-writable wherever they came from:
        # the root-run failure template can create them before the hub server ever
        # does, and a live switch inherits whatever the previous generation
        # left. `z` is a no-op when the path does not exist.
        "z /run/sinnix/health-transitions.jsonl 0664 root users -"
        "z /run/sinnix/health-state.json 0664 root users -"
        "z /run/sinnix/health-state.json.lock 0664 root users -"
      ];
      # Consumer entries from activation.consumers render as forced environment
      # overrides (proxy routing; see the consumers option comment),
      # merged with the failure-notify units.
      systemd.services = lib.mkMerge (
        lib.concatLists (
          lib.mapAttrsToList (
            _: surface:
            map (c: {
              ${c.unit}.environment = lib.mapAttrs (_: v: lib.mkForce v) c.environment;
            }) (surface.activation.consumers or [ ])
          ) units
        )
        ++ [
          (
            {
              "sinnix-unit-failure-notify@" = {
                description = "Record + surface the failure of %i";
                serviceConfig = {
                  Type = "oneshot";
                  ExecStart = "${unitFailureNotify}/bin/sinnix-unit-failure-notify %i";
                };
              };
            }
            //
              lib.mapAttrs'
                (
                  _name: surface:
                  lib.nameValuePair (lib.removeSuffix ".service" surface.unit) {
                    unitConfig.OnFailure = [ "sinnix-unit-failure-notify@%n.service" ];
                  }
                )
                (
                  lib.filterAttrs (
                    _: surface: surface.manager == "system" && surface.kind == "service" && surface.notifyOnFailure
                  ) units
                )
          )
        ]
      );
      home-manager.users.${cfg.user.name} = {
        systemd.user.services."sinnix-unit-failure-notify@" = {
          Unit.Description = "Record + surface the failure of user unit %i";
          Service = {
            Type = "oneshot";
            ExecStart = "${unitFailureNotify}/bin/sinnix-unit-failure-notify %i --user";
          };
        };

        # The failure bridge is a drop-in, not a unit body, because a user
        # surface may be declared in either of two option namespaces that never
        # merge: home-manager's `systemd.user.services` (~/.config/systemd/user)
        # or the NixOS-level `systemd.user.services` (/etc/systemd/user).
        # Injecting OnFailure as a unit body merges only for the former; for the
        # latter home-manager emits a standalone `[Unit] OnFailure=` file with no
        # [Service] section, and ~/.config outranks /etc in the user manager's
        # search path — the real unit becomes unreachable with
        # LoadState=bad-setting. A drop-in merges with whichever fragment exists,
        # so the declaring namespace stops mattering.
        xdg.configFile =
          lib.mapAttrs'
            (
              _name: surface:
              lib.nameValuePair "systemd/user/${surface.unit}.d/50-sinnix-unit-failure-notify.conf" {
                text = ''
                  [Unit]
                  OnFailure=sinnix-unit-failure-notify@%n.service
                '';
              }
            )
            (
              lib.filterAttrs (
                _: surface: surface.manager == "user" && surface.kind == "service" && surface.notifyOnFailure
              ) units
            );
      };
    }
  ];
}
