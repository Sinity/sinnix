# Runtime inventory registry
#
# One source of truth for Sinnix runtime surfaces, resource classes, systemd
# slices, command wrappers, static slice budgets, and capture inventory.
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
    surface: surface.kind != "capture" && !(lib.hasSuffix ".${surface.kind}" surface.unit)
  ) surfaceRows;
  commandRows = lib.mapAttrsToList (name: command: {
    inherit name;
    inherit (command) resourceClass;
  }) runtimeDefaults.commandClasses;
  unknownCommandClasses = builtins.filter (
    command: !(builtins.elem command.resourceClass resourceClassNames)
  ) commandRows;

  mountMonitoring = [
    {
      path = cfg.paths.realmRoot;
      warnPct = 80;
      failPct = 90;
    }
    {
      path = cfg.paths.neoOuterRealm;
      warnPct = 80;
      failPct = 90;
    }
  ];

  backupInventory = {
    snapshotDirs = [
      "${cfg.paths.realmRoot}/.btrfs/snapshot"
      "/persist/.btrfs/snapshot"
    ];
    backupTargets = [ ];
    drillLog = "${cfg.paths.capturesRoot}/machine/borg_drill.jsonl";
  };

  runtimeInventory = runtimeDefaults.mkInventory {
    hostname = config.networking.hostName;
    inherit surfaces;
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
              "capture"
            ];
            default = "service";
            description = "Runtime surface kind.";
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
          captures = lib.mkOption {
            type = lib.types.listOf (
              lib.types.submodule {
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
                      that this lane claims to populate. The health sentinel
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
              }
            );
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

  options.sinnix.runtime.inventory = lib.mkOption {
    type = lib.types.attrs;
    readOnly = true;
    default = runtimeInventory;
    description = "Canonical Sinnix runtime surfaces, resource classes, slices, command policy, and capture inventory.";
  };

  config = {
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
        assertion = unknownCommandClasses == [ ];
        message =
          "sinnix.runtime.inventory.commandClasses use unknown resource classes: "
          + lib.concatMapStringsSep ", " (
            command: "${command.name}:${command.resourceClass}"
          ) unknownCommandClasses;
      }
    ];

    sinnix.runtime.surfaces = runtimeDefaults.baseSurfaces;

    environment.etc."sinnix/runtime-inventory.json" = {
      text = builtins.toJSON config.sinnix.runtime.inventory;
      mode = "0444";
    };
    environment.systemPackages = [
      scriptPkgs.sinnix-health-sentinel
      scriptPkgs.sinnix-config-drift
      scriptPkgs.sinnix-preflight
      scriptPkgs.sinnix-capability-manifest
    ];
    systemd.tmpfiles.rules = [ "d /run/sinnix 0775 root users -" ];
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
            sinnix-health-sentinel = {
              description = "Inventory-driven runtime health sentinel";
              serviceConfig = {
                Type = "oneshot";
                ExecStart = "${scriptPkgs.sinnix-health-sentinel}/bin/sinnix-health-sentinel --check";
              };
            };
            "sinnix-health-transition@" = {
              description = "Record an inventory health transition for %i";
              serviceConfig = {
                Type = "oneshot";
                ExecStart = "${scriptPkgs.sinnix-health-sentinel}/bin/sinnix-health-sentinel --failure-unit %i";
              };
            };
            sinnix-config-drift = {
              description = "Compare live state with the evaluated Sinnix configuration";
              after = [ "local-fs.target" ];
              wants = [ "local-fs.target" ];
              serviceConfig = {
                Type = "oneshot";
                ExecStart = "${scriptPkgs.sinnix-config-drift}/bin/sinnix-config-drift --manifest /etc/sinnix/config.json --output ${cfg.paths.capturesRoot}/machine/config-drift.jsonl";
              };
            };
          }
          //
            lib.mapAttrs'
              (
                _name: surface:
                lib.nameValuePair (lib.removeSuffix ".service" surface.unit) {
                  unitConfig.OnFailure = [ "sinnix-health-transition@%n" ];
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
    systemd.timers.sinnix-health-sentinel = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "1min";
        OnUnitActiveSec = "1min";
        Persistent = true;
      };
    };
    systemd.timers.sinnix-config-drift = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "2min";
        OnUnitActiveSec = "5min";
        Persistent = true;
      };
    };
    home-manager.users.${cfg.user.name} = {
      systemd.user.services."sinnix-health-transition@" = {
        Unit.Description = "Record a user-manager health transition for %i";
        Service = {
          Type = "oneshot";
          ExecStart = "${scriptPkgs.sinnix-health-sentinel}/bin/sinnix-health-sentinel --failure-unit %i";
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
      xdg.configFile = lib.mapAttrs' (
        _name: surface:
        lib.nameValuePair "systemd/user/${surface.unit}.d/50-sinnix-health-transition.conf" {
          text = ''
            [Unit]
            OnFailure=sinnix-health-transition@%n
          '';
        }
      ) (
        lib.filterAttrs (
          _: surface: surface.manager == "user" && surface.kind == "service" && surface.observe.enable
        ) surfaces
      );
    };
  };
}
