# The hub

`sinnix.services.hub` is the operator's browser front door to the system:
generated reports, a live dashboard, and a control panel for the local AI
backends, reachable from a phone or the desktop and from nowhere else.

It makes each generated report a URL rather than a `file://` path, puts the
system's current state on the same origin, and gives report annotations
somewhere to go.

## Routes

Everything below is on the hub port (8880 by default), and every page carries
the same nav, so the routes are reachable from each other rather than by URL.

| Route            | What it is                                                          |
| ---------------- | ------------------------------------------------------------------- |
| `/`              | The three-second read: a verdict, six tiles, then supporting detail |
| `/work/`         | What is actually running, named — see below                         |
| `/pressure/`     | Which pressure regime the machine is in, and what acting costs      |
| `/services/`     | Every attested runtime surface, grouped by resource class           |
| `/ai/`           | The local AI backends and their activation semantics                |
| `/shaders/`      | The Hyprland screen-shader library, and which one is applied        |
| `/capabilities/` | Everything this machine can do and how to invoke it — see below     |
| `/reports/`      | The generated report tree, browsable and linkable                   |
| `/ops/v1/*`      | Reverse proxy onto the ops-reducer's read and action API            |
| `/feedback`      | Append-only spool for report annotations                            |
| `/terminals/`    | Live kitty terminal contents, control, and scrollback history       |

The loopback web UIs get one port each rather than a subpath of the hub —
`8881` Open WebUI, `8882` ComfyUI, `8883` KoboldCpp. They are single-page apps
that emit absolute asset URLs and have no base-path support, so a `/ui/comfyui/`
mount would half-work in the way that wastes an afternoon. One port each costs
one firewall entry and always works.

## The workload view

`/work/` answers "what is this machine doing right now?" in sentences, not in a
process list. It can, because sinnix already names its own work:

- **Project commands in flight** come from the project ledger. A row is
  "sinex is running `test`, in flight 3m 14s, developer-build".
- **AgentCTL jobs** show the declared operation or attested agent, registered
  checkout, lifecycle, and cancellation control from the canonical Sinnixd
  record.
- **Slice budgets** show the resource policy carried by declared services and
  AgentCTL jobs.

### What the page can and cannot do

Lifecycle control goes through the reducer's action API and nowhere else, so
the page can only offer what that API accepts: `start`/`stop`/`restart` on an
attested inventory unit that declares `observe.restartable`, `interrupt` on an
AgentCTL attested agent job, and `stop` on an admitted `{pid, start_ticks}`
process (sinnix-mble — see "Unshackling the hub" below). A process is admitted
by live cgroup membership — only inside `agent.slice`, `build.slice`, or a slice the
runtime inventory itself marks sacrificial — never by name, so the button is
only offered where the action would actually be accepted. Two gaps remain
and stay named rather than papered over: a slice-level policy change
(`MemoryHigh` on `agent.slice` itself) is refused because `set_policy`
resolves through the runtime inventory and slices are not registered surfaces
there, and nothing drains swap or reclaims a slice's already-swapped pages.

## The pressure view

`/pressure/` exists because the machine's two ways of becoming unusable look
nothing alike, and the conventional gauges see neither. It is derived from a
clustering of this host's own incident telemetry, so every number on it earns
its place:

- **A regime banner** naming the cluster rather than a severity: `CALM`,
  `SWAP-CRITICAL` (swap at/above 75%, or memory full PSI at/above 20),
  `SPIKE` (under 2 GiB available while nothing is stalling), `IO-SATURATED`
  (io full PSI at/above 40 with memory fine). They call for different actions,
  and two of them call for none.
- **Swap headroom as the primary widget.** Across 29 measured freeze onsets,
  swap was 90% consumed ten minutes before the freeze while available memory
  still read 12.8 GiB. Nothing else on this machine displays it.
- **`memory_psi_full` second** — the honest "is anything actually stalled" —
  and **available memory last and explicitly demoted**, because it is the
  number that looks healthy during a freeze and triggers the emergency killer
  during a burst the machine was surviving.
- **A hog table ranked on resident _plus_ swapped pages**, with a cost column:
  a re-runnable tool invocation (`rg`, `bd list`, `git diff`) is free to stop,
  an expensive job or model server is not, and session processes are summed in
  one row rather than given rows they would take from something actionable.
- **A scheduled-pressure strip** off the timer table: borg, btrbk, the scrubs
  and the SQLite dumps, with how long each one's last run took. This class of
  IO pressure is declared in advance, so the page predicts rather than alarms.

The same evidence produces one health lane, on the reducer's existing sweep:
swap at/above 75% while memory full PSI is below 20 emits a
`sinnix-health-transition-v1` transition and a desktop notification through the
same debounce, ledger and dedup path as every other lane. That pair is the
pre-freeze state specifically; swap saturated _while_ everything stalls is
reported as `stalled`, because the warning has already been missed.

Buttons exist only where the bounded action API admits the target: `park` with
its own thaw deadline on a _running_ backup unit the runtime inventory carries,
and — on hog rows the cost column classifies re-runnable — `stop` on the one process
(`{pid, start_ticks}`), so reclaiming a runaway `rg` no longer means stopping
its whole agent session. The pin is re-verified against `/proc/<pid>/stat`
at execution time (a mismatch means the pid was reused and is refused, never
silently retargeted), and admission is by live cgroup membership rather than
process name: only `agent.slice`, `build.slice`, and slices the runtime
inventory itself marks sacrificial (`ManagedOOMMemoryPressure = kill`) can be
targeted, so a PID 1 direct child, the reducer's own process, and anything in
a session-critical or unmarked slice never gets the button. The stop is
SIGTERM first, escalating to SIGKILL only if the same identity is still alive
after a 3-second grace window — short because every command this reaches is a
short-lived tool invocation with no state to flush. One gap remains and the
page still states it rather than routing around it: no slice target exists
for `set_policy`, since slices are not registered surfaces, and nothing drains
swap or reclaims a slice's already-swapped pages at all.

## The capability index

`/capabilities/` answers the question no other page does: not what is happening,
but what exists at all. Every row — feature, service, AI backend, script,
devshell command, agent skill, capture lane, MCP server, agent CLI lane, hub
page — carries a description, how to invoke it, whether it is enabled, and the
repo file that declares it.

Nothing on that page is written twice. `/etc/sinnix/capability-index.json` is
built at evaluation time (`modules/capability-index.nix`, builder in
`modules/lib/capability-index.nix`) out of the declarations that already carry
the description: script frontmatter, which fails evaluation without one; the
`description` argument `mkFeatureModule`/`mkServiceModule` require; the devshell
command registry; `SKILL.md` frontmatter; the MCP registry, which now throws on
a server that does not describe itself. Capture lanes and agent CLI lanes have
no prose of their own, so their rows are rendered from their own structured
fields — the owning service's description plus the declared cadence, the client
plus the MCP profile and backend.

The reducer adds the two things Nix cannot know:

- **The hub's own routes**, declared in `pages/shell.py` because that is where
  the routing lives. The nav and the `hub-page` rows read one table.
- **The usage census** (`sinnix census`, weekly), joined by name — and, for
  services, by every runtime surface the module declared, since the census
  enumerates services from the runtime inventory where `polylogue` the service
  is `polylogued` the surface. A capability that reads `unused-in-window` has
  been declared and never used since the window opened.

There are no buttons. Discovering a capability is not an action verb, and the
things you would do with one already have a page or a shell.

The same merged view is available without a browser:

```
sinnix-ops-reducer capabilities                # grouped table
sinnix-ops-reducer capabilities --json         # the whole view
sinnix-ops-reducer capabilities --kind script  # one kind
```

`sinnix cheatsheet` (SUPER SHIFT+Slash) renders it into the searchable offline
page next to the live Hyprland binds, so the same answer is one keystroke away
from the desktop and one tab away from the phone.

## Why it cannot be seen from the LAN

Two independent layers, either of which would suffice alone.

**Binding.** Caddy listens on exactly two addresses per port: loopback, and the
host's `tailscale0` IPv4 address. The tailnet address is not known at build time
and is not a fact this public repository should carry, so an `ExecStartPre`
reads it off the interface — not `tailscale ip`, which needs the privileged
tailscaled socket — retries while the interface comes up, and fails the unit if
it never appears. A hub that cannot bind the tailnet is supposed to be down, not
listening wider.

The `bind` directive in each site block is load-bearing. Listing two site
addresses on the same port does _not_ produce two listeners: Caddy merges
same-port sites into one server on `:PORT` — that is `0.0.0.0` — and separates
them by `Host` header, which is no boundary at all. After any edit to the
Caddyfile, check the adapted config rather than trusting how it reads:

```
caddy adapt --adapter caddyfile --config <file> | jq '.apps.http.servers | map_values(.listen)'
```

Every entry must be an explicit address. A bare `":8880"` is a regression.

**Firewall.** Ports are opened on `tailscale0` only, via
`networking.firewall.interfaces.tailscale0.allowedTCPPorts`. This matters
because `useRoutingFeatures = "none"` means upstream does not put `tailscale0`
in `trustedInterfaces` — without the per-interface opening, the phone would be
dropped; without the per-interface _scoping_, the LAN would not be.

## Why it runs in the user manager

The dashboard's whole value is the ops-reducer's current-state snapshot, and the
reducer is a _user_ service whose Unix socket is `0600` and operator-owned.
Running the hub in the same manager reaches that socket, the operator-owned
reports tree, and the action API without loosening a single permission. Nothing
here needs a privileged port.

## The shader page has no buttons

`/shaders/` lists the screen-shader library in `dots/hypr/shaders`, describes
each stage, and reports what Hyprland currently has applied — read live from
`hyprctl getoption`, not from a manifest that could be stale.

It stops there. Applying a shader is not a verb the reducer's action API has,
and the doctrine below is the whole reason: a page that shelled out to
`hyprctl` would be the second control plane. So the page prints the
`sinnix-shader` commands and says why they are not buttons. The keyboard is the
fast path anyway — `F4` cycles, `Shift+F4` clears — and `Shift+F4` matters,
because a shader can make the screen unreadable and the way out must not depend
on finding a terminal.

Making it clickable is a reducer change: a shader target with its own
attestation. It is not a hub change.

The page also carries the two facts that are easy to get wrong about screen
shaders here, because there is nowhere better to put them. Hyprland pins the
`time` and pointer uniforms to constants unless `debug:damage_tracking` is `0`,
so animation is real but costs a full-screen redraw per frame; and a shader that
reads those uniforms _while_ damage tracking is on makes Hyprland paint a red
error banner across the top of the display. Turning damage tracking off before
applying avoids the banner rather than dismissing it afterwards, which is the
order `sinnix-shader` uses. Measured cost of the animated case, from Hyprland's
own `debug:overlay`: 120fps/1.05ms render becomes 118fps/1.12ms, and GPU draw
moves about a watt.

Shaders compose. Hyprland takes one path, so nothing stacks at the compositor,
but `sinnix-shader apply a b c` generates a single fragment shader containing all
of them — warps on the sampling coordinate, one texture fetch, then shades — and
`_presets.conf` names the combinations worth keeping. `play` cycles shaders or
presets on an interval, crossfading by generating both pipelines into one shader
and mixing on `time`. It runs as a transient systemd unit whose `ExecStopPost`
clears the screen, so a `SIGKILL` mid-cycle still restores the display; that is
the one teardown a signal handler cannot promise, and it is why playback is a
unit rather than a background process.

Note that a screen shader cannot be verified by screenshotting. `grim` and
screencopy do not observe the final shader stage on this host — a full-screen
invert produces a byte-identical capture while whiting out the actual display.
They _do_ see the error overlay and the debug overlay, which is why both are
usable as instruments. Shader compilation is checked with `glslangValidator`
before anything reaches the display instead, because Hyprland defers the compile
to the next render pass and logs nothing when it fails.

## Why there is no second control plane

Every button on every page posts to `/ops/v1/actions` — the ops-reducer's existing
bounded action API. That API already owns admission (targets must be attested
runtime-inventory units that declare `observe.restartable`), optimistic
concurrency (`expected_revision` must match the snapshot the operator saw),
idempotency keys, and durable receipts. The hub adds no shell-out, no `sudo`,
and no privileged helper.

`start`, `stop`, and `restart` are one verb set behind that gate, sharing the
same admission and the same receipts. Privilege comes from the workstation
profile's existing polkit rule for `wheel` on `org.freedesktop.systemd1.*`; the
hub introduces no new grant.

The pages resolve every unit from `/etc/sinnix/runtime-inventory.json` — the
same attested document the action API validates against — so they cannot offer
a button the API would refuse for a reason the page does not know about. A
service whose module is not enabled renders as "not registered" rather than
silently disappearing, and a unit with no `observe.restartable` renders as "not
restartable" rather than with a button that would 403.

**The backends are socket-activated.** They sit behind `systemd-socket-proxyd`
and exit after a 30s idle timeout, so _idle_ is the normal resting state, not a
fault, and connecting to the public endpoint starts one with no privileged
action at all. Ollama and KoboldCpp hold the same `gpu-inference` admission key
and conflict by design. See `docs/local-ai-activation.md`.

## Unshackling the hub

The process-target admission rule above keeps the reducer as the only control
plane. The remaining verbs
(`freeze`/`thaw`/`park`/`set_policy`/`reset_policy`, already implemented and
already unit-only) belong on a page:

- **`park` and `set_policy`/`reset_policy` are on `/pressure/` and
  `/services/`.** `park` freezes a unit's cgroup and schedules its own thaw in
  the same action, so a parked backup cannot be forgotten frozen — the hub
  button prompts for the deadline rather than guessing one, because the
  action refuses to run without it. `set_policy`/`reset_policy` tune whichever
  `MemoryHigh`/`MemoryMax`/`MemoryLow`/`CPUWeight`/`IOWeight`/`Nice` properties
  a surface's own `effectiveResources` already declares, with one button that
  restores every one of them from the inventory's value — reversible by
  construction, which is the design goal the operator named ("auditability
  and reversibility, not restraint"), not a smaller or safer verb set than
  the one that already exists.
- **Bare `freeze`/`thaw` stay backend-only.** They are `park`'s own building
  blocks (`sinnix-pressure-park freeze`/`thaw`), and the difference that
  matters is the missing deadline: a bare freeze has no scheduled thaw, so a
  forgotten one is an indefinitely paused unit rather than a unit that
  resumes on its own. `park` is strictly more capable for every case a hub
  button would want (pause now, resume later) and carries the safety property
  bare freeze does not, so there is no case where surfacing the primitive
  adds power the composed verb lacks — it only adds a way to forget.
- **`/feedback/elicit/<domain>`** is the read-API design this bead also asked
  for, covered under "Report annotations, handed back" below.

## Report annotations, handed back

The html-report skill generates annotation widgets that autosave to
`localStorage` and export one JSON blob for the operator to paste into a chat.
With a server in front of the reports, that paste step can be one `fetch()`:

```js
fetch("/feedback", { method: "POST", body: JSON.stringify(collectState()) });
```

`collectState()` is the skill's own function. Deliberately a _simple_ request —
no custom headers, so no CORS preflight — which means the same line works from a
report served by the hub and from one opened straight off disk as `file://`
(`Origin: null`), as long as the hub is reachable and the URL is absolute in the
`file://` case.

`/feedback` is a route on the ops-reducer, reached through the same reverse
proxy as the pages. Submissions land in
`/realm/data/derived/hub-feedback/<UTC-date>.jsonl`, one JSON object per line,
each wrapping the payload in an envelope carrying the receive time, the
referring page, and a sequence number — so a consuming agent can tell
submissions apart without trusting client-supplied fields. That file format is
the contract and is unchanged from the earlier standalone feedback daemon
this route replaced.

The spool itself is write-only. There is no route that reads it back: serving
arbitrary posted payloads would turn a sink into an exfiltration surface for
the personal analysis those annotations describe. That refusal stands.

A `sinnix-elicit-v1` record arriving in the spool starts the drain
(`sinnix-elicit autoingest`, as a transient `sinnix-elicit-autoingest` unit)
instead of a 120s timer looking for one. The trigger coalesces: a comparison
session is a burst of one POST per judgment, and the Bradley-Terry refit happens
once, a few seconds after the last tap, rather than once per tap.

`GET /feedback/elicit/<domain>` is the one read this route does carry, and it
is a different decision from the spool refusal above, not a walk-back of it:
it serves back a domain's own fitted `model.json` (`sinnix-elicit`'s
`/realm/data/notes/preferences/<domain>/model.json`), a derived
Bradley-Terry fit over items the operator defined themselves on this host,
not an arbitrary posted payload. Bounded the same way as everything else
here — the domain name is checked against a fixed charset and the resolved
path must stay under the configured preferences root — never a general
filesystem read. This unblocks the in-session "learning so far" preview
noted onto this bead from sinnix-eb9c: a comparison session can poll its own
domain's model mid-session instead of only after the next full page load.
Wiring that poll into the session page's own JS is `scripts/sinnix-elicit`'s
follow-up, not this route's.

## Terminal views

`/terminals/` (sinnix-859p) reads and drives the operator's own kitty windows
over the browser, without a multiplexer. It is a route family on the
ops-reducer, absorbed from an earlier standalone terminal-viewing daemon —
same URLs, same response shapes, same design doctrine, now falling through
the same catch-all `handle` in the Caddyfile as every other page instead of
its own `handle_path` block and its own Unix-socket process.

Three sources, none of them a new capture lane:

- **Live** — every kitty shell already runs under `asciinema session
  --stream-local` (that is how the capture lake is written), so the reducer
  reads the recorder's own process environment and listening port back out of
  `/proc` and proxies its player and WebSocket under `/terminals/v1/live/
<pid>/<window_id>/`. A viewer joining late gets the current screen first.
- **Snapshot** — kitty's own remote-control protocol (`kitty @ get-text
--ansi`), for any window with no live stream (started before streaming was
  wired in, or outside `sinnix-captured-shell`).
- **History** — the existing full-ANSI scrollback captures
  `sinnix-capture-kitty-scrollback` already writes to
  `/realm/data/activity/kitty-scrollback`, joined to a window by the
  `(kitty_pid, window_id)` pair that is the capture's own filename key.

`send-text`/`send-key`, from the page's input box and quick-action buttons,
are the operator's own deliberate typing routed through a browser instead of
a keyboard — not the "never inject into a live agent TUI" case, which is
about _automated_ interruption of a session an agent doesn't own.

No auth beyond the tailnet boundary the rest of the hub relies on, and no
database: kitty's own `ls`/`get-text` and the scrollback files on disk are
the only state, and per-window sent-text recall lives in the browser's own
`localStorage`.

## Rendering

The ops-reducer renders every page on request and Caddy reverse-proxies the
page paths to its Unix socket; only `/reports/` is served off disk. Each
response is complete HTML: the browser fetches nothing to display state. A phone
on a flaky link, or a page left open overnight, shows the system as of a
timestamp it prints, rather than an empty skeleton waiting on XHR. Client-side
logic is limited to the action buttons, the theme and text-size toggles, the
services filter, and the three lines that rewrite the frontend port links to
whichever host you reached the hub on.

Rendering on request replaced an earlier render-on-timer design that wrote the
same pages to static files every 60 seconds. The reducer already held the
state those pages show, so the timer bought nothing but staleness: a page is
now as current as the moment it was asked for.

Inputs are the reducer's live snapshot, the runtime inventory, a Nix-generated
manifest, and live systemd state. A missing input degrades the page rather than
failing the request: `/` says plainly when it cannot tell whether anything is
wrong.

Serving the pages over the reducer's Unix socket is what keeps the auth model
intact. The reducer treats that socket as authorized — it is 0600 in the
operator's runtime directory — and still demands a bearer token on its loopback
TCP listener, so the page routes expose exactly what the action API already
exposed there. POSTs to `/ops/*` keep the same-origin gate and the reducer's
`expected_revision` check unchanged.

The visual language is sinnix's own: the same CSS custom properties, status
tones, stat tiles, badges and A−/A+ controls as the generated reports, in the
violet "ops" accent so the hub is distinguishable at a glance from a report.
It is styled for the phone first — one column, ≥2.4rem touch targets, no
horizontal scroll at 360px — and widens into columns on a desktop instead of
stretching one long list across 4K.

## Operating it

```
systemctl --user status sinnix-hub sinnix-ops-reducer
journalctl --user -u sinnix-hub -n 50             # Caddy errors only; access logs are off
journalctl --user -u sinnix-ops-reducer -n 50     # page rendering and the action API
```

State lives in `/realm/state/sinnix-hub` (Caddy's own scratch and the access
log) and holds nothing that is not regenerated, so it is on the NVMe volume
rather than the wear-limited root and needs no persistence entry.

## Deliberately not included

- **No HTTPS.** `tailscale serve` would provide it, but it needs MagicDNS and
  tailnet-wide cert provisioning, and this host runs `enableMagicDNS = false`
  under a standing "never touch DNS" posture. Plain HTTP over WireGuard is the
  honest trade; revisit only alongside that posture.
- **No proxying of the raw model APIs** (Ollama `:11434`, LiteLLM `:4000`).
  Republishing them would widen the surface and hold the idle proxies open,
  defeating the teardown the activation design exists for.
- **No auth beyond the tailnet.** Consistent with the rest of sinnix: the
  tailnet is the boundary, and every agent on this host is already
  root-equivalent.
