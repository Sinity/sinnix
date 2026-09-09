import json
import runpy
from html.parser import HTMLParser
from pathlib import Path


MODULE = runpy.run_path(str(Path(__file__).parents[3] / "scripts/sinnix-file-catalog-report"))
TEMPLATE = '<html data-accent=""><head><title>Example</title></head><body><script>/* shared controls */</script></body></html>'


class ScriptCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.current = {"attributes": dict(attrs), "text": ""}

    def handle_endtag(self, tag):
        if tag == "script":
            self.scripts.append(self.current)
            self.current = None

    def handle_data(self, data):
        if self.current is not None:
            self.current["text"] += data


def test_descriptions_are_text_and_embedded_data_round_trips(tmp_path):
    asset = {
        "id": "example", "kind": "file", "current_path": str(tmp_path / 'sample.txt'),
        "title": '<img src=x onerror="alert(1)">',
        "description": '</script><script>alert("unsafe")</script>',
        "inspections": [{"method": "excerpt", "scope": "first paragraph", "basis": "read"}],
        "relations": [],
    }
    catalog = {"schema_version": 1, "updated_at": "2026-01-01", "assets": [asset]}
    page = MODULE['render'](catalog, tmp_path / 'catalog.json', TEMPLATE, 'render example')
    assert '<img src=x' not in page
    parser = ScriptCollector()
    parser.feed(page)
    assert len(parser.scripts) == 3
    data = next(script for script in parser.scripts if script['attributes'].get('id') == 'catalog-source')
    assert json.loads(data['text']) == catalog
    assert 'first paragraph' in page
    assert 'id="asset-example"' in page


def test_dangling_relationship_is_not_rendered_as_valid(tmp_path):
    import pytest

    catalog = {
        "schema_version": 1, "updated_at": "2026-01-01",
        "assets": [{"id": "sample", "relations": [{"target_id": "missing"}]}],
    }
    with pytest.raises(ValueError, match='dangling relation'):
        MODULE['render'](catalog, tmp_path / 'catalog.json', TEMPLATE, 'render example')
