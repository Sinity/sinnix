# Polylogue — AI conversation archive daemon (user-mode)
#
# Thin wrapper over polylogue's upstream Home Manager module
# (inputs.polylogue.homeManagerModules.default). The upstream module
# defines programs.polylogued.* options, renders polylogue.toml, and
# creates the polylogued user unit. This module adds sinnix-specific
# wiring that the upstream cannot know about:
#
#   - ``sinnix.runtime.surfaces`` registration (resource class, observe)
#
# Everything else — archive/daemon/embedding/logging settings,
# systemd hardening — is delegated to upstream.
#
# Consumer site (hosts/sinnix-prime/default.nix):
#
#     polylogue = {
#       enable = true;
#       dataDir = "/realm/data/captures/polylogue";  # optional override
#     };
{
  config,
  lib,
  pkgs,
  inputs,
  ...
}:
let
  cfg = config.sinnix.services.polylogue;
  userName = config.sinnix.user.name;
  homeDir = config.users.users.${userName}.home;

  # Defaults matching what polylogue's runtime discovery picks up.
  defaultDataDir = "${homeDir}/.local/share/polylogue";

  polyloguePkg = pkgs.polylogue;
in
{
  options.sinnix.services.polylogue = {
    enable = lib.mkEnableOption "Polylogue AI conversation archive daemon (user-mode via home-manager)";

    dataDir = lib.mkOption {
      type = lib.types.str;
      default = defaultDataDir;
      description = ''
        Path to the Polylogue archive root. Mapped to
        ``programs.polylogued.settings.archive.root`` and persisted to
        the generated ``polylogue.toml``.

        Default: ``~/.local/share/polylogue``.
      '';
    };

    daemon = {
      host = lib.mkOption {
        type = lib.types.str;
        default = "127.0.0.1";
        description = ''
          Host for the daemon's HTTP API and browser-capture receiver.
          Mapped to ``programs.polylogued.settings.daemon.host``.
        '';
      };

      browserCapturePort = lib.mkOption {
        type = lib.types.port;
        default = 8765;
        description = ''
          Port for the browser-capture receiver. Passed as `--port` to
          `polylogued run` and written to
          `programs.polylogued.settings.browser-capture.port` in the TOML.
        '';
      };

      apiPort = lib.mkOption {
        type = lib.types.port;
        default = 8766;
        description = ''
          Port for the daemon HTTP API. Mapped to
          ``programs.polylogued.settings.daemon.port``.
        '';
      };

      autoStart = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = ''
          Start the polylogued user systemd unit at login
          (``WantedBy = default.target``). Mapped to
          ``programs.polylogued.autoStart``.
        '';
      };
    };
  };

  config = lib.mkIf cfg.enable {
    # ── Import the upstream Home Manager module ────────────────────
    #     This defines programs.polylogued.* and creates the unit.
    home-manager.users.${userName} = {
      imports = [ inputs.polylogue.homeManagerModules.default ];
      programs.polylogued = {
        enable = true;
        package = polyloguePkg;
        autoStart = cfg.daemon.autoStart;

        settings = {
          archive.root = cfg.dataDir;

          daemon = {
            host = cfg.daemon.host;
            port = cfg.daemon.apiPort;
          };

          browser-capture.port = cfg.daemon.browserCapturePort;
        };

        # NOTE(2026-05-28): upstream polylogue HM module no longer exposes
        # `service` or `extraServiceConfig`; systemd unit tuning is now
        # owned upstream.
      };
    };

    # ── Runtime-surface registration (sinnix-specific) ─────────────
    sinnix.runtime.surfaces.polylogued = {
      unit = "polylogued.service";
      manager = "user";
      resourceClass = "capture-runtime";
      observe = {
        enable = true;
        restartable = true;
      };
    };
  };
}
