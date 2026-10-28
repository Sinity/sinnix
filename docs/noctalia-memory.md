# Noctalia allocator observations

`noctalia msg status` preserves `barVisible`, `panelOpen`, `activePanelId` and
`locked`, and adds an `allocator` object. It observes allocator bookkeeping;
it does not purge or trim arenas, change policy, or create a profile.

The object has `schema_version: 1`, `backend`, `status`, `pid`,
`observed_at_unix_ms` (UTC epoch milliseconds), `units: "bytes"`, and
`allocated_bytes`, `active_bytes`, `resident_bytes`, `mapped_bytes`,
`retained_bytes`, `metadata_bytes`. A jemalloc epoch refresh precedes all six
reads. `status: "available"` means every read succeeded with its expected width.
Real zero counters remain numeric zero. Any epoch/read/width failure makes the
whole snapshot `unavailable`, leaves all six counters null, and adds
`{field, code, message}` entries to `errors`. A build without jemalloc reports
an unavailable backend with the same null/error contract.

Allocated bytes describe live allocator allocations; active bytes include
allocator page slack, and resident bytes include allocator metadata and unused
resident pages. These counters are not total process RSS or GPU memory.
Mapped and retained bytes describe allocator mappings and reserved address
space. Compare snapshots from the same PID/start identity with process anon
and swap observations before attributing growth to live objects.

The existing IPC socket is
`$XDG_RUNTIME_DIR/noctalia-$WAYLAND_DISPLAY.sock`. A root collector must select
the operator UID and the target shell's runtime directory and Wayland display,
then invoke the operator's installed Noctalia CLI with a bounded timeout.
The CLI's own send/receive timeout is two seconds. Consumers should validate
PID and timestamp against the selected process; an unavailable probe is a gap,
not zero usage. No timer or independent sampler belongs to this interface.

The optional root-level `ownership` object has `schema_version: 1`,
`provider: "luau"`, process PID, observation time, byte units, runtime counts,
and at most 32 records sorted by `state_token`. Each record identifies the
runtime and actual host generation, with the VM's allocator byte count,
`sampled_at_unix_ms` and `age_ms`. These are copied after existing serialized
worker events; status never reads a live VM, waits for a worker or runs Lua/GC.
An idle VM keeps its last observed values and time. A worker currently running
marks its previous observation `stale` with reason `worker_in_flight`.
An unobserved or absent host reports `unavailable` with null bytes and times.
Retirement erases the record; reload creates a new host generation.
The registry object lives until process exit so deferred State destruction can
erase records during shutdown without relying on static destruction order.

Top-level ownership status is `available` when all live records are available
(including an empty registry), `partial` for stale/mixed/truncated records,
and `unavailable` when no reported host has observed bytes. `runtime_count`,
`reported_runtime_count` and `truncated_count` make omitted records explicit.
Runtime labels use at most 128 ASCII identifier characters; invalid or longer
labels become null with an unavailable reason. Tokens still identify those
records. No guessed sum or fabricated zero replaces missing observations.
The collector preserves valid ownership under `allocator.ownership`; old
allocator responses remain valid when this optional diagnostic is absent.
