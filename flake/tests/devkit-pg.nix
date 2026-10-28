# Evaluate the deployed mount/unit and smoke-test their PostgreSQL command.
{ inputs, ... }:
{
  perSystem =
    { pkgs, ... }:
    let
      inherit (inputs.nixpkgs) lib;
      host = inputs.self.nixosConfigurations.sinnix-prime.config;
      service = host.systemd.user.services.sinnix-devkit-pg.serviceConfig;
      mount = host.fileSystems."/run/devkit-pg";
      manager =
        host.systemd.units."user@${toString host.users.users.${host.sinnix.user.name}.uid}.service";
      pre = service.ExecStartPre;
      # Preserve the exact server settings, replacing only isolated smoke paths.
      command =
        lib.replaceStrings [ "/run/devkit-pg/data" "%t/devkit/pg" ] [ "$TMPDIR/data" "$TMPDIR/socket" ]
          service.ExecStart;
      postgres = inputs.self.nixosConfigurations.sinnix-prime.pkgs.postgresql_18.withPackages (p: [
        p.timescaledb
      ]);
    in
    {
      checks.devkit-pg =
        assert mount.fsType == "tmpfs";
        assert lib.all (option: builtins.elem option mount.options) [
          "size=2G"
          "noswap"
          "mode=0700"
          "nodev"
          "nosuid"
          "noexec"
          "uid=${toString host.users.users.${host.sinnix.user.name}.uid}"
          "x-systemd.before=user@${toString host.users.users.${host.sinnix.user.name}.uid}.service"
        ];
        # Force the native user-manager drop-in too: do not replace its template.
        assert manager.overrideStrategy == "asDropin";
        assert lib.hasInfix "X-RestartIfChanged=false" manager.text;
        assert lib.hasInfix "tmpfs /run/devkit-pg tmpfs size=2G,noswap" host.environment.etc.fstab.text;
        assert service.MemorySwapMax == 0;
        assert service.Slice == "agent-tool.slice";
        assert lib.hasInfix "-D /run/devkit-pg/data" service.ExecStart;
        assert builtins.length pre == 2;
        pkgs.runCommand "devkit-pg-check"
          {
            nativeBuildInputs = [
              postgres
              pkgs.util-linux
            ];
          }
          ''
            # A missing mount must fail before initdb can fall back to disk.
            if ${builtins.head pre} >guard.log 2>&1; then
              echo "accepted an absent tmpfs" >&2
              exit 1
            fi
            grep -F 'requires the size-capped noswap tmpfs' guard.log
            mkdir "$TMPDIR/socket"
            ${lib.replaceStrings [ "/run/devkit-pg/data" ] [ "$TMPDIR/data" ] (builtins.elemAt pre 1)}
            ${command} >server.log 2>&1 &
            server=$!
            trap 'kill "$server" 2>/dev/null || true; wait "$server" || true' EXIT
            export PGHOST="$TMPDIR/socket" PGDATABASE=postgres
            for attempt in $(seq 1 100); do
              if pg_isready -q; then break; fi
              if ! kill -0 "$server" 2>/dev/null; then cat server.log; exit 1; fi
              sleep 0.1
            done
            pg_isready
            psql -X -v ON_ERROR_STOP=1 <<'SQL'
            DO $$ BEGIN
              ASSERT current_setting('fsync') = 'off';
              ASSERT current_setting('synchronous_commit') = 'off';
              ASSERT current_setting('full_page_writes') = 'off';
              ASSERT current_setting('wal_level') = 'minimal';
              ASSERT current_setting('max_wal_senders') = '0';
              ASSERT current_setting('checkpoint_timeout') = '1h';
              ASSERT current_setting('max_wal_size') = '256MB';
            END $$;
            CREATE DATABASE fixture;
            \connect fixture
            CREATE EXTENSION timescaledb;
            CREATE TABLE sample (value integer);
            INSERT INTO sample VALUES (42);
            \connect postgres
            CREATE DATABASE file_clone TEMPLATE fixture STRATEGY FILE_COPY;
            CREATE DATABASE wal_clone TEMPLATE fixture STRATEGY WAL_LOG;
            \connect file_clone
            UPDATE sample SET value = 7;
            \connect wal_clone
            DO $$ BEGIN ASSERT (SELECT value FROM sample) = 42; END $$;
            \connect fixture
            DO $$ BEGIN ASSERT (SELECT value FROM sample) = 42; END $$;
            \connect postgres
            DROP DATABASE file_clone;
            DROP DATABASE wal_clone;
            DROP DATABASE fixture;
            SQL
            touch "$out"
          '';
    };
}
