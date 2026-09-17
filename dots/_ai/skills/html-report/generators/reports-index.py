#!/usr/bin/env python3
"""Generate index.html over a directory of html-report artifacts.

Usage: reports-index.py <reports-dir> [--out index.html] [--navigation-markdown PATH]

Optional navigation.json adds subject links without copying their payloads.
External collection links can set probe=false to avoid waking their disks.

Reads every *.html recursively (the output index itself and
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
import json
import stat
import tempfile
from html.parser import HTMLParser
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
STATUS_RE = re.compile(
    r'class="badge[^"]*">\s*(notes|draft|in-progress|finished|plan[^<]*|living[^<]*)\s*<',
    re.I,
)
GENERATED_RE = re.compile(r'generated</dt>\s*<dd>\s*<time[^>]*datetime="([^"]+)"')
ANY_TIME_RE = re.compile(r'<time[^>]*class="age"[^>]*datetime="([^"]+)"')
ACCENT_RE = re.compile(r'<html[^>]*data-accent="([a-z]+)"')
DATE_IN_NAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")



def atomic_text(path: Path, text: str) -> None:
    """Publish a complete UTF-8 page without exposing a partially written index."""
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    fd, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), mode)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def explicitly_superseded(text: str) -> bool:
    """A mention in prose is not a declaration about the report itself."""
    class Metadata(HTMLParser):
        found = False

        def handle_starttag(self, tag, attrs):
            data = dict(attrs)
            if tag == "meta" and data.get("name", "").lower() in (
                "superseded-by", "report-superseded-by", "report:superseded-by"
            ):
                self.found |= bool((data.get("content") or "").strip())
            if tag == "html":
                self.found |= bool((data.get("data-superseded-by") or "").strip())
            if tag == "link" and "superseded-by" in (data.get("rel") or "").split():
                self.found |= bool((data.get("href") or "").strip())

    parser = Metadata()
    parser.feed(text)
    # The existing report template also permits a metadata definition list.
    match = re.search(r"<dt\b[^>]*>\s*superseded[- ]by\s*</dt>\s*<dd\b[^>]*>(.*?)</dd>", text, re.I | re.S)
    target = html_mod.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip() if match else ""
    return parser.found or target.casefold() not in ("", "—", "-", "none", "n/a", "unknown", "not applicable")


def render_navigation(reports_dir: Path, out: Path) -> tuple[str, list[dict]]:
    """Read optional links-only configuration; native resources remain authoritative.

    navigation.json may be a symlink to an independently maintained private
    manifest. probe=false avoids waking offline/automounted storage.
    """
    manifest = reports_dir / "navigation.json"
    if not manifest.exists():
        return "", []
    if manifest.stat().st_size > 1024 * 1024:
        raise ValueError("navigation.json exceeds the 1 MiB input bound")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("groups"), list):
        raise ValueError("navigation.json requires schema_version=1 and groups")
    if len(data["groups"]) > 32:
        raise ValueError("navigation.json has too many groups")
    sections, groups = [], []
    total = 0
    esc = html_mod.escape
    for group in data["groups"]:
        if not isinstance(group, dict) or not isinstance(group.get("title"), str) or not isinstance(group.get("items"), list):
            raise ValueError("navigation groups require a title and items")
        total += len(group["items"])
        if total > 512:
            raise ValueError("navigation.json has too many destinations")
        items, rendered = [], []
        for item in group["items"]:
            if not isinstance(item, dict) or not isinstance(item.get("title"), str) or not isinstance(item.get("path"), str):
                raise ValueError("navigation items require title and absolute filesystem path")
            raw_path = item["path"]
            if any(ord(ch) < 32 for ch in raw_path) or not Path(raw_path).is_absolute() or ".." in Path(raw_path).parts:
                raise ValueError("navigation paths must be absolute, normalized filesystem paths")
            target = Path(raw_path)
            status = "not-probed"
            if item.get("probe", True):
                try:
                    target.stat()
                    status = "available"
                except FileNotFoundError:
                    status = "missing"
                except OSError:
                    status = "unavailable"
            role, note = str(item.get("role", "resource")), str(item.get("note", ""))
            try:
                target.relative_to(reports_dir)
                href, cls = quote(os.path.relpath(target, out.parent)), ""
            except ValueError:
                href, cls = target.as_uri(), "local-link"
            items.append({**item, "status": status})
            rendered.append(
                f'<li class="nav-item" data-search="{esc(" ".join((group["title"], item["title"], raw_path, role, note)).casefold(), quote=True)}">'
                f'<a class="{cls}" href="{esc(href, quote=True)}">{esc(item["title"])}</a> '
                f'<span class="nav-role">{esc(role)}</span>'
                f'<button type="button" class="copy-path" data-path="{esc(raw_path, quote=True)}" aria-label="Copy path: {esc(item["title"], quote=True)}">Copy path</button>'
                f'<div class="nav-path">{esc(raw_path)}</div>'
                + (f'<div class="nav-note">{esc(note)}</div>' if note else '')
                + (f'<span class="nav-availability">{esc(status)} at generation</span>' if status != "available" else '')
                + '</li>'
            )
        groups.append({"title": group["title"], "items": items})
        sections.append(f'<details class="nav-group"><summary>{esc(group["title"])} <small>{len(items)}</small></summary><ul>{"".join(rendered)}</ul></details>')
    if not sections:
        return "", groups
    return (
        '<section aria-label="Subject navigation"><h2>Start with a subject</h2>'
        '<p class="nav-help">These are links to existing owners, not copied task or source records. '
        'In the web viewer, use Copy path for files outside reports. Open this index locally for direct file links. '
        'Availability is checked when generated; external disks marked not-probed are not touched.</p>'
        '<div class="nav-grid">' + ''.join(sections) + '</div><p id="copy-result" role="status" aria-live="polite"></p></section>', groups
    )


def navigation_markdown(groups: list[dict], destination: Path) -> str:
    lines = ["# Subject navigation", "", "Generated from the private navigation manifest. Links select existing material; they do not replace its owning application or prove a historical plan was executed.", ""]
    for group in groups:
        lines += ["## " + group["title"], ""]
        for item in group["items"]:
            label = item["title"].replace("[", "\\[").replace("]", "\\]")
            href = quote(os.path.relpath(item["path"], destination.parent))
            lines.append(f'- [{label}]({href}) — {item.get("role", "resource")}. {item.get("note", "")}')
        lines.append("")
    return "\n".join(lines) + "\n"


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
        "superseded": explicitly_superseded(text),
        "accent": accent,
        "size_kb": p.stat().st_size // 1024,
        "mtime": dt.datetime.fromtimestamp(p.stat().st_mtime),
    }


def build(reports_dir: Path, out: Path, navigation_out: Path | None = None) -> int:
    nav_html, nav_groups = render_navigation(reports_dir, out)
    files = sorted(
        [
            p
            for p in reports_dir.rglob("*.html")
            if p.resolve() != out.resolve() and not p.name.endswith(".pl.html")
        ],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    rows = []
    for p in files:
        try:
            rows.append(report_meta(p))
        except Exception as e:  # noqa: BLE001 - index must not die on one bad file
            print(f"warn: {p.name}: {e}", file=sys.stderr)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    trs = []
    for r in rows:
        badge = (
            "<span class='badge info'>superseded</span>"
            if r["superseded"]
            else f"<span class='badge ok'>{html_mod.escape(r['status'])}</span>"
            if r["status"]
            else ""
        )
        accent = f"<span class='chip'>{r['accent']}</span>" if r["accent"] else ""
        trs.append(
            f"<tr{' class=sup' if r['superseded'] else ''}>"
            f"<td><a href='{html_mod.escape(quote(os.path.relpath(r['path'], out.parent)))}'>{html_mod.escape(r['title'])}</a></td>"
            f"<td data-v='{int(r['mtime'].timestamp())}'>{r['mtime'].strftime('%Y-%m-%d %H:%M')}</td>"
            f"<td>{badge}</td><td>{accent}</td>"
            f"<td data-v='{r['size_kb']}'>{r['size_kb']} K</td></tr>"
        )
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
.nav-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,19rem),1fr));gap:.55rem;margin:1rem 0}}
.nav-group{{background:var(--panel);border:1px solid var(--line);border-radius:.4rem;padding:.45rem .7rem;font-size:.88rem}}
.nav-group summary{{cursor:pointer;font-weight:650}} .nav-group small,.nav-role{{color:var(--muted);font-weight:400;font-size:.75rem}}
.nav-group ul{{padding:0;list-style:none;margin:.4rem 0}} .nav-item{{border-top:1px solid var(--line);padding:.55rem 0}}
.nav-path{{font: .7rem/1.4 ui-monospace,monospace;overflow-wrap:anywhere;color:var(--muted);margin:.2rem 0}}
.nav-note,.nav-help,.nav-availability{{font-size:.78rem;color:var(--muted)}} .nav-help{{max-width:65rem}}
.copy-path{{float:right;font-size:.7rem;padding:.15rem .35rem;background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:.25rem;cursor:pointer}}
[hidden]{{display:none!important}} h2{{font-size:1.05rem}} [aria-disabled=true]{{color:var(--ink);text-decoration:none;cursor:default}}
#copy-result{{font-size:.8rem;min-height:1.2em}}
</style></head>
<body><main>
<h1>Reports — {reports_dir}</h1>
<p>{len(rows)} reports · generated {now} · superseded rows dimmed</p>
<input id="filter" aria-label="Search subjects and reports" placeholder="Find a subject, file, project or report…  /" oninput="filterAll(this.value)">
{nav_html}
<h2>Published reports</h2>
<table><thead><tr><th>report</th><th>modified</th><th>status</th><th>identity</th><th>size</th></tr></thead>
<tbody>{"".join(trs)}</tbody></table>
<footer>regenerate: <code>python3 generators/reports-index.py {reports_dir}</code>
(html-report skill) — every row measured from the files at generation time</footer>
</main>
<script>
function filterAll(value){{
 const q=value.trim().toLowerCase();
 document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));
 document.querySelectorAll('.nav-item').forEach(r=>r.hidden=!r.dataset.search.includes(q));
 document.querySelectorAll('.nav-group').forEach(g=>{{g.hidden=![...g.querySelectorAll('.nav-item')].some(r=>!r.hidden);g.open=Boolean(q)&&!g.hidden}});
}}
if(location.protocol!=='file:')document.querySelectorAll('.local-link').forEach(a=>{{a.removeAttribute('href');a.setAttribute('aria-disabled','true');a.title='Use Copy path, or open this index locally'}});
document.querySelectorAll('.copy-path').forEach(b=>b.addEventListener('click',async()=>{{
 const result=document.getElementById('copy-result');
 try{{if(navigator.clipboard&&navigator.clipboard.writeText)await navigator.clipboard.writeText(b.dataset.path);
 else{{const t=document.createElement('textarea');t.value=b.dataset.path;document.body.appendChild(t);t.select();const ok=document.execCommand('copy');t.remove();if(!ok)throw new Error('Clipboard unavailable')}}
 result.textContent='Copied: '+b.dataset.path;
 }}catch(e){{result.textContent='Copy this path: '+b.dataset.path}}
}}));
document.addEventListener('keydown',e=>{{const f=document.getElementById('filter');if(e.key==='/'&&!['INPUT','TEXTAREA'].includes(document.activeElement.tagName)){{e.preventDefault();f.focus()}}if(e.key==='Escape'&&document.activeElement===f){{f.value='';filterAll('');f.blur()}}}});
document.querySelectorAll('th').forEach((th,i)=>th.addEventListener('click',()=>{{
  const tb=th.closest('table');const dir=th.dataset.d=th.dataset.d==='a'?'d':'a';
  const val=td=>td.dataset.v!==undefined?+td.dataset.v:td.textContent.trim();
  [...tb.tBodies[0].rows].sort((r1,r2)=>{{const a=val(r1.cells[i]),b=val(r2.cells[i]);
    const c=(typeof a=='number'&&typeof b=='number')?a-b:String(a).localeCompare(String(b));
    return dir==='a'?c:-c}}).forEach(r=>tb.tBodies[0].appendChild(r))}}));
</script>
</body></html>
"""
    atomic_text(out, page)
    if navigation_out is not None:
        atomic_text(navigation_out, navigation_markdown(nav_groups, navigation_out))
    print(f"wrote {out} ({len(rows)} reports)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("reports_dir", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--navigation-markdown", type=Path, default=None, help="Also publish a Markdown projection of navigation.json")
    args = ap.parse_args()
    out = args.out or (args.reports_dir / "index.html")
    return build(args.reports_dir, out, args.navigation_markdown)


if __name__ == "__main__":
    raise SystemExit(main())
