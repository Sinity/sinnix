# Capture producers

The shared user-session capture family is declared under
`sinnix.capture.producers` by its
own service module, inside the existing enable gate. The service owns device
options, package construction and auxiliary configuration. The producer
specification contains typed output contracts and exactly one lifecycle:
`poll` or `stream`. Unknown fields fail evaluation.

`modules/capture.nix` renders private directories, units and the runtime
inventory entry from that declaration. Polling uses `mkScheduledJob` and its
wall-clock timer validation. Streams retain their Home Manager units and
session lifecycle. The shared renderer fixes privacy and restart policy; output names,
provenance, freshness and lifecycle belong in the typed fields.

The shared output type also describes captures written without an owning
unit. Audio's cooperating units, netflow's system-manager privilege boundary,
and terminal/hotkey producers retain their explicit owners and use the same
runtime output contract. They are not forced into a single user service.

Changing a declaration changes orchestration and observations, not stored
capture envelopes or historical data. Verify the evaluated unit and output
contract, then a genuine new producer record when activating a changed writer.

## Native evidence owners

The typed user-session renderer does not replace native capture stores:

| Owner             | Retained responsibility                                                      | Storage and lifecycle                                                                                    |
| ----------------- | ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Machine telemetry | Host sensors, power, pressure, service/cgroup state, GPU and network samples | Active/sealed SQLite files and their manifest; native seal, verification and lossless archive operations |
| Below             | Process/cgroup replay at its configured one-second cadence                   | Native dictionary-compressed store; indefinite history                                                   |
| Sinex             | Its event and activity evidence                                              | Sinex owns ingestion and historical source archives                                                      |
| Sinnix runtime    | Current operator observations and guarded action receipts                    | Shared CLI/hub/gateway semantics; the hub remains the sole action-receipt writer                         |

Machine telemetry and Below remain enabled. Shared CPU or memory fields do
not establish equivalent collection: cadence, attribution, missingness,
source-specific fields, reset behavior and numeric precision must agree for
all affected readers before a collector can be retired. Current-state views
and derived products do not replace historical raw evidence. Netdata is not
the selected operator UI or a replacement canonical store.

The telemetry module owns live/sealed SQLite placement and weekly sealing;
its host manifest remains in the machine home. Lynchpin owns interpretation
and its derived read model. Existing SQLite files, Below records and source
archives remain available at original precision. No TTL, downsampling or
rollup substitution is part of the shared runtime or capture refactors.

### Noctalia allocator observations

The existing 60-second top-PSS process sample optionally queries `noctalia msg
status` once when the selected user Noctalia process is present. The collector
uses that process's UID, start ticks and Wayland runtime, rechecks its identity
after the query, and bounds the CLI to one second and 16 KiB of stdout. The
existing collector owns this observation; it adds no timer.

`process_memory_sample.allocator_json` retains the versioned allocator payload
with probe status, reason and duration. Historical and unselected rows are NULL.
An unavailable probe has explicit status and null counters; an available numeric
zero remains zero. Provider timestamps use UTC epoch milliseconds and counters
use bytes. Reading counters refreshes jemalloc statistics without purging memory.
The nullable column is added to the active SQLite database; sealed history stays
unchanged. Compare allocated/active/resident counters with same-process PSS and
private memory rather than treating resident growth alone as live allocations.

The optional status `ownership` object is retained inside the stored allocator
object. Its version 1 Luau snapshots identify up to 32 runtimes by copied state
token, runtime ID and host generation, with explicit total/reported/truncated
counts. The collector validates this payload separately: missing, unsupported or
malformed ownership becomes `status: unavailable` with `collector_reason`, while
valid base allocator counters remain available. Older allocator-only producers
remain readable. The existing 16 KiB whole-response limit still applies.

Ownership bytes are worker-boundary snapshots. Each row retains its sample
timestamp and age; `stale` means an in-flight worker has a prior completed
snapshot. These last-known bytes are not a current total. An unobserved or absent
host keeps byte/time values null, while an observed zero stays numeric zero. No
age threshold, extra sampler or timer changes this meaning.
