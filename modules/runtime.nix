# Runtime inventory registry
#
# One source of truth for Sinnix runtime surfaces, resource classes, systemd
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
  # reports itself, so nothing has to poll it. It routes into the ops-reducer,
  # which owns the health sweep, rather than appending to the ledger directly:
  # one schema and one dedup state for both the OnFailure path and the sweep.
  # When they kept separate keys the same unit re-notified on every failure and
  # its recovery never paired with the outage (2026-08-14, on
  # borgbackup-status.service). `emit-failure` posts to the running reducer and
  # falls back to writing the same transition itself when the reducer is down,
  # which is exactly a moment when units fail.
  #
  # umask 0002 because this runs as root while the reducer runs as the
  # operator: both write the same two files in /run/sinnix, which is setgid
  # `users` for that reason.
  #
  # One body, two templates: a user-manager unit cannot OnFailure into a
  # system template, and only the systemctl scope differs.
  unitFailureNotify = pkgs.writeShellApplication {
    name = "sinnix-unit-failure-notify";
    runtimeInputs = [
      pkgs.systemd
      scriptPkgs.sinnix-ops-reducer
    ];
    text = ''
      umask 0002
      unit="$1"
      if [ "''${2:-}" = "--user" ]; then
        result="$(systemctl --user show "$unit" -p Result --value 2>/dev/null || true)"
      else
        result="$(systemctl show "$unit" -p Result --value 2>/dev/null || true)"
      fi
      exec sinnix-ops-reducer emit-failure --unit "$unit" --result "''${result:-unknown}"
    '';
  };

  surfaces = config.sinnix.runtime.surfaces;
  surfaceRows = lib.mapAttrsToList (name: surface: {
    inherit name;
    inherit (surface)
      kind
      manager
      resourceClass
      unit
      ;
  }) surfaces;
  surfaceUnitKeys = map (surface: "${surface.manager}:${surface.unit}") surfaceRows;
  duplicateSurfaceUnitKeys = lib.unique (
    builtins.filter (
      key: (builtins.length (builtins.filter (candidate: candidate == key) surfaceUnitKeys)) > 1
    ) surfaceUnitKeys
  );
  kindUnitMismatches = builtins.filter (
    surface: !(lib.hasSuffix ".${surface.kind}" surface.unit)
  ) surfaceRows;
  unreferencedAcknowledgements = lib.mapAttrsToList (name: _: name) (
    lib.filterAttrs (
      _: surface:
      surface.acknowledged.down
      && (
        surface.acknowledged.reason == ""
        || surface.acknowledged.since == ""
        || surface.acknowledged.ref == ""
      )
    ) surfaces
  );
  mountMonitoring = [
    {
      path = cfg.paths.realmRoot;
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

  backupInventory = {
    snapshotDirs = [
      "${cfg.paths.realmRoot}/.btrfs/snapshot"
      "/persist/.btrfs/snapshot"
    ];
    backupTargets = [ ];
    drillLog = "${cfg.paths.machineRoot}/borg_drill.jsonl";
  };

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
          have no numeric cadence for the sentinel's 2*cadence
          staleness check, so this is the only signal that flags
          them stale when writes stop. Lanes with a numeric
          cadenceSeconds may set this too; the sentinel flags a
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

                  Exit-code contract the sentinel relies on:
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
                  Bound on the probe's runtime. The sentinel runs
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
          that this lane claims to populate. The reducer's health sweep
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

  runtimeInventory = runtimeDefaults.mkInventory {
    hostname = config.networking.hostName;
    inherit surfaces;
    captures = config.sinnix.runtime.captures;
    mounts = mountMonitoring;
    backups = backupInventory;
  };
in
{
  options.sinnix.runtime.surfaces = lib.mkOption {
    type = lib.types.attrsOf (
      lib.types.submodule {
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
            default = "service";
            description = ''
              Runtime surface kind. Every value here is a real systemd unit
              type, and the assertion below enforces that `unit` ends in it.
              There is deliberately no "capture" member: a lane whose writer
              is not a unit belongs in sinnix.runtime.captures, not here with
              a synthetic unit name that makes the `unit` field mean two
              different things depending on this one.
            '';
          };
          resourceClass = lib.mkOption {
            type = lib.types.enum resourceClassNames;
            default = "system";
            description = "Sinnix runtime resource class.";
          };
          resources = {
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
          observe = {
            enable = lib.mkOption {
              type = lib.types.bool;
              default = false;
              description = "Expose this surface in /etc/sinnix/runtime-inventory.json.";
            };
            restartable = lib.mkOption {
              type = lib.types.bool;
              default = false;
              description = "Whether operators may restart this surface directly.";
            };
          };
          # A machine-readable carrier for "yes, this is down, we know".
          # Without one, every fresh agent session rediscovers an intentional
          # outage as an emergency and re-reports it. An acknowledgement is
          # not a mute: the surface still appears, in its own section, with
          # the reason and the tracking reference attached, so a stale ack is
          # visible rather than a permanent silence.
          acknowledged = {
            down = lib.mkOption {
              type = lib.types.bool;
              default = false;
              description = "This surface is expected to be down; do not report it as a failure.";
            };
            reason = lib.mkOption {
              type = lib.types.str;
              default = "";
              description = "Why it is down, in one line, for a human reading a status page.";
            };
            since = lib.mkOption {
              type = lib.types.str;
              default = "";
              description = "ISO date the acknowledgement was made, so its age is auditable.";
            };
            ref = lib.mkOption {
              type = lib.types.str;
              default = "";
              description = "Tracking reference (Beads id) for the work that ends the outage.";
            };
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
                Seconds a socket-proxy front door blocks its own start,
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
            dependsOn = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              default = [ ];
              description = "Runtime surface names required by this activation path.";
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
          dynamic = lib.mkOption {
            type = lib.types.bool;
            default = false;
            description = "Whether this inventory surface represents transient children selected by the declared unit/cgroup contract.";
          };
        };
      }
    );
    default = { };
    description = "Enabled runtime units and capture surfaces declared by owning modules.";
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
      a surface with a synthetic unit name, so the sentinel and the inventory
      see their freshness without anything having to special-case them.
    '';
  };

  options.sinnix.runtime.inventory = lib.mkOption {
    type = lib.types.attrs;
    readOnly = true;
    default = runtimeInventory;
    description = "Canonical Sinnix runtime surfaces, resource classes, slices, command policy, and capture inventory.";
  };

  config = lib.mkMerge [
    (lib.sinnix.mkScheduledJob
      {
        inherit config;
        unitName = "sinnix-config-drift";
        description = "Compare live state with the evaluated Sinnix configuration";
        surface = config.sinnix.runtime.surfaces.config-drift;
      }
      {
        execStart = "${scriptPkgs.sinnix-config-drift}/bin/sinnix-config-drift --manifest /etc/sinnix/config.json --output ${cfg.paths.machineRoot}/config-drift.jsonl";
        unit = {
          after = [ "local-fs.target" ];
          wants = [ "local-fs.target" ];
        };
        timer = {
          onBootSec = "2min";
          onUnitActiveSec = "5min";
          persistent = true;
        };
      }
    )
    {
      assertions = [
        {
          assertion = duplicateSurfaceUnitKeys == [ ];
          message =
            "sinnix.runtime.surfaces must not declare duplicate manager/unit pairs: "
            + lib.concatStringsSep ", " duplicateSurfaceUnitKeys;
        }
        {
          assertion = kindUnitMismatches == [ ];
          message =
            "sinnix.runtime.surfaces unit suffixes must match their kind: "
            + lib.concatMapStringsSep ", " (
              surface: "${surface.name}:${surface.kind}:${surface.unit}"
            ) kindUnitMismatches;
        }
        {
          # An acknowledgement without a reason and a tracking reference is
          # just a mute, and a mute is how an intentional outage quietly
          # becomes a forgotten one.
          assertion = unreferencedAcknowledgements == [ ];
          message =
            "sinnix.runtime.surfaces acknowledged outages must carry reason, since and ref: "
            + lib.concatStringsSep ", " unreferencedAcknowledgements;
        }
      ];

      sinnix.runtime.surfaces = runtimeDefaults.baseSurfaces // {
        # The drift probe itself is governed like everything else it audits:
        # classed, observed, and its output watched as a lane, so a silently
        # dead probe is a health verdict rather than a quiet absence.
        config-drift = {
          unit = "sinnix-config-drift.service";
          resourceClass = "background-maintenance";
          observe.enable = true;
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
        scriptPkgs.sinnix-lifecycle-manifest
      ];
      # setgid: the health transition ledger and its dedup state are written by
      # the ops-reducer (as the operator) and, when the reducer is down, by the
      # root-run failure template. Group `users` inherited by both is what keeps
      # the second writer from locking the first out of its own state file.
      systemd.tmpfiles.rules = [
        "d /run/sinnix 2775 root users -"
        # The two shared files, made group-writable wherever they came from:
        # the root-run failure template can create them before the reducer ever
        # does, and a live switch inherits whatever the previous generation
        # left. `z` is a no-op when the path does not exist.
        "z /run/sinnix/health-transitions.jsonl 0664 root users -"
        "z /run/sinnix/health-state.json 0664 root users -"
        "z /run/sinnix/health-state.json.lock 0664 root users -"
      ];
      # Consumer entries from activation.consumers render as forced environment
      # overrides (front-door routing; see the consumers option comment),
      # merged with the sentinel/observe units.
      systemd.services = lib.mkMerge (
        lib.concatLists (
          lib.mapAttrsToList (
            _: surface:
            map (c: {
              ${c.unit}.environment = lib.mapAttrs (_: v: lib.mkForce v) c.environment;
            }) (surface.activation.consumers or [ ])
          ) surfaces
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
                    _: surface: surface.manager == "system" && surface.kind == "service" && surface.observe.enable
                  ) surfaces
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
                _: surface: surface.manager == "user" && surface.kind == "service" && surface.observe.enable
              ) surfaces
            );
      };
    }
  ];
}
