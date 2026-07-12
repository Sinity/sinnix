# Agent gateway

The Sinnix agent gateway is a trusted local MCP surface for repository work.
It gives an external coding agent a bounded vocabulary for materializing a
repository, inspecting and editing files, running commands, collecting large
outputs as artifacts, and following background jobs across process restarts.

It is an operator tool, not a security sandbox. The gateway assumes that the
configured agent is trusted to work inside the repositories it exposes. Its
rails make operations inspectable and recoverable:

- repositories are materialized under a dedicated state root;
- every call is appended to a hash-chained audit ledger;
- foreground output is bounded and larger results become artifacts;
- background jobs retain metadata and logs on disk;
- host commands are a separate, disabled-by-default authority;
- repository write access is explicit per configured repository.

## Interfaces

The flake exports the package directly:

```bash
nix run .#sinnix-agent-gateway -- info
```

Configured MCP clients use the generated stdio wrapper:

```bash
sinnix-agent-gateway-mcp
```

An optional loopback HTTP endpoint exposes the same JSON-RPC tool surface for
local connector experiments:

```bash
sinnix-agent-gateway \
  --config /etc/sinnix/agent-gateway/config.json \
  http --host 127.0.0.1 --port 3020
```

The HTTP transport accepts MCP JSON-RPC requests at `/mcp`, returning ordinary
JSON or a single-message server-sent event when requested by the client.

## NixOS configuration

```nix
{
  sinnix.services.agent-gateway = {
    enable = true;
    yolo = true;
    allowArbitraryCommands = true;

    repositories."example/project" = {
      url = "https://github.com/example/project.git";
      defaultRef = "master";
      allowWrite = true;
      tasks.check = {
        command = [ "nix" "flake" "check" ];
        description = "Evaluate and build the project checks.";
        timeout = 1800;
        background = true;
        risk = "high";
      };
    };
  };
}
```

The module installs the gateway binary and MCP wrapper, renders matching
system/user configuration files, and can optionally define a user service for
the loopback HTTP endpoint.

## Tool model

The tool surface falls into six groups:

| Group | Representative tools | Role |
| --- | --- | --- |
| Orientation | `gateway_info`, `gateway_guide` | Discover configured repositories, tasks, limits, and workflow guidance. |
| Repository lifecycle | `repo_materialize`, `repo_status`, `repo_tree` | Create and inspect durable working copies. |
| Read/write | `repo_read_file`, `repo_write_file`, `repo_search`, `repo_apply_patch` | Perform structured repository operations. |
| Verification | `repo_diff`, `run_command`, `run_task` | Inspect changes and execute arbitrary or declared checks. |
| Durable work | `job_status`, `job_list`, `artifact_list`, `artifact_read` | Follow background processes and retrieve large outputs. |
| Authority | `host_run`, ordinary Git commands in a workspace | Perform explicitly enabled host or remote operations. |

A normal client flow is:

1. Read `gateway_guide`.
2. Materialize a configured repository and ref.
3. Inspect with tree/search/read tools.
4. Apply edits and inspect the resulting diff.
5. Run a configured task or command.
6. Pack large results as artifacts or export a Git bundle when another
   environment needs its own checkout.

Configured task metadata is returned by `gateway_info`, allowing clients to
prefer the repository's known verification commands and move expensive work to
durable background jobs.

## State and recovery

```text
~/.local/state/sinnix-agent-gateway/
  mirrors/      bare repository mirrors
  workspaces/   mutable materialized checkouts
  artifacts/    large outputs and repository bundles
  jobs/         job metadata, stdout, stderr, and exit status
  audit.jsonl   hash-chained call ledger
```

The on-disk job and artifact model is intentionally independent of one MCP
connection. A restarted gateway can still report completed work and serve its
logs. The audit ledger records the request boundary even when the command it
launched outlives the original client.

## Trust boundary

`yolo` mode is appropriate only for a trusted local operator and trusted agent.
It deliberately permits useful repository commands rather than simulating a
high-assurance sandbox. Host commands require separate opt-in, and the HTTP
transport should remain loopback-only unless an authenticated tunnel provides
the external boundary.
