# The hub

`sinnix.services.hub` is the operator's browser front door to the estate:
generated reports, a live dashboard, and a control panel for the local AI
backends, reachable from a phone or the desktop and from nowhere else.

It makes each generated report a URL rather than a `file://` path, puts the
estate's current state on the same origin, and gives report annotations
somewhere to go.

## Routes

Everything below is on the hub port (8880 by default), and every page carries
the same nav, so the routes are reachable from each other rather than by URL.

| Route        | What it is                                                          |
| ------------ | ------------------------------------------------------------------- |
| `/`          | The three-second read: a verdict, six tiles, then supporting detail |
| `/work/`     | What is actually running, named — see below                         |
| `/services/` | Every attested runtime surface, grouped by resource class           |
| `/ai/`       | The local AI backends and their activation semantics                |
| `/shaders/`  | The Hyprland screen-shader library, and which one is applied        |
| `/reports/`  | The generated report tree, browsable and linkable                   |
| `/ops/v1/*`  | Reverse proxy onto the ops-reducer's read and action API            |
| `/feedback`  | Append-only spool for report annotations                            |

The loopback web UIs get one port each rather than a subpath of the hub —
`8881` Open WebUI, `8882` ComfyUI, `8883` KoboldCpp. They are single-page apps
that emit absolute asset URLs and have no base-path support, so a `/ui/comfyui/`
mount would half-work in the way that wastes an afternoon. One port each costs
one firewall entry and always works.

## The workload view

`/work/` answers "what is this machine doing right now?" in sentences, not in a
process list. It can, because the estate already names its own work:

- **Project commands in flight** come from the project ledger the devshell
  wrappers write — the same records lynchpin reads. A row is
  "sinex is running `test`, in flight 3m 14s, developer-build".
- **Scopes** are the transient units `sinnix-scope` creates. The unit name
  carries the command class (`sinnix-build-…`, `sinnix-nix-build-…`), so a
  scope is never anonymous, and the scope's leader process supplies the command
  and working directory that turn it into "`xtask test -p sinexd` in `sinex`".
  Launch wrappers (`env`, `nice`, `ionice`, the scope supervisor, `nix develop
--command`) are stripped so the line reads as what was typed.
- **Memory against the ceiling that binds it.** Agent scopes carry their own
  8G/12G cap; a build scope does not, so the figure shown is against
  `build.slice`'s. Slice budgets get their own card, because "how much of the
  sacrificial budget is spent" is the question that predicts a stall.
- **Agent-gateway jobs** are matched to their `sinnix-agent-job-*.scope` by job
  id, so a live job shows its backend, model, work item and elapsed time, and
  the ones whose launcher has exited are listed separately, with the reducer's
  orphan policy on the ones that need a decision.

Long-lived scopes are labelled as such rather than filtered out. A devshell
Postgres or a Dolt server that has sat in `build.slice` for a week is not
"nothing" — it is spending the same budget the next compile wants.

### What the page cannot do

Lifecycle control goes through the reducer's action API and nowhere else, so
the page can only offer what that API accepts: `start`/`stop`/`restart` on an
attested inventory unit that declares `observe.restartable`, and `interrupt` on
an attested agent job. An ad-hoc `sinnix-scope` placement is neither, so a
running compile is fully _visible_ and not stoppable from the hub. The page
says so in place of the button. Making it stoppable is a reducer change — a
scope-target admission rule with its own attestation — not a hub change.

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
attestation, the same shape the scope target took. It is not a hub change.

The page also carries the two facts that are easy to get wrong about screen
shaders here, because there is nowhere better to put them. Hyprland pins the
`time` and pointer uniforms to constants unless `debug:damage_tracking` is `0`,
so animation is real but costs a full-screen redraw per frame; and a shader that
reads those uniforms *while* damage tracking is on makes Hyprland paint a red
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
They *do* see the error overlay and the debug overlay, which is why both are
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

Submissions land in `/realm/data/derived/hub-feedback/<UTC-date>.jsonl`, one
JSON object per line, each wrapping the payload in an envelope carrying the
receive time, the referring page, and a sequence number — so a consuming agent
can tell submissions apart without trusting client-supplied fields.

The endpoint is write-only. There is no read route: serving the spool back would
turn a sink into an exfiltration surface for the personal analysis those
annotations describe.

## Rendering

`sinnix-hub-render` runs on a timer (60s) and writes complete HTML: the browser
fetches nothing to display state. A phone on a flaky link, or a page left open
overnight, shows the estate as of a timestamp it prints, rather than an empty
skeleton waiting on XHR. Client-side logic is limited to the action buttons, the
theme and text-size toggles, the services filter, and the three lines that
rewrite the frontend port links to whichever host you reached the hub on.

Inputs are the reducer snapshot, the runtime inventory, a Nix-generated
manifest, live systemd state, and — for the workload view — the scope cgroups
and their leader processes. A missing input degrades the page rather than
failing the unit: with no reducer snapshot, `/work/` still shows live scopes
straight from systemd, and `/` says plainly that it cannot tell you whether
anything is wrong.

The visual language is the estate's own: the same CSS custom properties, status
tones, stat tiles, badges and A−/A+ controls as the generated reports, in the
violet "ops" accent so the hub is distinguishable at a glance from a report.
It is styled for the phone first — one column, ≥2.4rem touch targets, no
horizontal scroll at 360px — and widens into columns on a desktop instead of
stretching one long list across 4K.

## Operating it

```
systemctl --user status sinnix-hub sinnix-hub-feedback sinnix-hub-render.timer
systemctl --user start sinnix-hub-render          # re-render now
journalctl --user -u sinnix-hub -n 50             # Caddy errors only; access logs are off
```

State lives in `/realm/state/sinnix-hub` (rendered pages plus Caddy's scratch)
and holds nothing that is not regenerated on the next render, so it is on the
NVMe volume rather than the wear-limited root and needs no persistence entry.

## Deliberately not included

- **No HTTPS.** `tailscale serve` would provide it, but it needs MagicDNS and
  tailnet-wide cert provisioning, and this host runs `enableMagicDNS = false`
  under a standing "never touch DNS" posture. Plain HTTP over WireGuard is the
  honest trade; revisit only alongside that posture.
- **No proxying of the raw model APIs** (Ollama `:11434`, LiteLLM `:4000`).
  Republishing them would widen the surface and hold the idle proxies open,
  defeating the teardown the activation design exists for.
- **No auth beyond the tailnet.** Consistent with the rest of the estate: the
  tailnet is the boundary, and every agent on this host is already
  root-equivalent.
