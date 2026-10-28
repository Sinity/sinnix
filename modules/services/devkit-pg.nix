# devkit-pg: the per-user PostgreSQL that devkit (Sinity/polylogue-sinex-common)
# uses for compile-time SQL checks and test databases in Polylogue and Sinex.
#
# Everything in it is disposable: devkit rebuilds each project's schema
# database from source when it is missing, drops each test database when its
# test ends, and drops what killed tests left behind at the start of every
# run. The dedicated /run/devkit-pg tmpfs loses its data at reboot; no caller
# may depend on persistence. Its 2 GiB limit covers the measured 1.125 GB
# cluster plus about 0.9 GiB headroom. This is up to 2 GiB resident RAM, in
# addition to PostgreSQL process memory. noswap prevents tmpfs from filling
# zram; exhaustion reports ENOSPC instead of growing onto disk. Larger test
# populations must reduce concurrency or reap databases, not raise the cap
# casually on this 32 GiB workstation.
#
# Clients use the unchanged Unix socket in $XDG_RUNTIME_DIR/devkit/pg. The
# former /realm/state/cache/devkit-pg is left untouched and never reused.
# This service never opens the live database under /realm/state/sinex.
{
  mkServiceModule,
  lib,
  pkgs,
  ...
}@args:
let
  postgres = pkgs.postgresql_18.withPackages (p: [ p.timescaledb ]);
  initdb = pkgs.writeShellScript "sinnix-devkit-pg-initdb" ''
    set -eu
    data="$1"
    if [ ! -f "$data/PG_VERSION" ]; then
      ${postgres}/bin/initdb --no-sync --no-locale --auth=trust --data-checksums -D "$data" >/dev/null
    fi
  '';
in
mkServiceModule {
  name = "devkit-pg";
  description = "Disposable per-user PostgreSQL for Polylogue and Sinex development";
  surface = {
    unit = "sinnix-devkit-pg.service";
    manager = "user";
    resourceClass = "ordinary";
    notifyOnFailure = true;
  };
  configFn =
    { config, ... }:
    let
      dataDir = "/run/devkit-pg";
      uid = toString config.users.users.${config.sinnix.user.name}.uid;
      requireTmpfs = pkgs.writeShellScript "sinnix-devkit-pg-require-tmpfs" ''
        if ! ${pkgs.util-linux}/bin/findmnt --mountpoint ${dataDir} --types tmpfs --options noswap --noheadings >/dev/null; then
          echo "devkit-pg requires the size-capped noswap tmpfs at ${dataDir}" >&2
          exit 1
        fi
      '';
    in
    {
      environment.systemPackages = [ postgres ];
      fileSystems.${dataDir} = {
        device = "tmpfs";
        fsType = "tmpfs";
        options = [
          "size=2G"
          "noswap"
          "mode=0700"
          "uid=${uid}"
          "nodev"
          "nosuid"
          "noexec"
          # The system manager must mount this before starting user units.
          "x-systemd.before=user@${uid}.service"
        ];
      };
      systemd.user.services.sinnix-devkit-pg = {
        description = "Disposable PostgreSQL for devkit (socket in %t/devkit/pg)";
        wantedBy = [ "default.target" ];
        serviceConfig = lib.sinnix.mkRuntimeServiceConfig {
          runtimeInventory = config.sinnix.runtime.inventory;
          unit = "sinnix-devkit-pg.service";
          manager = "user";
          overrides = {
            Type = "notify";
            # Test databases are agent tool work, inside the agent budget. In
            # app.slice their pages (4.7G on 2026-10-19, mostly leaked)
            # counted against the desktop's memory reservation, and Chrome
            # was swapped out instead.
            Slice = "agent-tool.slice";
            RuntimeDirectory = "devkit/pg";
            RuntimeDirectoryMode = "0700";
            ExecStartPre = [
              requireTmpfs
              "${initdb} ${dataDir}/data"
            ];
            MemorySwapMax = 0;
            ExecStart = lib.concatStringsSep " " [
              "${postgres}/bin/postgres"
              "-D ${dataDir}/data"
              "-k %t/devkit/pg"
              "-c listen_addresses="
              "-c fsync=off"
              "-c synchronous_commit=off"
              "-c full_page_writes=off"
              # No replication or archive consumers exist for disposable tests.
              "-c wal_level=minimal"
              "-c max_wal_senders=0"
              "-c archive_mode=off"
              "-c checkpoint_timeout=1h"
              "-c checkpoint_completion_target=0.9"
              "-c min_wal_size=64MB"
              "-c max_wal_size=256MB"
              "-c wal_init_zero=off"
              "-c wal_recycle=off"
              "-c shared_buffers=64MB"
              "-c max_connections=300"
              "-c shared_preload_libraries=timescaledb"
              "-c timescaledb.telemetry_level=off"
              "-c timescaledb.enable_chunk_skipping=on"
            ];
            Restart = "on-failure";
            RestartSec = "5s";
          };
        };
      };
    };
} args
