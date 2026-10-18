# Preference ranking

One engine, thin frontends. Anything the operator can compare two of — backlog
items, wallpapers, keybindings, generated options, activities — is ranked by the
same Plackett-Luce fit, selected by the same selector, over an append-only
comparison log.

Two store formats exist. `sinnix-rank` domains hold choice-set records and
never store a fit; `sinnix-elicit` domains hold pairwise records, an
`items.json` roster, and a cached fit (`model.json`). Unifying them is tracked
as `sinnix-z8iq.14`; a domain keeps the format of the tool that created it.

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

`sinnix-rank` domains live at `/realm/activity/shared/ranking/<domain>/`
(`SINNIX_RANK_ROOT` moves the root for fixtures). Comparisons are never pruned
and the fit is recomputed from them on every read. A missing domain is new;
unreadable or malformed files are errors.

## `sinnix-rank`

The text frontend. Domain names are paths under the ranking root (nested
domains are fine); anything resolving outside it is refused.

```bash
sinnix rank add <domain> --items items.jsonl   # register options
sinnix rank compare <domain> --rounds 20       # the operator's own loop
sinnix rank next <domain> --json               # one set, no TTY
sinnix rank record <domain> --set A,B --winner A
sinnix rank retract <domain> --comparison <id>
sinnix rank status <domain> --json             # order + evidence
sinnix rank spin <domain> --commit             # draw one, into steering
```

`next`/`record` exist for agents, which hold the conversation instead of a
terminal; `compare` is the interactive loop.

`add` refuses to reuse an id with a different label (`--revise` relabels the
same option) and refuses two options with the same label
(`--allow-duplicate-labels` overrides).

`status --json` carries an `evidence` block — comparison counts, connected
components, items with no comparisons, the stopping threshold, and
`settled` with the reasons it is not. A total order always exists; whether it
means anything is what `evidence` answers.

## Steering's activity menu

`sinnix-steer activity menu` orders the activity registry by the fit over
the `steering-activities` domain. The energy filter only chooses what is shown,
not the order. With no comparisons recorded the registry's own order is used,
and the CLI says so.

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

A domain is `items.json` (an editable JSON array), `comparisons.jsonl`
(`{a, b, outcome}` records) and `model.json`, the cached fit that the hub
serves mid-session at `GET /feedback/elicit/<domain>`. Domains live at
`/realm/state/elicit/<domain>` (`SINNIX_ELICIT_DIR` for fixtures), with the
same path confinement as `sinnix-rank`.

A tap posts to the hub's `/feedback` spool; `sinnix-elicit autoingest` moves
it into the domain, skipping any comparison id the domain has ever seen
(including undone ones). The cached fit stores a digest of the roster and
comparisons and is rebuilt whenever that digest changes.

### `serve`

`session` renders a fixed pair list, so nothing refits between taps. `serve`
runs the same judgment against a live process on this machine: two images
filling the screen, one keypress each (left/right pick, `d` draw, `s` skip,
`u` undo, `q` quit), a refit after every answer, and the next pair chosen from
what the operator just said. It ranks a 126-image roster in one sitting.

It picks pairs with `rank_core.Selector`, which links unconnected items so
the whole roster ends up on one scale. The status bar shows comparison count,
items seen, component count and `top_k_stability` for the top ten, which
answers "am I done". `u` adds a tombstone instead of rewriting the log. The
port is ephemeral and printed (`--open` opens it); only image paths declared in
`items.json` are served.

## `rank-options` skill

`dots/_ai/skills/rank-options` routes agent-generated shortlists through the
CLI above: register options with stable semantic ids, run a bounded pass,
report the fitted order with its uncertainty and the domain needed to resume.
Agent-generated suggestions may seed the item set; they are never recorded as
comparisons.

## `sinnix-rank-keybinds`

Ranks the currently bound Hyprland chords for practice.

```bash
sinnix rank-keybinds inventory                 # what is bound right now
sinnix rank-keybinds sync                      # register them as items
sinnix rank compare keybinds                   # operator comparisons
sinnix rank-keybinds usage --source atuin      # bounded, labelled prior
sinnix rank-keybinds manifest --output /realm/activity/desktop/keyboard/keybinds/manifest.json
sinnix-deck-forge keybinds                     # a phone recall deck
```

The inventory is the Lua Home Manager renders from
`modules/features/desktop/hyprland/bindings.nix`
(`$XDG_CONFIG_HOME/hypr/sinnix-startup.lua`, defaulting to
`~/.config/hypr/sinnix-startup.lua`, or `--inventory`). The main
`hyprland.lua` loads this module; its reload callback installs the bindings.
Nothing here writes to that
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
