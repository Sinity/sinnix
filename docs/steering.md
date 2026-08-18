# Steering

Steering is the estate's memory for the operator's **own intentions** — the
things only he can decide or settle, as opposed to technical work an agent can
finish. An intention, once formed, is written down outside his head and
re-surfaced by agents and timers, so that _having a goal_ survives _not being
in a state to hold one_. It is deliberately not a task tracker; the sinnix
Beads database is that.

Every steering surface — the "Personal Steering" block at the top of agent
sessions, the cockpit at `http://127.0.0.1:8791`, the phone's steering
screens, the morning notification — is a view over one small store, described
here.

## Why it exists

The recorded rationale (beads `sinnix-q20`, `sinnix-jfiy`, `sinnix-iixf` carry
it; the deeper personal context stays in local scratch by design):
goal-formation requires self-contact, which is expensive for this operator,
and that cost produces long autopilot stretches. Steering decouples the two.
Forming an intention and acting on it become separate events: the store holds
the intention between them, and the surfaces re-present it without demanding
it be re-formed.

Three recorded design principles follow from that:

- **Prediction-calibration as the spine.** Day intentions carry a forecast
  probability ("deep work block, 60%"), outcomes are logged, and the
  calibration curve turns plans from self-judgment into measurement.
- **Decide-once scheduling.** One decision point per day picks 1–3 intentions
  from a standing menu — satisficing by construction, so no session starts
  from a blank page and no hour re-litigates the day.
- **State-aware surfacing.** Each standing intention names the internal state
  required to act on it (`state:settled` / `state:any` / `state:averse-ok`),
  so an agent can offer the one that fits the state the operator is actually
  in, instead of a flat list demanding triage he may not be able to do.

The mechanism never pings mid-day and never nags: agents surface intentions
when relevant, the operator steers. Realtime self-steering is aversive and is
explicitly designed out (the phone shows no live readouts for the same
reason).

## What the store holds

Everything lives in the steering workspace, `/realm/project/steering` — its
own git repo, consumed by sinnix as the `steering` flake input. Two carriers:

**1. Intentions** — a second Beads database with the `me-` prefix (the
`steer` wrapper in the workspace pins `bd` to it). These are the items the
session-start block prints. Real example:

> `me-cxg` (P1, `state:settled`) — Polylogue readiness gate: declare a v0
> done-DATE (not done — a date).

**2. `steering.sqlite`** — the typed store, three tables:

- **activities** — the standing menu the morning ritual chooses from, tiered
  by the state they need. Real example: _deep work block_ (task, ~90 min,
  energy: good). Experiments are activities with a hypothesis and a
  pre-registered prediction; the sleep-schedule-stabilization experiment sits
  here with a placeholder prediction that deliberately blocks treating it as
  running.
- **commitments** — day intentions with a forecast and an outcome. Real
  example: _deep work block_, forecast 60%, resolved **missed** — which is a
  calibration data point, not a failure entry.
- **reviews** — what the rituals write. Real example, morning 2026-08-18:
  _"Yesterday's miss: deep work block. Pattern says don't re-propose the same
  shape at the same size — shrink it or trade it."_

Calibration is always computed from commitments, never stored.

## What runs, and when

Three user timers (declared in `modules/services/steering.nix`), plus one
long-running service:

| Unit                      | When   | What it does                                                                                                                                                       |
| ------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `sinnix-steering-morning` | 08:00  | `sinnix-steer ritual morning`: `claude -p` over the store — one root-probing question, then 1–3 proposed intentions with forecasts. Writes a review row, notifies. |
| `sinnix-steering-evening` | 21:30  | `sinnix-steer ritual evening`: written review — what happened vs. intended, a done/missed/carry call per open commitment. Writes a review row, notifies.           |
| `sinnix-steering-export`  | 23:50  | Full store to `/realm/data/activity/steering/<date>.jsonl` — the lake copy lynchpin joins against telemetry.                                                       |
| `sinnix-cockpit`          | always | Read-only web view on loopback port 8791.                                                                                                                          |

## The surfaces, and why each exists

- **Session-start block** ("Personal Steering", in every agent session) — the
  open `me-` intentions. The operator lives in agent sessions, so state rides
  a path he already walks; no reminder to ignore, no app to open. Rendered by
  `dots/claude/hooks/sessionstart-steering.sh`.
- **Cockpit** — `http://127.0.0.1:8791`: `/today` (open commitments),
  `/calibration` (forecast vs. actual done-rate), `/activities` (the menu).
  Read-only on purpose; writes go through the CLI or an agent.
- **Phone** — three steering screens fed by `inbox/steering.json`, which
  prime renders on request via `sinnix-steer export-phone`: the menu, open
  commitments, and the ready queue of pre-composed outward actions (currently
  approximated as open commitments whose window ends today — see
  docs/phone.md).
- **CLI** — `sinnix-steer` for the sqlite store (`intent add/done/miss`,
  `activity menu`, `calibration`, `ritual`), `steer` (in the workspace) for
  the `me-` intentions.

## What the operator actually does with it

- **Morning**: read the ritual's notification; adopt, shrink, or swap its 1–3
  proposals (`sinnix-steer intent add "…" --forecast 0.7`).
- **During the day**: nothing. It will not contact you.
- **Evening**: resolve the day (`sinnix-steer intent done|miss <id>`), read
  the review.
- **Occasionally**: `sinnix-steer calibration` to see whether 70% means 70%;
  `steer ready` for the standing intentions when actually in a state matching
  their label.

## The boundary between the two trackers

| holds                                | tracker                   |
| ------------------------------------ | ------------------------- |
| technical work an agent can execute  | sinnix beads (`sinnix-*`) |
| intentions only the operator settles | steering beads (`me-*`)   |

One subject can legitimately exist in both at different altitudes: `me-z2l`
is the intention "reshape the browser"; its mechanical configuration is
sinnix work. When in doubt: if an agent could finish it, it is not a `me-`
item.

## Status, honestly

The design intent above is genuinely recorded (it is not a reconstructed
rationale), but two things should be said plainly. The personal-context
rationale beyond the self-model summary was deliberately kept out of public
carriers, so this page cites the mechanism-level reasons only. And whether
the wider program continues is an open question the operator paused on
2026-08-17, to be decided while looking at epic `sinnix-jfiy` and its seven
sub-programs rather than at a directory listing. The parts already judged
worth keeping regardless: the `state:` vocabulary and the never-nag surfacing
contract.
