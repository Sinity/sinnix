# Preference ranking

One engine, one tool. Anything the operator can compare two of — backlog
items, wallpapers, generated options, activities — is ranked by the same
Plackett-Luce fit, selected by the same selector, over an append-only
comparison log, through `sinnix-rank`.

## The engine

`pkgs/sinnix-rank-core` (`rank_core`) is importable and renders nothing:

- `store` — one directory per domain: `items.jsonl` (append-only registry,
  last write per id wins) and `comparisons.jsonl` (append-only, deleted only
  by a tombstone record, so undo and audit stay possible). `read_log` replays
  any such log — the live records, every id it has ever carried, and the
  tombstoned ones — and `append_log` writes one entry to it;
- `fit` — Plackett-Luce top-1 MM with virtual-tie anchors, returning theta,
  standard error, comparison count, and connected component per item. A pair
  is the size-2 case of a choice set, so there is one code path; a pair with
  no winner is a tie, fitted as two half-weight records;
- `stopping` — `top_k_stability`: sample theta from its posterior repeatedly
  and report how often the top-k set comes out the same;
- `selection` — which set to present next: uncertainty anchor plus a
  rank-window companion, periodic random exploration, recency exclusion, no
  re-asking of a set already put to the operator, and cross-component bridging
  on the first pick of a disconnected domain. Every surface enters through
  `build_selector(item_ids, comparisons, fit)`, so one domain state has one
  next question whichever surface asks it;
- `draw` — which item to hand over now: `top`, `softmax`, or Thompson
  sampling (the default).

Domains live at `/realm/activity/shared/ranking/<domain>/`
(`SINNIX_RANK_ROOT` moves the root for fixtures). Comparisons are never pruned
and the fit is recomputed from them on every read; no fit is stored. A missing
domain is new; unreadable or malformed files are errors.

The registered items are the domain's roster. A comparison naming an id that
is not registered stays in the log but is left out of the fit: the member is
dropped from its set, and a set left with fewer than two members, or without
its winner, carries no evidence.

## `sinnix-rank`

Domain names are paths under the ranking root (nested domains are fine);
anything resolving outside it is refused.

```bash
sinnix rank add <domain> --items items.jsonl   # register options
sinnix rank compare <domain> --rounds 20       # the operator's own loop
sinnix rank next <domain> --json               # one set, no TTY
sinnix rank record <domain> --set A,B --winner A   # or --tie
sinnix rank retract <domain> --comparison <id>
sinnix rank status <domain> --json             # order + evidence
sinnix rank spin <domain>                      # draw one
sinnix rank list                               # every domain
```

`next`/`record` exist for agents, which hold the conversation instead of a
terminal; `compare` is the interactive loop.

`add` takes a JSON array or JSONL of `{id, label, ...}`; every other field
(`image`, `description`, `features`) is kept on the item. It refuses to reuse
an id with a different label (`--revise` relabels the same option) and
refuses two options with the same label (`--allow-duplicate-labels`
overrides).

`status --json` carries an `evidence` block — comparison counts, connected
components, items with no comparisons, the stopping threshold, and
`settled` with the reasons it is not. A total order always exists; whether it
means anything is what `evidence` answers.

### Image domains

```bash
sinnix rank add wallpaper --items items.json --image-features
sinnix rank serve wallpaper --open           # side-by-side page on this machine
sinnix rank session wallpaper -n 20          # page on the hub, tap from the phone
sinnix rank explain wallpaper                # which features the choices track
```

`--image-features` fills each new image item's `features` from
`sinnix-image-features`. `explain` regresses standardised feature deltas on
the operator's pair choices and correlates each feature with the fitted
theta, which is a question about the items rather than about the ranking.

`session` renders a fixed pair list into `/realm/report/rank/<domain>/`, served
by the hub. Each tap posts a `sinnix-rank-v1` judgment to the hub's
`/feedback` spool, and its arrival runs `sinnix rank ingest` through the
`rank_ingest` operation. `ingest` appends a judgment only if its domain's log
has never carried that id, tombstoned ones included, and only if it names
registered items.

`serve` runs the same judgment against a live process on this machine: two
images filling the screen, one keypress each (left/right pick, `d` draw, `s`
skip, `u` undo, `q` quit), a refit after every answer, and the next pair
chosen from what the operator just said. It ranks a 126-image roster in one
sitting. The status bar shows comparison count, items seen, component count
and `top_k_stability` for the top ten, which answers "am I done". `u` adds a
tombstone instead of rewriting the log. The port is ephemeral and printed
(`--open` opens it); only image paths registered on items are served.

## `rank-options` skill

`dots/_ai/skills/rank-options` routes agent-generated shortlists through the
CLI above: register options with stable semantic ids, run a bounded pass,
report the fitted order with its uncertainty and the domain needed to resume.
Agent-generated suggestions may seed the item set; they are never recorded as
comparisons.
