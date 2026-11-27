# Polylogue: the Rust rewrite's daemon, its CLI and its browser capture.
#
# The CLI, daemon, hooks, MCP and browser host use one wrapper over liveRoot.
# The Python predecessor's archive at dataDir stays under its backup policy.
#
# `sinex.mode` chooses where the archive lives. Standalone keeps it under
# `dataHome` (default `liveRoot/data`). Primary stores it in the host's Sinex
# as the `polylogue` producer, over a separate, initially empty archive under
# `liveRoot/sinex-data`, so the standalone archive stays as it was. Moving to primary follows
# "Moving to primary mode" in the rewrite's docs/architecture.md; the switch is
# the operator's call. The operator's systemd user manager needs the sinex
# group (granted by the Sinex session), so it must have started after that
# grant.
{
  mkServiceModule,
  lib,
  pkgs,
  inputs,
  config,
  ...
}@args:
let
  userName = config.sinnix.user.name;
  homeDir = config.users.users.${userName}.home;
in
mkServiceModule {
  name = "polylogue";
  description = "Polylogue: the rewrite's live daemon, CLI and browser capture";
  extraOptions = {
    sinex = {
      mode = lib.mkOption {
        type = lib.types.enum [
          "standalone"
          "primary"
        ];
        default = "standalone";
        description = "Whether the live archive is Polylogue's own (standalone) or held by this host's Sinex (primary).";
      };
    };

    dataDir = lib.mkOption {
      type = lib.types.str;
      default = "${homeDir}/.local/share/polylogue";
      description = ''
        The Python predecessor's archive root, retained for backups.
        The live CLI uses liveRoot.
      '';
    };

    liveRoot = lib.mkOption {
      type = lib.types.str;
      default = "${config.sinnix.paths.stateRoot}/polylogue-live";
      description = ''
        The archive's data home (``dataHome``). The spools are under ``~/.local/state/polylogue`` on
        the root disk, persisted by modules/persistence.nix.
      '';
    };

    dataHome = lib.mkOption {
      type = lib.types.str;
      default =
        if config.sinnix.services.polylogue.sinex.mode == "primary" then
          "${config.sinnix.services.polylogue.liveRoot}/sinex-data"
        else
          "${config.sinnix.services.polylogue.liveRoot}/data";
      defaultText = lib.literalExpression ''"''${liveRoot}/data"'';
      description = ''
        The XDG data home every polylogue command runs with; the live
        archive is its ``polylogue`` directory. A new archive is built in a
        new data home beside the old one and the switch is this option.
      '';
    };

    mcpSocket = lib.mkOption {
      type = lib.types.str;
      default = "/run/user/${toString config.users.users.${userName}.uid}/polylogue-mcp.sock";
      internal = true;
      readOnly = true;
      description = "Private runtime socket shared by the installed MCP launcher and daemon.";
    };

    readSources = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = ''
        Whether the daemon reads the session sources (agent transcripts,
        hooks, browser capture) into the archive. Off, it serves and keeps
        deriving what the archive already stores, and new sessions wait.
      '';
    };

    startDaemon = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = ''
        Whether polylogue-live is wanted by the user session, so that login
        and installation start it. Activation keeps an existing process alive;
        changing the daemon or archive requires a deliberate restart. Off,
        the unit stays installed but only a
        manual `systemctl --user start polylogue-live` runs it.
      '';
    };

    retainedArchives = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      description = ''
        Archive directories set aside read-only after a cutover. They stay
        covered by the realm backup; their derived index.db is excluded like
        the live archive's.
      '';
    };
  };
  configFn =
    {
      cfg,
      lib,
      pkgs,
      inputs,
      ...
    }:
    let
      rewriteSource = inputs.polylogue-rewrite;

      primary = cfg.sinex.mode == "primary";
      # Polylogue reads only the archive mode from this file.
      sinexSettings = (pkgs.formats.toml { }).generate "sinex.toml" {
        inherit (cfg.sinex) mode;
      };
      cli = config.system.build.polylogueCli;

      extension = rewriteSource.packages.${pkgs.stdenv.hostPlatform.system}.polylogue-extension;
      browser = config.sinnix.features.desktop.browser;
      hostName = "com.polylogue.browser_capture";

      # The live class prioritizes daemon disk access. The daemon, its index
      # build included, fits 8G resident and 1G swapped, or the kernel ends it
      # inside this unit (docs/resource-control.md). There is no MemoryHigh:
      # throttling makes the daemon re-read its own evicted pages from disk.
      liveServiceClass = lib.sinnix.mkRuntimeServiceConfig {
        runtimeInventory = config.sinnix.runtime.inventory;
        unit = "polylogue-live.service";
        manager = "user";
        overrides = {
          MemoryMax = "8G";
          MemorySwapMax = "1G";
        };
      };
    in
    {
      sinnix.features.cli.polylogue.enable = true;

      systemd.tmpfiles.rules = [
        "d ${cfg.dataDir} 0700 ${userName} ${config.users.users.${userName}.group} -"
        "d ${cfg.dataDir}/inbox 0700 ${userName} users -"
        "d ${cfg.liveRoot} 0700 ${userName} ${config.users.users.${userName}.group} -"
      ];

      home-manager.users.${userName} =
        { lib, ... }:
        {
          systemd.user.startServices = lib.mkForce "sd-switch";

          # Completion asks the daemon for a query's fields, values seen and
          # recent session IDs while one is typed.
          programs.zsh.initContent = lib.mkAfter ''
            source <(${cli}/bin/polylogue install zsh --dry-run --program polylogue)
          '';

          # Without this file the archive is standalone.
          xdg.configFile."polylogue/sinex.toml" = lib.mkIf primary { source = sinexSettings; };

          # Chrome reads the native host manifest from its profile directory.
          home.file = lib.optionalAttrs browser.enable {
            "${browser.chromeUserDataDir}/NativeMessagingHosts/${hostName}.json" = {
              force = true;
              source = rewriteSource.lib.browserHostManifest pkgs {
                inherit extension;
                program = "${cli}/bin/polylogue";
              };
            };
          };

          # Chrome resolves the unpacked directory when it loads it. Link
          # each file so updates keep that directory and registration.
          xdg.dataFile."polylogue/extension" = lib.mkIf browser.enable {
            recursive = true;
            source = "${extension}/share/polylogue/extension";
          };

          systemd.user.services.polylogue-live = {
            Unit = {
              Description = "Polylogue daemon over the live archive";
              # An ordinary system switch must not discard a running rebuild.
              # Deploying a changed daemon/archive needs an explicit restart.
              X-SwitchMethod = "keep-old";
            };
            Service = liveServiceClass // {
              ExecStart = "${cli}/bin/polylogue daemon" + lib.optionalString (!cfg.readSources) " --no-sources";
              Environment = [ "POLYLOGUE_MCP_SOCKET=${cfg.mcpSocket}" ];
              # Restart even after a clean stop: a SIGTERM from the OOM response counts as clean.
              Restart = "always";
              RestartSec = "5s";
              # The daemon exits 78 when it refuses the archive (a schema it
              # cannot migrate); restarting cannot change that.
              RestartPreventExitStatus = 78;
              # Clean stops sync the index build so it resumes; SIGKILL forces a rebuild.
              # Fifteen minutes covers syncing a large file under disk contention.
              TimeoutStopSec = "15min";
            };
            Install.WantedBy = lib.optional cfg.startDaemon "default.target";
          };
        };

      assertions = [
        {
          assertion = !primary || (config.services ? sinex && config.services.sinex.enable);
          message = "sinnix.services.polylogue.sinex.mode = \"primary\" needs this host's Sinex";
        }
      ];

      sinnix.runtime.units.polylogue-live = {
        unit = "polylogue-live.service";
        manager = "user";
        resourceClass = "live";
        # Its indexes and caches stay resident beside the session producer
        # within the user live slice's protection (runtime-defaults.nix).
        resources.MemoryLow = "${toString args.helpers.data.runtimeDefaults.memoryBudget.polylogue}M";
        notifyOnFailure = true;
        operatorRestart = true;
      };
    };
} args
