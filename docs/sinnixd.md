# Sinnixd

`sinnixd` is the host-local runtime behind `agentctl` and the future execution-facing Sinnix MCP routes. It uses a mode-0600 Unix socket at `$XDG_RUNTIME_DIR/sinnixd.sock`. MCP remains a stateless policy frontend. Systemd, Git, project adapters, and task backends remain authoritative for their own state.

## Current vertical slice

The first deployed slice is intentionally read-only:

```text
agentctl status
agentctl project list
agentctl project get sinnix
agentctl project operations sinnix
```

It discovers only explicit `.agentctl/project.toml` adapters passed by the service. It does not scan arbitrary directories. Each descriptor is schema-versioned, identifies its repository root markers, and publishes named operation metadata without executing it.

The initial daemon does not yet own jobs, workspaces, agents, task mutation, service leases, Git operations, or process cancellation. Those move only after their existing authorities can be cut over to the same durable job identity. Until then, the gateway’s legacy job surface remains active and no parallel scheduler is claimed.

## Shared protocol

All requests and responses use `sinnix-mcp` v1. Every request carries an explicit principal, canonical dotted operation, owner, request ID, and correlation ID. Responses preserve owner identity, typed errors, bounded payloads, and optional source-generation bindings. `OwnerRegistry` rejects overlapping operation namespaces, so a frontend cannot silently choose an owner for a domain operation.

Project adapters are the local semantic boundary. A descriptor declares what an operation means, its intended pool, result contract, cache policy, and exclusivity keys. The daemon will later supply admission and lifecycle mechanics. It does not infer semantics from a command basename.
