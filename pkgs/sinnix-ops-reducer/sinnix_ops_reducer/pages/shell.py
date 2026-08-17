"""The hub's house style, components, and page shell.

Ported verbatim from sinnix-hub-render. The only client-side JavaScript on the
hub is here: theme/reading-size persistence, the services filter, and the
bounded action API driver.
"""

from __future__ import annotations

import datetime as dt
import html
from typing import Any


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def as_int(value: Any) -> int | None:
    try:
        number = int(str(value))
    except (TypeError, ValueError):
        return None
    # systemd reports an unset limit as 2**64-1; treat it as no limit.
    return None if number >= 2**63 else number


def bytes_human(value: Any) -> str:
    number = as_int(value)
    if number is None:
        return "—"
    if number < 1024:
        return f"{number} B"
    for unit, size in (("T", 1024**4), ("G", 1024**3), ("M", 1024**2), ("K", 1024)):
        if number >= size:
            scaled = number / size
            return f"{scaled:.1f} {unit}" if scaled < 100 else f"{scaled:.0f} {unit}"
    return f"{number} B"


def duration_human(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "—"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60:02d}s"
    if seconds < 86400:
        return f"{seconds // 3600}h {(seconds % 3600) // 60:02d}m"
    return f"{seconds // 86400}d {(seconds % 86400) // 3600}h"


def parse_iso(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def age_since(value: Any, now: dt.datetime) -> str:
    moment = parse_iso(value)
    if moment is None:
        return "—"
    return duration_human((now - moment).total_seconds()) + " ago"


# --------------------------------------------------------------------------
# components
# --------------------------------------------------------------------------


def badge(text: str, tone: str = "muted") -> str:
    return f'<span class="badge {tone}">{esc(text)}</span>'


def tile(value: str, label: str, tone: str = "", href: str = "") -> str:
    body = (
        f'<span class="n">{value}</span><span class="l">{esc(label)}</span>'
    )
    classes = f"tile {tone}".strip()
    if href:
        return f'<a class="{classes}" href="{esc(href)}">{body}</a>'
    return f'<div class="{classes}">{body}</div>'


def meter(current: int | None, limit: int | None, tone: str = "") -> str:
    """A single quiet bar. No gauges, no dials -- a bar or nothing."""
    if current is None:
        return ""
    if not limit:
        return '<div class="meter open"><i style="width:0"></i></div>'
    ratio = max(0.0, min(1.0, current / limit))
    grade = tone or ("bad" if ratio > 0.9 else "warn" if ratio > 0.7 else "ok")
    return f'<div class="meter {grade}"><i style="width:{ratio * 100:.1f}%"></i></div>'


def card(title: str, body: str, subtitle: str = "", wide: bool = False, anchor: str = "") -> str:
    sub = f'<p class="sub">{subtitle}</p>' if subtitle else ""
    ident = f' id="{esc(anchor)}"' if anchor else ""
    classes = "card wide" if wide else "card"
    return f'<section class="{classes}"{ident}><h2>{esc(title)}</h2>{sub}{body}</section>'


def kv_table(rows: list[tuple[str, str]]) -> str:
    if not rows:
        return '<p class="sub">nothing to show</p>'
    cells = "".join(f"<tr><th>{esc(key)}</th><td>{value}</td></tr>" for key, value in rows)
    return f'<table class="kv">{cells}</table>'


def empty(message: str) -> str:
    return f'<p class="empty">{esc(message)}</p>'


def row(
    headline: str,
    meta: list[str],
    controls: str = "",
    tone: str = "",
    search: str = "",
) -> str:
    """One workload/service as a stacked block rather than a table row.

    A table needs horizontal room the phone does not have; a block wraps. Each
    metadata fragment is its own element so the flex gap does the separating --
    no interpuncts to line up and no run-together text.
    """
    control_block = f'<div class="rc">{controls}</div>' if controls else ""
    fragments = "".join(f"<span>{part}</span>" for part in meta if part)
    attribute = f' data-search="{esc(search)}"' if search else ""
    return (
        f'<div class="row {tone}"{attribute}><div class="rh">{headline}</div>'
        f'<div class="rm">{fragments}</div>{control_block}</div>'
    )


def dot(tone: str) -> str:
    return f'<span class="dot {tone}"></span>'


# --------------------------------------------------------------------------
# style -- the estate's house tokens, not a second visual language
# --------------------------------------------------------------------------

STYLE = """
:root{
  --bg:#f6f7f9; --panel:#ffffff; --ink:#1a2129; --muted:#5b6773;
  --line:#dde3e9; --accent:#7c3aed; --accent-ink:#ffffff;
  --ok:#0f7b46; --ok-bg:#e2f5eb; --warn:#8a5a00; --warn-bg:#fdf0d3;
  --bad:#a01c1c; --bad-bg:#fbe4e4; --info:#1d4ed8; --info-bg:#e3ebfd;
  --code-bg:#eef1f4; --fs:17px;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#12161b; --panel:#1a2027; --ink:#e6ebf0; --muted:#94a1ad;
  --line:#2b333c; --accent:#b08df2; --accent-ink:#160d24;
  --ok:#4cc98a; --ok-bg:#12301f; --warn:#e2b93b; --warn-bg:#33290e;
  --bad:#ef7070; --bad-bg:#391717; --info:#7ea6f4; --info-bg:#16223b;
  --code-bg:#232a32;
}}
:root[data-theme="dark"]{
  color-scheme:dark;
  --bg:#12161b; --panel:#1a2027; --ink:#e6ebf0; --muted:#94a1ad;
  --line:#2b333c; --accent:#b08df2; --accent-ink:#160d24;
  --ok:#4cc98a; --ok-bg:#12301f; --warn:#e2b93b; --warn-bg:#33290e;
  --bad:#ef7070; --bad-bg:#391717; --info:#7ea6f4; --info-bg:#16223b;
  --code-bg:#232a32;
}
:root[data-theme="light"]{color-scheme:light}
*{box-sizing:border-box}
html{font-size:var(--fs)}
body{margin:0;background:var(--bg);color:var(--ink);
  font:1rem/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;
  -webkit-text-size-adjust:100%}

header.page{position:sticky;top:0;z-index:6;background:var(--panel);
  border-bottom:1px solid var(--line)}
.hbar{max-width:74rem;margin:0 auto;padding:.55rem .9rem;display:flex;
  align-items:baseline;gap:.5rem;flex-wrap:wrap}
.hbar h1{font-size:1.15rem;margin:0;letter-spacing:-.01em}
.hbar h1 b{color:var(--accent)}
.hbar .spacer{flex:1}
.chip{display:inline-block;padding:.1rem .55rem;border:1px solid var(--line);
  border-radius:99px;font-size:.78rem;color:var(--muted);background:var(--bg);
  white-space:nowrap;font-variant-numeric:tabular-nums}
.hbtn{border:1px solid var(--line);background:var(--bg);color:var(--ink);
  border-radius:.4rem;padding:.25rem .55rem;cursor:pointer;font:inherit;
  font-size:.8rem;min-height:2rem;min-width:2rem}
nav.tabs{max-width:74rem;margin:0 auto;padding:0 .55rem;display:flex;gap:.15rem;
  overflow-x:auto;scrollbar-width:none}
nav.tabs::-webkit-scrollbar{display:none}
nav.tabs a{display:block;padding:.55rem .75rem;min-height:2.75rem;
  color:var(--muted);text-decoration:none;font-size:.92rem;white-space:nowrap;
  border-bottom:2px solid transparent}
nav.tabs a:hover{color:var(--ink)}
nav.tabs a.on{color:var(--accent);border-bottom-color:var(--accent);font-weight:600}

main{max-width:74rem;margin:0 auto;padding:.9rem;display:grid;gap:.9rem;
  grid-template-columns:repeat(auto-fit,minmax(20rem,1fr))}
.card{background:var(--panel);border:1px solid var(--line);border-radius:.6rem;
  padding:.85rem 1rem;min-width:0;overflow-wrap:anywhere}
.card.wide{grid-column:1/-1}
h2{font-size:1rem;margin:0 0 .5rem;letter-spacing:.01em}
p.sub,.sub{color:var(--muted);font-size:.85rem;margin:.15rem 0 .6rem}
.empty{color:var(--muted);font-size:.88rem;margin:.3rem 0;font-style:italic}
a{color:var(--accent)}
code{background:var(--code-bg);border-radius:.3rem;padding:.05rem .3rem;
  font:.86em ui-monospace,SFMono-Regular,Menlo,monospace}

/* verdict: the three-second read, before any number */
.verdict{grid-column:1/-1;background:var(--panel);border:1px solid var(--line);
  border-left:.28rem solid var(--line);border-radius:.6rem;padding:.75rem 1rem}
.verdict.ok{border-left-color:var(--ok)}
.verdict.warn{border-left-color:var(--warn)}
.verdict.bad{border-left-color:var(--bad)}
.verdict p{margin:0;font-size:1.05rem;line-height:1.45;text-wrap:pretty}
.verdict .sub{margin:.35rem 0 0}

.tiles{grid-column:1/-1;display:grid;gap:.55rem;
  grid-template-columns:repeat(auto-fit,minmax(8.5rem,1fr))}
.tile{border:1px solid var(--line);border-radius:.55rem;padding:.55rem .7rem;
  background:var(--panel);text-decoration:none;color:inherit;display:block}
a.tile:hover{border-color:var(--accent)}
.tile .n{font-size:1.45rem;font-weight:650;display:block;line-height:1.2;
  font-variant-numeric:tabular-nums}
.tile .l{font-size:.8rem;color:var(--muted)}
.tile.ok .n{color:var(--ok)} .tile.warn .n{color:var(--warn)}
.tile.bad .n{color:var(--bad)} .tile.info .n{color:var(--info)}

.badge{display:inline-block;font-size:.75rem;font-weight:600;letter-spacing:.02em;
  padding:.08rem .5rem;border-radius:99px;white-space:nowrap}
.badge.ok{color:var(--ok);background:var(--ok-bg)}
.badge.warn{color:var(--warn);background:var(--warn-bg)}
.badge.bad{color:var(--bad);background:var(--bad-bg)}
.badge.info{color:var(--info);background:var(--info-bg)}
.badge.muted{color:var(--muted);background:var(--code-bg)}
.dot{display:inline-block;width:.5rem;height:.5rem;border-radius:50%;
  margin-right:.35rem;vertical-align:.05rem;background:var(--muted)}
.dot.ok{background:var(--ok)} .dot.warn{background:var(--warn)}
.dot.bad{background:var(--bad)} .dot.info{background:var(--info)}

/* a workload/service block: wraps on a phone, no horizontal scroll */
.row{border-top:1px solid var(--line);padding:.6rem 0}
.row:first-of-type{border-top:none}
.rh{font-size:.98rem;line-height:1.4;text-wrap:pretty}
.rh strong{font-weight:650}
.rm{color:var(--muted);font-size:.83rem;margin-top:.2rem;
  display:flex;flex-wrap:wrap;gap:.15rem .6rem;align-items:center;
  font-variant-numeric:tabular-nums}
.rc{margin-top:.45rem;display:flex;flex-wrap:wrap;gap:.35rem}
.row.warn{background:color-mix(in srgb,var(--warn) 7%,transparent);
  border-radius:.4rem;padding-left:.5rem;padding-right:.5rem}
.row.bad{background:color-mix(in srgb,var(--bad) 7%,transparent);
  border-radius:.4rem;padding-left:.5rem;padding-right:.5rem}

.meter{height:.32rem;border-radius:99px;background:var(--code-bg);
  margin:.35rem 0 .1rem;overflow:hidden}
.meter i{display:block;height:100%;border-radius:99px;background:var(--muted)}
.meter.ok i{background:var(--ok)} .meter.warn i{background:var(--warn)}
.meter.bad i{background:var(--bad)}
.meter.open{opacity:.35}

table{border-collapse:collapse;width:100%;font-size:.88rem}
.tablewrap{overflow-x:auto}
th,td{text-align:left;padding:.3rem .45rem;border-bottom:1px solid var(--line);
  vertical-align:top}
th{color:var(--muted);font-weight:500;font-size:.8rem}
table.kv th{white-space:nowrap;width:10rem}
tr:last-child th,tr:last-child td{border-bottom:none}

ul.links{list-style:none;padding:0;margin:0}
ul.links li{padding:.45rem 0;border-bottom:1px solid var(--line)}
ul.links li:last-child{border-bottom:none}
ul.links a{text-decoration:none;font-weight:550}
ul.links a:hover{text-decoration:underline}

.act{font:inherit;font-size:.85rem;padding:.35rem .8rem;border-radius:.4rem;
  border:1px solid var(--line);background:var(--bg);color:var(--ink);cursor:pointer;
  min-height:2.4rem;display:inline-flex;align-items:center;text-decoration:none}
.act:hover{border-color:var(--accent)}
.act.danger:hover{border-color:var(--bad);color:var(--bad)}
.act[disabled]{opacity:.4;cursor:not-allowed}
input.filter{width:100%;padding:.5rem .7rem;margin:.1rem 0 .6rem;font:inherit;
  font-size:.92rem;border:1px solid var(--line);border-radius:.45rem;
  background:var(--bg);color:var(--ink);min-height:2.6rem}
.group{margin-top:.9rem}
.group:first-of-type{margin-top:.2rem}
.group>h3{font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;
  color:var(--muted);margin:0 0 .1rem;font-weight:600}
/* On a wide screen a one-per-line list of 72 units is a pointless scroll and
   the right two thirds of the viewport sit empty. Columns, not smaller type. */
.group.cols{display:grid;gap:0 1.6rem;
  grid-template-columns:repeat(auto-fit,minmax(23rem,1fr))}
.group.cols>h3{grid-column:1/-1}
#log{max-height:13rem;overflow:auto;font-size:.85rem;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
#log div{padding:.15rem 0;border-bottom:1px solid var(--line)}
footer{max-width:74rem;margin:.6rem auto 1.4rem;padding:0 .9rem;
  color:var(--muted);font-size:.8rem}
@media(max-width:32rem){
  main{padding:.6rem;gap:.6rem;grid-template-columns:minmax(0,1fr)}
  .card{padding:.75rem .8rem}
  .tiles{grid-template-columns:repeat(auto-fit,minmax(7rem,1fr))}
}
"""

SHELL_SCRIPT = """
<script>
/* Theme and reading size persist per browser; both default to the system.
   Frontend links carry a port only, so they follow whichever host you reached
   the hub on (loopback from the desktop, the tailnet address from the phone).
   Everything else on this page is server-rendered and needs no script. */
(function(){
  var t = localStorage.getItem('hub-theme');
  if (t) document.documentElement.dataset.theme = t;
  var f = localStorage.getItem('hub-fs');
  if (f) document.documentElement.style.setProperty('--fs', f);
})();
function tgl(){
  var d = document.documentElement;
  var dark = d.dataset.theme
    ? d.dataset.theme === 'dark'
    : matchMedia('(prefers-color-scheme: dark)').matches;
  d.dataset.theme = dark ? 'light' : 'dark';
  localStorage.setItem('hub-theme', d.dataset.theme);
}
function fs(step){
  var d = document.documentElement;
  var now = parseFloat(getComputedStyle(d).fontSize) || 17;
  var next = Math.max(14, Math.min(24, now + step)) + 'px';
  d.style.setProperty('--fs', next);
  localStorage.setItem('hub-fs', next);
}
document.querySelectorAll('a[data-port]').forEach(function(a){
  a.href = location.protocol + '//' + location.hostname + ':' + a.dataset.port + '/';
});
var filter = document.getElementById('filter');
if (filter) filter.addEventListener('input', function(){
  var needle = filter.value.toLowerCase();
  document.querySelectorAll('[data-search]').forEach(function(el){
    el.hidden = needle !== '' && el.dataset.search.indexOf(needle) === -1;
  });
  document.querySelectorAll('.group').forEach(function(group){
    var rows = group.querySelectorAll('[data-search]');
    var shown = Array.prototype.filter.call(rows, function(r){ return !r.hidden; });
    group.hidden = rows.length > 0 && shown.length === 0;
  });
});
</script>
"""

ACTION_SCRIPT = """
<script>
// The only privileged client-side logic on the hub. All state above is
// server-rendered; this drives the ops-reducer's bounded action API
// (/ops/v1/actions), which enforces expected_revision, idempotency keys, and
// per-target admission on its own side. There is no second control plane and
// no shell-out from this page.
function hublog(message, tone){
  var el = document.getElementById('log');
  if (!el) return;
  var first = el.firstElementChild;
  if (first && first.dataset.placeholder) el.textContent = '';
  var line = document.createElement('div');
  if (tone) line.className = tone;
  line.textContent = new Date().toLocaleTimeString() + '  ' + message;
  el.prepend(line);
}
async function act(verb, kind, id, button){
  var label = verb + ' ' + id;
  if (!confirm(label + '?\\n\\nThis posts a bounded action to the ops-reducer and leaves a receipt.')) return;
  button.disabled = true;
  try {
    var snap = await fetch('/ops/v1/snapshot', {headers: {'Accept': 'application/json'}});
    if (!snap.ok) throw new Error('snapshot ' + snap.status);
    var revision = (await snap.json()).sequence;
    var target = {};
    target[kind] = id;
    var res = await fetch('/ops/v1/actions', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        action: verb,
        target: target,
        expected_revision: revision,
        idempotency_key: 'hub-' + verb + '-' + id + '-' + Date.now(),
        operator_reason: 'operator action from the hub control panel',
        parameters: {}
      })
    });
    var receipt = await res.json();
    if (!res.ok) throw new Error(receipt.error || ('HTTP ' + res.status));
    hublog(label + ' accepted, receipt ' + receipt.receipt_id, 'ok');
    setTimeout(function(){ location.reload(); }, 2500);
  } catch (error) {
    hublog('REFUSED ' + label + ': ' + error.message, 'bad');
  } finally {
    button.disabled = false;
  }
}
</script>
"""


PAGES = (
    ("/", "estate"),
    ("/work/", "work"),
    ("/services/", "services"),
    ("/ai/", "ai"),
    ("/shaders/", "shaders"),
    ("/reports/", "reports"),
)


def nav(active: str) -> str:
    items = "".join(
        f'<a href="{esc(href)}" class="{"on" if href == active else ""}">{esc(label)}</a>'
        for href, label in PAGES
    )
    return f'<nav class="tabs">{items}</nav>'


def page(
    title: str,
    host: str,
    chips: list[str],
    active: str,
    body: str,
    footnote: str = "",
    tail: str = "",
) -> str:
    chip_html = "".join(f'<span class="chip">{esc(chip)}</span>' for chip in chips)
    note = footnote or (
        "Server-rendered by <code>sinnix-ops-reducer</code> on request, tailnet "
        "only. State is a snapshot, not a live stream — reload for a newer one."
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{esc(title)}</title><style>{STYLE}</style></head>
<body>
<header class="page">
<div class="hbar"><h1><b>{esc(host)}</b> {esc(title)}</h1>{chip_html}
<span class="spacer"></span>
<button class="hbtn" onclick="fs(-1)" title="smaller text">A−</button>
<button class="hbtn" onclick="fs(1)" title="larger text">A+</button>
<button class="hbtn" onclick="tgl()" title="switch between light and dark">theme</button></div>
{nav(active)}
</header>
<main>{body}</main>
<footer>{note}</footer>
{SHELL_SCRIPT}
{tail}
</body></html>
"""


def log_card() -> str:
    return card(
        "Action log",
        '<div id="log"><div class="sub" data-placeholder="1">'
        "No actions this browser session. The durable record is "
        '<a href="/ops/v1/receipts">/ops/v1/receipts</a>.</div></div>',
        wide=True,
    )

