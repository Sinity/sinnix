# Sinex bridge
#
# Carries the genuinely host-specific glue between sinnix's options and
# upstream `services.sinex`:
#
# - selecting the Sinex runtime package from the flake input
# - secrets paths + sinex user home location + database password binding
# - storage placement (NATS state dir, runtime root)
# - workstation deployment policy expressed through upstream options:
#     services.sinex.runtime.target.{attachToMultiUser,manualStartOnly,
#       includeDatabase,extraAfter}
#     services.sinex.runtime.deferredStart.{enable,delay}
#     services.sinex.runtime.restartPolicy.*
#     services.sinex.bootstrap.restartPolicy
#     services.sinex.nats.killPolicy.*
#     services.sinex.database.setupWaitForPaths
# - the activation-profile mapping from sinnix's `cfg.activationProfile`
#   string to the runtime source/automaton `enable` flags
#
# Auxiliary-unit gating (wantedBy stripping, sinex-runtime.target wants
# graph, deferred-start timer, document-scan timer pinning) is owned by
# upstream as of sinex#1306 and intentionally not duplicated here.
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
  inherit (config.sinnix.paths) realmRoot;
  mkSinexPkgs = pkgs': inputs.sinex.packages.${pkgs'.stdenv.hostPlatform.system};
  sinexEnvironment = lib.toLower cfg.environment;
  targetUserName = config.sinnix.user.name;
  targetUserHome = "/home/${targetUserName}";
  homeManagerServiceName = "home-manager-${targetUserName}";
  # Sinex runtime state lives at /var/lib/sinex (NixOS convention for service
  # state). The earlier /realm/data/captures/sinex layout misused the captures
  # namespace — /realm/data/captures is for input data sinex *ingests*, not
  # sinex's own operational substrate. On sinnix-prime this currently places
  # the active substrate on the root SSD, not on /realm.
  sinexRuntimeRoot = "/var/lib/sinex";
  sinexStateRoot = "${sinexRuntimeRoot}/state";
  sinexHome = "${sinexRuntimeRoot}/home";
  sinexPostgresRoot = "${sinexRuntimeRoot}/postgresql";
  sinexPostgresDataDir = "${sinexPostgresRoot}/18";
  databaseHost = "127.0.0.1";
  databasePort = 5432;
  databaseUser = "sinex";
  databaseName = "sinex_${sinexEnvironment}";
  databasePasswordFile = lib.attrByPath [ "sinnix" "secrets" "paths" "sinex-local-db" ] null config;
  hostPrepared = cfg.prepareHost || cfg.enable || cfg.provisionDatabase;
  runtimeEnabled = cfg.enable;
  runtimeAutoStart = runtimeEnabled && cfg.autoStart;
  databasePrepared = cfg.provisionDatabase || cfg.enable;
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
            kitty = true;
          };
        }
        .${cfg.activationProfile};
      filesystemWatchPaths = [
        "${realmRoot}/project"
        "${realmRoot}/inbox/download"
      ];
      maintenanceTimerServiceNames = [
        "sinex-document-scan"
      ];
      # Post-Wave-B fold all source bindings run inside sinexd, not per-source
      # systemd units. ACL-granting target-access services must complete before
      # sinexd starts so it can reach user-owned data paths and sockets.
      # sinex-document-target-access gates the separate one-shot document scan.
      targetAccessServiceBefore = {
        sinex-browser-target-access = [ "sinexd.service" ];
        sinex-desktop-target-access = [ "sinexd.service" ];
        sinex-document-target-access = [ "sinex-document-scan.service" ];
        sinex-terminal-target-access = [ "sinexd.service" ];
      };
      mkScopedSinexPackage =
        sinexPkgs:
        pkgs.symlinkJoin {
          name = "sinex-runtime-${sinexEnvironment}";
          paths = lib.unique (
            lib.optionals runtimeEnabled [
              # Aggregate runtime so Nix builds Sinex once for deployment.
              # Selecting per-source packages reintroduces one SQLx/Postgres
              # build derivation per service.
              sinexPkgs.sinex
            ]
            ++ lib.optionals (!runtimeEnabled && databasePrepared) [ sinexPkgs.xtask ]
          );
        };
      mkScopedSinexToolPackage =
        toolName: sinexPkgs:
        pkgs.symlinkJoin {
          name = "${toolName}-${sinexEnvironment}";
          paths = [ sinexPkgs.sinex ];
        };
    in
    lib.mkMerge [
      (lib.mkIf (!runtimeEnabled) {
        services.sinex = {
          secrets.enableAgenix = lib.mkDefault false;
          core.enable = lib.mkDefault false;
          runtime.enable = lib.mkDefault false;
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
          services.sinex.cliPackage = lib.mkDefault (mkScopedSinexToolPackage "sinexctl" sinexPkgs);
          services.sinex.adminPackage = lib.mkDefault (mkScopedSinexToolPackage "xtask" sinexPkgs);
          services.sinex.users.target = targetUserName;
          sinex.secrets.paths = lib.mkForce (
            lib.mapAttrs (_: path: toString path) (
              lib.filterAttrs (
                name: _: lib.hasPrefix "sinex-" name || lib.hasPrefix "nats-" name
              ) config.sinnix.secrets.paths
            )
          );

          # Pin the sinex user home to /var/lib/sinex/home so it sits beside
          # the postgres data dir and state root, not nested under stateRoot.
          users.users.sinex = {
            home = lib.mkForce sinexHome;
            homeMode = lib.mkForce "0711";
            createHome = lib.mkForce true;
            extraGroups = lib.optionals (cfg.provisionDatabase || cfg.enable) [ "postgres" ];
          };

          systemd.tmpfiles.rules = lib.mkAfter (
            [
              "d ${sinexRuntimeRoot} 0755 root root -"
              "d ${sinexHome} 0711 sinex sinex -"
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
              jetstreamMaxStore = "32G";
              # Entity-enricher checkpoints currently exceed NATS' 1 MiB
              # default payload limit during recovery. The local server is
              # loopback-only; raise the transport ceiling so checkpoints can
              # persist while upstream trims checkpoint state size.
              extraSettings.max_payload = lib.mkDefault 8388608;
              # The dedicated /cache NVMe was removed after sustained I/O
              # failures. Keep JetStream under the normal NATS state root.
              storeDir = "/var/lib/nats/jetstream";
              killPolicy = {
                # Give JetStream enough bounded time to close a
                # production-sized store cleanly. Live stop evidence on
                # 2026-05-03 showed the old 10s timeout SIGKILLed NATS
                # during JetStream shutdown.
                signal = "SIGTERM";
                timeoutStopSec = "90s";
              };
            };

            stateRoot = sinexStateRoot;

            database = {
              enable = databasePrepared;
              autoSetup = databasePrepared;
              host = databaseHost;
              port = databasePort;
              name = databaseName;
              user = databaseUser;
              # Delay postgresql-setup until agenix has materialized the
              # password file (no-op when localAuth = "trust").
              setupWaitForPaths = lib.optional (
                cfg.provisionDatabase
                && databasePasswordFile != null
                && config.services.sinex.database.localAuth != "trust"
              ) databasePasswordFile;
            };

            core = {
              enable = runtimeEnabled;
              event_engine = {
                rejectInitialReplay = false;
                startupCatchUpMaxConcurrent = 1;
              };
              api = {
                enable = runtimeEnabled;
                autoGenerateTls = true;
              };
            };

            storage = {
              blob = {
                enable = runtimeEnabled;
                # Upstream only defines sinex-blob-init for legacy git-annex
                # storage, but generated source/core units depend on it whenever
                # autoInit is true. This host uses CAS storage, so keep autoInit
                # off to avoid a dangling optional dependency.
                autoInit = false;
              };
            };

            lifecycle = {
              # Full preflight can touch production-sized data and is an
              # operator diagnostic, not a safe prerequisite for desktop
              # activation.
              preflight.enable = false;
              maintenance.enable = runtimeEnabled;
              updates.enable = runtimeEnabled;
            };

            runtime = {
              enable = runtimeEnabled;
            };

            sources = {
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
                # Disabled post-sinexd-collapse: the single daemon runs as the
                # sinex system user without DISPLAY/XAUTHORITY, so the clipboard
                # adapter cannot reach X11 and triggers a runtime-wide critical
                # failure cascade. Re-enable when sinexd has per-binding env
                # injection or the runtime degrades source-worker failures
                # from "critical" to "binding-local".
                clipboard.enable = false;
              };

              system = {
                enable = runtimeEnabled && activationProfile.system;
              };

              document = {
                enable = runtimeEnabled && activationProfile.document;
              };
            };

            automata = {
              enable = runtimeEnabled && activationProfile.automata;
              canonicalizer = {
                enable = runtimeEnabled && activationProfile.automata;
                profile = lib.mkDefault "heavy";
              };
              healthAggregator = {
                enable = runtimeEnabled && activationProfile.automata;
                profile = lib.mkDefault "heavy";
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
            # Sinex itself owns the wantedBy stripping, sinex-runtime.target
            # wants graph, and deferred-start timer.
            runtime = {
              target = {
                attachToMultiUser = false;
                manualStartOnly = true;
                # Postgres exists on this host solely to serve Sinex; gate
                # it through sinex-runtime.target.
                includeDatabase = databasePrepared;
                extraAfter = [
                  "multi-user.target"
                  "graphical.target"
                  "network-online.target"
                ];
              };
              deferredStart = {
                # Always define the timer when the runtime is enabled so its
                # shape (5min delay, sinex-runtime.target unit) is
                # introspectable; gate timers.target installation on the
                # host's auto-start policy.
                enable = runtimeEnabled;
                autoStart = runtimeAutoStart;
                delay = "5min";
                accuracy = "15s";
              };
              restartOnSwitch = false;
              restartPolicy = {
                # Bound failure loops at three retries / 10 minutes / 30s
                # backoff so a stuck capture daemon stops generating
                # NATS/Postgres pressure.
                mode = "on-failure";
                backoffSec = 30;
                intervalSec = 600;
                burst = 3;
              };
            };
            bootstrap.restartPolicy = "no";
          };
        };
      })

      # Workstation policy that sinex itself does not own:
      #   - keep PostgreSQL/NATS below interactive priority; they are
      #     long-lived capture substrate writers, not login/TTY-critical
      #     services
      #   - declare RequiresMountsFor on /var/lib/sinex for postgresql so
      #     activation waits for the mount when /var/lib/sinex is a separate
      #     filesystem
      #   - retitle sinex-runtime.target to reflect the host's automation
      #     model
      #   - give notify-style source services enough time to acquire their
      #     local data-source lease before the unit start deadline
      #   - drop workstation-civil scheduler bias from one-shot maintenance
      #     timers and force their next-fire semantics
      #   - re-run sinex-desktop-target-access after every nixos-rebuild switch
      #     because home-manager activation calls chmod 700 on the target home,
      #     maps the group bits to the POSIX ACL mask, resetting mask::--x →
      #     mask::--- and nullifying the sinex traverse grant. Ordering after
      #     the Home Manager service ensures the ACL is set last.
      (lib.mkIf runtimeEnabled {
        sinnix.runtime.surfaces = {
          sinex-runtime = {
            unit = "sinex-runtime.target";
            kind = "target";
            resourceClass = "capture-runtime";
            observe = {
              enable = runtimeAutoStart;
              restartable = false;
            };
          };
          sinex-runtime-timer = {
            unit = "sinex-runtime.timer";
            kind = "timer";
            resourceClass = "capture-runtime";
          };
          nats = {
            unit = "nats.service";
            resourceClass = "capture-substrate";
          };
          postgresql = {
            unit = "postgresql.service";
            resourceClass = "capture-substrate";
          };
          sinex-document-scan = {
            unit = "sinex-document-scan.service";
            resourceClass = "background-maintenance";
          };
        };

        systemd.services = lib.mkMerge [
          {
            postgresql = {
              unitConfig.RequiresMountsFor = [ sinexRuntimeRoot ];
              serviceConfig = lib.sinnix.mkRuntimeServiceConfig {
                runtimeInventory = config.sinnix.runtime.inventory;
                unit = "postgresql.service";
              };
            };
            nats.serviceConfig = lib.sinnix.mkRuntimeServiceConfig {
              runtimeInventory = config.sinnix.runtime.inventory;
              unit = "nats.service";
            };
            # home-manager activation calls chmod 700 /home/${targetUserName}
            # which maps the group bits to the POSIX ACL mask, resetting
            # mask::--x → mask::--- and nullifying sinex's traverse grant.
            # Re-run sinex-desktop-target-access after each home-manager run
            # so the mask is restored immediately.
            ${homeManagerServiceName} = {
              # The `+` prefix runs this command as root regardless of the
              # service user, which has no privilege to restart system services.
              serviceConfig.ExecStartPost = lib.mkAfter [
                "+${pkgs.systemd}/bin/systemctl restart --no-block sinex-desktop-target-access.service"
              ];
            };
            sinexd = {
              restartIfChanged = false;
              stopIfChanged = false;
              serviceConfig.TimeoutStopSec = lib.mkForce "10min";
            };
          }
          (lib.genAttrs maintenanceTimerServiceNames (_: {
            restartIfChanged = false;
            stopIfChanged = false;
            serviceConfig = {
              Nice = lib.mkForce null;
              CPUWeight = lib.mkForce null;
              IOWeight = lib.mkForce null;
              IOSchedulingClass = lib.mkForce null;
              TimeoutStopSec = lib.mkDefault "15s";
            };
          }))
          (lib.mapAttrs (_: before: {
            before = lib.mkForce before;
          }) targetAccessServiceBefore)
        ];
        systemd.targets.sinex-runtime = {
          description = lib.mkForce "Delayed automatic Sinex runtime";
          # extraAfter declares ordering against network-online.target; pair
          # it with wants so systemd doesn't emit an unfulfilled-ordering
          # warning at evaluation time.
          wants = [ "network-online.target" ] ++ lib.optionals databasePrepared [ "postgresql.target" ];
        };
        systemd.timers = lib.genAttrs maintenanceTimerServiceNames (_: {
          timerConfig.Persistent = lib.mkForce false;
        });
      })

      # ── deploymentRole: workstation-thin ────────────────────────────────
      # Host runs the sinex capture runtime but reads database + NATS over
      # the wire from a remote replica. Local postgresql/nats are disabled
      # and DATABASE_URL/NATS_URL are sourced from an agenix-decrypted env
      # file (typically /run/agenix/sinex-remote-db, written by the operator
      # as a sequence of `KEY=value` lines).
      (lib.mkIf (cfg.deploymentRole == "workstation-thin") {
        services.postgresql.enable = lib.mkForce false;
        services.nats.enable = lib.mkForce false;
        services.sinex.database.enable = lib.mkForce false;
        services.sinex.database.autoSetup = lib.mkForce false;
        services.sinex.nats.enable = lib.mkForce false;
        services.sinex.nats.autoSetup = lib.mkForce false;

        # Wire the remote-db env file into sinexd. The file is operator-managed;
        # if it is absent at start time, the unit will fail explicitly rather
        # than silently fall back to a local socket.
        systemd.services.sinexd.serviceConfig.EnvironmentFile = [
          "/run/agenix/sinex-remote-db"
        ];
      })

      # ── deploymentRole: replica ─────────────────────────────────────────
      # Host runs postgresql + NATS for remote workstation-thin sources but
      # does not run the local sinexd capture runtime. The collector/
      # receiver path stays alive via the database + nats services; ingest
      # sources are disabled.
      (lib.mkIf (cfg.deploymentRole == "replica") {
        services.sinex = {
          sources = {
            filesystem.enable = lib.mkForce false;
            terminal.enable = lib.mkForce false;
            browser.enable = lib.mkForce false;
            desktop.enable = lib.mkForce false;
            system.enable = lib.mkForce false;
            document.enable = lib.mkForce false;
          };
          automata.enable = lib.mkForce false;
        };
      })
    ]
  );
}
