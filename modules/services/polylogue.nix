# Polylogue — AI conversation archive daemon (user-mode)
#
# Thin wrapper over polylogue's upstream Home Manager module
# (inputs.polylogue.homeManagerModules.default), which defines
# programs.polylogued.*, renders polylogue.toml, and creates the polylogued
# user unit. This module adds the sinnix-specific wiring upstream cannot
# know about: option surface, package pinning, and runtime-surface
# registration. Everything else is delegated to upstream.
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

  # Defaults matching what polylogue's runtime discovery picks up.
  defaultDataDir = "${homeDir}/.local/share/polylogue";
in
mkServiceModule {
  name = "polylogue";
  description = "Polylogue AI conversation archive daemon (user-mode via home-manager)";
  extraOptions = {
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

    memoryBudgetGiB = lib.mkOption {
      type = lib.types.ints.positive;
      default = 16;
      description = ''
        Polylogued's cgroup memory budget in GiB. MemoryHigh is derived as
        7/8 of this budget, leaving 1/8 for pre-limit throttling headroom;
        MemoryMax is derived as 9/8, leaving another 1/8 for transient
        bursts above the throttle. The value must be divisible by 8 so both
        derived limits remain whole GiB values.
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
        default = false;
        description = ''
          Start the polylogued user systemd unit at login
          (``WantedBy = default.target``). Mapped to
          ``programs.polylogued.autoStart``.

          Defaults to false so updating the Polylogue package/MCP/runtime
          surface does not implicitly start archive convergence; operators can
          enable daemon ingestion deliberately per host.
        '';
      };
    };

    embedding = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = ''
          Enable Polylogue's daemon-side embedding stage. The Voyage API key is
          expected to come from the user manager environment; this option does
          not render secrets into the generated polylogue.toml.
        '';
      };

      model = lib.mkOption {
        type = lib.types.str;
        default = "voyage-4-lite";
        description = "Voyage embedding model for Polylogue.";
      };

      dimension = lib.mkOption {
        type = lib.types.ints.unsigned;
        default = 1024;
        description = "Embedding vector dimension for the configured model.";
      };

      maxCostUsd = lib.mkOption {
        type = lib.types.number;
        default = 1000.0;
        description = "Polylogue embedding cost cap in USD; 0 means unlimited upstream.";
      };
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
      # Free-threaded build so daemon thread-parse fan-outs run parallel
      # instead of serializing on GIL writer-commit contention; rollback is
      # repinning `.default`.
      polyloguePkg = inputs.polylogue.packages.${pkgs.stdenv.hostPlatform.system}.polylogue;
      # One source of truth for the daemon's memory ceiling, derived from a
      # single budget knob and used both for upstream's own service.memory*
      # options and for the runtime surface declaration, so the inventory
      # cannot claim a limit the unit does not actually carry. MemoryHigh at
      # 7/8 leaves throttling headroom below the ceiling; MemoryMax at 9/8
      # leaves room for transient bursts above the throttle.
      memoryBudgetBytes = cfg.memoryBudgetGiB * 1024 * 1024 * 1024;
      polyloguedMemoryHigh = "${toString (cfg.memoryBudgetGiB * 7 / 8)}G";
      polyloguedMemoryMax = "${toString (cfg.memoryBudgetGiB * 9 / 8)}G";
    in
    {
      assertions = [
        {
          assertion = cfg.memoryBudgetGiB / 8 * 8 == cfg.memoryBudgetGiB;
          message = "sinnix.services.polylogue.memoryBudgetGiB must be divisible by 8";
        }
      ];

      # ── Import the upstream Home Manager module ────────────────────
      home-manager.users.${userName} = {
        imports = [ inputs.polylogue.homeManagerModules.default ];
        systemd.user.startServices = lib.mkForce "sd-switch";

        programs.polylogued = {
          enable = true;
          package = polyloguePkg;

          # Must be set through upstream's OWN options, not only via
          # mkRuntimeServiceConfig below: upstream assigns MemoryMax as a plain
          # value (default "2G") while mkRuntimeServiceConfig returns
          # mkDefault, and plain beats mkDefault. polylogued self-terminates
          # once its mmap budget reaches the cgroup limit, so losing to 2G
          # turns into a silent ~90s start/self-terminate/restart loop that
          # ingests nothing.
          service = {
            memoryHigh = polyloguedMemoryHigh;
            memoryMax = polyloguedMemoryMax;
          };
          # The daemon runs the free-threaded build; the PATH CLI stays the
          # standard-CPython polylogue-cli wrapper — without this the two
          # collide on bin/polylogue in the home profile.
          installPackage = false;
          autoStart = cfg.daemon.autoStart;

          settings = {
            archive.root = cfg.dataDir;

            daemon = {
              host = cfg.daemon.host;
              port = cfg.daemon.apiPort;
              debounce-s = 30;
            };

            browser-capture.port = cfg.daemon.browserCapturePort;

            embedding = {
              enabled = cfg.embedding.enable;
              model = cfg.embedding.model;
              dimension = cfg.embedding.dimension;
              max-cost-usd = cfg.embedding.maxCostUsd;
            };
          };
        };

        systemd.user.services.polylogued.Service =
          (lib.sinnix.mkRuntimeServiceConfig {
            runtimeInventory = config.sinnix.runtime.inventory;
            unit = "polylogued.service";
          })
          // {
            # The upstream unit does not pass its rendered TOML path to the
            # daemon process. Keep the service's startup-bound archive root
            # aligned with the generated user configuration.
            Environment = [
              "POLYLOGUE_ARCHIVE_ROOT=${cfg.dataDir}"
              "POLYLOGUE_MEMORY_BUDGET_BYTES=${toString memoryBudgetBytes}"
            ];
          };

      };

      # ── Runtime-surface registration (sinnix-specific) ─────────────
      # A direct attrset rather than the single-surface `surface` factory
      # argument: the unit name differs from the "polylogue" service name.
      sinnix.runtime.surfaces = {
        polylogued = {
          unit = "polylogued.service";
          manager = "user";
          resourceClass = "capture-runtime";
          resources = {
            MemoryHigh = polyloguedMemoryHigh;
            MemoryMax = polyloguedMemoryMax;
          };
          observe = {
            enable = true;
            restartable = true;
          };
          # Parked: the durable and live tiers disagree on archive identity
          # and the startup check refuses to proceed. The repair is migration
          # surgery in the polylogue repo. Acknowledged rather than silenced,
          # so it stays visible as known-down.
          acknowledged = {
            down = true;
            reason = "DurableChangeTrainError blocks every start; AI-session ingestion is down pending polylogue-side migration repair";
            since = "2026-08-14";
            ref = "sinnix-qh6s";
          };
        };
      };
    };
} args
