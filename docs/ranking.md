# Preference ranking

One engine, thin frontends. Anything the operator can compare two of — backlog
items, wallpapers, keybindings, generated options, activities — is ranked by the
same Plackett-Luce fit, selected by the same selector, over an append-only
comparison log.

Two store formats exist. `sinnix-rank` writes choice-set records and caches no
fit; `sinnix-elicit` writes pairwise records, an `items.json` roster and the one
cached fit. Unifying them is a migration over live domains and is tracked as
`sinnix-z8iq.14`; until it happens, the format a domain uses is the format of
the tool that created it.

## The engine

`pkgs/sinnix-rank-core` (`rank_core`) is importable and renders nothing:

- `store` — one directory per domain: `items.jsonl` (append-only registry,
  last write per id wins) and `comparisons.jsonl` (append-only, deleted only
  by a tombstone record, so undo and audit stay possible). `read_log` replays
  any such log — the live records, every id it has ever carried, and the
  tombstoned ones — and `append_log` writes one entry to it;
- `fit` — Plackett-Luce top-1 MM with virtual-tie anchors, returning theta,
  standard error, comparison count, and connected component per item. A pair
  is the size-2 case of a choice set, so there is one code path;
- `stopping` — `top_k_stability`: sample theta from its posterior repeatedly
  and report how often the top-k set comes out the same;
- `selection` — which set to present next: uncertainty anchor plus a
  rank-window companion, periodic random exploration, recency exclusion, no
  re-asking of a set already put to the operator, and cross-component bridging
  on the first pick of a disconnected domain. Every frontend enters through
  `build_selector(item_ids, comparisons, fit)`, so one domain state has one
  next question whichever surface asks it;
- `draw` — which item to hand over now: `top`, `softmax`, or Thompson
  sampling (the default).

Raw comparisons live at `/realm/activity/ranking/<domain>/` and are never
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
sinnix elicit serve wallpaper --open         # side-by-side page on this machine
sinnix elicit session wallpaper -n 20        # page on the hub, tap from the phone
sinnix elicit ask wallpaper                  # terminal loop
sinnix elicit rank wallpaper                 # fitted order + `explain`
sinnix elicit explain wallpaper              # which features the choices track
```

It fits, selects and replays its log through `rank_core`, and owns only its own
surfaces: `ask`, `session` and `pairs` ask the same next question `sinnix-rank
next` would. Two things it does that the engine does not:

- a record naming an id that is not in `items.json` is dropped, where the
  engine would fit a comparison-only id. The roster is the operator's declared
  item set, so a stale id is evidence about something deleted;
- `explain` regresses standardised feature deltas on the operator's choices,
  which is a question about the items rather than about the ranking.

Its domain format is its own: `items.json` (a JSON array, editable),
`comparisons.jsonl` with `{a, b, outcome}` pairwise records, and `model.json`,
the one cached fit in the estate — the hub serves it back mid-session at
`GET /feedback/elicit/<domain>`. State lives at `/realm/state/elicit/<domain>` --
mutable application state, in the state root, not in the prose tree;
`SINNIX_ELICIT_DIR` moves the root for fixtures. `sinnix-elicit-migrate` moves
domains there from the retired root: it refuses to run while the drain unit is
active, moves each domain by rename, and re-checks every file's size and
sha256 at the destination.

A tap posts to the hub's `/feedback` spool and `sinnix-elicit autoingest`
drains it into the domain, coalesced per burst. The drain dedups against every
comparison id the log has ever carried, tombstones included: a record the
operator undid is still one this domain has seen.

### `serve`

`session` renders a fixed pair list, so nothing refits between taps. `serve`
runs the same judgment against a live process on this machine: two images
filling the screen, one keypress each (left/right pick, `d` draw, `s` skip,
`u` undo, `q` quit), a refit after every answer, and the next pair chosen from
what the operator just said. It ranks a 126-image roster in one sitting.

It selects through `rank_core.Selector`, not this file's `pick_pairs`: a cold
roster is one connected component per item, and only the Selector deliberately
bridges components, without which thetas across the roster stay mutually
meaningless however long the operator clicks. The status bar carries the
evidence — comparison count, items seen, component count, and
`top_k_stability` for the top ten, which is the answer to "am I done".

Every judgment is appended to the domain's own log through the same store as
every other surface, and `u` tombstones rather than rewriting. The server
re-reads the log's full id set before each append, tombstones included, so a
retried POST and a record the hub drain landed concurrently are both
recognised as already seen.

The port is ephemeral by default and the URL is printed: this is an
operator-run foreground process, not a declared service, so it claims no
number from `flake/data/ports.nix`. `--open` follows the URL with `xdg-open`.
Images are read only from the paths `items.json` declares; a request naming
anything else is a 404. Both the roster's image paths and the comparisons stay
in local state.

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
sinnix-rank-keybinds manifest --output /realm/activity/keylog/keybinds/manifest.json
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
