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
agentctl job get <job-id>
agentctl job list
agentctl job wait <job-id>
agentctl job logs <job-id> --max-bytes 64000
agentctl job cancel <job-id>
```

It discovers only `.agentctl/project.toml` adapters passed by the service. It does not scan arbitrary directories. Each descriptor is schema-versioned, identifies its repository root markers, declares the execution environment, and publishes named operation metadata.

`job start` accepts a project ID and one declared operation name, never an arbitrary command. Declared operations and internal synthetic foreground commands construct the same durable generic-job spec, record, transient user `.service` launch, log artifact, reconciliation, wait, and cancellation route. The public AgentCTL RPC surface exposes only declared operations.

Each record is stored under `$XDG_STATE_HOME/sinnixd` and contains safe operation identity, environment key names, and its bounded-read log artifact path. Internal foreground argv is launch-only: the durable record has only a SHA-256 digest and constant display metadata, never raw argv or environment values. The systemd-launched capture helper drains output but writes at most 1 MiB per job; it creates its overflow marker with the first discarded byte, so a live log reader can see truncation before the producer exits. It does not own a PID, process state, queue, task, workspace, or retry policy. A job ID deterministically derives its unit name. After a daemon restart, `get`, `list`, `wait`, and `cancel` reload the record and reconcile with the user manager. Missing or unreachable post-launch units are terminal `missing` or `lost` results, while a rejected launch is a distinct terminal `launch-failed` record. Cancellation persists its intent before asking systemd to stop the service, then preserves an observed systemd success, timeout, or failure result. A `cancelled` result needs matching systemd signal evidence, or a durably recorded successful stop acknowledgement for the observed invocation when systemd has already garbage-collected the transient unit. Systemd remains authoritative for the process, cgroup, timeout, terminal result, cancellation, and journal evidence.

## Source-scoped owner adapters

A project descriptor can declare a source-scoped, read-only owner adapter in `[owner_adapters.<name>]`. Each declaration names a non-overlapping canonical namespace, owner identity, protocol versions, canonical source reference, fixed executable, and bounded timeout. AgentCTL sends the request envelope to that exact executable through a transient user service. It does not pass caller-selected argv.

The first reserved contract is `polylogue.archive.status`, owned by `polylogue-archive` and bound to `sinnix://polylogue/archive`. A successful response must use the same request and correlation IDs, retain the declared owner identity, carry exactly one matching source binding, and use a bounded inline or opaque payload. An optional `expected_source_binding` request field is an AgentCTL precondition. When present, the returned generation and root digest must match it exactly. The adapter owns archive semantics and availability errors. AgentCTL owns transport, validation, systemd lifecycle, and result bounds.

The daemon still does not own job queues, retries, task mutation, service leases, Git operations, arbitrary shells, admission policy, or generic workspaces. Descriptor pool, cache, and exclusivity metadata remain descriptive until their existing authorities move behind an explicit shared contract. The gateway’s legacy controllers remain downstream and are unchanged here.

## Shared protocol

All requests and responses use `sinnix-mcp` v1. Every request carries an explicit principal, canonical dotted operation, owner, request ID, and correlation ID. Responses preserve owner identity, typed errors, bounded payloads, and optional source-generation bindings. `OwnerRegistry` rejects overlapping operation namespaces, so a frontend cannot silently choose an owner for a domain operation.

Project adapters are the local semantic boundary. A descriptor declares what an operation means, its intended pool, result contract, cache policy, and exclusivity keys. The daemon will later supply admission and lifecycle mechanics. It does not infer semantics from a command basename.
