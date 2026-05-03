# Sinex bridge
#
# This module carries the heavy integration with the upstream `services.sinex`
# option tree. Keep it opt-in so the generic sinnix module graph does not pay
# for Sinex evaluation when the host does not import the upstream module.
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
      runtimeServicePolicy = {
        wantedBy = lib.mkForce [ ];
        unitConfig = {
          PartOf = [ "sinex-runtime.target" ];
          RequiresMountsFor = [ sinexCaptureRoot ];
        };
        # Sinex starts through sinex-runtime.target, not as a side effect of
        # host activation. Several services require bootstrap/preflight units
        # that pull NATS/PostgreSQL up; restart-on-switch recreated pressure
        # incidents during ordinary NixOS activation.
        restartIfChanged = false;
      };
      uncappedRuntimeServicePolicy = {
        serviceConfig = {
          # Upstream Sinex's reusable NixOS module ships concrete
          # MemoryMax/CPUQuota defaults for portability. This workstation keeps
          # runtime daemons bounded at the substrate where it matters
          # (PostgreSQL/NATS) and otherwise uses restart limits/weights, not
          # per-node hard caps that can silently throttle capture correctness.
          MemoryMax = lib.mkForce null;
          CPUQuota = lib.mkForce null;
        };
      };
      boundedRuntimeRestartPolicy = {
        unitConfig = {
          # Upstream Sinex uses unlimited StartLimitIntervalSec=0 for capture
          # daemons. On this workstation, failure loops must stop and become
          # visible instead of generating unbounded NATS/Postgres/git-annex
          # pressure. Normal transient failures still get a few retries.
          StartLimitIntervalSec = lib.mkForce 600;
          StartLimitBurst = lib.mkForce 3;
        };
        serviceConfig = {
          Restart = lib.mkForce "on-failure";
          RestartSec = lib.mkForce "30s";
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
          };
        };
      })

      (lib.mkIf runtimeEnabled {
        # Sinex is a capture runtime, not a boot prerequisite for the desktop.
        # Start the stack shortly after boot through an explicit target so
        # PostgreSQL/schema apply/NATS/node startup cannot hold graphical.target.
        # Strip both direct services and the postgresql.target install surface;
        # otherwise local PostgreSQL still leaks into multi-user.target.
        systemd.services =
          lib.genAttrs delayedRuntimeServices (_: runtimeServicePolicy)
          // lib.genAttrs uncappedRuntimeServices (
            _:
            lib.mkMerge [
              runtimeServicePolicy
              uncappedRuntimeServicePolicy
            ]
          )
          // lib.genAttrs restartableRuntimeServices (
            _:
            lib.mkMerge [
              runtimeServicePolicy
              uncappedRuntimeServicePolicy
              boundedRuntimeRestartPolicy
            ]
          )
          // {
            # Keep NATS bounded without forcing JetStream restore into swap.
            # Live delayed-start verification on 2026-05-03 showed the old 1G
            # cap pinned nats-server at the limit and pushed ~1.8G to swap while
            # restoring the confirmation stream. The high/max pair below leaves
            # room for the observed working set while still bounding runaway
            # growth. IOWeight=10 keeps sustained JetStream I/O below
            # interactive work without hard per-device throughput ceilings.
            nats = lib.mkMerge [
              runtimeServicePolicy
              {
                serviceConfig = {
                  MemoryHigh = "4G";
                  MemoryMax = "6G";
                  IOWeight = 10;
                  # NATS' graceful SIGUSR2 drain can sit for minutes while
                  # JetStream is already the pressure source. Operator stops
                  # need to converge quickly.
                  KillSignal = lib.mkForce "SIGTERM";
                  TimeoutStopSec = lib.mkForce "10s";
                };
              }
            ];

            # These are validation/bootstrap one-shots. Restart loops here keep
            # pulling NATS/PostgreSQL back up after an operator stops the runtime,
            # which is exactly the failure mode seen during the 2026-05-02
            # pressure incident.
            sinex-nats-bootstrap = {
              restartIfChanged = false;
              unitConfig.PartOf = [ "sinex-runtime.target" ];
              wantedBy = lib.mkForce [ ];
              serviceConfig = {
                Restart = lib.mkForce "no";
                MemoryMax = lib.mkForce null;
                CPUQuota = lib.mkForce null;
              };
            };
            sinex-preflight = {
              restartIfChanged = false;
              unitConfig.PartOf = [ "sinex-runtime.target" ];
              wantedBy = lib.mkForce [ ];
              serviceConfig = {
                Restart = lib.mkForce "no";
                MemoryMax = lib.mkForce null;
                CPUQuota = lib.mkForce null;
              };
            };

            # Restrict PostgreSQL from consuming all system memory and give it
            # proportional background I/O priority without fixed device caps.
            postgresql = lib.mkMerge [
              runtimeServicePolicy
              {
                unitConfig.PartOf = lib.mkAfter [ "sinex-runtime.target" ];
                serviceConfig = {
                  MemoryHigh = "8G";
                  MemoryMax = "12G";
                  IOWeight = 10;
                };
              }
            ];
          };
        systemd.targets =
          lib.genAttrs delayedRuntimeTargets (_: {
            wantedBy = lib.mkForce [ ];
          })
          // {
            sinex-runtime = {
              description = "Delayed automatic Sinex runtime";
              # NixOS activation metadata only: do not start/restart the target
              # during a switch. The sinex-runtime.timer still starts this
              # target automatically after the configured delay.
              unitConfig.X-OnlyManualStart = true;
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
