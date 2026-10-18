# Steering

Steering holds the operator's own intentions: things only the operator can
decide or settle, as opposed to technical work an agent can finish. Agents
and surfaces re-present an intention once it is written down; nothing pings
or nags. It is not a task tracker; the sinnix Beads database is that.

Design rules:

- **Forecasts.** Day intentions carry a forecast probability ("deep work
  block, 60%"); outcomes are logged, and calibration compares the two.
- **One decision per day.** 1–3 intentions are picked from a standing menu.
- **State labels.** Each standing intention names the state needed to act on
  it (`state:settled` / `state:any` / `state:averse-ok`), so an agent can
  offer one that fits.

## What the store holds

Everything lives in the steering workspace, `/realm/project/steering/repo`,
its own git repo consumed by sinnix as the `steering` flake input.

1. **Intentions**: a second Beads database with the `me-` prefix (the `steer`
   wrapper in the workspace pins `bd` to it). The session-start block prints
   these.
2. **`steering.sqlite`**, three tables:
   - **activities**: the standing menu, tiered by the state they need.
     Experiments are activities with a hypothesis and a pre-registered
     prediction.
   - **commitments**: day intentions with a forecast and an outcome.
   - **reviews**: written reviews of a day.

Calibration is computed from commitments, never stored.

## What runs

`modules/services/steering.nix` declares one user timer:
`sinnix-steering-export` at 23:50 writes the full store to
`/realm/activity/shared/steering/<date>.jsonl`, the copy Lynchpin reads.

## Surfaces

- **Session-start block** ("Personal Steering", in every agent session): the
  open `me-` intentions, rendered by
  `dots/claude/hooks/sessionstart-steering.sh`.
- **Phone**: three steering screens fed by `inbox/steering.json`, which prime
  renders on request via `sinnix-steer export-phone`: the menu, open
  commitments, and the ready queue (see docs/phone.md).
- **CLI**: `sinnix-steer` for the sqlite store (`intent add/done/miss`,
  `activity menu`, `calibration`, `ritual`), and `steer` (in the workspace)
  for the `me-` intentions.

## Daily use

- Pick the day's intentions: `sinnix-steer intent add "…" --forecast 0.7`.
- Resolve them in the evening: `sinnix-steer intent done|miss <id>`.
- Check calibration occasionally with `sinnix-steer calibration`; list the
  standing intentions with `steer ready`.

## The two trackers

| holds                                | tracker                   |
| ------------------------------------ | ------------------------- |
| technical work an agent can execute  | sinnix beads (`sinnix-*`) |
| intentions only the operator settles | steering beads (`me-*`)   |

One subject can exist in both at different levels: `me-z2l` is the intention
"reshape the browser"; its configuration is sinnix work. If an agent could
finish it, it is not a `me-` item.
