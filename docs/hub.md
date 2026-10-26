# The hub

`sinnix.services.hub` is the browser entry point to the workstation: a
dashboard, generated reports, and the phone's receiver. It is
reachable from the desktop and over Tailscale (the phone), and from nowhere
else. It runs as a Caddy user service in front of `sinnix-hub-server`, the
user service that serves machine state and executes actions through the shared
`sinnix-runtime` implementation. CLI observation and gateway machine actions
use that same runtime package. The existing hub socket remains the single
action writer; clients never create an independent receipt owner.

## Routes

Control pages use port 8880; generated reports use a separate port, 8883.
Open WebUI and ComfyUI are republished on 8881 and 8882 (they cannot run under
a sub-path).

| Route        | What it is                                                     |
| ------------ | -------------------------------------------------------------- |
| `/`          | Summary: a verdict, six tiles, then detail                     |
| `/work/`     | What is running: project commands, pueue groups, jobs, budgets |
| `/services/` | Declared services grouped by resource class                    |
| `/reports/`  | Generated reports (report port only)                           |
| `/ops/v1/*`  | The hub-server's read and action API                           |
| `/feedback`  | Write-only inbox for report annotations                        |

## Actions

Every button posts to `/ops/v1/actions`, the hub-server's action API; the hub
itself runs no commands. The API only accepts:

- `start`, `stop`, `restart` on a unit listed in
  `/etc/sinnix/runtime-inventory.json` that declares `operatorRestart`;
- `interrupt` on a queued or running agentctl job;
- `stop` on one process, identified by PID and start time, and only inside
  `agent-cli.slice`, `agent-tool.slice` or a slice the inventory marks as killable
  (SIGTERM, then SIGKILL after 3 s);
- `park` (freeze a unit with a required thaw time) and
  `set_policy`/`reset_policy` (runtime-only changes to the resource limits a
  unit declares).

Each action carries the target the page observed; if the unit, job or process
changed in the meantime, the action is refused rather than retargeted. Pages
build their buttons from the same inventory, so they never offer an action the
API would refuse. Privilege comes from the existing polkit rule for `wheel`.

## Swap warning

Swap at or above 75% while memory full PSI is still below 20 raises a desktop
notification: past freezes started with swap nearly full while "available
memory" still looked healthy, so this is the warning that leaves time to act.

## Capability index

`sinnix capabilities` lists every feature, service, AI backend, script,
devshell command, skill, capture lane, MCP server and agent CLI, with its
description, how to run it, whether it is enabled, and the file that declares
it. `/etc/sinnix/capability-index.json` is built at evaluation time
(`modules/capability-index.nix`) from the descriptions those declarations
already require, so nothing is written twice; the hub-server adds the hub's
own routes.

```bash
sinnix capabilities                            # grouped table
sinnix capabilities --json
sinnix capabilities --kind script
```

## Access boundaries

- **Binding.** Caddy listens only on loopback and on this machine's
  `tailscale0` address, which a start-up step reads from the interface and
  checks against `tailscale status`. Each site block needs an explicit `bind`:
  without it Caddy merges same-port sites into one `0.0.0.0` listener. After
  editing the Caddyfile, check the result:

  ```bash
  caddy adapt --adapter caddyfile --config <file> | jq '.apps.http.servers | map_values(.listen)'
  ```

  Every listen entry must be an explicit address; a bare `":8880"` is a bug.

- **Host and Origin.** Requests with an unknown `Host` are refused before
  anything is served. Accepted names: localhost, loopback, the machine name,
  and its tailnet IP and DNS name. Republished frontends also refuse requests
  from other browser origins.
- **Firewall.** The ports are opened on `tailscale0` only
  (`networking.firewall.interfaces.tailscale0.allowedTCPPorts`).

The hub runs in the user manager because the hub-server's socket and the
reports tree are operator-owned; no privileged port or extra permission is
needed.

## AI backends

The local AI backends start on first connection and stop when idle, so "idle"
is their normal state. See `docs/local-ai-activation.md`.

## Report annotations

Reports made with the html-report skill can send their annotations with one
request:

```js
fetch("/feedback", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(collectState()),
});
```

Submissions are appended to `/realm/state/hub-feedback/<UTC-date>.jsonl`, each
wrapped with receive time, referring page and a sequence number. There is no
route that reads the inbox back. POST routes require exactly one
`application/json` Content-Type.

A `sinnix-rank-v1` submission (a `sinnix rank session` page) starts
`sinnix-rank ingest` a few seconds after the last tap, so a burst of
comparisons is drained once.
