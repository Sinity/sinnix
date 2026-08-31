# Sinex bridge
#
# Host-specific glue between sinnix's options and upstream `services.sinex`:
# runtime package selection, secrets/home/storage placement, workstation
# deployment policy expressed through upstream options, and the mapping from
# `cfg.activationProfile` to the runtime source/automaton enable flags.
#
# Auxiliary-unit gating (wantedBy stripping, sinex-runtime.target wants
# graph, deferred-start timer, document-scan timer pinning) is owned by
# upstream and intentionally not duplicated here.
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
  mkSinexPkgs = pkgs': inputs.sinex.packages.${pkgs'.stdenv.hostPlatform.system};
  sinexEnvironment = lib.toLower cfg.environment;
  targetUserName = config.sinnix.user.name;
  targetUserHome = "/home/${targetUserName}";
  homeManagerServiceName = "home-manager-${targetUserName}";
  # Sinex's own operational substrate, distinct from /realm/data/captures
  # (which is input data sinex *ingests*). On sinnix-prime this places the
  # active substrate on the root SSD, not on /realm.
  sinexRuntimeRoot = "/var/lib/sinex";
  sinexStateRoot = "${sinexRuntimeRoot}/state";
  sinexHome = "${sinexRuntimeRoot}/home";
  sinexPostgresRoot = "${sinexRuntimeRoot}/postgresql";
  sinexPostgresDataDir = "${sinexPostgresRoot}/18";
  # On /realm, not /persist: keeps dump bytes off the worn MX500 while
  # staying inside the /realm btrbk→borg coverage.
  sinexPostgresDumpRoot = "/realm/state/db-dumps/sinex-postgres";
  databaseHost = "127.0.0.1";
  databasePort = 5432;
  databaseUser = "sinex";
  databaseName = "sinex_${sinexEnvironment}";
  databaseAuthentication = ''
    local   all             postgres                                peer
    local   all             all                                     scram-sha-256
    host    all             all             127.0.0.1/32            scram-sha-256
    host    all             all             ::1/128                 scram-sha-256
    host    all             all             0.0.0.0/0               reject
    host    all             all             ::/0                    reject
  '';
  databasePasswordFile = lib.attrByPath [ "sinnix" "secrets" "paths" "sinex-local-db" ] null config;
  natsCliMaxBytes = "2147483647";
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
          user-mile = {
            filesystem = false;
            terminal = true;
            browser = false;
            desktop = false;
            system = false;
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
      maintenanceTimerServiceNames = [
        "sinex-blob-cas-fsck"
        "sinex-blob-cas-sweep"
      ]
      ++ lib.optional activationProfile.document "sinex-document-scan";
      # All source bindings run inside sinexd, so the ACL-granting
      # target-access services must complete before sinexd starts for it to
      # reach user-owned data paths and sockets.
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
          paths = [ sinexPkgs.${toolName} ];
        };
      mkProjectedSinexToolPackage =
        toolName: runtimePackage:
        pkgs.runCommand "${toolName}-${sinexEnvironment}" { } ''
          install -d "$out/bin"
          ln -s ${runtimePackage}/bin/${toolName} "$out/bin/${toolName}"
        '';
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
          sinexPackage = mkScopedSinexPackage sinexPkgs;
          mkToolPackage =
            toolName:
            if runtimeEnabled then
              mkProjectedSinexToolPackage toolName sinexPackage
            else
              mkScopedSinexToolPackage toolName sinexPkgs;
        in
        {
          services.sinex.package = lib.mkDefault sinexPackage;
          services.sinex.cliPackage = lib.mkDefault (mkToolPackage "sinexctl");
          services.sinex.adminPackage = lib.mkDefault (mkToolPackage "xtask");
          services.sinex.users.target = targetUserName;
          sinex.secrets.paths = lib.mkForce (
            lib.mapAttrs (_: toString) (
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
              "d ${sinexPostgresDumpRoot} 0700 postgres postgres -"
            ]
          );
        }
      ))

      (lib.mkIf hostPrepared {
        services = {
          postgresql.dataDir = sinexPostgresDataDir;
          # NixOS's own `authentication` default outranks whatever the sinex
          # module supplies, so without mkForce the deployed pg_hba is
          # upstream's permissive default rather than the policy above -- and
          # nothing in the build says so. Force it until the pinned input
          # carries a priority that loses to a host policy.
          postgresql.authentication = lib.mkForce databaseAuthentication;

          # Upstream validates nats.conf at build time by running
          # `nats-server --config ... -t`, which parses the TLS block and
          # opens the certificate and key. Those are agenix paths under
          # /run/agenix, so they cannot exist inside a build sandbox and the
          # check fails on a configuration that is correct at runtime. This
          # option exists for exactly that case ("when the config can't be
          # checked during build time"). The cost is real -- a syntax error in
          # the NATS settings now surfaces when the unit starts rather than
          # when the system builds -- and it is the price of keeping the
          # listener's credentials out of the world-readable store.
          nats.validateConfig = false;
          # Compress full-page images in WAL: they dominate WAL volume on a
          # write-hot database and the data dir sits on the wear-limited
          # root SSD. lz4 is cheap CPU-wise and reload-safe. Keep
          # full_page_writes on: the nodatacow @sinex subvol has no btrfs
          # checksums, so FPW is the remaining torn-page defense.
          postgresql.settings.wal_compression = "lz4";
          # Sinex defaults connection audit logging on; on a localhost-only
          # single-app DB it is pure noise that the syslog capture source
          # then re-ingests into sinex's own dataset.
          postgresql.settings.log_connections = false;
          postgresql.settings.log_disconnections = false;

          sinex = {
            enable = runtimeEnabled;

            secrets = {
              enableAgenix = false;
            };
            nats = {
              environment = sinexEnvironment;
              enable = runtimeEnabled;
              autoSetup = runtimeEnabled;
              # The capture bus carries raw material and controls admission.
              # Keep its loopback listener encrypted and require the shared
              # Sinex NKey, so an arbitrary local process cannot read or forge
              # capture events. The matching private material is agenix-owned
              # under the sinex-nats-* names configured in modules/secrets.nix.
              tls.enable = true;
              authorization.sharedClient = {
                enable = true;
                nkey = "UDUVCAYOTOC223CCR5FZOWVDFOJYZAQZ7ENQQVWU3ZTH52RFS233KYLI";
              };
              # dataDir/storeDir stay at the upstream default path, which
              # hosts/sinnix-prime/storage.nix bind-mounts from
              # /realm/state/nats — the realm state volume, not the /persist
              # impermanence tree. Nothing here shows that; check storage.nix
              # before assuming this state lives on root.
              dataDir = "/var/lib/nats";
              jetstreamMaxStore = "32G";
              # Express ONLY this host's genuine deltas. The streams attrset is
              # keyed by stream name and every field sinex ships lands at
              # mkDefault, so unset fields inherit from sinex's nats.nix and
              # streams sinex adds later flow in automatically. Re-declaring a
              # byte-identical stream silently shadows that inheritance.
              bootstrapStreams.streams = {
                # natscli rejects --max-bytes above signed 32-bit range, and the
                # live stream already carries a 16 GiB cap; passing no
                # --max-bytes leaves that cap intact instead of shrinking a
                # near-full JetStream during activation. Raw retention is 7 days
                # on this host vs sinex's 72h dev default.
                SINEX_RAW_EVENTS = {
                  maxAge = "168h";
                  maxBytes = null;
                };
                # Same natscli >2 GiB ceiling workaround for the confirmed bus.
                SINEX_RAW_EVENTS_CONFIRMED.maxBytes = null;
                # 7-day diagnostic retention on this host vs sinex's 72h default.
                SINEX_RAW_EVENTS_DLQ.maxAge = "168h";
                SINEX_RAW_EVENTS_PROCESSING_FAILURES.maxAge = "168h";

                # Host-local streams NOT in sinex's canonical topology: the
                # confirmation-watermark lanes this deployment provisions ahead
                # of the Rust runtime consuming them. maxMsgsPerSubject=1 keeps
                # them as compacted last-value lanes.
                SINEX_RAW_EVENTS_CONFIRMATIONS = {
                  subjects = [ "events.confirmations.>" ];
                  maxAge = "72h";
                  maxBytes = natsCliMaxBytes;
                  maxMsgsPerSubject = 1;
                };
                SINEX_RAW_EVENTS_CONFIRMATION_RETRIES = {
                  subjects = [ "events.confirmation_retries.>" ];
                  maxAge = "72h";
                  maxBytes = natsCliMaxBytes;
                  maxMsgsPerSubject = 1;
                };
              };
              # Entity-enricher checkpoints exceed NATS' 1 MiB default payload
              # limit during recovery; the local server is loopback-only, so
              # raise the transport ceiling rather than lose checkpoints.
              extraSettings.max_payload = lib.mkDefault 8388608;
              storeDir = "/var/lib/nats/jetstream";
              killPolicy = {
                # Bounded but generous: JetStream needs real time to close a
                # production-sized store cleanly; a short timeout SIGKILLs
                # NATS mid-shutdown.
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
              # Keep the production policy explicit instead of inheriting an
              # upstream default. This governs application Unix-socket and
              # loopback-TCP connections; the upstream module retains peer
              # only for the postgresql-setup service account.
              localAuth = "scram-sha-256";
              # Deliberately NOT sinex's setupWaitForPaths: it renders
              # ConditionPathIsReadable=, which systemd does not implement, so
              # the gate never gated anything and warned on every reparse. The
              # equivalent condition is declared below with a real key. Drop
              # this override once sinex fixes the option upstream.
              setupWaitForPaths = [ ];
            };

            core = {
              enable = runtimeEnabled;
              api = {
                enable = runtimeEnabled;
                autoGenerateTls = true;
                # The shared per-service pool default (4,
                # database.connectionPool.maxConnections) starves the API under
                # real load: one long replay-preview transaction can time out
                # concurrent telemetry sampling on the same pool. 16 is sinex's
                # own Rust-level PoolConfig::default. Automata and the event
                # engine stay at 4.
                poolMaxConnections = 16;
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
                watchPaths = cfg.filesystem.watchPaths;
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
                # sinexd runs as the sinex system user without
                # DISPLAY/XAUTHORITY, so the clipboard adapter cannot reach X11
                # and triggers a runtime-wide critical failure cascade.
                # Re-enable once sinexd has per-binding env injection or
                # degrades source-worker failures to binding-local.
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
            runtime = {
              nats = {
                # The upstream module derives the tls:// endpoint from the
                # managed server. Pin the remaining client contract here so
                # malformed or missing credential wiring cannot fall back to
                # an unauthenticated plaintext connection.
                tls = {
                  requireTls = true;
                  caCertFile = config.sinnix.secrets.paths.sinex-nats-ca;
                };
                auth.nkeySeedFile = config.sinnix.secrets.paths.sinex-nats-client-nkey;
              };
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
                # Define the timer whenever the runtime is enabled so its shape
                # stays introspectable; only its timers.target installation is
                # gated on the host's auto-start policy.
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

      # The first-user-mile trial is deliberately one source domain. Upstream
      # enables static imports by default, which would otherwise add the Git
      # and Raindrop importers even while every non-terminal domain is disabled.
      (lib.mkIf (runtimeEnabled && cfg.activationProfile == "user-mile") {
        services.sinex.sources.staticImports = lib.mkForce { };
      })

      # Workstation policy that sinex itself does not own: resource class
      # placement for PostgreSQL/NATS, mount ordering for /var/lib/sinex,
      # maintenance-timer scheduling, and the post-activation ACL repair.
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
          sinexd = {
            unit = "sinexd.service";
            resourceClass = "capture-runtime";
            observe = {
              enable = runtimeAutoStart;
              restartable = false;
            };
          };
          nats = {
            unit = "nats.service";
            resourceClass = "capture-substrate";
            observe = {
              enable = runtimeAutoStart;
              restartable = false;
            };
          };
          postgresql = {
            unit = "postgresql.service";
            resourceClass = "capture-substrate";
            observe = {
              enable = runtimeAutoStart;
              restartable = false;
            };
          };
          sinex-postgres-dump = {
            unit = "sinex-postgres-dump.service";
            resourceClass = "backup-maintenance";
          };
          sinex-postgres-dump-timer = {
            unit = "sinex-postgres-dump.timer";
            kind = "timer";
            resourceClass = "backup-maintenance";
          };
        }
        // lib.optionalAttrs activationProfile.document {
          sinex-document-scan = {
            unit = "sinex-document-scan.service";
            resourceClass = "background-maintenance";
          };
        };

        systemd.services = lib.mkMerge [
          # The gate sinex's setupWaitForPaths was meant to be, spelled with a
          # condition systemd implements. agenix writes the file with its
          # content in place, so existence is the materialization signal, and
          # an unmet condition SKIPS the unit rather than failing it -- the
          # same semantics the original intended.
          (lib.mkIf
            (
              cfg.provisionDatabase
              && databasePasswordFile != null
              && config.services.sinex.database.localAuth != "trust"
            )
            {
              postgresql-setup.unitConfig.ConditionPathExists = [ databasePasswordFile ];
            }
          )
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
            # Bootstrap is a client of NATS, not the NATS daemon. It must use
            # the same narrowly-owned client credentials as sinexd rather than
            # requiring the listener account to read them.
            sinex-nats-bootstrap.serviceConfig = {
              User = lib.mkForce "sinex";
              Group = lib.mkForce "sinex";
            };
            sinex-postgres-dump = {
              description = "Dump Sinex PostgreSQL database for disaster recovery";
              after = [
                "postgresql.target"
                "realm.mount"
              ];
              requires = [
                "postgresql.target"
                "realm.mount"
              ];
              unitConfig.RequiresMountsFor = [
                sinexRuntimeRoot
                sinexPostgresDumpRoot
              ];
              restartIfChanged = false;
              serviceConfig =
                (lib.sinnix.mkRuntimeServiceConfig {
                  runtimeInventory = config.sinnix.runtime.inventory;
                  unit = "sinex-postgres-dump.service";
                })
                // {
                  Type = "oneshot";
                  User = "postgres";
                  Group = "postgres";
                  TimeoutStopSec = "15s";
                };
              path = [
                config.services.postgresql.package
                pkgs.coreutils
                pkgs.findutils
                pkgs.gawk
              ];
              script = ''
                set -euo pipefail

                umask 077
                install -d -m 0700 -o postgres -g postgres ${lib.escapeShellArg sinexPostgresDumpRoot}

                stamp="$(date -u +%Y%m%dT%H%M%SZ)"
                final=${lib.escapeShellArg sinexPostgresDumpRoot}/${databaseName}-"$stamp".dump
                tmp="$final.tmp"

                cleanup() {
                  rm -f "$tmp"
                }
                trap cleanup EXIT

                PGPASSWORD="$(tr -d '\r\n' < ${lib.escapeShellArg databasePasswordFile})" \
                  pg_dump \
                    --host=${databaseHost} \
                    --port=${toString databasePort} \
                    --username=${databaseUser} \
                    --dbname=${databaseName} \
                    --format=custom \
                    --file="$tmp"

                chmod 0600 "$tmp"
                mv -f "$tmp" "$final"
                trap - EXIT

                find ${lib.escapeShellArg sinexPostgresDumpRoot} \
                  -maxdepth 1 \
                  -type f \
                  -name ${lib.escapeShellArg "${databaseName}-*.dump"} \
                  -printf '%T@ %p\n' \
                  | sort -rn \
                  | awk 'NR > 14 { print substr($0, index($0, $2)) }' \
                  | xargs -r rm -f
              '';
            };
            # home-manager activation calls chmod 700 /home/${targetUserName}
            # which maps the group bits to the POSIX ACL mask, resetting
            # mask::--x → mask::--- and nullifying sinex's traverse grant.
            # Re-run the generated source access repairs after each
            # home-manager run so the mask is restored immediately. Execute
            # helpers directly instead of restarting their systemd units:
            # the helpers are ordered Before=sinexd.service, and restarting
            # those units during activation pulls sinexd into a restart
            # transaction even when sinexd itself has X-RestartIfChanged=false.
            ${homeManagerServiceName} =
              lib.mkIf (activationProfile.desktop || activationProfile.terminal || activationProfile.browser)
                {
                  # The `+` prefix runs this command as root regardless of the
                  # service user, which has no privilege to repair user ACLs.
                  serviceConfig.ExecStartPost = lib.mkAfter (
                    lib.optionals activationProfile.terminal [
                      "+${config.systemd.services.sinex-terminal-target-access.serviceConfig.ExecStart}"
                    ]
                    ++ lib.optionals activationProfile.browser [
                      "+${config.systemd.services.sinex-browser-target-access.serviceConfig.ExecStart}"
                    ]
                    ++ lib.optionals activationProfile.desktop [
                      "+${config.systemd.services.sinex-desktop-target-access.serviceConfig.ExecStart}"
                    ]
                  );
                };
            sinexd = {
              restartIfChanged = false;
              stopIfChanged = false;
              serviceConfig.Environment = lib.mkAfter [
                # Host runtime policy: bound the DB pool well under the
                # upstream 100-connection default; 32 concurrent sessions
                # still covers catch-up bursts.
                "SINEX_DB_MAX_CONNECTIONS=32"
                "SINEX_DB_MIN_CONNECTIONS=4"
                # git-commit-history invokes git asynchronously inside sinexd,
                # after per-binding env guards have released. Keep this
                # service-level and scoped to the single configured repo.
                "GIT_CONFIG_COUNT=1"
                "GIT_CONFIG_KEY_0=safe.directory"
                "GIT_CONFIG_VALUE_0=/realm/project/sinex"
                # Event-engine policies are exposed as runtime env vars, not
                # Nix module options.
                "SINEX_EVENT_ENGINE_REJECT_INITIAL_REPLAY=false"
                "SINEX_EVENT_ENGINE_STARTUP_CATCH_UP_MAX_CONCURRENT=1"
                # The pinned Sinex Nix module emits `1` for this boolean, but
                # the daemon's top-level Clap argument accepts only true/false.
                # A later Environment= assignment wins in systemd.
                "SINEX_NATS_REQUIRE_TLS=true"
              ];
              # Bounded drain window: forced kills replay cleanly via
              # JetStream, so bounding activation stalls beats waiting on a
              # daemon that may ignore SIGTERM.
              serviceConfig.TimeoutStopSec = lib.mkForce "90s";
            };
          }
          (lib.genAttrs maintenanceTimerServiceNames (_: {
            restartIfChanged = false;
            stopIfChanged = false;
            serviceConfig = {
              TimeoutStopSec = lib.mkForce "15s";
            };
          }))
          (lib.mapAttrs (_: before: {
            before = lib.mkForce before;
          }) targetAccessServiceBefore)
        ];
        systemd.targets.sinex-runtime = {
          description = lib.mkForce "Delayed automatic Sinex runtime";
          unitConfig = {
            X-RestartIfChanged = false;
            X-StopIfChanged = false;
          };
          # extraAfter declares ordering against network-online.target; pair
          # it with wants so systemd doesn't emit an unfulfilled-ordering
          # warning at evaluation time.
          wants = [ "network-online.target" ] ++ lib.optionals databasePrepared [ "postgresql.target" ];
        };
        # PostgreSQL owns its own aggregate target. It otherwise keeps its
        # Wants= graph alive after sinex-runtime.target stops, leaving the
        # manually parked runtime half-running.
        systemd.targets.postgresql.unitConfig.PartOf = [ "sinex-runtime.target" ];
        # Maintenance timers follow the runtime TARGET, not the auto-start
        # POLICY: this host is manual-start by policy but runs 24/7, so gating
        # timers on auto-start masks them and silently kills the DR dump.
        # wantedBy pulls a timer up whenever sinex-runtime.target starts
        # (manual or auto); PartOf stops it with the target.
        systemd.timers =
          lib.genAttrs maintenanceTimerServiceNames (_: {
            wantedBy = lib.mkForce [ "sinex-runtime.target" ];
            unitConfig.PartOf = [ "sinex-runtime.target" ];
            timerConfig.Persistent = lib.mkForce false;
          })
          // {
            sinex-postgres-dump = {
              wantedBy = [ "sinex-runtime.target" ];
              unitConfig.PartOf = [ "sinex-runtime.target" ];
              timerConfig = {
                OnCalendar = "*-*-* 03:12:00";
                RandomizedDelaySec = "20min";
                # A missed daily DR dump should catch up after downtime.
                Persistent = true;
              };
            };
          };
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
