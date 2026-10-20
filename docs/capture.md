# Capture producers

Each unit-owned producer is declared under `sinnix.capture.producers` by its
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
