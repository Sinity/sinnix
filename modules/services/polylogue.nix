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
      polyloguePkg = pkgs.polylogue;
      dbRoot = "${config.sinnix.paths.realmRoot}/db/polylogue";
      # 2026-07-10: moved off /persist (worn MX500) to /realm; still inside
      # the /realm btrbk→borg coverage.
      backupRoot = "/realm/backup/polylogue-sqlite";
      dbNames = [
        "daemon_events.db"
        "embeddings.db"
        "index.db"
        "ops.db"
        "source.db"
        "user.db"
      ];
      backupScript = pkgs.writeShellApplication {
        name = "polylogue-sqlite-backup";
        runtimeInputs = [
          pkgs.coreutils
          pkgs.findutils
          pkgs.gawk
          pkgs.sqlite
          pkgs.zstd
        ];
        text = ''
          set -euo pipefail

          umask 077
          install -d -m 0700 ${lib.escapeShellArg backupRoot}

          stamp="$(date -u +%Y%m%dT%H%M%SZ)"
          for db_name in ${lib.escapeShellArgs dbNames}; do
            source=${lib.escapeShellArg dbRoot}/"$db_name"
            if [ ! -f "$source" ]; then
              echo "Skipping missing Polylogue SQLite DB: $source" >&2
              continue
            fi

            stem="''${db_name%.db}"
            raw_tmp=${lib.escapeShellArg backupRoot}/"$stem-$stamp.sqlite.tmp"
            zst_tmp="$raw_tmp.zst.tmp"
            final=${lib.escapeShellArg backupRoot}/"$stem-$stamp.sqlite.zst"

            cleanup() {
              rm -f "$raw_tmp" "$zst_tmp"
            }
            trap cleanup EXIT

            sqlite3 "$source" ".backup '$raw_tmp'"
            chmod 0600 "$raw_tmp"
            zstd -T1 -q -f "$raw_tmp" -o "$zst_tmp"
            chmod 0600 "$zst_tmp"
            mv -f "$zst_tmp" "$final"
            rm -f "$raw_tmp"
            trap - EXIT

            find ${lib.escapeShellArg backupRoot} \
              -maxdepth 1 \
              -type f \
              -name "$stem-*.sqlite.zst" \
              -printf '%T@ %p\n' \
              | sort -rn \
              | awk 'NR > 3 { print substr($0, index($0, $2)) }' \
              | xargs -r rm -f
          done
        '';
      };
    in
    {
      systemd.tmpfiles.rules = [
        "d ${backupRoot} 0700 ${userName} users -"
      ];

      # ── Import the upstream Home Manager module ────────────────────
      #     This defines programs.polylogued.* and creates the unit.
      home-manager.users.${userName} = {
        imports = [ inputs.polylogue.homeManagerModules.default ];
        systemd.user.startServices = lib.mkForce "sd-switch";

        programs.polylogued = {
          enable = true;
          package = polyloguePkg;
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

        systemd.user.services.polylogued.Service = {
          # Each live batch costs ~14 MiB of WAL/FTS index writes
          # regardless of payload size (measured 2026-06-12: 435
          # batches/hr ~= 6.3 GiB written per 70 min while tailing two
          # active agent sessions: roughly 1000x app-level amplification on
          # few-KB JSONL appends). Coalescing to 30s caps that at
          # ~2 batches/min for a ~4x steady-state write cut. Tradeoff:
          # live sessions land in the archive within ~30s instead of
          # ~2s. The watcher flush loop settles on pending-set size,
          # so a continuously-appending file cannot starve the window.
          # Keep the soft reclaim threshold tight enough to protect the desktop,
          # but leave hard headroom for large catch-up insight refreshes.
          IOAccounting = true;
          MemoryHigh = lib.mkForce "4G";
          MemoryMax = lib.mkForce "6G";
        };

        systemd.user.services.polylogue-sqlite-backup = {
          Unit = {
            Description = "Back up Polylogue SQLite databases";
            After = [ "default.target" ];
            RequiresMountsFor = [
              dbRoot
              backupRoot
            ];
          };
          Service = {
            Type = "oneshot";
            ExecStart = "${backupScript}/bin/polylogue-sqlite-backup";
            TimeoutStartSec = "2h";
            Slice = "backup.slice";
            Nice = 10;
            CPUSchedulingPolicy = "idle";
            IOSchedulingClass = "idle";
            CPUWeight = 20;
            IOWeight = 20;
            IOAccounting = true;
            # The index backup writes a large temporary SQLite copy before
            # compression. systemd accounts that page cache to the unit; the
            # first successful run peaked near 9.5 GiB despite a 6 GiB hard cap.
            MemoryHigh = "8G";
            MemoryMax = "12G";
          };
        };

        systemd.user.timers.polylogue-sqlite-backup = {
          Unit.Description = "Weekly Polylogue SQLite backup";
          Timer = {
            OnCalendar = "Sun 04:35:00";
            RandomizedDelaySec = "45min";
            Persistent = false;
          };
          Install.WantedBy = [ "timers.target" ];
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
        polylogue-sqlite-backup = {
          unit = "polylogue-sqlite-backup.service";
          manager = "user";
          resourceClass = "backup-maintenance";
          observe.enable = true;
        };
        polylogue-sqlite-backup-timer = {
          unit = "polylogue-sqlite-backup.timer";
          kind = "timer";
          manager = "user";
          resourceClass = "backup-maintenance";
        };
      };
    };
} args
