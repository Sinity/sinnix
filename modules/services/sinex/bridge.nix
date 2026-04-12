# Sinex upstream bridge
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
  inherit (config.sinnix.paths) realmRoot;
  mkSinexPkgs = pkgs': inputs.sinex.packages.${pkgs'.stdenv.hostPlatform.system};
  sinexEnvironment = lib.toLower cfg.environment;
  targetUserName = config.sinnix.user.name;
  targetUserHome = lib.attrByPath [
    "users"
    "users"
    targetUserName
    "home"
  ] "/home/${targetUserName}" config;
  targetUserUid = lib.attrByPath [ "users" "users" targetUserName "uid" ] null config;
  databaseHost = "127.0.0.1";
  databasePort = 5432;
  databaseUser = "sinex";
  databaseName = "sinex_${sinexEnvironment}";
  databaseSocketDir = "/run/postgresql";
  schemaBootstrapUser = "postgres";
  databasePasswordFile = lib.attrByPath [ "sinnix" "secrets" "paths" "sinex-local-db" ] null config;
  gatewayAdminTokenFile = lib.attrByPath [
    "sinnix"
    "secrets"
    "paths"
    "sinex-gateway-admin-token"
  ] "/run/agenix/sinex-gateway-admin-token" config;
  natsCaCertFile = lib.attrByPath [ "sinnix" "secrets" "paths" "sinex-nats-ca" ] null config;
  natsClientCertFile = lib.attrByPath [
    "sinnix"
    "secrets"
    "paths"
    "sinex-nats-client-cert"
  ] null config;
  natsClientKeyFile = lib.attrByPath [
    "sinnix"
    "secrets"
    "paths"
    "sinex-nats-client-key"
  ] null config;
  natsTokenFile = lib.attrByPath [ "sinnix" "secrets" "paths" "sinex-nats-token" ] null config;
  natsCredsFile = lib.attrByPath [ "sinnix" "secrets" "paths" "sinex-nats-client-creds" ] null config;
  natsNkeySeedFile = lib.attrByPath [
    "sinnix"
    "secrets"
    "paths"
    "sinex-nats-client-nkey"
  ] null config;
  databaseUrl = "postgresql://${databaseUser}@${databaseHost}:${toString databasePort}/${databaseName}";
  schemaBootstrapUrl = "postgresql:///${databaseName}?host=${databaseSocketDir}&user=${schemaBootstrapUser}";
  hostPrepared = cfg.prepareHost || cfg.enable || cfg.provisionDatabase;
  runtimeEnabled = cfg.enable;
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
            desktop = false;
            system = true;
            automata = false;
            canonicalizer = false;
            healthAggregator = false;
            kitty = false;
          };
          capture = {
            filesystem = true;
            terminal = true;
            desktop = false;
            system = true;
            automata = true;
            canonicalizer = true;
            healthAggregator = true;
            kitty = true;
          };
          full = {
            filesystem = true;
            terminal = true;
            desktop = true;
            system = true;
            automata = true;
            canonicalizer = true;
            healthAggregator = true;
            kitty = true;
          };
        }
        .${cfg.activationProfile};
      terminalHistorySources = [
        {
          path = "${targetUserHome}/.bash_history";
          shell = "bash";
        }
        {
          path = "${targetUserHome}/.zsh_history";
          shell = "zsh";
        }
        {
          path = "${targetUserHome}/.local/share/atuin/history.db";
          shell = "atuin";
        }
        {
          path = "${targetUserHome}/.local/share/fish/fish_history";
          shell = "fish";
        }
      ];
      terminalBindReadOnlyPaths = lib.optional (targetUserHome != null) {
        source = targetUserHome;
        destination = targetUserHome;
      };
      activitywatchDbPath = "${targetUserHome}/.local/share/activitywatch/aw-server-rust/sqlite.db";
      desktopRuntimeDir = if targetUserUid == null then null else "/run/user/${toString targetUserUid}";
      desktopBindReadOnlyPaths = lib.optional (desktopRuntimeDir != null) {
        source = desktopRuntimeDir;
        destination = desktopRuntimeDir;
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
            dlq.enable = lib.mkDefault false;
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
          services.sinex.package = lib.mkDefault sinexPkgs.sinex;
          services.sinex.cliPackage = lib.mkDefault sinexPkgs.sinexctl;
        }
      ))

      (lib.mkIf hostPrepared {
        services.sinex.users.target = targetUserName;
      })

      (lib.mkIf hostPrepared {
        sinex.secrets.paths = lib.mkForce (
          lib.mapAttrs (_: path: toString path) (
            lib.filterAttrs (
              name: _: lib.hasPrefix "sinex-" name || lib.hasPrefix "nats-" name
            ) config.sinnix.secrets.paths
          )
        );

        users.users.sinex = {
          home = lib.mkForce "/var/lib/sinex";
          createHome = lib.mkForce true;
          extraGroups = lib.optionals (cfg.provisionDatabase || cfg.enable) [ "postgres" ];
        };

        system.activationScripts.sinexStateRootOwnership.text = ''
          if getent passwd sinex >/dev/null; then
            install -d -m 0755 -o sinex -g sinex \
              /var/lib/sinex \
              /var/lib/sinex/.local \
              /var/lib/sinex/.local/state \
              /var/lib/sinex/.local/state/sinex \
              /var/lib/sinex/.local/state/sinex/blob-repository \
              /var/lib/sinex/.local/state/sinex/failures \
              /var/lib/sinex/.local/state/sinex/logs \
              /var/lib/sinex/.local/state/sinex/run \
              /var/lib/sinex/.local/state/sinex/spool \
              /var/lib/sinex/.local/state/sinex/tls
            ${pkgs.systemd}/bin/systemd-tmpfiles --create --prefix=/var/lib/sinex
          fi
        '';

        services.postgresql.authentication = lib.mkForce ''
          local   all             postgres                                peer map=postgres
          local   all             all                                     peer
          host    all             all             127.0.0.1/32            ${config.services.sinex.database.localAuth}
          host    all             all             ::1/128                 ${config.services.sinex.database.localAuth}
          host    all             all             0.0.0.0/0               reject
          host    all             all             ::/0                    reject
        '';

        services.sinex = {
          enable = runtimeEnabled;

          secrets = {
            enableAgenix = false;
            gatewayAdminTokenFile = lib.mkDefault gatewayAdminTokenFile;
          };
          nats = {
            environment = sinexEnvironment;
            enable = runtimeEnabled;
            autoSetup = runtimeEnabled;
          };

          stateRoot = "/var/lib/sinex/.local/state/sinex";
          logLevel = "info";

          database = {
            enable = databasePrepared;
            autoSetup = databasePrepared;
            host = databaseHost;
            port = databasePort;
            name = databaseName;
            user = databaseUser;
            passwordFile = databasePasswordFile;
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
            dlq.enable = runtimeEnabled;
          };

          lifecycle = {
            preflight.enable = runtimeEnabled;
            maintenance = {
              enable = runtimeEnabled;
              tasks.dlq = lib.mkForce false;
            };
            updates.enable = runtimeEnabled;
          };

          nodes = {
            enable = runtimeEnabled;
            defaults.instances = 1;

            filesystem = {
              enable = runtimeEnabled && activationProfile.filesystem;
              instances = 1;
              watchPaths = [ realmRoot ];
            };

            terminal = {
              enable = runtimeEnabled && activationProfile.terminal;
              instances = 1;
              historySources = terminalHistorySources;
              access.bindReadOnlyPaths = lib.mkDefault terminalBindReadOnlyPaths;
            };

            desktop = {
              enable = runtimeEnabled && activationProfile.desktop;
              instances = 1;
              clipboard.enable = true;
              history.activitywatchDbPath = activitywatchDbPath;
              session.runtimeDir = desktopRuntimeDir;
              access.bindReadOnlyPaths = lib.mkDefault desktopBindReadOnlyPaths;
            };

            system = {
              enable = runtimeEnabled && activationProfile.system;
              instances = 1;
            };

            automata = {
              enable = runtimeEnabled && activationProfile.automata;
              canonicalizer.enable = runtimeEnabled && activationProfile.canonicalizer;
              healthAggregator.enable = runtimeEnabled && activationProfile.healthAggregator;
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

        # Upstream sinex module omits SINEX_ENVIRONMENT from the preflight service;
        # the binary panics without it on non-dev builds.
        systemd.services.sinex-preflight.environment.SINEX_ENVIRONMENT =
          lib.mkIf runtimeEnabled sinexEnvironment;
      })

      (lib.mkIf cfg.provisionDatabase {
        assertions = [
          {
            assertion = databasePasswordFile != null;
            message = "sinnix.services.sinex requires the sinex-local-db agenix secret";
          }
        ];

        # Skip postgresql-setup cleanly when agenix hasn't decrypted yet (boot race).
        # On the next activation the secret exists and the service succeeds.
        systemd.services.postgresql-setup.unitConfig.ConditionPathIsReadable = lib.mkIf (
          databasePasswordFile != null
        ) [ databasePasswordFile ];
      })

      # Schema-apply pool cap: the upstream sinex-schema-apply oneshot inherits
      # the default pool size (100) which can exceed PostgreSQL max_connections
      # on a host that only provisions the database without the full runtime.
      (lib.mkIf databasePrepared {
        systemd.services.sinex-schema-apply.environment.SINEX_DB_MAX_CONNECTIONS = "5";
      })
    ]
  );
}
