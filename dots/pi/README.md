# Sinnix pi package

Loaded by pi as a local package (`modules/features/dev/agents/pi.nix` lists it
in pi's settings). Pi runs the TypeScript directly, so an edit is live after
`/reload`.

| File                         | What it adds                                                                                                     |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `extensions/guard.ts`        | Runs every `bash` tool call through `dots/claude/hooks/pretooluse-bash.py`, the guard Claude Code and Codex use. |
| `extensions/ask.ts`          | `ask_operator`: the model asks one question in a fixed shape and gets the answer back as data.                   |
| `extensions/compare.ts`      | `/compare <domain>` and `rank_options`: pairwise comparison over `sinnix-rank`.                                  |
| `extensions/presets.ts`      | `--preset <name>` and `/preset`: named modes read from `presets/`.                                               |
| `extensions/plan-billing.ts` | Stops a Claude Code turn that was charged to usage credits instead of the plan.                                  |

## Front ends

Every interaction has two forms. In the terminal it is a component that takes
one key per answer. Anywhere else that can show a dialog (`pi --mode rpc`
clients) it falls back to pi's `select` and `input` dialogs, which every front
end implements. New interactions go through `lib/choice.ts` so they keep both.

## Presets

A preset is `presets/<name>.json` plus the instruction file it names:

```json
{
  "description": "One line for the /preset list",
  "instructions": "name.md",
  "tools": ["read", "ask_operator"],
  "model": "provider/model-id",
  "thinking": "medium"
}
```

`model` and `thinking` are optional. While a preset is active the model gets
the preset's instructions, only the listed tools, and not the global
instruction file from the agent directory; project instruction files still
load. Adding a preset is adding those two files.

## Comparison displays

`lib/item-display.ts` holds a list of displays; the first whose `applies`
accepts an item renders it. Today: files (an item whose metadata has `path`)
and plain text. A new kind of item is one more entry in that list.

## Tests

`tests/run.mjs` loads the extensions against a stand-in for pi's API and
exercises the guard, the question tool, the comparison loop and the presets.
`flake/tests/pi.nix` runs it against the pinned pi.

## Neutral questions and non-coding modes

`ask_operator` requires `question`. Optional `why`, `recommendation`, `choices`
and `recommended` add decision support; omit recommendation for neutral
elicitation and omit choices for a direct text answer. With choices, another
text answer and dismissal remain available. RPC receives the same consequences
as the terminal. Dismissal never accepts a default and typed text is not rewritten.

- `pi --preset inquire`: personal reflection and worldview inquiry; read tools
  and questions, no automatic profile or task publication.
- `pi --preset explore`: open-ended thought and making, without requiring a
  therapeutic or productivity purpose; ordinary file/shell tools available.
- `pi --preset learn`: concrete tutoring, references and checked scratch
  exercises; file/shell tools available.
- `pi --preset questions`: structured decisions and operator-authored rankings.
  Ranking writes options and comparisons to its own store.

Use `/preset <name>` to switch or `/preset off` to return to general work.
These modes change instructions and model-callable tools, not OS permissions,
commands, extension authority, billing or session recording. They are not a
sandbox. Project AGENTS.md still loads. Sessions persist in Pi's normal store;
keep private conversations out of public repositories and published reports.
The local package is live: a new session or `/reload` picks up source changes;
no npm install, system activation or provider request is needed for this edit.
