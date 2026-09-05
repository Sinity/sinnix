---
name: rank-options
description: Order several generated options by real operator preference — brainstorm shortlists, design alternatives, candidate plans — with a few pairwise comparisons, a fitted order, and a resumable domain.
---

# Rank options

You produced N options and need the operator's order, not your guess. Register
the options as items in a ranking domain, run a bounded comparison pass, and
report the fitted order together with what the evidence does and does not
support.

The engine, the store and the fit are shipped: `sinnix-rank` over
`rank_core`. Never implement a scoring scheme, a tie-break heuristic, or a
second comparison log inside this workflow.

## Route

Use this when several options exist and the choice between them is the
operator's to make: brainstorm output, design alternatives, portfolio entries,
candidate names, competing plans. Do not use it to rank work the tracker
already orders (`bd ready`), or to decide something you can settle from
evidence.

## The four commands

```bash
sinnix-rank add <domain> --items options.jsonl   # register, once per option
sinnix-rank next <domain> --json                 # which pair to ask about
sinnix-rank record <domain> --set A,B --winner A # one operator judgment
sinnix-rank status <domain> --json               # fitted order + evidence
```

State lives in `/realm/data/activity/ranking/<domain>/` (override the root
with `SINNIX_RANK_ROOT`). `items.jsonl` and `comparisons.jsonl` are
append-only; comparisons are never pruned, only tombstoned by
`sinnix-rank retract`.

## Registering options

One JSON object per line, `id` and `label` required; everything else is
carried through as metadata.

```jsonl
{"id": "opt-hub-page", "label": "Render the comparison as a hub page"}
{"id": "opt-phone-deck", "label": "Ship it as a phone drill deck"}
```

See [fixtures/options.example.jsonl](fixtures/options.example.jsonl).

Rules that are not optional:

- **Ids are stable and semantic.** `opt-hub-page`, not `1`. A positional id
  silently re-points at a different option the next time you generate a
  shortlist, and every comparison recorded against it becomes a lie.
- **Labels are what the operator reads.** Write the option, not a summary of
  your reasoning about it.
- **Private option text stays in the domain.** The domain directory is local
  state, not a tracked file. Never copy option text into a commit, a bead, a
  PR body, or a skill file.
- **Your own ranking is not evidence.** You may seed the item set and you may
  say what you would pick, but nothing you believe is ever written as a
  comparison. Only `record` calls answering an actual operator choice are.

## Running the pass

`next` returns a set chosen for information gain, not order of arrival; ask
the operator exactly that question, then `record` the answer with the id they
chose. Ten comparisons over six options is a normal pass; stop when `status`
reports `evidence.settled`, or when the operator is done.

```bash
sinnix-rank next design-directions --json
# ask: "Which do you want more: the hub page, or the phone deck?"
sinnix-rank record design-directions --set opt-hub-page,opt-phone-deck \
    --winner opt-phone-deck --context "2026-09-05 shortlist pass"
```

`--context` is free text carried on the comparison; use it to name the pass so
a later refit can tell one sitting from another.

## Reading the result

`status --json` returns the fitted order plus an `evidence` block. Report both.

| Field                | Meaning                                                   |
| -------------------- | --------------------------------------------------------- |
| `items[].theta`      | fitted strength, higher is preferred                      |
| `items[].se`         | standard error; a large one means the order is guesswork  |
| `items[].component`  | connected comparison component                            |
| `stability.p_stable` | fraction of posterior samples whose top-k is the same set |
| `evidence.settled`   | whether the order is supported at all                     |
| `evidence.reasons`   | why it is not, when it is not                             |

**Never present an unsettled fit as a decision.** If `evidence.settled` is
false, say the order is provisional and name the reason from
`evidence.reasons` — then either ask another comparison or hand the operator
the shortlist.

## The five situations this skill exists to define

**Duplicate labels.** `add` refuses two options that read the same, because
the operator's answer to a prompt showing two identical lines cannot be
attributed afterwards. Disambiguate the label. `--allow-duplicate-labels`
exists for genuinely-identical items whose distinction is in metadata; using
it because the error was in the way is a bug you are about to record as data.

**Changed option sets.** Re-running `add` with the same ids and labels is a
no-op, so resuming is free. Re-running with the _same id and a different
label_ is refused: that is a different option wearing an old identity. Give
the new option a new id — `opt-hub-page-v2` — and the comparisons already
recorded against `opt-hub-page` keep meaning what they meant. `--revise` is
only for fixing the wording of an option that did not change.

**Disconnected evidence.** If comparisons split the options into groups that
were never compared with each other, `evidence.connected` is false and
`components` is greater than one. Items in different components have thetas
anchored only to the model's virtual tie; ordering across them is not a
result. `next` deliberately schedules cross-component comparisons, so the fix
is to keep going, not to reinterpret the numbers.

**Interruption.** The store is append-only, so a pass that stops mid-way loses
nothing. To resume, run `add` again with the same domain and the same ids (a
no-op that confirms the roster), then `next`. Always name the exact domain in
your report — it is the only handle the next session has.

**Insufficient evidence.** Zero comparisons still produce a total order: every
theta is zero and the sort is arbitrary. `evidence.operator_comparisons` and
`evidence.unjudged_items` are how you tell. An option nobody compared is
unranked, not last.

## What to report back

The domain name, the fitted order with theta and se, `stability.p_stable`,
`evidence.settled` with its reasons, and the exact command to resume:

```bash
sinnix-rank status <domain> --json
```
