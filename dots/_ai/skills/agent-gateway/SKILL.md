---
name: agent-gateway
description: Use when invoking, inspecting, or documenting Sinnix Agent Gateway actions through their typed MCP tools or the sinnix-agent-gateway CLI.
---

<!-- GENERATED FILE. DO NOT EDIT. -->
<!-- gateway-catalog-revision: v3-typed-actions -->
<!-- gateway-catalog-sha256: 4fff9d72457f2b5a3496543fb7a675f7e5de3beb8ca3e963edd545275f0d2411 -->

# Agent Gateway

Every gateway action is one MCP tool named after the action; its input schema in `tools/list` is the contract and its output envelope schema is the `sinnix://gateway/actions/<name>` resource. Paths, ids, titles and unit names are accepted where a canonical `sinnix://` ref is; responses return the canonical ref and `next_actions` naming the next actions. Images arrive as image content blocks, other binary as resource blocks.

## Invocation

- MCP: call the tool by action name with the fields of its input schema.
- CLI: `sinnix-agent-gateway call <action> --input '{...}'` or `--set key=value` (values parse as JSON); `sinnix-agent-gateway catalog <action> --schema` prints the live schemas, `--example` the examples, `catalog --complete <prefix>` lists names.
- Discovery: `gateway.catalog` with a plain-words `query` finds actions, resources and brokered MCP tools; `gateway.status` reports contract hashes and route availability.

Effectful actions (families change, operate, run) require `idempotency_key`. Confirmed responses replay unchanged. Pending calls refuse concurrent execution; interrupted calls become indeterminate and never retry their effects automatically. `operations.run` and `shell.run` reconcile through durable agentctl launch identities; hub-backed machine actions and process stop reconcile only exact confirmed owner receipts. Other interrupted mutations remain indeterminate. Preconditions are owner-specific checks, best effort unless the owner explicitly guarantees atomic comparison and mutation.

Run ordinary commands through `shell.run` and declared jobs through `operations.run`. `terminals.open` and `terminals.run` operate graphical Kitty windows; use them when the task needs an interactive terminal. If a checkout is unregistered, register its project and environment before running its jobs.

## Workflows

- Read the relevant action schema before calling it. Discover actions with `gateway.catalog`; use `gateway.describe` for an exact name. When a client has not loaded a typed tool, `gateway.read`, `gateway.change` and `gateway.run` accept the exact action name and its ordinary input in `arguments`.
- Resolve locators once, then use the returned canonical refs. A conflict lists candidates; choose from those using the task context. A stale browser element needs a new page snapshot.
- Before changing a file or checkout, read it and pass its returned hash or revision as the action's precondition. Preconditions have the owner's guarantees; inspect partial filesystem receipts before continuing.
- Keep both job identifiers: numeric `task_id` is pueue's queue position, while string `job_id` follows the job across a reorder. Include both in subsequent `jobs.*` targets. Batch worker and landing rows carry the same pair.
- Wait on the returned job handle. `running` and `queued` are continuations. Use the continuation's `target` and previous `output.next_offset` as `jobs.wait`'s `target` and `output_offset` to receive new bytes. Inspect the terminal result before retrying.
- Choose an `idempotency_key` before an effectful call. If its response is lost, query `audit.operation` with the action and key before doing anything else. A confirmed response is recoverable; pending or indeterminate effects require owner evidence.
- Read large responses through their `snapshot_ref` or artifact refs; preserve cursors and offsets. Component coverage distinguishes empty data from unavailable evidence.

## Contract and troubleshooting

The live catalog owns action names, schemas, examples and follow-up actions. `sinnix-agent-gateway-generate --reference` prints the complete reference from the same declarations. Read `/realm/project/sinnix/repo/docs/agent-gateway.md` for authority, deployment, connector refresh and upstream ownership; load `agent-runtime` for job and batch recovery.

`gateway.status` compares live, packaged and last-recorded connector hashes. The saved connector snapshot does not prove which tools the current client loaded. After a refresh, inspect the client's actual schema before recording its observed hash. A numeric `job_id` schema is stale: the current contract uses a string and a separate numeric `task_id`.

Catalog revision: `v3-typed-actions`. Catalog SHA-256: `4fff9d72457f2b5a3496543fb7a675f7e5de3beb8ca3e963edd545275f0d2411`.
