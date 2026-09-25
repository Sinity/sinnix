import json
import runpy
import stat
import subprocess
from html.parser import HTMLParser
from pathlib import Path

MODULE = runpy.run_path(
    str(Path(__file__).parents[3] / "scripts/sinnix-file-catalog-report")
)
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
        "id": "example",
        "kind": "file",
        "current_path": str(tmp_path / "sample.txt"),
        "title": '<img src=x onerror="alert(1)">',
        "description": '</script><script>alert("unsafe")</script>',
        "inspections": [
            {"method": "excerpt", "scope": "first paragraph", "basis": "read"}
        ],
        "relations": [],
    }
    catalog = {"schema_version": 1, "updated_at": "2026-01-01", "assets": [asset]}
    page = MODULE["render"](
        catalog, tmp_path / "catalog.json", TEMPLATE, "render example"
    )
    assert "<img src=x" not in page
    parser = ScriptCollector()
    parser.feed(page)
    assert len(parser.scripts) == 3
    data = next(
        script
        for script in parser.scripts
        if script["attributes"].get("id") == "catalog-source"
    )
    assert json.loads(data["text"]) == catalog
    assert "first paragraph" in page
    assert 'id="asset-example"' in page


def test_dangling_relationship_is_not_rendered_as_valid(tmp_path):
    import pytest

    catalog = {
        "schema_version": 1,
        "updated_at": "2026-01-01",
        "assets": [{"id": "sample", "relations": [{"target_id": "missing"}]}],
    }
    with pytest.raises(ValueError, match="dangling relation"):
        MODULE["render"](catalog, tmp_path / "catalog.json", TEMPLATE, "render example")


def test_cli_publishes_private_report(tmp_path):
    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps({"schema_version": 1, "updated_at": "2026-01-01", "assets": []}),
        encoding="utf-8",
    )
    template = tmp_path / "template.html"
    template.write_text(TEMPLATE, encoding="utf-8")
    output = tmp_path / "reports" / "catalog.html"
    script = Path(__file__).parents[3] / "scripts/sinnix-file-catalog-report"
    result = subprocess.run(
        [
            str(script),
            "--catalog",
            str(catalog),
            "--template",
            str(template),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(output)
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert "File inspection catalog" in output.read_text(encoding="utf-8")


def test_collection_facets_coverage_and_proposals_are_visible(tmp_path):
    asset = {
        "id": "collection", "kind": "collection", "current_path": str(tmp_path),
        "title": "Field notes", "description": "Observations from expeditions",
        "inspections": [{"method": "collection_survey", "scope": "Two notes", "basis": "Read pages"}],
        "facets": {"topic": "geology"},
        "coverage": {"status": "sampled", "scope": "Two of five notes", "unit": "files",
                     "discovered_count": 5, "inspected_count": 2},
        "organization": {"action": "navigate", "rationale": "Connect to the research index"},
        "utility": ["Which sites were observed?"],
        "related_paths": [{"path": str(tmp_path / "index.md"), "type": "index", "basis": "Explicit link"}],
    }
    page = MODULE["render"]({"schema_version": 1, "updated_at": "2026-01-01", "assets": [asset]},
                            tmp_path / "catalog.json", TEMPLATE, "render")
    assert 'data-kind="collection"' in page
    assert 'data-coverage="sampled"' in page
    assert "2 / 5 files" in page
    assert "geology" in page
    assert "Connect to the research index" in page
    assert "Which sites were observed?" in page
