# devkit-pg: the per-user PostgreSQL that devkit (Sinity/polylogue-sinex-common)
# uses for compile-time SQL checks and test databases in Polylogue and Sinex.
#
# Everything in it is disposable: devkit rebuilds each project's schema
# database from source when it is missing, drops each test database when its
# test ends, and drops what killed tests left behind at the start of every
# run. So it runs without fsync, and its data lives in the regenerable cache
# root on disk, outside backups. It listens on no TCP port; clients use the
# Unix socket in $XDG_RUNTIME_DIR/devkit/pg, which is where devkit looks for
# it. Without this service devkit starts a throwaway server per run instead.
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
      # Until 2026-10-27 the cluster lived in $XDG_RUNTIME_DIR, a tmpfs: its
      # 7.6 GB of test and measurement databases were RAM that could only be
      # swapped, never dropped, while the desktop was being swapped out. On
      # disk the same data is page cache the agent budget reclaims, and
      # without fsync most of a short-lived test database is deleted before
      # writeback reaches it.
      dataDir = "${config.sinnix.paths.realmRoot}/state/cache/devkit-pg";
    in
    {
      environment.systemPackages = [ postgres ];
      systemd.tmpfiles.rules = [
        "d ${dataDir} 0700 ${config.sinnix.user.name} users -"
        # PostgreSQL rewrites pages in place; files created inside inherit
        # No_COW, so they do not fragment into one extent per rewrite.
        "h ${dataDir} - - - - +C"
      ];
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
            ExecStartPre = "${initdb} ${dataDir}/data";
            ExecStart = lib.concatStringsSep " " [
              "${postgres}/bin/postgres"
              "-D ${dataDir}/data"
              "-k %t/devkit/pg"
              "-c listen_addresses="
              "-c fsync=off"
              "-c synchronous_commit=off"
              "-c full_page_writes=off"
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
