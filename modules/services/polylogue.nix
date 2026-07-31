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
        default = "voyage-4";
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
      # 2026-07-21 (polylogue-dcz5): free-threaded 3.14t build so daemon
      # thread-parse fan-outs actually run parallel (GIL writer-commit
      # interference ~5000x on 3.13 vs ~0 on 3.14t). Rollback = repin
      # `.default`.
      polyloguePkg = inputs.polylogue.packages.${pkgs.stdenv.hostPlatform.system}.polylogue;
      # 2026-07-10: moved off /persist (worn MX500) to /realm; still inside
      # the /realm btrbk→borg coverage.
      # Ordered most-irreplaceable first. A run that dies partway (the 2h
      # TimeoutStartSec, an OOM, a reboot) then still leaves the tiers that
      # cannot be rebuilt covered. The 2026-07-30 failure did the opposite:
      # alphabetical order spent the whole window on the two large derived
      # tiers and was killed before reaching source.db, so the run following a
      # full index rebuild -- exactly when a durable-tier snapshot matters
      # most -- captured no durable tier at all.
      #
      # `daemon_events.db` is deliberately absent: it has been a 0-byte file
      # with no tables since 2026-07-17 (daemon events live in ops.db), and
      # backing it up produced a 71-byte artifact every run that reads as
      # coverage while covering nothing.
    in
    {
      # ── Import the upstream Home Manager module ────────────────────
      #     This defines programs.polylogued.* and creates the unit.
      home-manager.users.${userName} = {
        imports = [ inputs.polylogue.homeManagerModules.default ];
        systemd.user.startServices = lib.mkForce "sd-switch";

        programs.polylogued = {
          enable = true;
          package = polyloguePkg;
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
            # 2026-07-28: the shared resource class's 2G MemoryMax was
            # observed live-thrashing (memory.events max counter at 306K+
            # within 35 minutes post-restart, MemoryCurrent pinned exactly at
            # MemoryMax) against a 36GB/5-tier archive with ~4.9M blocks --
            # every ingest/status-component read was stalling in
            # folio_wait_bit_common (page reclaim under cgroup memory
            # pressure), not a code bug. Overriding just this unit rather
            # than the shared class. (The former polylogue-sqlite-backup
            # unit, since removed, used 8G/12G for comparable data volume.)
            #
            # 2026-07-31: 6G/8G proved too low in practice -- polylogued was
            # throttled CONTINUOUSLY against it (polylogue-e98k), because
            # BULK_BUILD_MMAP_SIZE_BYTES is 4 GiB and SQLite mmap counts
            # toward the cgroup budget. A runtime override to 14G stopped
            # the throttling; raised here so a rebuild does not silently
            # revert that finding.
            overrides = {
              MemoryHigh = lib.mkForce "14G";
              MemoryMax = lib.mkForce "18G";
            };
          })
          // {
            # The upstream unit does not pass its rendered TOML path to the
            # daemon process. Keep the service's startup-bound archive root
            # aligned with the generated user configuration.
            Environment = [ "POLYLOGUE_ARCHIVE_ROOT=${cfg.dataDir}" ];
          };


      };

      # ── Runtime-surface registration (sinnix-specific) ─────────────
      # Three differently-named units (none equal to the "polylogue"
      # service name itself), so this stays a direct attrset rather than
      # the single-surface `surface` factory argument — same pattern as
      # machine-telemetry.nix's backup/timer surfaces.
      sinnix.runtime.surfaces = {
        polylogued = {
          unit = "polylogued.service";
          manager = "user";
          resourceClass = "capture-runtime";
          observe = {
            enable = true;
            restartable = true;
          };
        };
      };
    };
} args
