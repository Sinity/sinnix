# The hub

`sinnix.services.hub` is the operator's browser front door to the estate:
generated reports, a live dashboard, and a control panel for the local AI
backends, reachable from a phone or the desktop and from nowhere else.

Before it existed, a generated HTML report was a `file://` path — unlinkable,
unreadable on a phone, and unable to send anything back. The hub makes each one
a URL, puts the estate's current state on the same origin, and gives report
annotations somewhere to go.

## Routes

Everything below is on the hub port (8880 by default).

| Route                | What it is                                                            |
| -------------------- | --------------------------------------------------------------------- |
| `/`                  | Server-rendered dashboard: pressure, sources, storage, units, agents  |
| `/ai/`               | AI control panel: per-service state plus start/stop/restart           |
| `/reports/`          | The generated report tree, browsable and linkable                     |
| `/ops/v1/*`          | Reverse proxy onto the ops-reducer's read and action API              |
| `/feedback`          | Append-only spool for report annotations                              |

The loopback web UIs get one port each rather than a subpath of the hub —
`8881` Open WebUI, `8882` ComfyUI, `8883` KoboldCpp. They are single-page apps
that emit absolute asset URLs and have no base-path support, so a `/ui/comfyui/`
mount would half-work in the way that wastes an afternoon. One port each costs
one firewall entry and always works.

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
addresses on the same port does *not* produce two listeners: Caddy merges
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
dropped; without the per-interface *scoping*, the LAN would not be.

## Why it runs in the user manager

The dashboard's whole value is the ops-reducer's current-state snapshot, and the
reducer is a *user* service whose Unix socket is `0600` and operator-owned.
Running the hub in the same manager reaches that socket, the operator-owned
reports tree, and the action API without loosening a single permission. Nothing
here needs a privileged port.

## Why there is no second control plane

The AI panel's buttons post to `/ops/v1/actions` — the ops-reducer's existing
bounded action API. That API already owns admission (targets must be attested
runtime-inventory units that declare `observe.restartable`), optimistic
concurrency (`expected_revision` must match the snapshot the operator saw),
idempotency keys, and durable receipts. The hub adds no shell-out, no `sudo`,
and no privileged helper.

`start` and `stop` were added to that verb set rather than built beside it, so
they inherit the same gate and the same receipts as `restart`. Privilege comes
from the workstation profile's existing polkit rule for `wheel` on
`org.freedesktop.systemd1.*`; the hub introduces no new grant.

The panel resolves every unit from `/etc/sinnix/runtime-inventory.json` — the
same attested document the action API validates against — so it cannot offer a
button the API would refuse for a reason the panel does not know about. A
service whose module is not enabled renders as "not registered" rather than
silently disappearing.

**The backends are socket-activated.** They sit behind `systemd-socket-proxyd`
and exit after a 30s idle timeout, so *idle* is the normal resting state, not a
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

`collectState()` is the skill's own function. Deliberately a *simple* request —
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

The skill is unchanged. Adopting the line above is a later, optional edit.

## Rendering

`sinnix-hub-render` runs on a timer (60s) and writes complete HTML: the browser
fetches nothing to display state. A phone on a flaky link, or a page left open
overnight, shows the estate as of a timestamp it prints, rather than an empty
skeleton waiting on XHR. The only client-side logic is the action buttons and a
three-line script that rewrites the frontend port links to whichever host you
reached the hub on.

Inputs are the reducer snapshot, the runtime inventory, and a Nix-generated
manifest. A missing input degrades the page — "estate state unavailable", with
the links still working — rather than failing the unit.

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
