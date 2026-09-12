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
  helpers,
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
          Mapped to the daemon API and browser-capture listen hosts.
        '';
      };

      browserCapturePort = lib.mkOption {
        type = lib.types.port;
        default = helpers.data.ports.polylogue.browserCapture;
        description = ''
          Port for the browser-capture receiver. Passed as `--port` to
          `polylogued run` and written to
          `programs.polylogued.settings.browser-capture.port` in the TOML.
        '';
      };

      apiPort = lib.mkOption {
        type = lib.types.port;
        default = helpers.data.ports.polylogue.api;
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

      # These are Polylogue archive inputs, so their destination must follow
      # the same archive-root option as the daemon and hook spool.
      systemd.tmpfiles.rules = [
        "d ${cfg.dataDir} 0755 ${userName} users -"
        "d ${cfg.dataDir}/inbox 0755 ${userName} users -"
        "L+ ${cfg.dataDir}/inbox/chatgpt - - - - /realm/accounts/chatgpt"
        "L+ ${cfg.dataDir}/inbox/claude - - - - /realm/accounts/claude"
      ];

      # ── Import the upstream Home Manager module ────────────────────
      home-manager.users.${userName} = {
        imports = [ inputs.polylogue.homeManagerModules.default ];
        systemd.user.startServices = lib.mkForce "sd-switch";

        # ── Deliberate hold: the daemon must not run before the reindex ──
        # Operator decision 2026-08-24: the archive stays down until the
        # rebuild, so nothing is acquired into an archive mid-surgery while
        # the blob store is being reconciled against its sources and pruned.
        # `daemon.autoStart = false` already removes the [Install] section, so
        # nothing pulls the unit in — but a manual `systemctl --user start`
        # still worked, and did (accidentally) on 2026-08-24. This closes that.
        #
        # To release: delete this block and switch. Do NOT release before the
        # blob-collector liveness fixes have landed (#4133) — that path can
        # unlink live payload it cannot prove is referenced.
        systemd.user.services.polylogued.Unit = {
          # The upstream unit is wanted by default.target, so ordering it
          # after that target leaves the user manager with a startup cycle.
          After = lib.mkForce [ ];
          RefuseManualStart = true;
        };

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
              debounce-s = 30;
            };

            daemon-api = {
              host = cfg.daemon.host;
              port = cfg.daemon.apiPort;
            };

            browser-capture = {
              host = cfg.daemon.host;
              port = cfg.daemon.browserCapturePort;
            };

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
          resourceClass = "capture";
          resources = {
            MemoryHigh = polyloguedMemoryHigh;
            MemoryMax = polyloguedMemoryMax;
          };
          observe = {
            enable = true;
            restartable = true;
          };
          # Archive availability is owned by the reindex campaign, not by this
          # package's activation. The owning task records
          # restart authorization; installing a new reader does not grant it.
          acknowledged = {
            down = true;
            reason = "Daemon autostart is disabled; archive deployment follows the Polylogue reindex campaign rather than package activation";
            since = "2026-08-14";
            ref = "polylogue-reindex-2026.1";
          };
        };
      };
    };
} args
