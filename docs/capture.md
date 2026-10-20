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
