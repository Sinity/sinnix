---
name: enrichment-pass
description: >
  Process a state bundle (runtime inventory, steering export, atuin tail,
  polylogue hook-spool deltas, session JSONL deltas, lynchpin products,
  journald highlights) into a versioned narrative + structured state delta.
  Invoked headlessly by sinnix-enrich-dump (sinnix-jfiy.2) via `claude -p`;
  not interactive.
metadata:
  short-description: Enrichment-loop bundle -> narrative + state-delta
---

# Enrichment pass

You are given a directory of raw evidence files (a "bundle") assembled by
`scripts/sinnix-enrich-dump` and asked to produce exactly two outputs. This is
a non-interactive, single-shot invocation — there is no follow-up turn.

## Input

The bundle directory (passed as your working context / first argument) contains
a subset of these files, only some of which may be present or non-empty on any
given run — a file being empty or absent just means nothing changed in that
source since the last run (the watermark), not that the source is broken:

- `runtime-inventory.json` — current `/etc/sinnix/runtime-inventory.json`
- `steering-export.jsonl` — `bd export` of the steering workspace
- `atuin-tail.txt` — shell history, last 24h
- `polylogue-hooks.jsonl` — polylogue hook-spool deltas since the watermark
- `session-deltas/*.jsonl` — raw Claude/Codex session JSONL deltas since the watermark
- `lynchpin-current-state.json` — lynchpin's current-state product, if fresh (<24h)
- `journald-warnings.txt` — `journalctl -p warning` since the watermark, capped

## Output (exactly these two files, written to the bundle directory)

1. **`narrative.md`** — a short, plain-prose "since you last looked" summary.
   Cover: what agent sessions did (from session-deltas), what shell/dev activity
   happened (atuin), anything the runtime inventory flags as unhealthy, anything
   in journald warnings worth a human's attention. Skip sections with no signal
   rather than padding. Terse — this is a briefing, not a report.

2. **`state-delta.json`** — strict JSON matching schema `sinnix-enrichment-v1`:

   ```json
   {
     "schema": "sinnix-enrichment-v1",
     "generated_at": "<ISO-8601 UTC>",
     "window": { "from": "<ISO-8601 or null>", "to": "<ISO-8601>" },
     "inputs": [
       { "source": "atuin-tail", "path": "atuin-tail.txt", "items": 42 }
     ],
     "narrative_ref": "narrative.md",
     "flags": [
       {
         "kind": "unhealthy-surface",
         "severity": "warning",
         "ref": "runtime-inventory.json#/surfaces/foo",
         "summary": "One sentence: what is wrong and why it matters."
       }
     ]
   }
   ```

   `inputs[]` MUST list every bundle file you actually read, with a rough
   item count (lines for jsonl/txt, top-level array length for json — use your
   best judgment, this is for provenance not precision). `flags[]` is your
   judgment call on anything the operator should see in a steering review
   (a failed/degraded runtime surface, a repeated error pattern in journald,
   an open commitment that looks stale) — empty array is a valid, honest
   output when nothing stands out.

   `severity` MUST be one of `info`, `warning`, `error`, `critical`.
   `summary` is REQUIRED: one sentence, specific enough to act on.

### `kind` is a closed vocabulary

`kind` MUST be exactly one of the values below. Do not coin new ones, do not
pluralise, do not add qualifiers — pick the closest match and put the nuance in
`summary`. If genuinely nothing fits, use `other`.

| kind                       | use for                                                  |
| -------------------------- | -------------------------------------------------------- |
| `unhealthy-surface`        | a runtime surface reporting degraded/down                |
| `failed-unit`              | a systemd unit in a failed state                         |
| `service-churn`            | restart loops, crash loops, flapping                     |
| `invalid-unit-config`      | a unit file systemd rejects or warns about               |
| `journal-storm`            | one message repeated enough to crowd the log             |
| `repeated-error-pattern`   | a recurring error that is not a single-message flood     |
| `resource-pressure`        | memory/disk/IO pressure, OOM kills, capacity limits      |
| `filesystem-fault`         | read-only remounts, corruption, mount failures           |
| `capture-gap`              | a capture lane stale, thin, truncated, or losing records |
| `backup-fault`             | a backup or verification job failing                     |
| `data-loss`                | records confirmed dropped or unrecoverable               |
| `open-commitment`          | a tracked intention that looks stale or unmet            |
| `unverified-change`        | a change landed but not yet exercised by its real path   |
| `operator-action-required` | needs a human: credentials, consent, a decision          |
| `bundle-incomplete`        | an input was absent, unreadable, or only partly read     |
| `self-degraded`            | this pass itself was impaired (tool failure, truncation) |
| `other`                    | nothing above fits; explain fully in `summary`           |

Why this is closed: across the first 27 passes an open `kind` field produced 96
distinct values, including seven separate spellings of "the journal is flooded"
(`journal-storm`, `journal-flood`, `log-spam`, `log-flood`, `journald-noise`,
`journal-warning-flood`, `log-flooded-by-single-warning`). Free-text kinds make
the flags unaggregatable across runs, which defeats the point of emitting
structured output alongside the prose.

## Invariants (do not violate)

- **Read-only on every input.** Never write to polylogue's or sinex's stores,
  never write anywhere except the two output files named above in the bundle
  directory you were given.
- **Failure is not silence.** If you cannot produce a valid output (e.g. the
  bundle is empty, or you're asked to process something malformed), still
  write `state-delta.json` with your best-effort `inputs`/`flags`, and note
  the problem in `narrative.md` rather than producing nothing. (The dump
  script itself has a separate hard failure-marker path for when the `claude
-p` invocation fails entirely — this invariant is about _your_ output being
  honest when you _do_ run, not a duplicate of that mechanism.)
