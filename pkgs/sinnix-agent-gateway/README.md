# sinnix-agent-gateway

Stdlib Python MCP server for trusted local coding-agent workflows.

Run over stdio:

```bash
sinnix-agent-gateway --config ~/.config/sinnix-agent-gateway/config.json stdio
```

Run local Streamable HTTP-compatible JSON-RPC for tunnel experiments:

```bash
sinnix-agent-gateway --config ~/.config/sinnix-agent-gateway/config.json http --host 127.0.0.1 --port 3020
```

The HTTP server accepts MCP JSON-RPC requests at `/mcp` and keeps the legacy
POST `/` endpoint for local smoke tests.

Tool definitions include `inputSchema` and `outputSchema`; command/task tools
declare foreground command results and durable background job descriptors.
The `gateway_guide` tool gives model-facing workflow guidance so clients use
the host workspace tools instead of stopping at sandbox-boundary disclaimers.
For agents that need their own checkout, `repo_export_bundle` creates a git
bundle artifact and `artifact_read_base64` streams it out in reconstructable
chunks.

The NixOS module installs `sinnix-agent-gateway-mcp`, a wrapper that points at the generated Sinnix config and starts stdio mode.
