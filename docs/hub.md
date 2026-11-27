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
| `/state/`    | Agent work across every project (see "Operator state")         |
| `/work/`     | What is running: project commands and slice budgets            |
| `/services/` | Declared services grouped by resource class                    |
| `/reports/`  | Generated reports (report port only)                           |
| `/ops/v1/*`  | The hub-server's read and action API                           |
| `/feedback`  | Write-only inbox for report annotations                        |

Terminal capture runs independently of the hub. `sinnix-captured-shell` uses
`asciinema rec` to write `session.cast` alongside session and command metadata
under `/realm/activity/terminal/asciinema/YYYY/MM/DD/<session-id>/`. It records
input and output through an anonymous pipe to a separate writer with a bounded
256 MiB memory queue. The writer is a child process in its own session, so
closing the window does not cut it off mid-drain. Disk stalls do not
backpressure the recorder until the queue fills; exhaustion logs a warning and
blocks without dropping bytes. Session exit waits for the queue to drain, and
writer failures propagate as a nonzero launcher status. The queue is volatile:
a machine crash or forced writer kill can lose queued bytes, as with unflushed
filesystem buffers. It opens no browser stream or listening port.

The shell and the launcher never write under the capture root or run git, so
a stalled disk delays neither a new prompt nor a command. The shell hooks
print each event line into a second pipe; one session writer per terminal, in
its own session, creates the directory, appends the lines to `events.jsonl` in
order, queries the repository state at the start and the end, and is the only
writer of `session.json` (format `terminal-session-v1`) while it lives. The
launcher sends it the recorder's exit status over the same pipe and does not
wait for it. If no session writer is reading, the pipe write fails and the
shell and launcher write those files themselves.

## Actions

Every button posts to `/ops/v1/actions`, the hub-server's action API; the hub
itself runs no commands. The API only accepts:

- `start`, `stop`, `restart` on a unit listed in
  `/etc/sinnix/runtime-inventory.json` that declares `operatorRestart`;
- `interrupt` on a queued or running agentctl job, and `retry` on one that
  ended without success;
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

## Operator state

One engine (`sinnix_runtime.operator_state`) computes what is going on across
all agent work, and four views show its document. None of them computes its
own.

| View             | Reads                                                          |
| ---------------- | -------------------------------------------------------------- |
| Desktop bar      | `counts.waiting` from the summary in the hub snapshot          |
| Desktop panel    | the summary's ready-made lines                                 |
| `/state/` page   | the whole document                                             |
| `sinnix state`   | the whole document, as text or with `--json`                   |

The bar shows only the number of things waiting on the operator; zero means
nothing needs him. The panel and the page list what waits on him first, then
what runs, then what finished since he last looked, then the rest: stalled or
looping jobs, limits and load, forecast, the state of each product, recent
jobs. The page offers cancel on an unfinished job and retry on a failed one,
through the action API.

"Last looked" is one stored time. It moves when the operator opens the panel
or the page (`POST /ops/v1/state/looked`), never when `sinnix state` or
`GET /ops/v1/state` reads the document. `/state/?peek=1` renders the page
without moving it.

What each part is computed from:

- **Waiting on the operator**: open Beads labelled `human` in every registered
  project (`bd human list`).
- **Running**: the agentctl job snapshot. A row names the project and
  operation, the command, the checkout, the caller recorded at launch, how
  long, and for a queued job the reason it waits.
- **Finished**: a first-parent commit on a project's default branch whose pull
  request checks passed (or that had no pull request), and which the revision
  running on this machine contains when the product is deployed here. The
  running revision is `nixos-version --configuration-revision` for the host
  configuration and, for a product pinned as a flake input, the revision that
  configuration's `flake.lock` pins. A change on the default branch that the
  running revision lacks is shown as "merged, not yet live".
- **Stalled or looping**: a job beyond twice the upper end of its usual range,
  a running job whose log has been quiet for 30 minutes, and one job failing
  three times in a row with the same exit code.
- **Limits and load**: `claude-quota`, the limits the newest Codex session
  reported, memory, file page cache, swap, pressure, and the agent slices'
  memory against their limits.
- **Products**: open tasks, the default branch's hosted check, the last merged
  change, the running revision and the state of the product's units.
- **Activations**: queued and running jobs of operations declared
  `announce = true` (the host's `switch` and `boot`), each with its caller and
  the commit its checkout stood on when it was requested.
- **Path claims** and **Agent sessions**: see the next section.

Text an agent wrote (a commit subject, a task title) appears only as a quoted
field beside the commit, pull request or task that carries it. Every other
sentence is assembled from the facts above.

The schema reserves two fields that nothing writes yet: `muted` (a mark for a
companion agent) and `small_next_move`.

### Sessions sharing the machine

Several agent sessions work on this machine at once. Three small tools let
them see each other; none of them blocks anything.

**Path claims.** `sinnix claim <path> --for "<what>" [--until <duration>]`
records that the calling session works under a path (default four hours, at
most seven days). A claim on a path that overlaps another session's claim is
still recorded; the command prints the other claim, and `sinnix state` lists
the pair as an overlap. `sinnix claims` lists every claim, `sinnix release
[<path>]` drops the caller's. An expired claim disappears without a release.
The caller is the agent session named by `CLAUDE_CODE_SESSION_ID` or
`CODEX_THREAD_ID`, or the login name at a plain terminal. The store is one
document, `/realm/state/hub/path-claims.json`:

```json
{"schema": "sinnix-path-claims-v1",
 "claims": [{"id": "c-1a2b3c4d", "path": "/abs/path", "purpose": "...",
             "harness": "claude", "session": "<session id>",
             "claimed_at": "<UTC time>", "expires_at": "<UTC time>"}]}
```

**Agent sessions.** `sinnix sessions` lists the interactive Claude Code and
Codex sessions with the memory each holds (its `agent-cli.slice` scope,
resident plus swapped), its idle time and its project, and says for each
whether it could be parked or why it stays. `sinnix state` shows the same rows
with a two-hour idle limit.

`sinnix sessions park --idle <duration>` ends Claude Code sessions idle at
least that long and prints the command that resumes each
(`cd <project> && claude --resume <id>`); `sinnix sessions parked` lists them
again later. It is a dry run without `--apply`, and nothing runs it on a
timer. Idle is not abandoned, so a session stays when any of these holds:

- it was started by another agent session (an agent's session variable in its
  start environment, or an agent process among its ancestors), or has no
  terminal: only sessions the operator started are candidates;
- the harness reports it busy or waiting on a dialog, a tool call has no
  result yet, or a command its shell tool started is still running;
- background agents were pending at its last turn end, or a subagent has a
  tool call without a result;
- its last turn called another agent, started a background task, or ran a
  command that waits on a queued job or a hosted check (`agentctl job wait`,
  `job start --wait`, `gh pr checks`, `gh run watch`, `--watch`, `sleep`);
- an unfinished agentctl job names it as caller, or the job queue cannot be
  read;
- its terminal received input within `--touched` (default 30 minutes);
- its input box holds text, or cannot be read (checked through kitty just
  before ending it);
- it has no transcript, so no ID to resume by; or it is a Codex session, which
  is reported only.

Parking sends the session's process `SIGTERM` after checking it is the process
the registry recorded, and never kills one that does not exit.

**Quota.** `sinnix quota ok --for discretionary` says whether work that can
wait may use the subscription now: exit 0 to start, 1 to wait, 3 when usage
could not be read, with one line of reason (`--json` for the reading). Work
waits while the weekly usage is at or above `--threshold` (default 85). The
gate is Claude's weekly window by default; `--provider codex` or `any` uses
the Codex limits the newest Codex session reported. `agentctl job start
--discretionary` asks this check (see [agentctl](agentctl.md)).

### Forecast and the Bead convention

Ranges are the 10th to 90th percentile of past durations and always carry the
number of samples behind them. With fewer than 8 samples the range is the
observed minimum to maximum and is marked as resting on few samples.

History comes from the agentctl event log (run time per operation, queue wait
per pool), the task-runner history database, and Beads closed in the last 120
days. Four clocks are reported separately: agent working time (claim to
close), waiting for machine resources (enqueue to start), waiting for the
operator (tasks labelled `human`, created to closed) and total elapsed
(created to closed).

A Bead records its forecast inputs in three places:

| Fact          | Where                                                              |
| ------------- | ------------------------------------------------------------------ |
| Size class    | label `size:small`, `size:medium`, `size:large` or `size:xlarge`   |
| Kind of work  | label `kind:<word>`; without one the issue type is the kind        |
| Own range     | metadata `estimate_low_minutes` and `estimate_high_minutes`        |

A closed Bead without a size label is sized from its single estimate in
minutes: up to 60 is small, up to 240 medium, up to 960 large, more is extra
large.

`sinnix estimate range <kind> <size>` answers "how long do tasks like this
take" from the closed Beads, and `sinnix estimate job <project> <operation>`
does the same for a declared operation. When the exact kind and size have too
few closed tasks, the answer says which wider set it used.

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
