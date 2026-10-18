# The hub

`sinnix.services.hub` is the browser front door to the workstation: a
dashboard, generated reports, and controls for the local AI backends. It is
reachable from the desktop and over Tailscale (the phone), and from nowhere
else. It runs as a Caddy user service in front of `sinnix-ops-reducer`, the
user service that collects machine state and executes actions.

## Routes

Control pages use port 8880; generated reports use a separate port, 8883.
Open WebUI and ComfyUI are republished on 8881 and 8882 (they cannot run under
a sub-path).

| Route            | What it is                                                     |
| ---------------- | -------------------------------------------------------------- |
| `/`              | Summary: a verdict, six tiles, then detail                     |
| `/work/`         | What is running: project commands, pueue groups, jobs, budgets |
| `/pressure/`     | Memory and I/O pressure, the biggest processes, scheduled load |
| `/services/`     | Declared services grouped by resource class                    |
| `/ai/`           | Local AI backends and how they start                           |
| `/shaders/`      | Screen-shader library and the one applied                      |
| `/capabilities/` | Everything the machine can do and how to invoke it             |
| `/terminals/`    | Live kitty terminals, control and scrollback                   |
| `/reports/`      | Generated reports (report port only)                           |
| `/ops/v1/*`      | The ops-reducer's read and action API                          |
| `/feedback`      | Write-only inbox for report annotations                        |

## Actions

Every button posts to `/ops/v1/actions`, the ops-reducer's action API; the hub
itself runs no commands. The API only accepts:

- `start`, `stop`, `restart` on a unit listed in
  `/etc/sinnix/runtime-inventory.json` that declares `observe.restartable`;
- `interrupt` on a queued or running agentctl job;
- `stop` on one process, identified by PID and start time, and only inside
  `agent.slice`, `build.slice` or a slice the inventory marks as killable
  (SIGTERM, then SIGKILL after 3 s);
- `park` (freeze a unit with a required thaw time) and
  `set_policy`/`reset_policy` (runtime-only changes to the resource limits a
  unit declares).

Each action carries the target the page observed; if the unit, job or process
changed in the meantime, the action is refused rather than retargeted. Pages
build their buttons from the same inventory, so they never offer an action the
API would refuse. Privilege comes from the existing polkit rule for `wheel`.

## Pressure page

`/pressure/` names the current state instead of showing gauges:

- `CALM`;
- `SWAP-CRITICAL`: swap at or above 75%, or memory full PSI at or above 20;
- `SPIKE`: under 2 GiB available but nothing stalling;
- `IO-SATURATED`: I/O full PSI at or above 40 while memory is fine.

Swap use is the main widget because past freezes started with swap nearly full
while "available memory" still looked healthy. The process table ranks
resident plus swapped memory and marks which processes are cheap to stop. A
strip lists the scheduled heavy jobs (Borg, btrbk, scrubs, database dumps) and
their last durations. Swap at 75% with memory PSI still low also raises a
desktop notification, since that is the state just before a freeze.

## Capability index

`/capabilities/` lists every feature, service, AI backend, script, devshell
command, skill, capture lane, MCP server and agent CLI, with its description,
how to run it, whether it is enabled, and the file that declares it.
`/etc/sinnix/capability-index.json` is built at evaluation time
(`modules/capability-index.nix`) from the descriptions those declarations
already require, so nothing is written twice. The ops-reducer adds the hub's
own routes and the weekly usage report (`sinnix census`). Missing usage data
means "unknown", never "unused".

```bash
sinnix-ops-reducer capabilities                # grouped table
sinnix-ops-reducer capabilities --json
sinnix-ops-reducer capabilities --kind script
sinnix cheatsheet                              # offline HTML, also Super+Shift+/
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

The hub runs in the user manager because the ops-reducer's socket and the
reports tree are operator-owned; no privileged port or extra permission is
needed.

## Shaders

`/shaders/` lists `dots/hypr/shaders` and the shader Hyprland currently has
applied (from `hyprctl getoption`). It has no buttons: use `F4` to cycle and
`Shift+F4` to clear, or `sinnix-shader apply a b c`, which compiles several
shaders into one. `sinnix-shader play` cycles them from a transient unit that
clears the screen when it stops. Two things to know:

- Animated shaders need `debug:damage_tracking = 0` (full redraw each frame);
  otherwise Hyprland shows a red error banner. `sinnix-shader` sets it first.
- Screenshots (`grim`) do not show the shader stage, so check shaders with
  `glslangValidator`, not with a screenshot.

## AI backends

The backends behind `/ai/` start on first connection and stop after 30 s idle,
so "idle" is their normal state. See `docs/local-ai-activation.md`.

## Report annotations

Reports made with the html-report skill can send their annotations with one
request:

```js
fetch("/feedback", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(collectState()) });
```

Submissions are appended to `/realm/state/hub-feedback/<UTC-date>.jsonl`, each
wrapped with receive time, referring page and a sequence number. There is no
route that reads the inbox back. POST routes require exactly one
`application/json` Content-Type.

A `sinnix-elicit-v1` submission starts `sinnix-elicit autoingest` a few
seconds after the last tap, so a burst of comparisons is fitted once.
`GET /feedback/elicit/<domain>` returns that domain's fitted `model.json`, so a
comparison session can show progress; the domain name is checked and confined
to the elicit state root.
