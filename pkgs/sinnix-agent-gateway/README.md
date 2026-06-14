# sinnix-agent-gateway

Stdlib Python MCP server for trusted local coding-agent workflows.

Run over stdio:

```bash
sinnix-agent-gateway --config ~/.config/sinnix-agent-gateway/config.json stdio
```

Run local HTTP JSON-RPC for tunnel experiments:

```bash
sinnix-agent-gateway --config ~/.config/sinnix-agent-gateway/config.json http --host 127.0.0.1 --port 3020
```

The NixOS module installs `sinnix-agent-gateway-mcp`, a wrapper that points at the generated Sinnix config and starts stdio mode.
