# Sinex bridge
#
# This module carries the heavy integration with the upstream `services.sinex`
# option tree. Keep it opt-in so the generic sinnix module graph does not pay
# for Sinex evaluation when the host does not import the upstream module.
#
# Workstation policy is now expressed through upstream options
# (services.sinex.runtime.*, .bootstrap.*, .nats.killPolicy). This bridge
# only carries what is genuinely host-specific:
#   - workstation memory / IO budgets for NATS and PostgreSQL
#   - per-node MemoryMax/CPUQuota suppression (until upstream surfaces
#     services.sinex.nodes.<n>.resources.memoryMax = null as an option)
#   - cache placement under /cache/nats/jetstream and /cache/sinex
#   - secrets paths + sinex user home + database password binding
#   - the deferred-startup orchestration around sinex-runtime.timer for
#     non-sinex bootstrap units (postgresql/postgresql-setup) that the
#     upstream module cannot gate on its own attachToMultiUser flag
{
  config,
  options,
  pkgs,
  lib,
  inputs,
  ...
}:
let
  cfg = config.sinnix.services.sinex;
  inherit (config.sinnix.paths) capturesRoot realmRoot;
  mkSinexPkgs = pkgs': inputs.sinex.packages.${pkgs'.stdenv.hostPlatform.system};
  sinexEnvironment = lib.toLower cfg.environment;
  targetUserName = config.sinnix.user.name;
  targetUserHome = "/home/${targetUserName}";
  sinexCaptureRoot = "${capturesRoot}/sinex";
  sinexHome = "${sinexCaptureRoot}/home";
  sinexPostgresRoot = "${sinexCaptureRoot}/postgresql";
  sinexPostgresDataDir = "${sinexPostgresRoot}/18";
  sinexStateRoot = "${sinexCaptureRoot}/state";
  databaseHost = "127.0.0.1";
  databasePort = 5432;
  databaseUser = "sinex";
  databaseName = "sinex_${sinexEnvironment}";
  databasePasswordFile = lib.attrByPath [ "sinnix" "secrets" "paths" "sinex-local-db" ] null config;
  hostPrepared = cfg.prepareHost || cfg.enable || cfg.provisionDatabase;
  runtimeEnabled = cfg.enable;
  runtimeAutoStart = runtimeEnabled && cfg.autoStart;
  databasePrepared = cfg.provisionDatabase || cfg.enable;
  sinexRuntimeStartDelay = "5min";
  sinexAutoTimers = [
    "sinex-blob-fsck"
    "sinex-blob-gc"
    "sinex-cache-prune"
    "sinex-document-scan"
  ];
in
{
  config = lib.mkIf (options.services ? sinex) (
    let
      activationProfile =
        {
          foundation = {
            filesystem = true;
            terminal = false;
            browser = false;
            desktop = false;
            system = true;
            document = false;
            automata = false;
            canonicalizer = false;
            healthAggregator = false;
            kitty = false;
          };
          capture = {
            filesystem = true;
            terminal = true;
            browser = true;
            desktop = false;
            system = true;
            document = true;
            automata = true;
            canonicalizer = true;
            healthAggregator = true;
            kitty = true;
          };
          full = {
            filesystem = true;
            terminal = true;
            browser = true;
            desktop = true;
            system = true;
            document = true;
            automata = true;
            canonicalizer = true;
            healthAggregator = true;
            kitty = true;
          };
        }
        .${cfg.activationProfile};
      filesystemWatchPaths = [
        "${realmRoot}/project"
        "${realmRoot}/inbox/download"
      ];
      generatedNodeServices = lib.optionals runtimeEnabled (config.sinex._generatedUnits or [ ]);
      documentScanEnabled =
        runtimeEnabled && lib.attrByPath [ "services" "sinex" "nodes" "document" "enable" ] false config;
      preflightEnabled =
        runtimeEnabled
        && lib.attrByPath [ "services" "sinex" "lifecycle" "preflight" "enable" ] false config;
      kittyAutoConfigureEnabled =
        runtimeEnabled
        && lib.attrByPath [ "services" "sinex" "shell" "kitty" "enable" ] false config
        && lib.attrByPath [ "services" "sinex" "shell" "kitty" "autoConfigure" ] false config;
      delayedRuntimeServices = lib.unique (
        lib.optionals databasePrepared [
          "postgresql"
          "postgresql-setup"
          "sinex-schema-apply"
        ]
        ++ lib.optionals runtimeEnabled [
          "nats"
          "sinex-nats-bootstrap"
          "sinex-blob-init"
          "sinex-tls-init"
          "sinex-ingestd"
          "sinex-gateway"
        ]
        ++ lib.optionals preflightEnabled [ "sinex-preflight" ]
        ++ generatedNodeServices
        ++ lib.optionals documentScanEnabled [ "sinex-document-scan" ]
        ++ lib.optionals kittyAutoConfigureEnabled [ "sinex-kitty-setup" ]
      );
      delayedRuntimeTargets = lib.optionals databasePrepared [ "postgresql" ];
      delayedRuntimeUnits =
        map (name: "${name}.service") delayedRuntimeServices
        ++ map (name: "${name}.target") delayedRuntimeTargets;
      restartableRuntimeServices = [
        "sinex-ingestd"
        "sinex-gateway"
      ]
      ++ generatedNodeServices;
      cappedRuntimeServices = [
        "nats"
        "postgresql"
      ];
      uncappedRuntimeServices = builtins.filter (
        name: !(builtins.elem name cappedRuntimeServices)
      ) delayedRuntimeServices;
      # Bridge-side policy that the upstream options can't yet express:
      # - RequiresMountsFor on the captureRoot (host-specific path)
      # - wantedBy=[] for non-sinex services (postgresql/postgresql-setup)
      #   that upstream's runtime.target.attachToMultiUser cannot gate
      bridgeRuntimePolicy = {
        wantedBy = lib.mkForce [ ];
        unitConfig = {
          PartOf = [ "sinex-runtime.target" ];
          RequiresMountsFor = [ sinexCaptureRoot ];
        };
        restartIfChanged = false;
      };
      # why mkForce: upstream Sinex's per-node resourceModule sets concrete
      # MemoryMax/CPUQuota defaults for portability. Workstation pressure
      # concentrates at the storage substrate (PostgreSQL/NATS) where the
      # bridge sets explicit caps below; per-node hard caps would silently
      # throttle capture correctness without solving the underlying issue.
      perNodeUncapped = {
        serviceConfig = {
          MemoryMax = lib.mkForce null;
          CPUQuota = lib.mkForce null;
        };
      };
      mkScopedSinexPackage =
        sinexPkgs:
        pkgs.symlinkJoin {
          name = "sinex-runtime-${sinexEnvironment}";
          paths = lib.unique (
            lib.optionals runtimeEnabled [
              # Use the upstream aggregate runtime so Nix builds Sinex once for
              # deployment. Selecting per-node packages here reintroduces one
              # SQLx/Postgres build derivation per service.
              sinexPkgs.sinex
            ]
            ++ lib.optionals (!runtimeEnabled && databasePrepared) [ sinexPkgs.xtask ]
          );
        };
    in
    lib.mkMerge [
      (lib.mkIf (!runtimeEnabled) {
        services.sinex = {
          secrets.enableAgenix = lib.mkDefault false;
          core.enable = lib.mkDefault false;
          nodes.enable = lib.mkDefault false;
          nats.enable = lib.mkDefault false;
          nats.autoSetup = lib.mkDefault false;
          observability.enable = lib.mkDefault false;
          shell.kitty.enable = lib.mkDefault false;
          storage = {
            blob = {
              enable = lib.mkDefault false;
              autoInit = lib.mkDefault false;
            };
          };
          lifecycle = {
            preflight.enable = lib.mkDefault false;
            maintenance.enable = lib.mkDefault false;
            updates.enable = lib.mkDefault false;
          };
        };
      })

      (lib.mkIf hostPrepared (
        let
          sinexPkgs = mkSinexPkgs pkgs;
        in
        {
          services.sinex.package = lib.mkDefault (mkScopedSinexPackage sinexPkgs);
          services.sinex.cliPackage = lib.mkDefault sinexPkgs.sinexctl;
          services.sinex.users.target = targetUserName;
          sinex.secrets.paths = lib.mkForce (
            lib.mapAttrs (_: path: toString path) (
              lib.filterAttrs (
                name: _: lib.hasPrefix "sinex-" name || lib.hasPrefix "nats-" name
              ) config.sinnix.secrets.paths
            )
          );

          users.users.sinex = {
            home = lib.mkForce sinexHome;
            homeMode = lib.mkForce "0711";
            createHome = lib.mkForce true;
            extraGroups = lib.optionals (cfg.provisionDatabase || cfg.enable) [ "postgres" ];
          };

          systemd.tmpfiles.rules = lib.mkAfter (
            [
              "d ${sinexCaptureRoot} 0755 root root -"
              "d ${sinexHome} 0711 sinex sinex -"
              "d ${sinexStateRoot} 0750 sinex sinex -"
            ]
            ++ lib.optionals databasePrepared [
              "d ${sinexPostgresRoot} 0750 postgres postgres -"
              "d ${sinexPostgresDataDir} 0750 postgres postgres -"
            ]
          );
        }
      ))

      (lib.mkIf hostPrepared {
        services = {
          postgresql.dataDir = sinexPostgresDataDir;

          sinex = {
            enable = runtimeEnabled;

            secrets = {
              enableAgenix = false;
            };
            nats = {
              environment = sinexEnvironment;
              enable = runtimeEnabled;
              autoSetup = runtimeEnabled;
              dataDir = "/var/lib/nats";
              # JetStream on the dedicated NVMe cache partition so its
              # sustained write load (message store + index compaction) does
              # not compete with system and interactive I/O on the root volume.
              storeDir = "/cache/nats/jetstream";
            };

            stateRoot = sinexStateRoot;

            database = {
              enable = databasePrepared;
              autoSetup = databasePrepared;
              host = databaseHost;
              port = databasePort;
              name = databaseName;
              user = databaseUser;
            };

            core = {
              enable = runtimeEnabled;
              gateway = {
                enable = runtimeEnabled;
                autoGenerateTls = true;
              };
            };

            storage = {
              blob = {
                enable = runtimeEnabled;
                autoInit = runtimeEnabled;
              };
            };

            lifecycle = {
              # Full preflight can touch production-sized data and is an operator
              # diagnostic, not a safe prerequisite for desktop activation.
              preflight.enable = false;
              maintenance.enable = runtimeEnabled;
              updates.enable = runtimeEnabled;
            };

            nodes = {
              enable = runtimeEnabled;

              filesystem = {
                enable = runtimeEnabled && activationProfile.filesystem;
                watchPaths = filesystemWatchPaths;
                ignoredDirectoryNames = lib.mkForce [
                  ".btrfs"
                  ".claude"
                  ".cache"
                  ".direnv"
                  ".git"
                  ".hg"
                  ".jj"
                  ".sinex"
                  ".svn"
                  ".Trash-1000"
                  "__pycache__"
                  "asciinema"
                  "kitty-scrollback"
                  "node_modules"
                  "target"
                ];
              };

              terminal = {
                enable = runtimeEnabled && activationProfile.terminal;
                historySources = [
                  {
                    path = "${targetUserHome}/.local/share/atuin/history.db";
                    shell = "atuin";
                  }
                ];
              };

              browser = {
                enable = runtimeEnabled && activationProfile.browser;
              };

              desktop = {
                enable = runtimeEnabled && activationProfile.desktop;
                clipboard.enable = false;
              };

              system = {
                enable = runtimeEnabled && activationProfile.system;
              };

              document = {
                enable = runtimeEnabled && activationProfile.document;
              };

              automata = {
                enable = runtimeEnabled && activationProfile.automata;
                canonicalizer = {
                  enable = runtimeEnabled && activationProfile.canonicalizer;
                  profile = lib.mkDefault "heavy";
                };
                healthAggregator = {
                  enable = runtimeEnabled && activationProfile.healthAggregator;
                  profile = lib.mkDefault "heavy";
                };
              };
            };

            observability = {
              enable = runtimeEnabled;
              monitoring = {
                enable = false;
                prometheus.enable = false;
                grafana.enable = false;
                exporters = {
                  node = false;
                  postgres = false;
                  nats = false;
                };
              };
            };

            shell.kitty = {
              enable = runtimeEnabled && activationProfile.kitty;
              autoConfigure = runtimeEnabled && activationProfile.kitty;
            };

            # Workstation runtime policy via upstream options.
            # Replaces the per-attribute mkForce overrides this bridge
            # used to scatter across runtimeServicePolicy and
            # boundedRuntimeRestartPolicy.
            runtime = {
              target = {
                attachToMultiUser = false;
                manualStartOnly = true;
              };
              restartOnSwitch = false;
              restartPolicy = {
                # Bound failure loops at three retries / 10 minutes / 30s
                # backoff so a stuck capture daemon stops generating
                # NATS/Postgres pressure and becomes visible instead.
                mode = "on-failure";
                backoffSec = 30;
                intervalSec = 600;
                burst = 3;
              };
            };
            bootstrap.restartPolicy = "no";
            nats.killPolicy = {
              # NATS' graceful SIGUSR2 drain can sit for minutes while
              # JetStream is already the pressure source. Operator stops
              # need to converge quickly.
              signal = "SIGTERM";
              timeoutStopSec = "10s";
            };
          };
        };
      })

      (lib.mkIf runtimeEnabled {
        # Sinex is a capture runtime, not a boot prerequisite for the desktop.
        # The upstream module's runtime.target.attachToMultiUser=false +
        # restartOnSwitch=false + restartPolicy options (set above) handle the
        # six long-running runtime services; this block carries only what
        # upstream cannot:
        #   - workstation memory/IO budgets for NATS and PostgreSQL
        #   - per-node MemoryMax/CPUQuota suppression for capture daemons
        #   - bridge-side gating for non-sinex services (postgresql) and the
        #     sinex one-shots (blob-init, tls-init, schema-apply, kitty-setup,
        #     document-scan, nats-bootstrap, preflight) that upstream keeps
        #     attached to multi-user.target
        systemd.services = lib.mkMerge [
          # Per-node uncap (until upstream surfaces a node-resources option):
          # workstation pressure concentrates at NATS/PostgreSQL where the
          # bridge sets explicit caps below. Drop the per-daemon caps that
          # upstream's resourceModule defaults pin on capture nodes,
          # ingestd, and gateway.
          (lib.genAttrs (uncappedRuntimeServices ++ restartableRuntimeServices) (_: perNodeUncapped))
          # Bridge-gated services that aren't the six upstream-handled ones
          # (postgresql/postgresql-setup/sinex-blob-init/sinex-tls-init/...).
          (lib.genAttrs (
            lib.filter (
              n: !(builtins.elem n [
                "sinex-ingestd"
                "sinex-gateway"
              ])
            ) delayedRuntimeServices
          ) (_: bridgeRuntimePolicy))
          {
            # Keep NATS bounded without forcing JetStream restore into swap.
            # Live delayed-start verification on 2026-05-03 showed the old 1G
            # cap pinned nats-server at the limit and pushed ~1.8G to swap
            # while restoring the confirmation stream. The high/max pair below
            # leaves room for the observed working set while still bounding
            # runaway growth. IOWeight=10 keeps sustained JetStream I/O below
            # interactive work without hard per-device throughput ceilings.
            nats = lib.mkMerge [
              bridgeRuntimePolicy
              {
                serviceConfig = {
                  MemoryHigh = "4G";
                  MemoryMax = "6G";
                  IOWeight = 10;
                };
              }
            ];

            # PostgreSQL: nixpkgs module, not sinex; upstream Sinex options
            # cannot gate it. Keep the bridge override.
            postgresql = lib.mkMerge [
              bridgeRuntimePolicy
              {
                unitConfig.PartOf = lib.mkAfter [ "sinex-runtime.target" ];
                serviceConfig = {
                  MemoryHigh = "8G";
                  MemoryMax = "12G";
                  IOWeight = 10;
                };
              }
            ];
          }
        ];
        # postgresql.target leaks into multi-user even with the runtime
        # service's wantedBy stripped; suppress separately.
        systemd.targets = lib.genAttrs delayedRuntimeTargets (_: {
          wantedBy = lib.mkForce [ ];
        }) // {
          sinex-runtime = {
            # Augment the upstream-defined sinex-runtime.target with the
            # workstation-specific description and the extra wants/after
            # this host needs (the bridge-gated services above are not in
            # the upstream's PartOf graph).
            description = lib.mkForce "Delayed automatic Sinex runtime";
            wants = delayedRuntimeUnits ++ [ "network-online.target" ];
            after = [
              "multi-user.target"
              "graphical.target"
              "network-online.target"
            ];
          };
        };
        systemd.timers = {
          sinex-runtime = {
            description = "Delay Sinex runtime startup until after boot";
            wantedBy = lib.mkIf runtimeAutoStart [ "timers.target" ];
            timerConfig = {
              OnActiveSec = sinexRuntimeStartDelay;
              AccuracySec = "15s";
              Unit = "sinex-runtime.target";
            };
          };
        }
        // (lib.genAttrs sinexAutoTimers (_: {
          wantedBy = lib.mkForce (lib.optionals runtimeAutoStart [ "sinex-runtime.target" ]);
          unitConfig.PartOf = [ "sinex-runtime.target" ];
        }));

        # NATS JetStream lives on the /cache NVMe partition. Ensure the
        # directory exists before the service starts so the auto-setup
        # bootstrap doesn't race with fs init.
        systemd.tmpfiles.rules = [
          "d /cache/nats 0750 nats nats -"
        ];
      })

      (lib.mkIf
        (
          cfg.provisionDatabase
          && databasePasswordFile != null
          && config.services.sinex.database.localAuth != "trust"
        )
        {
          # Delay postgresql-setup until agenix has materialized the password file.
          systemd.services.postgresql-setup.unitConfig.ConditionPathIsReadable = [
            databasePasswordFile
          ];
        }
      )

    ]
  );
}
