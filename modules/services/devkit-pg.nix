# devkit-pg: the per-user PostgreSQL that devkit (Sinity/polylogue-sinex-common)
# uses for compile-time SQL checks and test databases in Polylogue and Sinex.
#
# Everything in it is disposable: devkit rebuilds each project's schema
# database from source when it is missing. So the data lives in
# $XDG_RUNTIME_DIR (tmpfs, gone at logout or reboot) and runs without fsync.
# It listens on no TCP port; clients use the Unix socket in
# $XDG_RUNTIME_DIR/devkit/pg, which is where devkit looks for it. Without this
# service devkit starts a throwaway server per run instead.
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
    observe.enable = true;
  };
  configFn =
    { config, ... }:
    {
      environment.systemPackages = [ postgres ];
      # logind sizes $XDG_RUNTIME_DIR at 10% of RAM (3.2G here); concurrent
      # test databases from parallel build lanes filled it. tmpfs takes RAM
      # only as it fills. Applies at the next login; a live session needs
      # `mount -o remount,size=10G /run/user/<uid>`.
      services.logind.settings.Login.RuntimeDirectorySize = "10G";
      systemd.user.services.sinnix-devkit-pg = {
        description = "Disposable PostgreSQL for devkit (socket in %t/devkit/pg)";
        wantedBy = [ "default.target" ];
        serviceConfig = lib.sinnix.mkRuntimeServiceConfig {
          runtimeInventory = config.sinnix.runtime.inventory;
          unit = "sinnix-devkit-pg.service";
          manager = "user";
          overrides = {
            Type = "notify";
            RuntimeDirectory = "devkit/pg";
            RuntimeDirectoryMode = "0700";
            ExecStartPre = "${initdb} %t/devkit/pg/data";
            ExecStart = lib.concatStringsSep " " [
              "${postgres}/bin/postgres"
              "-D %t/devkit/pg/data"
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
