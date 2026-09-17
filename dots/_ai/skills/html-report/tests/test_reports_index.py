from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import pytest

SCRIPT = Path(__file__).parents[1] / "generators" / "reports-index.py"
spec = importlib.util.spec_from_file_location("reports_index_under_test", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def config(root, path, **extra):
    data = {"schema_version": 1, "groups": [{"title": "A subject", "items": [{"title": "A resource", "path": str(path), **extra}]}]}
    (root / "navigation.json").write_text(json.dumps(data))


def test_plain_report_index_still_works(tmp_path):
    (tmp_path / "report.html").write_text("<title>Example</title><p>Discuss superseded-by metadata.</p>")
    out = tmp_path / "index.html"
    assert mod.build(tmp_path, out) == 0
    assert "Example" in out.read_text()
    assert 'class=sup' not in out.read_text()


@pytest.mark.parametrize("markup", [
    '<meta content="new.html" name="superseded-by">',
    '<html data-superseded-by="new.html">',
    '<link rel="superseded-by" href="new.html">',
    '<dl><dt>Superseded by</dt><dd><a href="new.html">New report</a></dd></dl>',
])
def test_only_explicit_supersession_metadata_marks_a_report(markup):
    assert mod.explicitly_superseded(markup)


@pytest.mark.parametrize("markup", [
    '<p>The words superseded-by appear in this discussion.</p>',
    '<dt>superseded-by</dt><dd>—</dd>',
    '<meta name="superseded-by" content="">',
])
def test_mentions_and_empty_supersession_are_not_a_status(markup):
    assert not mod.explicitly_superseded(markup)


def test_navigation_is_escaped_and_does_not_read_payloads(tmp_path):
    target = tmp_path / "a # unusual.md"
    target.write_text("PRIVATE PAYLOAD MUST NOT BE COPIED")
    config(tmp_path, target, note="<script>bad()</script>")
    out = tmp_path / "index.html"
    md = tmp_path / "nav.md"
    assert mod.build(tmp_path, out, md) == 0
    page = out.read_text()
    assert "&lt;script&gt;" in page
    assert "PRIVATE PAYLOAD MUST NOT BE COPIED" not in page
    assert "a%20%23%20unusual.md" in page
    assert md.exists()


def test_external_link_uses_file_uri_and_copy_path(tmp_path):
    root = tmp_path / "reports"
    root.mkdir()
    target = tmp_path / "outside.md"
    target.write_text("outside")
    config(root, target)
    markup, groups = mod.render_navigation(root, root/"index.html")
    assert target.as_uri() in markup
    assert 'class="local-link"' in markup
    assert 'class="copy-path"' in markup
    assert groups[0]["items"][0]["status"] == "available"


def test_unprobed_collection_does_not_touch_its_path(tmp_path, monkeypatch):
    target = tmp_path / "offline" / "collection"
    config(tmp_path, target, probe=False)
    original = Path.stat
    def guarded(self, *args, **kwargs):
        if self == target:
            raise AssertionError("Offline collection was probed")
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Path, "stat", guarded)
    _, groups = mod.render_navigation(tmp_path, tmp_path/"index.html")
    assert groups[0]["items"][0]["status"] == "not-probed"


def test_missing_resource_is_not_reported_as_an_empty_collection(tmp_path):
    config(tmp_path, tmp_path/"absent")
    _, groups = mod.render_navigation(tmp_path, tmp_path/"index.html")
    assert groups[0]["items"][0]["status"] == "missing"


def test_invalid_navigation_cannot_overwrite_good_index(tmp_path):
    out = tmp_path / "index.html"
    out.write_text("existing index")
    config(tmp_path, "javascript:alert(1)")
    with pytest.raises(ValueError):
        mod.build(tmp_path, out)
    assert out.read_text() == "existing index"


def test_rebuild_does_not_index_itself(tmp_path):
    out = tmp_path / "index.html"
    out.write_text("<title>DO NOT INDEX ME</title>")
    mod.build(tmp_path, out)
    assert "DO NOT INDEX ME" not in out.read_text()


def test_table_has_a_separate_accessible_horizontal_scroll_region(tmp_path):
    (tmp_path / "long-report.html").write_text("<title>" + "UnbrokenLongTitle" * 30 + "</title>")
    out = tmp_path / "index.html"
    assert mod.build(tmp_path, out) == 0
    page = out.read_text()
    assert '<div class="table-wrap" role="region" aria-label="Published reports" tabindex="0"><table>' in page
    assert '</table></div>' in page
    assert '.table-wrap{max-width:100%;overflow-x:auto}' in page
