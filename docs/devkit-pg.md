# Disposable development PostgreSQL

`modules/services/devkit-pg.nix` supplies the shared PostgreSQL 18 server for
Polylogue and Sinex schema checks and test databases. The module and shared
`devkit` helper both treat every database in this cluster as regenerable.
Schema templates are rebuilt from source after reboot; test clones remain
independent. The service socket stays at `$XDG_RUNTIME_DIR/devkit/pg`.

Data lives at `/run/devkit-pg/data` on a dedicated 2 GiB tmpfs with `noswap`.
The measured cluster was 1.125 GB, leaving about 0.9 GiB headroom. The mount
can consume up to 2 GiB resident RAM plus PostgreSQL process memory (including
64 MiB shared buffers). PostgreSQL process swapping is also disabled. Full
storage causes PostgreSQL errors, including possible transaction failure or
server shutdown, rather than disk spill. Reduce test concurrency or reap
unused databases when the cap is reached. A previous test population reached
7.6 GB, so the cap deliberately cannot accommodate every historical workload.

The service requires the mount and rejects startup without it. Durability is
disabled (`fsync`, `synchronous_commit`, `full_page_writes`); WAL is minimal,
replication senders and archiving are disabled. A one-hour checkpoint timeout
and 256 MiB WAL target reduce periodic checkpoint work. `max_wal_size` is a
soft target, not a storage reservation or hard limit; the tmpfs is the hard
boundary. Explicit `FILE_COPY` clones still force checkpoints. Both clone
strategies work with these settings and TimescaleDB in the smoke check.

The old `/realm/state/cache/devkit-pg` remains untouched and is not reused.
The live Sinex database under `/realm/state/sinex` has separate ownership and
configuration. Devkit's existing fallback when the service is unavailable
starts per-run clusters; those clusters are controlled by the shared helper,
not this module's size limit.

## Verification

Run the module contract and isolated PostgreSQL smoke check:

```sh
nix build --no-link -L .#checks.x86_64-linux.devkit-pg
```

After coordinator activation, check the installed revision, mount, active
service and server settings as the workstation user:

```sh
nixos-version --configuration-revision
findmnt --mountpoint /run/devkit-pg -o TARGET,FSTYPE,SIZE,OPTIONS
systemctl --user status sinnix-devkit-pg.service
systemctl --user show sinnix-devkit-pg.service -p MemorySwapMax -p ExecStart
psql -X -v ON_ERROR_STOP=1 -h "$XDG_RUNTIME_DIR/devkit/pg" -d postgres <<'SQL'
SELECT name, setting, unit FROM pg_settings WHERE name IN (
  'data_directory', 'fsync', 'synchronous_commit', 'full_page_writes',
  'wal_level', 'max_wal_senders', 'archive_mode', 'checkpoint_timeout',
  'max_wal_size', 'shared_buffers', 'wal_init_zero', 'wal_recycle'
) ORDER BY name;
SQL
```

Expect the intended revision, active service, tmpfs with `size=2097152k`
(2 GiB) and `noswap`, data directory `/run/devkit-pg/data`, durability settings
`off`, WAL level `minimal`, zero senders, archive mode `off`, checkpoint timeout
3600 seconds and WAL target 256 MiB. Follow with the coordinator's normal
Sinex database test operation to verify schema regeneration and clone use by
the real client. Device write reduction still requires a comparable workload
measurement after activation.
