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

## Bounded allocation-stack attribution

`sinnix.features.desktop.noctalia.heapProfiling.enable` defaults to false.
Enabling it adds profiling options only to `noctalia.service` at its next
coordinated restart. The existing allocator policy stays unchanged. Profiling
starts inactive, with a 64 KiB average sampling interval, no cumulative history
and no automatic dumps. The private output root is
`/realm/state/noctalia-heap-profiles` (operator-owned, mode 0700).

`noctalia msg heap-profile status` reads copied control observations without
starting a worker or activating profiling. `start <seconds>` accepts 1–300
seconds; `stop <session>` stops that exact session. A single independent worker
enforces the monotonic deadline even when the UI loop is blocked, disables
profiling before dumping, and rejects another start until completion. IPC
does not wait for allocator or filesystem work. At most four explicit sessions
can run in one process. Shutdown signals and joins the worker.
If three deactivation/write-readback attempts cannot confirm inactivity, the
process exits with status 70 without a core. The existing service restart
restores startup-inactive profiling; that interrupted run is not an accepted
profile. This failure path does not wait for the UI loop or filesystem.

Each server-generated PID/session directory is exclusive and mode 0700;
`final.heap` and `metadata.json` are mode 0600. Directory traversal rejects
symlinks. The dump writes through an exclusively created file descriptor,
with no caller-supplied path. Status returns IDs, timestamps, capabilities,
errors and completion metadata; it contains no dump paths or stack contents.
Private metadata preserves executable/mapping identity and sample interval.

Profiles contain sampled allocation stacks, not object contents. Their byte
counts are weighted estimates: 64 KiB sampling gives roughly 25 retained samples
for 1.6 MiB growth, with substantial uncertainty in small categories. Profiling
also allocates bookkeeping, so its total allocated slope is not a clean
baseline. Compare retained sampled stacks with the pre-profile growth evidence;
do not attribute all profiler-enabled growth to application objects.

After attribution, archive the session into its private owning analysis and
set the option false for the next coordinated restart. No profiler starts on
ordinary status reads, and no periodic sampler or automatic profile retention
cleanup is installed.
