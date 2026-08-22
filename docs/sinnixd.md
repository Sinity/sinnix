# Sinnixd

`sinnixd` is the host-local runtime behind `agentctl` and the future execution-facing Sinnix MCP routes. It uses a mode-0600 Unix socket at `$XDG_RUNTIME_DIR/sinnixd.sock`. MCP remains a stateless policy frontend. Systemd, Git, project adapters, and task backends remain authoritative for their own state.

## Current vertical slice

The deployed slice discovers explicit project adapters and can launch only their declared operations:

```text
agentctl status
agentctl project list
agentctl project get sinnix
agentctl project operations sinnix
agentctl job start sinnix lint
agentctl job status <job-id>
agentctl job cancel <job-id>
```

It discovers only `.agentctl/project.toml` adapters passed by the service. It does not scan arbitrary directories. Each descriptor is schema-versioned, identifies its repository root markers, declares the execution environment, and publishes named operation metadata.

`job start` accepts a project ID and one declared operation name, never an arbitrary command. It creates one transient user `.service` unit in `agent.slice`; systemd remains authoritative for the process, cgroup, timeout, result, cancellation, and journal evidence. A job ID deterministically derives its unit name, so status and cancellation survive a `sinnixd` restart without a daemon-owned process record.

The daemon still does not own job queues, retries, task mutation, service leases, Git operations, arbitrary shells, or generic workspaces. Descriptor pool, cache, and exclusivity metadata remain descriptive until their existing authorities move behind an explicit shared contract. The gateway’s legacy job surface remains active while replacement parity is built.

## Shared protocol

All requests and responses use `sinnix-mcp` v1. Every request carries an explicit principal, canonical dotted operation, owner, request ID, and correlation ID. Responses preserve owner identity, typed errors, bounded payloads, and optional source-generation bindings. `OwnerRegistry` rejects overlapping operation namespaces, so a frontend cannot silently choose an owner for a domain operation.

Project adapters are the local semantic boundary. A descriptor declares what an operation means, its intended pool, result contract, cache policy, and exclusivity keys. The daemon will later supply admission and lifecycle mechanics. It does not infer semantics from a command basename.
