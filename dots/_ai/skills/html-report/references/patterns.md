# Interactivity & layout patterns (paste-in snippets)

All snippets assume the template's CSS variables/classes. Everything inline,
no external requests, JS-optional where possible.

## Tabs (CSS-only, radio-based — survives JS-off)

```html
<div class="tabs">
  <input type="radio" name="tg1" id="ta" checked /><label for="ta"
    >Before</label
  >
  <input type="radio" name="tg1" id="tb" /><label for="tb">After</label>
  <div class="pane pa"><!-- before content --></div>
  <div class="pane pb"><!-- after content --></div>
</div>
<style>
  .tabs input {
    display: none;
  }
  .tabs label {
    display: inline-block;
    padding: 0.25rem 0.8rem;
    border: 1px solid var(--line);
    border-bottom: none;
    border-radius: 0.4rem 0.4rem 0 0;
    cursor: pointer;
    color: var(--muted);
  }
  .tabs input:checked + label {
    background: var(--panel);
    color: var(--ink);
    font-weight: 600;
  }
  .tabs .pane {
    display: none;
    border: 1px solid var(--line);
    padding: 0.8rem;
    border-radius: 0 0.4rem 0.4rem 0.4rem;
  }
  #ta:checked ~ .pa,
  #tb:checked ~ .pb {
    display: block;
  }
</style>
```

## Timeline (incidents, campaign history)

```html
<ol class="tl">
  <li>
    <time>2026-07-10</time><b>Runtime stopped</b> — during reorg night; never
    restarted.
  </li>
  <li>
    <time>2026-07-21</time><b>Campaign "COMPLETE"</b> — prematurely declared.
  </li>
</ol>
<style>
  .tl {
    list-style: none;
    margin: 0;
    padding: 0 0 0 1.1rem;
    border-left: 2px solid var(--line);
  }
  .tl li {
    margin: 0.55rem 0;
    position: relative;
    padding-left: 0.8rem;
  }
  .tl li::before {
    content: "";
    position: absolute;
    left: -1.45rem;
    top: 0.35rem;
    width: 0.55rem;
    height: 0.55rem;
    border-radius: 50%;
    background: var(--accent);
  }
  .tl time {
    color: var(--muted);
    font-size: 0.8rem;
    margin-right: 0.5rem;
  }
</style>
```

## Correction ladder (claim → challenge → reversal, kept visible)

For a report whose whole point is _how a conclusion moved_ (a debugging
session, a review thread, a multi-pass investigation) — a vertical sequence
of rungs, each one **narration you wrote** optionally followed by **a quote
someone actually said**, never merged into one box. Narration is a plain
`<p>`; only the `<blockquote class="q">` gets the quote treatment (see
"Quotes vs. narration" above the crib in the template). Reuse the badge
classes for stage labels.

```html
<ol class="ladder">
  <li class="claim">
    <p class="who">assistant <span class="stage stage-claim">claim</span></p>
    <blockquote class="q">
      DOM should either get stable ids or be retired for providers with a
      working native path.<cite>assistant</cite>
    </blockquote>
  </li>
  <li class="challenge">
    <p class="who">operator <span class="stage stage-challenge">push</span></p>
    <blockquote class="q user">
      but do we actually want this fallback, or is it cargo culting?<cite
        >operator</cite
      >
    </blockquote>
  </li>
  <li class="reversal">
    <p class="who">
      assistant <span class="stage stage-reversal">reversal</span>
    </p>
    <p>
      Counts the archive: the fallback fired 17 times, and none of those
      sessions also has a native capture — it's the only surviving record for 24
      of them.
    </p>
    <blockquote class="q">
      That inverts my recommendation.<cite>assistant</cite>
    </blockquote>
  </li>
</ol>
<style>
  .ladder {
    list-style: none;
    margin: 0.6rem 0;
    padding: 0;
    border-left: 3px solid var(--line);
  }
  .ladder li {
    position: relative;
    padding: 0.55rem 0 0.55rem 1.3rem;
  }
  .ladder li::before {
    content: "";
    position: absolute;
    left: -0.62rem;
    top: 1.05rem;
    width: 0.7rem;
    height: 0.7rem;
    border-radius: 50%;
    background: var(--muted);
    border: 2px solid var(--panel);
  }
  .ladder li.claim::before {
    background: var(--info);
  }
  .ladder li.challenge::before {
    background: var(--todo);
  }
  .ladder li.reversal::before {
    background: var(--warn);
  }
  .ladder .who {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
    font-weight: 700;
    margin: 0 0 0.2rem;
  }
</style>
```

The narration paragraph is optional per rung (a bare claim/challenge/reversal
often needs nothing but the quote); the quote is optional too (a rung can be
pure narration, e.g. "assistant re-tests, finds X" with no direct words to
show). What must never happen is both living in the same box — that's the
"which part is the quote?" failure this pattern exists to prevent.

## Annotated diff / code callouts

```html
<pre class="diff"><code><span class="ctx">  join scenes_files sf</span>
<span class="del">-   and sf."primary" = 1   <i>← bash eats the quotes</i></span>
<span class="add">+   and sf.[primary] = 1   <i>← shell-safe bracket quoting</i></span></code></pre>
<style>
  .diff .del {
    display: block;
    background: var(--bad-bg);
  }
  .diff .add {
    display: block;
    background: var(--ok-bg);
  }
  .diff .ctx {
    display: block;
    color: var(--muted);
  }
  .diff i {
    float: right;
    color: var(--muted);
    font-size: 0.8em;
  }
</style>
```

## Inline SVG diagram (boxes + labeled arrows)

```html
<svg
  viewBox="0 0 460 120"
  role="img"
  aria-label="data flow"
  style="max-width:34rem"
>
  <defs>
    <marker
      id="ar"
      viewBox="0 0 10 10"
      refX="9"
      refY="5"
      markerWidth="6"
      markerHeight="6"
      orient="auto"
    >
      <path d="M0 0L10 5L0 10z" fill="currentColor" />
    </marker>
  </defs>
  <g fill="none" stroke="currentColor">
    <rect x="8" y="38" width="120" height="40" rx="8" />
    <rect x="180" y="38" width="120" height="40" rx="8" />
    <rect x="342" y="38" width="110" height="40" rx="8" />
    <path d="M128 58h48" marker-end="url(#ar)" />
    <path d="M300 58h38" marker-end="url(#ar)" />
  </g>
  <g font-size="12" text-anchor="middle" fill="currentColor">
    <text x="68" y="62">capture</text>
    <text x="240" y="62">archive</text>
    <text x="397" y="62">analysis</text>
    <text x="152" y="50" font-size="10">ingest</text>
    <text x="321" y="50" font-size="10">query</text>
  </g>
</svg>
```

`currentColor` inherits the theme ink — diagrams need no per-theme colors.

## Keyboard-navigable deck

```html
<div class="deck">
  <section class="slide on"><h2>One</h2></section>
  <section class="slide"><h2>Two</h2></section>
</div>
<style>
  .deck .slide {
    display: none;
    min-height: 60vh;
  }
  .deck .on {
    display: block;
  }
</style>
<script>
  let i = 0,
    S = document.querySelectorAll(".deck .slide");
  addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight" && i < S.length - 1)
      (S[i].classList.remove("on"), S[++i].classList.add("on"));
    if (e.key === "ArrowLeft" && i > 0)
      (S[i].classList.remove("on"), S[--i].classList.add("on"));
  });
</script>
```

## Copy button for paths/commands

```html
<button
  class="cp"
  data-t="/realm/some/path"
  onclick="navigator.clipboard.writeText(this.dataset.t);this.textContent='✓'"
>
  ⧉
</button>
<style>
  .cp {
    border: none;
    background: none;
    cursor: pointer;
    color: var(--muted);
  }
</style>
```

## Swatches / contact sheet (design tokens, image sets)

```html
<div class="sw"><i style="--c:#2563eb"></i><code>--accent #2563eb</code></div>
<style>
  .sw {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .sw i {
    width: 1.4rem;
    height: 1.4rem;
    border-radius: 0.3rem;
    background: var(--c);
    border: 1px solid var(--line);
  }
</style>
```

Contact sheets: CSS grid of `figure` cells, `data:` URI thumbnails, captions.

## Lead register (living workspace spine)

One row per lead, state as a badge, provenance as an id. Duds stay in the table
with their reason — that is the whole point. Filter box + sortable `th` come
free from the template.

```html
<input class="filter" placeholder="filter leads…" oninput="flt(this,'leads')" />
<div class="tablewrap">
  <table id="leads">
    <thead>
      <tr>
        <th>ID</th>
        <th>Lead</th>
        <th>State</th>
        <th data-v>Value</th>
        <th class="nosort">Evidence / why</th>
        <th>Tracker</th>
      </tr>
    </thead>
    <tbody>
      <tr data-state="open">
        <td><code>A3</code></td>
        <td>move repair.py to maintenance/</td>
        <td><span class="badge todo">open</span></td>
        <td data-v="2">med</td>
        <td>doctrine conflict, undecided in hotspots doc</td>
        <td><code>—</code></td>
      </tr>
      <tr data-state="dud">
        <td><code>A8</code></td>
        <td>render burden</td>
        <td><span class="badge info">dud</span></td>
        <td data-v="0">none</td>
        <td>all 17 targets derive from source; cannot go stale</td>
        <td><code>—</code></td>
      </tr>
    </tbody>
  </table>
</div>
```

Add quick state filters with plain buttons over `data-state` when the register
grows past ~20 rows:

```html
<button class="fs" onclick="st('')">all</button>
<button class="fs" onclick="st('open')">open only</button>
<script>
  function st(s) {
    document
      .querySelectorAll("#leads tbody tr")
      .forEach(
        (r) => (r.style.display = !s || r.dataset.state === s ? "" : "none"),
      );
  }
</script>
```

## Checklist table for decision queues

Use `.badge todo` → `.badge ok` cells; one row per decision, columns:
priority badge · decision · blocker/owner · evidence link. Sortable for free
via the template's table JS.

## Annotations, corrections & handback (operator input → paste back to agent)

A `file://` page has no backend — it cannot push an edit anywhere on its own.
Two techniques close the loop without breaking the one-file/zero-request
contract:

1. **Autosave to `localStorage`**, keyed by the page's own path, the same way
   the template already persists theme/font-size. Chromium treats each
   absolute `file://` path as a stable origin, so edits genuinely survive
   closing and reopening _that exact file_ — free durability, no agent
   involved. It does **not** get the data back to the agent; the agent can't
   read the browser's storage.
2. **A "copy for agent" button** that serializes every tagged field into one
   JSON blob, shown in a visible, pre-selected `<textarea>` and pushed to the
   clipboard. This is the actual bridge: the operator pastes that block into
   the chat. Show the textarea always (don't rely on the clipboard API alone)
   — it is the fallback when `navigator.clipboard` is blocked, and it doubles
   as visible confirmation that something was captured.

True realtime two-way sync (agent sees edits without a paste) needs either a
companion local server — which breaks the zero-external-request contract this
skill is built on — or Claude's Artifact runtime capabilities (`window.claude.*`,
gated behind the `artifact-capabilities` skill), which only apply when the
deliverable is specifically published as a Claude Artifact, not a generic file
opened by Codex/Gemini or via `file://`. Out of scope here; the copy-button
handback below is the general-purpose answer.

**Core script** (put once, near the other scripts):

````html
<script>
  /* ---- tagged-field state: collect/restore/handback ---------------------
   Tag any input/textarea/select with data-field="unique-key". Radio groups:
   put the same data-field on every <input type=radio> in the group. ---- */
  function collectState() {
    const o = {};
    document.querySelectorAll("[data-field]").forEach((el) => {
      const k = el.dataset.field;
      if (el.type === "checkbox") o[k] = el.checked;
      else if (el.type === "radio") {
        if (el.checked) o[k] = el.value;
      } else o[k] = el.value;
    });
    return o;
  }
  const HR_SKEY = "hr_state:" + location.pathname;
  function saveState() {
    try {
      localStorage.setItem(HR_SKEY, JSON.stringify(collectState()));
    } catch (e) {}
  }
  function restoreState() {
    try {
      const s = JSON.parse(localStorage.getItem(HR_SKEY) || "{}");
      document.querySelectorAll("[data-field]").forEach((el) => {
        if (!(el.dataset.field in s)) return;
        const v = s[el.dataset.field];
        if (el.type === "checkbox") el.checked = !!v;
        else if (el.type === "radio") el.checked = el.value === v;
        else el.value = v;
      });
    } catch (e) {}
  }
  document.addEventListener("input", saveState);
  restoreState();
  function copyState() {
    const txt = "```json\n" + JSON.stringify(collectState(), null, 2) + "\n```";
    const ta = document.getElementById("handback");
    ta.value = txt;
    ta.style.display = "block";
    ta.select();
    navigator.clipboard.writeText(txt).catch(() => {});
    const b = document.getElementById("handback-btn");
    if (b) {
      const o = b.textContent;
      b.textContent = "✓ copied — paste into the chat";
      setTimeout(() => (b.textContent = o), 2000);
    }
  }
</script>
````

**Handback control** (place once, wherever the operator will finish — end of
the decision queue is typical):

```html
<button id="handback-btn" class="fs" onclick="copyState()">
  📋 copy annotations for agent
</button>
<textarea
  id="handback"
  readonly
  rows="6"
  style="display:none;width:100%;margin-top:.5rem;
  font:.85em ui-monospace,monospace;background:var(--code-bg);color:var(--ink);
  border:1px solid var(--line);border-radius:.4rem;padding:.5rem .7rem"
></textarea>
```

**Annotation/correction cell** — free-text note or fix attached to a finding
row (works inside any table the template already sorts/filters):

```html
<tr>
  <td><code>/some/path</code></td>
  <td data-v="204">204G</td>
  <td><span class="badge warn">needs-judgment</span></td>
  <td>
    <textarea
      data-field="note.some-path"
      rows="1"
      placeholder="annotate / correct…"
      style="width:100%;resize:vertical;background:var(--bg);color:var(--ink);
      border:1px solid var(--line);border-radius:.3rem;padding:.2rem .4rem;font:.85em inherit"
      oninput="this.rows=Math.max(1,this.value.split('\n').length)"
    ></textarea>
  </td>
</tr>
```

**Decision widget** — approve/defer/reject + optional note, dropped straight
into a decision-queue row. Style as real buttons, not bare radios — a plain
`<input type=radio>` plus a short text label is a genuinely small click target
once a table has 10+ rows stacked for density, and operators notice ("these
aren't tiny little controls to hunt for" — confirmed complaint, 2026-08-01).
Hide the native input, style its `<label for=id>` as a button, fill it solid
on `:checked`. **Two uniqueness requirements, both load-bearing**: every row
needs its own `name` (`d1`, `d2`, …) — radio grouping is by `name`, so reusing
it across rows silently merges rows into one group even when `data-field`
differs — _and_ every option within a row needs its own `id`/`for` pair (the
`input:checked + label` selector needs a real sibling relationship per option):

```html
<td>
  <div class="seg" role="group" aria-label="decision">
    <input
      type="radio"
      id="d1-a"
      name="d1"
      data-field="decision.204g-cache"
      value="approve"
    /><label for="d1-a">✅ approve</label>
    <input
      type="radio"
      id="d1-b"
      name="d1"
      data-field="decision.204g-cache"
      value="defer"
    /><label for="d1-b">⏸ defer</label>
    <input
      type="radio"
      id="d1-c"
      name="d1"
      data-field="decision.204g-cache"
      value="reject"
    /><label for="d1-c">✕ reject</label>
  </div>
  <input
    type="text"
    data-field="decision.204g-cache.note"
    placeholder="note (optional)"
    style="width:12rem;margin-left:.4rem;background:var(--bg);color:var(--ink);
    border:1px solid var(--line);border-radius:.3rem;padding:.3rem .5rem;font-size:.95rem"
  />
</td>
<style>
  .seg {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin: 0.15rem 0;
  }
  .seg input {
    position: absolute;
    opacity: 0;
    pointer-events: none;
  }
  .seg label {
    display: inline-block;
    padding: 0.45rem 1rem;
    border: 2px solid var(--line);
    border-radius: 0.5rem;
    cursor: pointer;
    font-size: 0.95rem;
    font-weight: 600;
    background: var(--bg);
    color: var(--ink);
    user-select: none;
    transition:
      background 0.1s,
      border-color 0.1s;
  }
  .seg label:hover {
    border-color: var(--accent);
  }
  .seg input:checked + label {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--accent-ink);
  }
  .seg input:focus-visible + label {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
</style>
```

Same technique works for any single-choice row control (approve/defer/reject,
priority tiers, yes/no/unsure) — swap the option count and labels, keep the
hide-input/style-label/`:checked+label` mechanism.

**Questionnaire block** — a self-contained fieldset for a one-off question
(naming scheme, priority ranking, yes/no with reasoning):

```html
<fieldset class="q">
  <legend>Which naming scheme for the JPK pipeline stages?</legend>
  <label
    ><input type="radio" name="q1" data-field="q.jpk-naming" value="kebab" />
    kebab-case (00-source-…)</label
  >
  <label
    ><input type="radio" name="q1" data-field="q.jpk-naming" value="keep" />
    keep the existing 00_jpk_…</label
  >
  <textarea
    data-field="q.jpk-naming.why"
    rows="2"
    placeholder="why (optional)"
    style="width:100%;margin-top:.4rem;background:var(--bg);color:var(--ink);
    border:1px solid var(--line);border-radius:.3rem;padding:.3rem .5rem;font:inherit"
  ></textarea>
</fieldset>
<style>
  .q {
    border: 1px solid var(--line);
    border-radius: 0.5rem;
    padding: 0.6rem 0.9rem;
    margin: 0.6rem 0;
  }
  .q legend {
    padding: 0 0.4rem;
    font-weight: 600;
    font-size: 0.92rem;
  }
  .q label {
    display: block;
    margin: 0.25rem 0;
  }
</style>
```

Field-key convention: dotted, lowercase, stable across regenerations of the
same report (`decision.<row-id>`, `note.<row-id>`, `q.<topic>`) — that lets a
later agent match a pasted-back blob to the exact rows it came from without
guessing.

---

# Data-derived reports (numbers that came from a real query)

The patterns above shape _narrative_. These shape _measurement_ — reports whose
content was computed from a system rather than written from memory. The
governing rule: **a number the reader cannot trace is a number they have to
take on faith**, and this skill's whole provenance apparatus exists to avoid
exactly that.

## Query-attributed metric (the flagship)

Every headline number carries the exact invocation that produced it. Click the
figure, see the command. This makes a report self-verifying, turns "the tool
can do this" into something checkable, and — the practical payoff — means the
next agent regenerating the report knows precisely how each cell was derived.

```html
<div class="tile qa">
  <b>4,905,637</b>
  <span>messages archived</span>
  <template class="pop"
    ><figure class="code">
      <figcaption>measured 2026-07-31</figcaption>
      <pre>
sqlite3 "file:$ARCHIVE/index.db?mode=ro" \
  "select count(*) from messages;"</pre
      >
    </figure></template
  >
</div>
```

```css
.tile.qa {
  position: relative;
  cursor: help;
}
.tile.qa::after {
  content: "⌕";
  position: absolute;
  top: 0.35rem;
  right: 0.45rem;
  opacity: 0.35;
  font-size: 0.8rem;
}
```

Bind with the same popup engine as `a.path` — the `<template class="pop">` must
be a **direct child** of the element it annotates (the binding selector is
`:has(> template.pop)`), or the preview silently attaches to the parent block.

The template's stat-tile slot now ships with this popup pre-wired and a
`POP-TODO` sentinel inside — fill the query in or delete the template
deliberately; the shipping check greps for the sentinel so a forgotten one is
visible. Adoption history says this matters: when the slot lived only in this
file, four of six shipped reports carried zero query popups.

Use `ev-measured` on anything carrying a query, `ev-derived` for arithmetic over
measured values, `ev-inferred` for reasoning. If a number came from reading
prose rather than querying, say so — an honest `ev-inferred` beats a confident
figure nobody can reproduce. Where a query was _supposed_ to produce a number
and could not (timeout, missing surface), show the gap rather than substituting
an estimate; a visible hole is information.

## Conversation exchange

For transcript excerpts. Role is not enough — chat archives distinguish
_authoredness_ (who actually wrote this) from _role_ (what slot it occupies),
because protocol/tool rows often carry `role=user` while being machine-written.
Style them differently or every statistic downstream reads wrong.

```html
<div class="xc">
  <div class="turn human">
    <b>operator</b><time datetime="2026-07-31T08:12:00Z">08:12</time>
    <p>why is beads an origin? beads is not a chatlog</p>
  </div>
  <div class="turn asst">
    <b>assistant</b><time datetime="2026-07-31T08:13:04Z">08:13</time>
    <p>Because ingestion treats any parseable record stream as a session…</p>
  </div>
  <div class="turn proto">
    <b>runtime_protocol</b><span class="mo">role=user, machine-authored</span>
  </div>
</div>
```

```css
.xc {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin: 0.8rem 0;
}
.turn {
  border-left: 3px solid var(--line);
  padding: 0.4rem 0.7rem;
  border-radius: 0 0.3rem 0.3rem 0;
}
.turn b {
  font-size: 0.82rem;
  letter-spacing: 0.02em;
}
.turn time {
  float: right;
  font-size: 0.78rem;
  opacity: 0.6;
}
.turn p {
  margin: 0.25rem 0 0;
}
.turn.human {
  border-left-color: var(--accent);
  background: color-mix(in oklab, var(--accent) 6%, transparent);
}
.turn.asst {
  border-left-color: var(--line);
}
.turn.proto {
  opacity: 0.6;
  font-size: 0.85rem;
  border-left-style: dashed;
}
.turn .mo {
  font-size: 0.78rem;
  opacity: 0.7;
  margin-left: 0.5rem;
}
```

Truncate long turns to the load-bearing sentences and mark the elision (`…`) —
a "full transcript" nobody scrolls is worse than a chosen excerpt that makes
the point. Never paste an entire session into a report.

## Activity histogram (pure SVG, no library)

Messages per hour, commits per day, errors per run. Compute the bars yourself
and emit a `viewBox`-only SVG; it scales, prints, and needs no JS.

```html
<figure class="chart">
  <svg viewBox="0 0 240 40" role="img" aria-label="messages per hour">
    <!-- one <rect> per bucket: x = i*4, height = v/max*36, y = 40-height -->
    <rect x="0" y="28" width="3" height="12" class="bar" />
    <rect x="4" y="10" width="3" height="30" class="bar" />
    <rect x="8" y="4" width="3" height="36" class="bar peak" />
  </svg>
  <figcaption>
    messages/hour · peak 214 at 03:00 UTC ·
    <span class="ev-measured">measured</span>
  </figcaption>
</figure>
```

```css
.chart svg {
  width: 100%;
  height: auto;
  max-height: 5rem;
}
.bar {
  fill: var(--accent);
  opacity: 0.55;
}
.bar.peak {
  opacity: 1;
}
```

Always label the peak and the units in the caption — an unlabelled shape is
decoration. For a sparkline inside a table cell, same technique at
`viewBox="0 0 60 14"` with `height:1em`.

## Distribution bars (in-table)

Ranked counts read faster as bars than as digits. Keep the number too — the bar
gives shape, the number gives fact.

```html
<td class="dist"><span style="--w:78%"></span><b>1,204</b></td>
```

```css
.dist {
  position: relative;
  text-align: right;
  white-space: nowrap;
}
.dist span {
  position: absolute;
  left: 0;
  top: 0.25rem;
  bottom: 0.25rem;
  width: var(--w);
  background: var(--accent);
  opacity: 0.18;
  border-radius: 0.2rem;
}
.dist b {
  position: relative;
  font-variant-numeric: tabular-nums;
}
```

Normalize `--w` against the column max, not the total, or everything below rank
one becomes an invisible sliver.

## Hierarchy / delegation tree

Subagent fan-out, session lineage (fork/resume/compaction), call trees. Nested
`<ul>` with CSS connectors beats hand-drawn SVG here: it reflows, stays
selectable, and degrades to a plain indented list with CSS off.

```html
<ul class="tree">
  <li>
    coordinator <span class="meta">1,861 msgs</span>
    <ul>
      <li>audit: invariants <span class="meta ok">30 checked</span></li>
      <li>audit: fidelity <span class="meta warn">running</span></li>
    </ul>
  </li>
</ul>
```

```css
.tree,
.tree ul {
  list-style: none;
  margin: 0;
  padding-left: 1.1rem;
}
.tree li {
  position: relative;
  padding: 0.15rem 0 0.15rem 0.8rem;
}
.tree li::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  border-left: 1px solid var(--line);
}
.tree li::after {
  content: "";
  position: absolute;
  left: 0;
  top: 0.85rem;
  width: 0.65rem;
  border-top: 1px solid var(--line);
}
.tree > li:last-child::before {
  bottom: auto;
  height: 0.85rem;
}
.tree .meta {
  font-size: 0.8rem;
  opacity: 0.7;
  margin-left: 0.4rem;
}
```

## Two-subject comparison

Comparing two runs/sessions/branches: put them on a **shared scale** or the
comparison lies. Grid with a label column beats two separate tables — the eye
compares rows, not pages.

```html
<table class="cmp">
  <thead>
    <tr>
      <th>metric</th>
      <th>session A</th>
      <th>session B</th>
      <th>Δ</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th scope="row">messages</th>
      <td>1,493</td>
      <td>1,861</td>
      <td class="up">+368</td>
    </tr>
  </tbody>
</table>
```

```css
.cmp td {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.cmp th[scope="row"] {
  text-align: left;
  font-weight: 500;
}
.cmp .up {
  color: var(--ok);
}
.cmp .down {
  color: var(--bad);
}
```

State the direction convention in a caption ("Δ = B − A"). A signed number with
no stated sign convention is a coin flip.

## Measured treemap (SVG, no libs)

For "codebase atlas" / disk-usage / any part-of-whole breakdown where area should equal a
measured quantity. Don't hand-place rects — generate them from the data with a 10-line
slice-and-dice layout, then paste the fragment into the report's `<svg>`:

```python
# rows: big items get the top band sized by their share; the tail shares the bottom band.
data=[(name, value, files), ...]           # sorted desc, measured
W,H=960,300; total=sum(v for _,v,_ in data)
row1, row2 = data[:7], data[7:]            # split so top row labels stay readable
s1=sum(v for _,v,_ in row1); h1=H*s1/total
x=0
for name,v,f in row1:
    w=W*v/s1
    emit(f'<g><rect x="{x:.1f}" y="0" width="{w:.1f}" height="{h1:.1f}" '
         f'fill="var(--e2)" opacity=".28" stroke="var(--panel)" stroke-width="2"/>'
         f'<text ...>{name}</text><title>{name}: {v:,} lines, {f} files</title></g>')
    x+=w
# same loop for row2 at y=h1, height H-h1; label only when w>52, abbreviate when w>34
```

Rules learned building it: `stroke="var(--panel)" stroke-width="2"` gives clean cell
separation in both themes; fill with theme vars at low opacity (.22-.28) so labels stay
readable; every cell gets a `<title>` (free hover tooltip, no JS); suppress labels below
~34px width rather than letting them overflow; put the exact numbers in a companion
sortable table — the treemap is for proportion-at-a-glance, the table is for lookup.

## Entity chip (dense inline reference — micro-DSL)

For reports that reference many tracked entities (beads, PRs, findings, hosts),
a chip encodes id + priority + status + type + degree in one inline token, with
the expanded reading on hover. Proven at scale in the beads-state generator
(1,500 chips on one page). The notation must be **explained once in a legend
section** — it is a DSL the reader learns, not self-evident.

```html
<span
  class="bchip p0 open"
  title="P0 open bug polylogue-kadx — blocks 3 open beads"
>
  <b>P0</b>○<code>polylogue-kadx</code>✕<small>↓3</small></span
>
<style>
  .bchip {
    display: inline-flex;
    align-items: center;
    gap: 0.15rem;
    border: 1px solid var(--line);
    border-radius: 0.3rem;
    padding: 0 0.35rem;
    font-size: 0.82rem;
    white-space: nowrap;
    border-left: 3px solid var(--muted);
  }
  .bchip.p0 {
    border-left-color: var(--bad);
  }
  .bchip.p1 {
    border-left-color: var(--warn);
  }
  .bchip.p2 {
    border-left-color: var(--info);
  }
  .bchip.closed code {
    text-decoration: line-through;
    opacity: 0.6;
  }
  .bchip.inprog {
    outline: 1px solid var(--info);
  }
  .bchip small {
    opacity: 0.7;
  }
</style>
```

Glyph conventions that worked: `○` open · `◐` in progress · `●` closed ·
`▪` task · `✕` bug · `✦` feature · `▣` epic · `↑n`/`↓n` blocked-by/blocks
degree. Strike the id when closed; dashed border for deferred.

## Hand-placed SVG diagrams — layout rules that survive contact

Rules extracted from a real layout-fix round-trip (5-lane dataflow, 2026-08-02):

1. **Pins/markers are rounded `<rect>`s, never small circles** — 3-char labels
   overflow r=11 circles; rect w ≈ 22 + 6·chars, h=18, seated ON the border of
   the box they annotate (half in, half out) so attachment is unambiguous.
2. **Orthogonal elbow arrows only**, routed through inter-lane gutters
   (`M x1,y1 V gutter H x2 V y2`) — diagonals always cross text at some viewport.
3. **Lane bands as tinted background rects with labels ABOVE the band** —
   labels inside the band collide with row boxes sooner or later.
4. **A legend row inside the SVG** for any marker-color semantics.
5. **Proofread SVG `<text>` separately** — typos there pass every automated
   check (tag balance, node --check, headless render).

Working constants: box h 48-70, ≤3 text lines (13px title / 11px subs),
≥30px vertical gutters, viewBox padded ~40px below the last row for the legend.

## Provenance-aware time series (era bands + event markers + synthetic hatch)

When part of a time axis is known-unreliable (rewritten git history, backfilled
data), tinted era bands and dashed event markers are not enough — readers still
read the bars as data. Add a 45° hatch `<pattern>` overlay across the unreliable
region, reduce bar opacity there, and set an inline italic label naming the
defect ("synthetic dates — rebuilt history"). Stagger clustered marker labels
vertically (`y - (i%3)*13`) or they overprint. Used twice (trajectory rev 2+3).

## Lens-first system explainer (structure for "explain this whole codebase/system")

A comprehensive system report organized as a package tour reads as inventory and teaches
nothing. The structure that worked (polylogue-atlas, 2026-08-02):

1. **One-paragraph thesis** — what the system IS, no history.
2. **N lenses (4-7)** — each a design commitment stated in one bold sentence, then one
   short paragraph tracing its consequences into measured structural facts ("hence
   storage is 25% of the product"). Each lens gets a `.lens` card with a distinct
   left-border color reused consistently in every later diagram.
3. **Measured atlas** — treemap + heavy-modules table + one-line-per-package collapsed
   table. Numbers here, not in the lenses.
4. **2-4 core diagrams** (tiers/data-model/flows) that _draw_ the lenses.
5. **Honest tensions table** — where the code fights its own lenses; link deep-dives
   instead of restating them.
6. **"How to read this codebase" ordered file list** — the exit ramp into the real thing.

Anti-fluff rules that held: every section is a diagram or a table plus at most two short
paragraphs; every fact appears exactly once (link, don't repeat); companion reports get
linked in the meta block, never summarized inline. The lenses double as review
checklists — "code that fights its lens is where the next incident lives" gives the
report an operational point beyond description.
