# Polylogue: the Rust rewrite's daemon, its CLI and its browser capture.
#
# The rewrite (input `polylogue-rewrite`) runs live as polylogue-live.service
# over its own archive under `liveRoot`. The retained Python stack keeps only
# its CLI, MCP and hook packages (modules/features/cli/polylogue.nix) and the
# polylogue.toml they read; its daemon unit is gone. The Python archive at
# `dataDir` is left as it is.
#
# The rewrite locates everything from the environment: the archive is
# `$XDG_DATA_HOME/polylogue` and its spools are under `$XDG_STATE_HOME/polylogue`.
# One wrapper, `polylogue-live`, sets both and is the daemon's command, the
# operator's CLI and the browser extension's native messaging host, so all
# three always agree on the archive.
#
# `sinex.mode` chooses where the archive lives. Standalone keeps it under
# `liveRoot/data`. Primary stores it in the host's Sinex as the `polylogue`
# producer, over a separate, initially empty archive under `liveRoot/sinex-data`,
# so the standalone archive stays as it was. Moving to primary follows
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
  helpers,
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
      passwordFile = lib.mkOption {
        type = lib.types.str;
        default = config.sinnix.secrets.paths.sinex-nats-polylogue;
        description = "The `polylogue` producer's NATS password, readable by the operator.";
      };
    };

    dataDir = lib.mkOption {
      type = lib.types.str;
      default = "${homeDir}/.local/share/polylogue";
      description = ''
        The Python predecessor's archive root, read by the retained Python
        CLI and MCP tools and written to their ``polylogue.toml``.
      '';
    };

    liveRoot = lib.mkOption {
      type = lib.types.str;
      default = "${config.sinnix.paths.stateRoot}/polylogue-live";
      description = ''
        Everything the rewrite keeps: ``data/polylogue`` is the archive,
        ``state/polylogue`` its spools, ``extension`` the unpacked browser
        extension Chrome loads.
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
      system = pkgs.stdenv.hostPlatform.system;
      rewriteSource = inputs.polylogue-rewrite;
      rewritePackage = inputs.polylogue-rewrite.packages.${system}.polylogue;
      ports = helpers.data.ports.polylogue;

      primary = cfg.sinex.mode == "primary";
      sinex = config.services.sinex;
      # Read by every polylogue-live command. Polylogue reads the password
      # from the file when it connects; it is never in this one.
      sinexSettings = (pkgs.formats.toml { }).generate "sinex.toml" {
        inherit (cfg.sinex) mode;
        nats = "nats://${sinex.nats.address}:${toString sinex.nats.port}";
        password_file = cfg.sinex.passwordFile;
        subject_root = sinex.nats.subjectRoot;
        store = sinex.storeDir;
      };
      dataHome = if primary then "${cfg.liveRoot}/sinex-data" else "${cfg.liveRoot}/data";

      cli = pkgs.writeShellScriptBin "polylogue-live" ''
        export XDG_DATA_HOME=${lib.escapeShellArg dataHome}
        export XDG_STATE_HOME=${lib.escapeShellArg "${cfg.liveRoot}/state"}
        exec ${rewritePackage}/bin/polylogue "$@"
      '';

      # The unpacked extension is its manifest and sources; its third-party
      # code is vendored under src/.
      extensionFiles = pkgs.runCommand "polylogue-browser-extension" { } ''
        mkdir -p "$out"
        cp -R ${rewriteSource}/extension/manifest.json ${rewriteSource}/extension/src "$out/"
      '';
      extensionDir = "${cfg.liveRoot}/extension";
      browser = config.sinnix.features.desktop.browser;
      hostName = "com.polylogue.browser_capture";
      # Chrome names an unpacked extension after its directory: the first
      # 32 hex digits of the path's SHA-256, each mapped 0-f to a-p. A fixed
      # real directory keeps the ID, and the host manifest below, stable
      # across rebuilds; a store path would change it with every build.
      extensionId =
        let
          digits = lib.stringToCharacters "0123456789abcdef";
          letters = lib.stringToCharacters "abcdefghijklmnop";
          letterOf = lib.listToAttrs (lib.zipListsWith lib.nameValuePair digits letters);
        in
        lib.concatMapStrings (d: letterOf.${d}) (
          lib.stringToCharacters (builtins.substring 0 32 (builtins.hashString "sha256" extensionDir))
        );

      # The retained Python CLI reads this file; the values are those its
      # removed Home Manager module rendered.
      # The capture class's CPU and IO yielding. Its memory bounds are left
      # off: the daemon peaked at 15.6 GB on 2026-10-27 and a 6G MemoryHigh
      # would throttle a real anonymous spike into a stall instead of
      # explaining it. Without this the Home Manager unit ran in app.slice
      # with the desktop's IOWeight while reading ~5 MB/s around the clock.
      liveServiceClass = lib.sinnix.mkRuntimeServiceConfig {
        runtimeInventory = config.sinnix.runtime.inventory;
        unit = "polylogue-live.service";
        manager = "user";
        omit = [
          "MemoryHigh"
          "MemoryMax"
        ];
      };
      pythonSettings = (pkgs.formats.toml { }).generate "polylogue.toml" {
        archive.root = cfg.dataDir;
        daemon = {
          api = {
            host = "127.0.0.1";
            port = ports.api;
          };
          browser_capture = {
            host = "127.0.0.1";
            port = ports.browserCapture;
          };
        };
        embedding = {
          enabled = false;
          model = "voyage-4";
          dimension = 1024;
          max_cost_usd = 1000.0;
        };
      };
    in
    {
      systemd.tmpfiles.rules = [
        "d ${cfg.dataDir} 0700 ${userName} ${config.users.users.${userName}.group} -"
        "d ${cfg.dataDir}/inbox 0700 ${userName} users -"
        "d ${cfg.liveRoot} 0700 ${userName} ${config.users.users.${userName}.group} -"
      ];

      home-manager.users.${userName} =
        { lib, ... }:
        {
          systemd.user.startServices = lib.mkForce "sd-switch";

          home.packages = [ cli ];

          # Completion asks the daemon for a query's fields, values seen and
          # recent session IDs while one is typed.
          programs.zsh.initContent = lib.mkAfter ''
            source <(${cli}/bin/polylogue-live completions zsh --program polylogue-live)
          '';

          xdg.configFile."polylogue/polylogue.toml".source = pythonSettings;
          # Without this file the archive is standalone.
          xdg.configFile."polylogue/sinex.toml" = lib.mkIf primary { source = sinexSettings; };

          # Replaces the file the Python stack's installer wrote by hand.
          home.file = lib.optionalAttrs browser.enable {
            "${browser.chromeUserDataDir}/NativeMessagingHosts/${hostName}.json" = {
              force = true;
              text = builtins.toJSON {
                name = hostName;
                description = "Polylogue browser capture host";
                path = "${cli}/bin/polylogue-live";
                type = "stdio";
                allowed_origins = [ "chrome-extension://${extensionId}/" ];
              };
            };
          };

          # Chrome loads the extension from this directory once
          # (`sinnix-chrome-control load-extension --path <dir>`) and picks up
          # new files when the extension reloads.
          home.activation.polylogueBrowserExtension = lib.mkIf browser.enable (
            lib.hm.dag.entryAfter [ "writeBoundary" ] ''
              run mkdir -p ${lib.escapeShellArg extensionDir}
              run ${pkgs.rsync}/bin/rsync -rL --delete --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r \
                ${extensionFiles}/ ${lib.escapeShellArg extensionDir}/
            ''
          );

          systemd.user.services.polylogue-live = {
            Unit.Description = "Polylogue daemon over the live archive";
            Service = liveServiceClass // {
              ExecStart = "${cli}/bin/polylogue-live daemon";
              Restart = "on-failure";
              RestartSec = "5s";
              # The daemon exits 78 when it refuses the archive (a schema it
              # cannot migrate); restarting cannot change that.
              RestartPreventExitStatus = 78;
            };
            Install.WantedBy = [ "default.target" ];
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
        resourceClass = "capture";
        notifyOnFailure = true;
        operatorRestart = true;
      };
    };
} args
