# Preference ranking

One engine, one store convention, thin frontends. Anything the operator can
compare two of — backlog items, wallpapers, keybindings, generated options,
activities — is ranked by the same Plackett-Luce fit over the same append-only
comparison log.

## The engine

`pkgs/sinnix-rank-core` (`rank_core`) is importable and renders nothing:

- `store` — one directory per domain: `items.jsonl` (append-only registry,
  last write per id wins) and `comparisons.jsonl` (append-only, deleted only
  by a tombstone record, so undo and audit stay possible);
- `fit` — Plackett-Luce top-1 MM with virtual-tie anchors, returning theta,
  standard error, comparison count, and connected component per item. A pair
  is the size-2 case of a choice set, so there is one code path;
- `stopping` — `top_k_stability`: sample theta from its posterior repeatedly
  and report how often the top-k set comes out the same;
- `selection` — which set to present next: uncertainty anchor plus a
  rank-window companion, periodic random exploration, recency exclusion, and
  deliberate cross-component bridging;
- `draw` — which item to hand over now: `top`, `softmax`, or Thompson
  sampling (the default).

Raw comparisons live at `/realm/data/activity/ranking/<domain>/` and are never
pruned. Fits are always recomputed from them, never cached back into the
domain directory. `SINNIX_RANK_ROOT` moves the root for fixtures.

## `sinnix-rank`

The text frontend for any domain.

```bash
sinnix-rank add <domain> --items items.jsonl   # register options
sinnix-rank compare <domain> --rounds 20       # the operator's own loop
sinnix-rank next <domain> --json               # one set, no TTY
sinnix-rank record <domain> --set A,B --winner A
sinnix-rank retract <domain> --comparison <id>
sinnix-rank status <domain> --json             # order + evidence
sinnix-rank spin <domain> --commit             # draw one, into steering
```

`next`/`record` exist for agents, which hold the conversation instead of a
terminal; `compare` is the interactive loop.

`add` refuses silent identity reuse. An id already carrying a different label
is a changed option, not an update (`--revise` to relabel the same one); two
options that read the same cannot be attributed after the operator answers
(`--allow-duplicate-labels` to override).

`status --json` carries an `evidence` block — comparison counts, connected
components, items with no comparisons, the stopping threshold, and
`settled` with the reasons it is not. A total order always exists; whether it
means anything is what `evidence` answers.

## Steering's activity menu

`sinnix-steer activity menu` and both rituals order the activity registry by
the fit over the `steering-activities` domain, so the morning shortlist is the
head of the operator's own preference order at the energy tier he states. The
fit runs over the whole registry, so the energy filter chooses what is shown
and never what it is worth. With no comparisons recorded the order is the
registry's own and the CLI says so.

## `sinnix-elicit`

The image and phone-session frontend: a domain is a roster of items with
optional images, descriptions, and feature vectors, compared by tapping
through a generated HTML page served by the hub.

```bash
sinnix elicit init wallpaper --items items.json --image-features
sinnix elicit session wallpaper -n 20        # page on the hub, tap from the phone
sinnix elicit ask wallpaper                  # terminal loop
sinnix elicit rank wallpaper                 # fitted order + `explain`
sinnix elicit explain wallpaper              # which features the choices track
```

It fits through `rank_core` and owns only its own surfaces. Two things it does
that the engine does not:

- a record naming an id that is not in `items.json` is dropped, where the
  engine would fit a comparison-only id. The roster is the operator's declared
  item set, so a stale id is evidence about something deleted;
- `explain` regresses standardised feature deltas on the operator's choices,
  which is a question about the items rather than about the ranking.

Its domain format is its own: `items.json` (a JSON array, editable),
`comparisons.jsonl` with `{a, b, outcome}` pairwise records, and `model.json`,
the one cached fit in the estate — the hub serves it back mid-session at
`GET /feedback/elicit/<domain>`. State lives at `/realm/data/notes/preferences/<domain>`;
`SINNIX_ELICIT_DIR` moves the root for fixtures.

A tap posts to the hub's `/feedback` spool and `sinnix-elicit autoingest`
drains it into the domain, coalesced per burst. The drain dedups against every
comparison id the log has ever carried, tombstones included: a record the
operator undid is still one this domain has seen.

## `rank-options` skill

`dots/_ai/skills/rank-options` routes agent-generated shortlists through the
CLI above: register options with stable semantic ids, run a bounded pass,
report the fitted order with its uncertainty and the domain needed to resume.
Agent-generated suggestions may seed the item set; they are never recorded as
comparisons.

## `sinnix-rank-keybinds`

Ranks the currently bound Hyprland chords for practice.

```bash
sinnix-rank-keybinds inventory                 # what is bound right now
sinnix-rank-keybinds sync                      # register them as items
sinnix-rank compare keybinds                   # operator comparisons
sinnix-rank-keybinds usage --source atuin      # bounded, labelled prior
sinnix-rank-keybinds manifest --output /realm/data/derived/keybinds/manifest.json
sinnix-deck-forge keybinds                     # a phone recall deck
```

The inventory is the Lua Home Manager renders from
`modules/features/desktop/hyprland/bindings.nix`
(`~/.config/hypr/hyprland.lua`, or `--inventory`). Nothing here writes to that
module or to the compositor.

Identity is the chord plus the intent, hashed. Not the action: it carries
`/nix/store` paths that move on unrelated rebuilds, and a rebuild must not
orphan a binding's comparison history. Re-chording a binding, or changing what
it is for, is a different binding.

Three inputs stay separate and stay labelled:

| Input                | Where it lives                               | Weight                                                       |
| -------------------- | -------------------------------------------- | ------------------------------------------------------------ |
| operator comparisons | `comparisons.jsonl` in the shared store      | full once a binding has `evidence_threshold` (4) comparisons |
| usage prior          | `usage-prior.json` beside it, never mixed in | bounded to ±1.0 theta, faded out as comparisons arrive       |
| uncertainty          | the fit's standard error                     | `uncertainty_weight` (0.5) of it, added to priority          |

Missing usage is unknown, not zero. A compositor dispatch leaves no shell
trace, and scoring that silence as "never used" would bury exactly the
bindings worth drilling; such records are `state: "unavailable"` with a
reason, while a real zero count is `state: "measured", count: 0`. Every
manifest row carries its `provenance.basis` — `comparisons`, `blend`,
`usage-prior`, or `unmeasured`.

The manifest contains only bindings present in the current inventory. Ranking
state for a retired binding stays on disk, and stays out of the manifest.
`sinnix-deck-forge keybinds` takes its drill order from the manifest verbatim,
so the only way to change what gets drilled is to change the ranking.
