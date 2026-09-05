"""Shared sinnix library.

One home for the primitives sinnix scripts kept reinventing: the atomic
publish and its JSON/JSONL encoders, JSONL ledger appends, flock, desktop
notification across live session buses, batched systemd unit probes and the
sd_notify datagram, one guarded subprocess wrapper, lenient scalar reads,
common path resolution, and the spool (durable inbox with exactly-once
processing).

Library only, by contract: no daemons, no CLIs of its own. Consumers are
sinnix's Python tools and packages (sinnix-ops-reducer, sinnix-observe,
migrated scripts), which depend on this package rather than copying its
bodies.
"""

__all__ = [
    "atomic",
    "atomic_json",
    "ledger",
    "lock",
    "notify",
    "paths",
    "phone_inbox",
    "process",
    "spool",
    "systemd",
    "values",
]
