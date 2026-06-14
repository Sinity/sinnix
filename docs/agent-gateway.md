# Sinnix Agent Gateway

`agent-gateway` is a trusted local MCP gateway for coding-agent workflows. It is the successor to the archived `chatgpt-mcp` bridge in `modules/attic/museum/`: instead of exposing a generic SSH shell through ngrok, it exposes a first-class tool surface for repositories, commands, patches, artifacts, jobs, and selected host operations.

The default posture is deliberately **trusted operator / yolo-friendly**. Sinnix already runs local coding agents with broad authority; the gateway should be useful enough to replace ad-hoc shell bridges. It keeps a few rails where they matter:

- normal work happens in materialized workspaces under the gateway state dir;
- stdout/stderr are capped inline and larger outputs can become artifacts;
- every tool call writes an append-only hash-chained audit ledger;
- host-level commands are separate from workspace commands and disabled by default;
- remote writes are intentionally left to normal git commands in a workspace or future explicit tools.

## Package

The flake exports:

```bash
nix run .#sinnix-agent-gateway -- info
```

The binary is a stdlib-only Python MCP server. It speaks JSON-RPC over stdio and implements the minimal MCP methods used by current MCP clients:

- `initialize`
- `tools/list`
- `tools/call`
- `ping`

It also has a local Streamable HTTP-compatible JSON-RPC mode for tunnel experiments:

```bash
sinnix-agent-gateway --config /etc/sinnix/agent-gateway/config.json http --host 127.0.0.1 --port 3020
```

The HTTP server accepts MCP JSON-RPC POST requests at `/mcp`, returns ordinary
`application/json` responses by default, and can return single-message SSE when
the client only accepts `text/event-stream`. The legacy POST `/` endpoint remains
available for simple local probes.

For stdio MCP clients, use:

```bash
sinnix-agent-gateway-mcp
```

## NixOS module

Enable the package and configuration surface:

```nix
{
  sinnix.services.agent-gateway = {
    enable = true;

    # Default: useful, not precious.
    yolo = true;
    allowArbitraryCommands = true;

    repositories."Sinity/sinex" = {
      url = "https://github.com/Sinity/sinex.git";
      defaultRef = "master";
      allowWrite = true;
      tasks = {
        cargo-check = {
          command = [ "cargo" "check" "--workspace" ];
          description = "Check all Rust workspace crates.";
          timeout = 1800;
        };
        cargo-test = {
          command = [ "cargo" "test" "--workspace" ];
          description = "Run all Rust workspace tests.";
          timeout = 3600;
          background = true;
          risk = "high";
        };
      };
    };
  };
}
```

The module installs:

- `sinnix-agent-gateway`
- `sinnix-agent-gateway-mcp`
- `/etc/sinnix/agent-gateway/config.json`
- `~/.config/sinnix-agent-gateway/config.json`

Optional local HTTP endpoint:

```nix
sinnix.services.agent-gateway.http = {
  enable = true;
  host = "127.0.0.1";
  port = 3020;
};
```

## Tool surface

The MCP server currently exposes:

- `gateway_info`
- `gateway_guide`
- `audit_tail`
- `repo_materialize`
- `repo_status`
- `repo_tree`
- `repo_read_file`
- `repo_write_file`
- `repo_search`
- `repo_pack`
- `repo_export_bundle`
- `repo_apply_patch`
- `repo_diff`
- `run_command`
- `run_task`
- `job_status`
- `job_list`
- `artifact_list`
- `artifact_read`
- `artifact_read_base64`
- `host_run`

Every `tools/list` entry includes both `inputSchema` and `outputSchema`.
Command/task tools use a `oneOf` output schema because they can either return a
foreground command result or a durable background job descriptor.
`repo_export_bundle` plus `artifact_read_base64` is the path for agents that
need their own checkout: reconstruct the bundle in the remote environment and
run `git clone <bundle>`.

The intended loop:

1. `gateway_guide` for connector-facing workflow guidance.
2. `repo_materialize` a configured repo/ref.
2. Use `repo_search`, `repo_tree`, and `repo_read_file` for orientation.
3. Use `run_command` freely for yolo-mode local work.
4. Use `repo_write_file` or `repo_apply_patch` for edits.
5. Use `repo_diff`, `run_task`, and `repo_pack` to validate and report.
6. Use normal git commands through `run_command` when deliberately pushing from a configured writable workspace.

Configured tasks can be either concise command vectors or metadata-rich objects.
Metadata is exposed through `gateway_info` so a client can prefer known checks,
start expensive tasks in the background, and report expected outputs.

## State layout

Default state root:

```text
~/.local/state/sinnix-agent-gateway/
  mirrors/      bare git mirrors
  workspaces/   checked-out mutable worktrees
  artifacts/    prompt packs and large outputs
  jobs/         durable background job records and logs
  audit.jsonl   hash-chained tool-call ledger
```

Background jobs are recorded on disk with `job.json`, `stdout.log`,
`stderr.log`, and `exitcode`. `job_status` and `job_list` can inspect jobs after
the gateway process restarts, as long as the underlying process or logs still
exist.

## Policy stance

This is not a high-assurance sandbox. It is a productive local toolgate for a trusted owner. The module does not try to prevent all agent mistakes because that would make it useless for real development. Instead it separates the dangerous planes:

- workspace commands: allowed by default;
- host commands: opt-in with `allowedHostCommands = true`;
- remote writes: use normal git commands in a workspace or add future explicit write tools.

That gives ChatGPT/Codex the missing "clone, grep, build, test, patch, pack" capability without making the ChatGPT Python/container side need direct network access.
