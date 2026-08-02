#!/usr/bin/env python3
"""Generate index.html over a directory of html-report artifacts.

Usage: reports-index.py <reports-dir> [--out index.html]

Reads every *.html in the directory (non-recursive; index.html itself and
*.pl.html translations are grouped under their base report), extracts title,
dates, status, and supersession metadata from the report's own markup, and
emits a single self-contained index page following the skill's template
conventions (both themes, no external requests, newest first).

Everything shown is measured from the files; the generator prints its own
regenerate command in the page footer. Findings-as-predicates: a report is
flagged stale/superseded only while the condition holds.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html as html_mod
import re
import sys
from pathlib import Path

TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
STATUS_RE = re.compile(r'class="badge[^"]*">\s*(notes|draft|in-progress|finished|plan[^<]*|living[^<]*)\s*<', re.I)
GENERATED_RE = re.compile(r'generated</dt>\s*<dd>\s*<time[^>]*datetime="([^"]+)"')
ANY_TIME_RE = re.compile(r'<time[^>]*class="age"[^>]*datetime="([^"]+)"')
SUPERSEDED_RE = re.compile(r"superseded[- ]by", re.I)
ACCENT_RE = re.compile(r'<html[^>]*data-accent="([a-z]+)"')
DATE_IN_NAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def report_meta(p: Path) -> dict:
    text = p.read_text(errors="replace")
    title_m = TITLE_RE.search(text)
    title = html_mod.unescape(title_m.group(1).strip()) if title_m else p.stem
    gen = None
    m = GENERATED_RE.search(text) or ANY_TIME_RE.search(text)
    if m:
        gen = m.group(1)
    name_date = DATE_IN_NAME_RE.search(p.name)
    accent = (ACCENT_RE.search(text) or [None, ""])[1]
    return {
        "path": p,
        "title": title,
        "generated": gen or (name_date.group(1) if name_date else ""),
        "status": (STATUS_RE.search(text) or [None, ""])[1],
        "superseded": bool(SUPERSEDED_RE.search(text)),
        "accent": accent,
        "size_kb": p.stat().st_size // 1024,
        "mtime": dt.datetime.fromtimestamp(p.stat().st_mtime),
    }


def build(reports_dir: Path, out: Path) -> int:
    files = sorted(
        [p for p in reports_dir.glob("*.html")
         if p.name != out.name and not p.name.endswith(".pl.html")],
        key=lambda p: p.stat().st_mtime, reverse=True)
    rows = []
    for p in files:
        try:
            rows.append(report_meta(p))
        except Exception as e:  # noqa: BLE001 - index must not die on one bad file
            print(f"warn: {p.name}: {e}", file=sys.stderr)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    trs = []
    for r in rows:
        badge = ("<span class='badge info'>superseded</span>" if r["superseded"]
                 else f"<span class='badge ok'>{html_mod.escape(r['status'])}</span>" if r["status"] else "")
        accent = f"<span class='chip'>{r['accent']}</span>" if r["accent"] else ""
        trs.append(
            f"<tr{' class=sup' if r['superseded'] else ''}>"
            f"<td><a href='{html_mod.escape(r['path'].name)}'>{html_mod.escape(r['title'])}</a></td>"
            f"<td data-v='{int(r['mtime'].timestamp())}'>{r['mtime'].strftime('%Y-%m-%d %H:%M')}</td>"
            f"<td>{badge}</td><td>{accent}</td>"
            f"<td data-v='{r['size_kb']}'>{r['size_kb']} K</td></tr>")
    page = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reports index — {reports_dir}</title>
<style>
:root{{--bg:#f6f7f9;--panel:#fff;--ink:#1a2129;--muted:#5b6773;--line:#dde3e9;--accent:#2563eb;
--ok:#0f7b46;--ok-bg:#e2f5eb;--info:#1d4ed8;--info-bg:#e3ebfd}}
@media (prefers-color-scheme: dark){{:root{{--bg:#12161b;--panel:#1a2027;--ink:#e6ebf0;
--muted:#94a1ad;--line:#2b333c;--accent:#5b8def;--ok:#4cc98a;--ok-bg:#12301f;
--info:#7ea6f4;--info-bg:#16223b}}}}
:root[data-theme=dark]{{--bg:#12161b;--panel:#1a2027;--ink:#e6ebf0;--muted:#94a1ad;
--line:#2b333c;--accent:#5b8def;--ok:#4cc98a;--ok-bg:#12301f;--info:#7ea6f4;--info-bg:#16223b}}
:root[data-theme=light]{{--bg:#f6f7f9;--panel:#fff;--ink:#1a2129;--muted:#5b6773;
--line:#dde3e9;--accent:#2563eb;--ok:#0f7b46;--ok-bg:#e2f5eb;--info:#1d4ed8;--info-bg:#e3ebfd}}
body{{margin:0;background:var(--bg);color:var(--ink);font:17px/1.6 system-ui,sans-serif}}
main{{max-width:70rem;margin:0 auto;padding:1.2rem}}
h1{{font-size:1.3rem}}
table{{border-collapse:collapse;width:100%;font-size:.95rem;background:var(--panel);
border:1px solid var(--line);border-radius:.5rem}}
th,td{{border-bottom:1px solid var(--line);text-align:left;padding:.45rem .6rem}}
th{{color:var(--muted);font-size:.85rem;text-transform:uppercase;letter-spacing:.04em;cursor:pointer}}
td[data-v]{{text-align:right;font-variant-numeric:tabular-nums}}
tr.sup{{opacity:.55}}
a{{color:var(--accent)}}
.badge{{font-size:.8rem;font-weight:600;padding:.1rem .55rem;border-radius:99px}}
.ok{{color:var(--ok);background:var(--ok-bg)}} .info{{color:var(--info);background:var(--info-bg)}}
.chip{{font-size:.8rem;border:1px solid var(--line);border-radius:99px;padding:.05rem .5rem;color:var(--muted)}}
footer{{color:var(--muted);font-size:.85rem;padding:1rem 0}}
input{{width:100%;max-width:24rem;margin:.4rem 0;padding:.35rem .6rem;border:1px solid var(--line);
border-radius:.4rem;background:var(--bg);color:var(--ink)}}
</style></head>
<body><main>
<h1>Reports — {reports_dir}</h1>
<p>{len(rows)} reports · generated {now} · superseded rows dimmed</p>
<input placeholder="filter…" oninput="const q=this.value.toLowerCase();
document.querySelectorAll('tbody tr').forEach(r=>r.style.display=r.textContent.toLowerCase().includes(q)?'':'none')">
<table><thead><tr><th>report</th><th>modified</th><th>status</th><th>identity</th><th>size</th></tr></thead>
<tbody>{''.join(trs)}</tbody></table>
<footer>regenerate: <code>python3 generators/reports-index.py {reports_dir}</code>
(html-report skill) — every row measured from the files at generation time</footer>
</main>
<script>
document.querySelectorAll('th').forEach((th,i)=>th.addEventListener('click',()=>{{
  const tb=th.closest('table');const dir=th.dataset.d=th.dataset.d==='a'?'d':'a';
  const val=td=>td.dataset.v!==undefined?+td.dataset.v:td.textContent.trim();
  [...tb.tBodies[0].rows].sort((r1,r2)=>{{const a=val(r1.cells[i]),b=val(r2.cells[i]);
    const c=(typeof a=='number'&&typeof b=='number')?a-b:String(a).localeCompare(String(b));
    return dir==='a'?c:-c}}).forEach(r=>tb.tBodies[0].appendChild(r))}}));
</script>
</body></html>
"""
    out.write_text(page)
    print(f"wrote {out} ({len(rows)} reports)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("reports_dir", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    out = args.out or (args.reports_dir / "index.html")
    return build(args.reports_dir, out)


if __name__ == "__main__":
    raise SystemExit(main())
