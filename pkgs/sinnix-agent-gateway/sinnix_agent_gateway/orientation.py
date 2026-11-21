"""Canonical standing guidance shared by MCP, documentation and client skill."""

ORIENTATION = """For machine, project and work questions use gateway.catalog, then context.compose for the intent. Discover session queries with mcp.tools (server=polylogue). Follow campaign.progress and events.tail refs as relevant. Verify a harmless direct read before proposing another executor or reconnect. Distinguish agent activity, job state, ownership, delivery and verification.

Use the private Plannotator Inbox for operator decisions, design comparisons, material changes and finished reports. Discover plannotator-inbox with mcp.tools. Read via mcp.call and send via mcp.change with an idempotency key. Pass the absolute project_path and a stable agent_session for the conversation. Reuse one thread per work stream. Explain options, attach workstation files, link the thread and read replies on resumption.

Distinguish observation time, data dates and index watermarks. Report missing coverage, denial and transport failure distinctly. Follow stale results to their owner. For missing typed tools use gateway.read, gateway.change or gateway.run with the exact action and arguments. Use a local executor only for the missing capability and respect denials.

Status requests authorize reads. Start builds, refreshes, state changes and paid workers only for an authorized task. Skip private orientation for unrelated questions. Verify scheduled ChatGPT access and model routing separately. Keep refs and inspect receipts before retrying effects."""
