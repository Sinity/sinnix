{ lib, pkgs, ... }:
let
  dbPkgs = pkgs.postgresql16Packages;
in
{
  services.postgresql = {
    enable = true;
    package = pkgs.postgresql_16;
    extensions =
      with dbPkgs;
      [
        timescaledb
      ]
      ++ lib.optional (dbPkgs ? pg_jsonschema) dbPkgs.pg_jsonschema
      ++ [
        pgx_ulid
        pgvector
      ];
    settings = {
      listen_addresses = "localhost";
      shared_preload_libraries = "timescaledb";
      max_connections = 200;
      shared_buffers = "256MB";
      effective_cache_size = "1GB";
      maintenance_work_mem = "256MB";
      checkpoint_completion_target = 0.9;
      wal_buffers = "16MB";
      default_statistics_target = 100;
      random_page_cost = 1.1;
      effective_io_concurrency = 200;
      max_prepared_transactions = 256;
      statement_timeout = "60s";
      lock_timeout = "30s";
      idle_in_transaction_session_timeout = "300s";
      log_statement = "mod";
      log_duration = true;
      log_min_duration_statement = "1000ms";
    };
    authentication = ''
      local   all             all                                     peer
      host    all             all             0.0.0.0/0               reject
      host    all             all             ::/0                    reject
    '';
    ensureDatabases = [ "sinex" ];
    ensureUsers = [
      {
        name = "sinex";
        ensureDBOwnership = true;
      }
    ];
  };
}
