---
name: agent-gateway
description: Use when invoking, inspecting, or documenting Sinnix Agent Gateway V2 resources and actions through its ten-verb CLI or MCP contract.
---

<!-- GENERATED FILE. DO NOT EDIT. -->
<!-- gateway-catalog-revision: v2-g3.0-pueue-jobs -->
<!-- gateway-catalog-sha256: 885e3a2cee22a5488d8cc0dd289312bb9105a7f9679c8a247afeda5dbb919548 -->

# Agent Gateway V2

Use `sinnix-agent-gateway` when a local agent needs the same principal-scoped routes and normalized envelopes as MCP. The complete action schemas and examples are in `docs/generated/agent-gateway-reference.md`.

## Invocation

Start with `sinnix-agent-gateway catalog --query "<need>" --principal <principal>` when the route is unknown. Catalog discovery is optional when a canonical action and resource reference are already known. Use `catalog --schema <action>` for the live input schema and `catalog --example <action>` for executable examples.

Every request accepts one bounded JSON source: `--input '{"ref":"..."}'`, `--input-file request.json`, or `--stdin`. Common controls include `--request-id`, `--actor`, `--reason`, `--idempotency-key`, `--deadline-at`, and `--preconditions`. Outputs are normalized V2 envelopes with result, receipt, refs, source metadata, and typed errors.

The CLI invokes the matching MCP verb through the same server runtime and principal. It does not create an alternate owner route. Invalid JSON, non-object JSON, unknown fields, schema violations, and inputs larger than 262144 bytes are rejected before owner dispatch.

## Workflow prompts

- Project orientation: call `projects.context` with a canonical `sinnix://projects/<project>` ref and `intent=project`, then follow the returned checkout and task-authority refs.
- Beads triage: call `beads.query` with bounded project IDs, a view or native filters, and only the includes needed for the decision.
- Bulk Beads changes: call `beads.changeset` with `operation=preview`, inspect every planned step and source revision, then replay the same request with the returned preview digest and `operation=apply`.
- Start a lane for a bead: `agent.for_bead` with the canonical bead ref; agentctl compiles the prompt, creates the worktree and queues the agent. Review the job afterwards with `projects.context` and `intent=job.review`.
- Incident orientation: use `machine.query` for one bounded owner-selected section and `audit.events` for recent gateway receipts. Do not reconstruct a whole-machine view locally.
- Browser or desktop manipulation: discover or use the canonical gateway-owned browser page or desktop ref, then invoke `browser.operate` or `desktop.operate` as operator. Existing operator tabs are never accepted as implicit targets.
- Machine action: discover a canonical machine target, query `machine.query` with `operation=actions` for the current owner revision, then supply it with the reason, idempotency key, and preconditions to `machine.operate`.

## Beads direct-owner fallback

The gateway is the preferred route for typed, principal-scoped Beads work. The direct owner fallback is `bd 1.1.0-dev` against the project’s canonical standalone Dolt workspace, resolved through the project’s canonical worktree and `.beads/redirect`. Dolt is the authority for ordinary mutations. `issues.jsonl` is an optional JSONL export, not a write authority. Use the gateway `beads.operate` action with `snapshot.publish` when an explicit deterministic snapshot is required. Snapshot publication does not imply a Git commit or a Dolt push. Use `sync.push` or `sync.pull` explicitly for Dolt synchronization. Never hand-author `bd` argv when the gateway catalog exposes the needed action.

Catalog revision: `v2-g3.0-pueue-jobs`. Catalog SHA-256: `885e3a2cee22a5488d8cc0dd289312bb9105a7f9679c8a247afeda5dbb919548`.
