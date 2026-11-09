# Polylogue: the Rust rewrite's daemon, its CLI and its browser capture.
#
# The CLI, daemon, hooks, MCP and browser host use one wrapper over liveRoot.
# The Python predecessor's archive at dataDir stays under its backup policy.
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
        The Python predecessor's archive root, retained for backups.
        The live CLI uses liveRoot.
      '';
    };

    liveRoot = lib.mkOption {
      type = lib.types.str;
      default = "${config.sinnix.paths.stateRoot}/polylogue-live";
      description = ''
        Everything the rewrite keeps except its spools: ``data/polylogue``
        is the archive, ``extension`` the unpacked browser extension Chrome
        loads. The spools are under ``~/.local/state/polylogue`` on the root
        disk, persisted by modules/persistence.nix.
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
      sinex = config.services.sinex;
      # Read by every polylogue command. Polylogue reads the password
      # from the file when it connects; it is never in this one.
      sinexSettings = (pkgs.formats.toml { }).generate "sinex.toml" {
        inherit (cfg.sinex) mode;
        nats = "nats://${sinex.nats.address}:${toString sinex.nats.port}";
        password_file = cfg.sinex.passwordFile;
        subject_root = sinex.nats.subjectRoot;
        store = sinex.storeDir;
      };
      cli = config.system.build.polylogueCli;

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

      # The live class places the daemon in the user manager's live.slice,
      # ahead of the desktop and agent work for the disk. Memory bounds are
      # its own: start-up peaked at 15.6 GB on
      # 2026-10-27, and at 16:09 that day host OOM pressure killed it.
      # 6G high / 9G max / 2G swap trades slower start-up under reclaim for a
      # host that stays up, until Polylogue's ingest bounds memory by work in
      # flight (its owner's redesign).
      liveServiceClass = lib.sinnix.mkRuntimeServiceConfig {
        runtimeInventory = config.sinnix.runtime.inventory;
        unit = "polylogue-live.service";
        manager = "user";
        overrides = {
          MemoryHigh = "6G";
          MemoryMax = "9G";
          MemorySwapMax = "2G";
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
            source <(${cli}/bin/polylogue completions zsh --program polylogue)
          '';

          # Without this file the archive is standalone.
          xdg.configFile."polylogue/sinex.toml" = lib.mkIf primary { source = sinexSettings; };

          # Chrome reads the native host manifest from its profile directory.
          home.file = lib.optionalAttrs browser.enable {
            "${browser.chromeUserDataDir}/NativeMessagingHosts/${hostName}.json" = {
              force = true;
              text = builtins.toJSON {
                name = hostName;
                description = "Polylogue browser capture host";
                path = "${cli}/bin/polylogue";
                type = "stdio";
                allowed_origins = [ "chrome-extension://${extensionId}/" ];
              };
            };
          };

          # Chrome loads the extension from this directory and never rereads
          # its files by itself: a running background keeps the old code
          # against new page scripts. When the files change, loading the
          # same directory again reloads the extension under the same ID.
          # Files are compared by content, so an unchanged extension is not
          # reloaded on every switch.
          # Without a reachable Chrome the next browser start loads them.
          home.activation.polylogueBrowserExtension = lib.mkIf browser.enable (
            lib.hm.dag.entryAfter [ "writeBoundary" ] ''
              run mkdir -p ${lib.escapeShellArg extensionDir}
              changed=$(run ${pkgs.rsync}/bin/rsync -rLic --delete --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r \
                ${extensionFiles}/ ${lib.escapeShellArg extensionDir}/)
              control="$HOME/.local/bin/sinnix-chrome-control"
              if [[ -n $changed && ! -v DRY_RUN && -x $control ]]; then
                PATH=${
                  lib.makeBinPath [
                    pkgs.curl
                    pkgs.jq
                    pkgs.websocat
                  ]
                }:$PATH "$control" load-extension --path ${lib.escapeShellArg extensionDir} >/dev/null 2>&1 \
                  || echo "Polylogue extension files changed; Chrome was not reachable, so it loads them on its next start"
              fi
            ''
          );

          systemd.user.services.polylogue-live = {
            Unit.Description = "Polylogue daemon over the live archive";
            Service = liveServiceClass // {
              ExecStart = "${cli}/bin/polylogue daemon";
              # always, not on-failure: a SIGTERM from the OOM response counts
              # as a clean stop, and on 2026-10-27 that left the daemon down.
              Restart = "always";
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
        resourceClass = "live";
        # Its indexes and caches stay resident beside the session producer
        # within the user live slice's protection (runtime-defaults.nix).
        resources.MemoryLow = "2500M";
        notifyOnFailure = true;
        operatorRestart = true;
      };
    };
} args
