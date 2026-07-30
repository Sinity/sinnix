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

## Checklist table for decision queues

Use `.badge todo` → `.badge ok` cells; one row per decision, columns:
priority badge · decision · blocker/owner · evidence link. Sortable for free
via the template's table JS.
