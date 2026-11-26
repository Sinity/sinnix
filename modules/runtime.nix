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

  # Failure notifications share the hub's per-unit state and write it directly
  # if the hub is down; root and user templates share group users and umask 0002.
  # Two hooks run it: OnFailure= (the unit entered failed) and ExecStopPost=
  # (any end of the main process, with SERVICE_RESULT set). A unit that
  # Restart= brings back never enters failed, so only ExecStopPost sees its
  # crash; when both run for one failure, the hub's state records it once.
  unitFailureNotify = pkgs.writeShellApplication {
    name = "sinnix-unit-failure-notify";
    runtimeInputs = [
      pkgs.systemd
      scriptPkgs.sinnix-hub-server
    ];
    text = ''
      umask 0002
      unit="$1"
      if [ "''${SERVICE_RESULT:-}" = success ]; then
        exit 0
      fi
      if [ "''${2:-}" = "--user" ]; then
        manager=user
        result="''${SERVICE_RESULT:-$(systemctl --user show "$unit" -p Result --value 2>/dev/null || true)}"
      else
        manager=system
        result="''${SERVICE_RESULT:-$(systemctl show "$unit" -p Result --value 2>/dev/null || true)}"
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
      # /neo-outer-realm holds bulk media and temporary Sinex backup artifacts.
      # It holds no live database or snapshot queue, so "nearly full" is its
      # normal working state rather than
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

  # Capture outputs share one shape, inline on their owning unit or standalone
  # in sinnix.runtime.captures when their writer is not a systemd unit.
  captureLaneType = import ./lib/capture-output-type.nix { inherit lib; };

  runtimeInventory =
    runtimeDefaults.mkInventory {
      hostname = config.networking.hostName;
      inherit units;
      captures = config.sinnix.runtime.captures;
      mounts = mountMonitoring;
    }
    // {
      # The archive root is configuration, not a guessed XDG sibling.
      polylogue.archiveRoot = "${config.sinnix.services.polylogue.dataHome}/polylogue";
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
              # Only services have serviceConfig; resource classes cannot apply
              # to timers and must be declared on the service they trigger.
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
              OOMScoreAdjust = lib.mkOption {
                type = lib.types.nullOr lib.types.int;
                default = null;
                description = "Kernel OOM rank; retryable work uses 900 like agentctl jobs (docs/resource-control.md).";
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
            # Expected outages stay visible with their reason, without
            # repeatedly reporting the unit as an unexpected failure.
            expectedDown = lib.mkOption {
              type = lib.types.nullOr lib.types.nonEmptyStr;
              default = null;
              example = "Stopped while the archive index is rebuilt";
              description = "Why this unit is expected to be down; null when it should run.";
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

  # Outputs from hotkeys, shell wrappers and external drops have no owning
  # systemd unit; they still need freshness monitoring.
  options.sinnix.runtime.captures = lib.mkOption {
    type = lib.types.listOf captureLaneType;
    default = [ ];
    description = ''
      Capture lanes that no runtime surface owns. Declared here rather than as
      a surface with a synthetic unit name, so the health sweep and the inventory
      see their freshness without anything having to special-case them.
    '';
  };

  options.sinnix.runtime.inventory = lib.mkOption {
    type = lib.types.attrs;
    readOnly = true;
    default = runtimeInventory;
    description = "Sinnix runtime units, slices and capture inventory.";
  };

  config = lib.mkMerge [
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
          # A resource class applies only when its owning module writes the
          # settings onto a service; reject declarations with no applied settings.
          inertResourceClasses = lib.filter (surface: surface != null) (
            lib.mapAttrsToList (
              name: surface:
              let
                unitName = lib.removeSuffix ".service" surface.unit;
                system = (surface.manager or "system") == "system";
                # User services can come from NixOS or Home Manager; check both.
                homeUnits = config.home-manager.users.${cfg.user.name}.systemd.user.services or { };
                exists =
                  if system then
                    config.systemd.services ? "${unitName}"
                  else
                    config.systemd.user.services ? "${unitName}" || homeUnits ? "${unitName}";
                applied =
                  if system then
                    config.systemd.services.${unitName}.serviceConfig or { }
                  else
                    (config.systemd.user.services.${unitName}.serviceConfig or { })
                    // (homeUnits.${unitName}.Service or { });
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
                surface.kind == "service"
                && surface.resourceClass != "ordinary"
                # A configuration that never builds the unit has nothing to
                # govern; the defect is a unit that exists and runs ungoverned.
                && exists
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

      sinnix.runtime.units = runtimeDefaults.baseSurfaces;

      environment.etc."sinnix/runtime-inventory.json" = {
        text = builtins.toJSON config.sinnix.runtime.inventory;
        mode = "0444";
      };
      environment.systemPackages = [
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
                    serviceConfig.ExecStopPost = [ "-${unitFailureNotify}/bin/sinnix-unit-failure-notify %n" ];
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

                  [Service]
                  ExecStopPost=-${unitFailureNotify}/bin/sinnix-unit-failure-notify %n --user
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
