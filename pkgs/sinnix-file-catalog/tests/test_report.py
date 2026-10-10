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
        "id": "collection",
        "kind": "collection",
        "current_path": str(tmp_path),
        "title": "Field notes",
        "description": "Observations from expeditions",
        "inspections": [
            {"method": "collection_survey", "scope": "Two notes", "basis": "Read pages"}
        ],
        "facets": {"topic": "geology"},
        "coverage": {
            "status": "sampled",
            "scope": "Two of five notes",
            "unit": "files",
            "discovered_count": 5,
            "inspected_count": 2,
        },
        "organization": {
            "action": "navigate",
            "rationale": "Connect to the research index",
        },
        "utility": ["Which sites were observed?"],
        "related_paths": [
            {
                "path": str(tmp_path / "index.md"),
                "type": "index",
                "basis": "Explicit link",
            }
        ],
    }
    page = MODULE["render"](
        {"schema_version": 1, "updated_at": "2026-01-01", "assets": [asset]},
        tmp_path / "catalog.json",
        TEMPLATE,
        "render",
    )
    assert 'data-kind="collection"' in page
    assert 'data-coverage="sampled"' in page
    assert "2 / 5 files" in page
    assert "geology" in page
    assert "Connect to the research index" in page
    assert "Which sites were observed?" in page


def enriched_asset(tmp_path):
    return {
        "id": "enriched",
        "kind": "file",
        "current_path": str(tmp_path / "unread-source.html"),
        "title": "A retained report",
        "description": "A bounded observation",
        "inspections": [
            {
                "method": "static",
                "scope": "Opening paragraph",
                "basis": "saved evidence",
            }
        ],
        "utility": ["Where is the source argument?"],
        "enrichment": {
            "document_type": "historical-design",
            "language": "en",
            "topics": ["reconstruction"],
            "questions": [
                "Where is the source argument?",
                "Which uncertainty remains?",
            ],
            "claims": [
                {
                    "claim": "The source proposes a design.",
                    "status": "source_statement",
                    "source_locator": "report.html:42",
                }
            ],
            "outline": [{"heading": "Limitations", "source_locator": "report.html:89"}],
            "extraction": {
                "path": str(tmp_path / "evidence.json"),
                "source_sha256": "a" * 64,
                "recipe": "static sample",
                "truncated": True,
            },
            "limitations": ["Not a current execution record."],
        },
    }


def test_enrichment_is_readable_outside_the_raw_json(tmp_path):
    asset = enriched_asset(tmp_path)
    fragment = MODULE["render_enrichment"](asset)
    assert "<pre" not in fragment and "<script" not in fragment
    assert "Useful for finding" in fragment
    assert fragment.count("Where is the source argument?") == 1
    assert "source_statement" in fragment and "report.html:42" in fragment
    assert "Inspected document outline" in fragment and "report.html:89" in fragment
    assert "Not a current execution record." in fragment
    assert "does not independently verify" in fragment


def test_enrichment_escapes_every_annotation_including_locators(tmp_path):
    asset = enriched_asset(tmp_path)
    e = asset["enrichment"]
    bad = '</script><img src=x onerror="alert(1)">'
    e["document_type"] = bad
    e["language"] = bad
    e["summary"] = bad
    e["topics"] = [bad]
    e["questions"] = [bad]
    e["claims"] = [{"claim": bad, "status": bad, "source_locator": "javascript:" + bad}]
    e["outline"] = [{"heading": bad, "source_locator": bad}]
    e["extraction"] = {
        "path": "javascript:alert(1)",
        "recipe": bad,
        "source_sha256": bad,
    }
    e["limitations"] = [bad]
    fragment = MODULE["render_enrichment"](asset)
    assert "<img " not in fragment and "</script>" not in fragment
    assert 'href="javascript:' not in fragment
    assert "&lt;img" in fragment and "Evidence locator:" in fragment


def test_rendering_does_not_open_or_stat_evidence_files(tmp_path, monkeypatch):
    asset = enriched_asset(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("renderer opened or statted a source")

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "stat", forbidden)
    monkeypatch.setattr(Path, "exists", forbidden)
    fragment = MODULE["render_enrichment"](asset)
    assert "evidence.json" in fragment and "a" * 64 in fragment


def test_unknown_enrichment_shape_survives_roundtrip(tmp_path):
    import copy

    asset = enriched_asset(tmp_path)
    asset["enrichment"] = {
        "document_type": ["legacy"],
        "claims": [None, {"unexpected": 42}],
        "questions": {"not": "list"},
        "future_field": {"opaque": "preserved"},
    }
    catalog = {"schema_version": 1, "updated_at": "2026-01-01", "assets": [asset]}
    original = copy.deepcopy(catalog)
    page = MODULE["render"](catalog, tmp_path / "catalog.json", TEMPLATE, "render")
    parser = ScriptCollector()
    parser.feed(page)
    embedded = next(
        s["text"]
        for s in parser.scripts
        if s["attributes"].get("id") == "catalog-source"
    )
    assert json.loads(embedded) == original and catalog == original
    assert "future_field" in page


def test_type_filter_reflects_only_actual_document_types(tmp_path):
    a = enriched_asset(tmp_path)
    b = {**a, "id": "plain", "enrichment": {}}
    page = MODULE["render"](
        {"schema_version": 1, "updated_at": "2026-01-01", "assets": [a, b]},
        tmp_path / "catalog.json",
        TEMPLATE,
        "render",
    )
    assert 'id="catalog-document-type"' in page
    assert '<option value="historical-design">historical-design</option>' in page
    assert 'data-document-type="historical-design"' in page
    assert 'data-document-type=""' in page


def test_absent_claim_status_or_locator_is_not_invented(tmp_path):
    a = enriched_asset(tmp_path)
    a["enrichment"]["claims"] = [{"claim": "An unclassified observation"}]
    page = MODULE["render_enrichment"](a)
    assert "status not recorded" in page and "locator not recorded" in page
    assert "source_statement" not in page


def test_same_summary_is_not_repeated_and_complete_extraction_is_not_full_review(
    tmp_path,
):
    a = enriched_asset(tmp_path)
    a["enrichment"]["summary"] = a["description"]
    a["enrichment"]["extraction"]["truncated"] = False
    fragment = MODULE["render_enrichment"](a)
    assert "Catalog summary:" not in fragment
    assert "does not imply full review" in fragment


def test_empty_legacy_record_needs_no_enrichment_scaffolding():
    assert MODULE["render_enrichment"]({"enrichment": None}) == ""
    assert MODULE["document_type"]({"enrichment": None}) == ""


def test_filter_runs_against_one_cached_search_projection(tmp_path):
    import shutil

    # The file-catalog-suite check provides Node; a missing runtime is a
    # failure, not a skip, so the filter behavior is always exercised.
    node = shutil.which("node")
    assert node is not None, "the page-script test needs node on PATH"
    harness = r"""
const assert=require('node:assert/strict');
const fs=require('node:fs');
const source=fs.readFileSync(process.argv[2],'utf8');
let reads=0,methodReads=0;
const rows=[['asset-a','source argument','historical-design'],['asset-b','current source','navigation-guide']].map(([id,text,type])=>({id,hidden:false,scrollIntoView(){},get textContent(){reads++;return text},dataset:{kind:'file',coverage:'sampled',documentType:type,get methods(){methodReads++;return '["static"]'}}}));
const ids={};
for(const name of ['catalog-query','catalog-method','catalog-kind','catalog-coverage','catalog-document-type','catalog-count','catalog-reset','catalog'])ids[name]={value:'',callbacks:{},addEventListener(event,fn){this.callbacks[event]=fn},scrollIntoView(){}};
for(const row of rows)ids[row.id]=row;
const controls={hidden:true},globalCallbacks={};
let replacement=null;
const localLink={className:'path',textContent:'/synthetic/source',replaceWith(label){replacement=label}};
global.document={createElement(){return {}},querySelectorAll(selector){return selector==='.asset'?rows:selector==='a[href^="file:"]'?[localLink]:[]},getElementById(id){return ids[id]},querySelector(){return controls}};
global.location={hash:'',protocol:'https:'};global.addEventListener=(event,fn)=>globalCallbacks[event]=fn;
eval(source);
assert.equal(replacement.textContent,'/synthetic/source (local path)');
assert.equal(replacement.className,'path');
assert.equal(reads,2);assert.equal(methodReads,2);assert.equal(controls.hidden,false);
ids['catalog-query'].value='SOURCE ARGUMENT';ids['catalog-query'].callbacks.input();
assert.deepEqual(rows.map(r=>r.hidden),[false,true]);
ids['catalog-query'].value='';ids['catalog-document-type'].value='navigation-guide';ids['catalog-document-type'].callbacks.change();
assert.deepEqual(rows.map(r=>r.hidden),[true,false]);
ids['catalog-reset'].callbacks.click();assert.deepEqual(rows.map(r=>r.hidden),[false,false]);
ids['catalog-document-type'].value='historical-design';location.hash='#asset-b';globalCallbacks.hashchange();
assert.equal(ids['catalog-document-type'].value,'');assert.deepEqual(rows.map(r=>r.hidden),[false,false]);
assert.equal(reads,2);assert.equal(methodReads,2);
console.log('cached-search, type-filter, reset and hash navigation passed');
"""
    script = tmp_path / "filter.js"
    script.write_text(MODULE["SCRIPT"])
    driver = tmp_path / "driver.js"
    driver.write_text(harness)
    result = subprocess.run(
        [node, str(driver), str(script)], capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_known_unavailable_current_addresses_are_text_not_active_links(tmp_path):
    path = str(tmp_path / "retained historical address")
    for status in ("unavailable", "missing", "offline_mount", "denied", "inaccessible", "wrong_type"):
        asset = dict(id="fixture", kind="file", current_path=path, title="Fixture",
            description="Retained historical evidence", inspections=[], relations=[], location_status=status)
        page = MODULE["render_asset"](asset, {"fixture": asset})
        assert "Location unavailable." in page
        assert MODULE["esc"](path) in page
        assert MODULE["path_link"](path) not in page


def test_available_and_unobserved_current_addresses_keep_their_links(tmp_path):
    path = str(tmp_path / "fixture")
    for status in (None, "available"):
        asset = dict(id="fixture", kind="file", current_path=path, title="Fixture",
            description="Evidence", inspections=[], relations=[], location_status=status)
        page = MODULE["render_asset"](asset, {"fixture": asset})
        assert MODULE["path_link"](path) in page
