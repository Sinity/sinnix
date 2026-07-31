# Interactivity & layout patterns (paste-in snippets)

All snippets assume the template's CSS variables/classes. Everything inline,
no external requests, JS-optional where possible.

## Tabs (CSS-only, radio-based — survives JS-off)

```html
<div class="tabs">
  <input type="radio" name="tg1" id="ta" checked><label for="ta">Before</label>
  <input type="radio" name="tg1" id="tb"><label for="tb">After</label>
  <div class="pane pa"><!-- before content --></div>
  <div class="pane pb"><!-- after content --></div>
</div>
<style>
.tabs input{display:none}
.tabs label{display:inline-block;padding:.25rem .8rem;border:1px solid var(--line);
  border-bottom:none;border-radius:.4rem .4rem 0 0;cursor:pointer;color:var(--muted)}
.tabs input:checked+label{background:var(--panel);color:var(--ink);font-weight:600}
.tabs .pane{display:none;border:1px solid var(--line);padding:.8rem;border-radius:0 .4rem .4rem .4rem}
#ta:checked~.pa,#tb:checked~.pb{display:block}
</style>
```

## Timeline (incidents, campaign history)

```html
<ol class="tl">
  <li><time>2026-07-10</time><b>Runtime stopped</b> — during reorg night; never restarted.</li>
  <li><time>2026-07-21</time><b>Campaign "COMPLETE"</b> — prematurely declared.</li>
</ol>
<style>
.tl{list-style:none;margin:0;padding:0 0 0 1.1rem;border-left:2px solid var(--line)}
.tl li{margin:.55rem 0;position:relative;padding-left:.8rem}
.tl li::before{content:"";position:absolute;left:-1.45rem;top:.35rem;width:.55rem;
  height:.55rem;border-radius:50%;background:var(--accent)}
.tl time{color:var(--muted);font-size:.8rem;margin-right:.5rem}
</style>
```

## Correction ladder (claim → challenge → reversal, kept visible)

For a report whose whole point is *how a conclusion moved* (a debugging
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
    <blockquote class="q">DOM should either get stable ids or be
      retired for providers with a working native path.<cite>assistant</cite></blockquote>
  </li>
  <li class="challenge">
    <p class="who">operator <span class="stage stage-challenge">push</span></p>
    <blockquote class="q user">but do we actually want this fallback, or is it
      cargo culting?<cite>operator</cite></blockquote>
  </li>
  <li class="reversal">
    <p class="who">assistant <span class="stage stage-reversal">reversal</span></p>
    <p>Counts the archive: the fallback fired 17 times, and none of those
      sessions also has a native capture — it's the only surviving record for
      24 of them.</p>
    <blockquote class="q">That inverts my recommendation.<cite>assistant</cite></blockquote>
  </li>
</ol>
<style>
.ladder{list-style:none;margin:.6rem 0;padding:0;border-left:3px solid var(--line)}
.ladder li{position:relative;padding:.55rem 0 .55rem 1.3rem}
.ladder li::before{content:"";position:absolute;left:-.62rem;top:1.05rem;width:.7rem;
  height:.7rem;border-radius:50%;background:var(--muted);border:2px solid var(--panel)}
.ladder li.claim::before{background:var(--info)}
.ladder li.challenge::before{background:var(--todo)}
.ladder li.reversal::before{background:var(--warn)}
.ladder .who{font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;
  color:var(--muted);font-weight:700;margin:0 0 .2rem}
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
.diff .del{display:block;background:var(--bad-bg)} .diff .add{display:block;background:var(--ok-bg)}
.diff .ctx{display:block;color:var(--muted)} .diff i{float:right;color:var(--muted);font-size:.8em}
</style>
```

## Inline SVG diagram (boxes + labeled arrows)

```html
<svg viewBox="0 0 460 120" role="img" aria-label="data flow" style="max-width:34rem">
  <defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6"
    markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10z" fill="currentColor"/></marker></defs>
  <g fill="none" stroke="currentColor">
    <rect x="8"  y="38" width="120" height="40" rx="8"/>
    <rect x="180" y="38" width="120" height="40" rx="8"/>
    <rect x="342" y="38" width="110" height="40" rx="8"/>
    <path d="M128 58h48" marker-end="url(#ar)"/><path d="M300 58h38" marker-end="url(#ar)"/>
  </g>
  <g font-size="12" text-anchor="middle" fill="currentColor">
    <text x="68" y="62">capture</text><text x="240" y="62">archive</text><text x="397" y="62">analysis</text>
    <text x="152" y="50" font-size="10">ingest</text><text x="321" y="50" font-size="10">query</text>
  </g>
</svg>
```
`currentColor` inherits the theme ink — diagrams need no per-theme colors.

## Keyboard-navigable deck

```html
<div class="deck"><section class="slide on"><h2>One</h2></section>
<section class="slide"><h2>Two</h2></section></div>
<style>.deck .slide{display:none;min-height:60vh}.deck .on{display:block}</style>
<script>let i=0,S=document.querySelectorAll('.deck .slide');
addEventListener('keydown',e=>{if(e.key==='ArrowRight'&&i<S.length-1)S[i].classList.remove('on'),S[++i].classList.add('on');
if(e.key==='ArrowLeft'&&i>0)S[i].classList.remove('on'),S[--i].classList.add('on')});</script>
```

## Copy button for paths/commands

```html
<button class="cp" data-t="/realm/some/path" onclick="navigator.clipboard.writeText(this.dataset.t);this.textContent='✓'">⧉</button>
<style>.cp{border:none;background:none;cursor:pointer;color:var(--muted)}</style>
```

## Swatches / contact sheet (design tokens, image sets)

```html
<div class="sw"><i style="--c:#2563eb"></i><code>--accent #2563eb</code></div>
<style>.sw{display:flex;align-items:center;gap:.5rem}
.sw i{width:1.4rem;height:1.4rem;border-radius:.3rem;background:var(--c);border:1px solid var(--line)}</style>
```
Contact sheets: CSS grid of `figure` cells, `data:` URI thumbnails, captions.

## Lead register (living workspace spine)

One row per lead, state as a badge, provenance as an id. Duds stay in the table
with their reason — that is the whole point. Filter box + sortable `th` come
free from the template.

```html
<input class="filter" placeholder="filter leads…" oninput="flt(this,'leads')">
<div class="tablewrap"><table id="leads">
<thead><tr><th>ID</th><th>Lead</th><th>State</th><th data-v>Value</th>
  <th class="nosort">Evidence / why</th><th>Tracker</th></tr></thead>
<tbody>
<tr data-state="open"><td><code>A3</code></td><td>move repair.py to maintenance/</td>
  <td><span class="badge todo">open</span></td><td data-v="2">med</td>
  <td>doctrine conflict, undecided in hotspots doc</td><td><code>—</code></td></tr>
<tr data-state="dud"><td><code>A8</code></td><td>render burden</td>
  <td><span class="badge info">dud</span></td><td data-v="0">none</td>
  <td>all 17 targets derive from source; cannot go stale</td><td><code>—</code></td></tr>
</tbody></table></div>
```

Add quick state filters with plain buttons over `data-state` when the register
grows past ~20 rows:

```html
<button class="fs" onclick="st('')">all</button>
<button class="fs" onclick="st('open')">open only</button>
<script>function st(s){document.querySelectorAll('#leads tbody tr').forEach(r=>
  r.style.display=(!s||r.dataset.state===s)?'':'none')}</script>
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
   closing and reopening *that exact file* — free durability, no agent
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

```html
<script>
/* ---- tagged-field state: collect/restore/handback ---------------------
   Tag any input/textarea/select with data-field="unique-key". Radio groups:
   put the same data-field on every <input type=radio> in the group. ---- */
function collectState(){
  const o={};
  document.querySelectorAll('[data-field]').forEach(el=>{
    const k=el.dataset.field;
    if(el.type==='checkbox')o[k]=el.checked;
    else if(el.type==='radio'){if(el.checked)o[k]=el.value}
    else o[k]=el.value});
  return o}
const HR_SKEY='hr_state:'+location.pathname;
function saveState(){try{localStorage.setItem(HR_SKEY,JSON.stringify(collectState()))}catch(e){}}
function restoreState(){try{
  const s=JSON.parse(localStorage.getItem(HR_SKEY)||'{}');
  document.querySelectorAll('[data-field]').forEach(el=>{
    if(!(el.dataset.field in s))return;const v=s[el.dataset.field];
    if(el.type==='checkbox')el.checked=!!v;
    else if(el.type==='radio')el.checked=(el.value===v);
    else el.value=v})}catch(e){}}
document.addEventListener('input',saveState);restoreState();
function copyState(){
  const txt='```json\n'+JSON.stringify(collectState(),null,2)+'\n```';
  const ta=document.getElementById('handback');
  ta.value=txt;ta.style.display='block';ta.select();
  navigator.clipboard.writeText(txt).catch(()=>{});
  const b=document.getElementById('handback-btn');
  if(b){const o=b.textContent;b.textContent='✓ copied — paste into the chat';setTimeout(()=>b.textContent=o,2000)}}
</script>
```

**Handback control** (place once, wherever the operator will finish — end of
the decision queue is typical):

```html
<button id="handback-btn" class="fs" onclick="copyState()">📋 copy annotations for agent</button>
<textarea id="handback" readonly rows="6" style="display:none;width:100%;margin-top:.5rem;
  font:.85em ui-monospace,monospace;background:var(--code-bg);color:var(--ink);
  border:1px solid var(--line);border-radius:.4rem;padding:.5rem .7rem"></textarea>
```

**Annotation/correction cell** — free-text note or fix attached to a finding
row (works inside any table the template already sorts/filters):

```html
<tr><td><code>/some/path</code></td><td data-v="204">204G</td>
  <td><span class="badge warn">needs-judgment</span></td>
  <td><textarea data-field="note.some-path" rows="1" placeholder="annotate / correct…"
      style="width:100%;resize:vertical;background:var(--bg);color:var(--ink);
      border:1px solid var(--line);border-radius:.3rem;padding:.2rem .4rem;font:.85em inherit"
      oninput="this.rows=Math.max(1,this.value.split('\n').length)"></textarea></td></tr>
```

**Decision widget** — approve/defer/reject + optional note, dropped straight
into a decision-queue row. **Each row needs its own `name`** (`d1`, `d2`, …):
radio grouping is by `name`, so reusing it across rows silently merges them
into one group even when `data-field` differs:

```html
<td>
  <label><input type="radio" name="d1" data-field="decision.204g-cache" value="approve"> approve</label>
  <label><input type="radio" name="d1" data-field="decision.204g-cache" value="defer"> defer</label>
  <label><input type="radio" name="d1" data-field="decision.204g-cache" value="reject"> reject</label>
  <input type="text" data-field="decision.204g-cache.note" placeholder="note (optional)"
    style="width:12rem;margin-left:.4rem;background:var(--bg);color:var(--ink);
    border:1px solid var(--line);border-radius:.3rem;padding:.15rem .4rem">
</td>
<style>td label{display:inline-flex;align-items:center;gap:.25rem;margin-right:.7rem;font-size:.9rem}</style>
```

**Questionnaire block** — a self-contained fieldset for a one-off question
(naming scheme, priority ranking, yes/no with reasoning):

```html
<fieldset class="q">
  <legend>Which naming scheme for the JPK pipeline stages?</legend>
  <label><input type="radio" name="q1" data-field="q.jpk-naming" value="kebab"> kebab-case (00-source-…)</label>
  <label><input type="radio" name="q1" data-field="q.jpk-naming" value="keep"> keep the existing 00_jpk_…</label>
  <textarea data-field="q.jpk-naming.why" rows="2" placeholder="why (optional)"
    style="width:100%;margin-top:.4rem;background:var(--bg);color:var(--ink);
    border:1px solid var(--line);border-radius:.3rem;padding:.3rem .5rem;font:inherit"></textarea>
</fieldset>
<style>.q{border:1px solid var(--line);border-radius:.5rem;padding:.6rem .9rem;margin:.6rem 0}
.q legend{padding:0 .4rem;font-weight:600;font-size:.92rem}
.q label{display:block;margin:.25rem 0}</style>
```

Field-key convention: dotted, lowercase, stable across regenerations of the
same report (`decision.<row-id>`, `note.<row-id>`, `q.<topic>`) — that lets a
later agent match a pasted-back blob to the exact rows it came from without
guessing.
