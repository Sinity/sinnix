"""Browser-decoded action arguments and report filename URLs."""

import datetime as dt
import json
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from sinnix_hub_server.pages import dashboard, queue, services, shell


class Attributes(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.handlers = []
        self.links = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "onclick" in values:
            self.handlers.append(values["onclick"])
        if tag == "a":
            self.links.append(values.get("href"))


def test_action_arguments_survive_browser_attribute_decoding():
    unit = "neutral\\x2dunit');globalThis.injected=true;//.service"
    value = "neutral'\\value&\""
    snippets = [
        (
            services.lifecycle_controls(unit, True, True, False),
            [("act", ["start", "unit", unit])],
        ),
        (
            services.policy_controls(unit, {"MemoryHigh": value}),
            [
                ("setPolicy", [unit, "MemoryHigh", value]),
                ("act", ["reset_policy", "unit", unit]),
            ],
        ),
        (
            queue.job_row(
                {"job_id": unit, "terminal": False}, dt.datetime.now(dt.timezone.utc)
            ),
            [("act", ["interrupt", "job_id", unit])],
        ),
    ]
    cases = []
    for markup, expected in snippets:
        handlers = Attributes(markup).handlers
        assert len(handlers) == len(expected)
        cases.extend(
            {"handler": handler, "expected": wanted}
            for handler, wanted in zip(handlers, expected, strict=True)
        )
    script = r"""
const assert = require('node:assert/strict');
const cases = JSON.parse(require('node:fs').readFileSync(0,'utf8'));
for (const item of cases) {
 globalThis.injected = false;
 const calls = [], button = {};
 const spy = name => (...args) => { assert.equal(args.pop(), button); calls.push([name,args]); };
 new Function('act','setPolicy',item.handler).call(button,spy('act'),spy('setPolicy'));
 assert.equal(globalThis.injected,false);
 assert.deepEqual(calls,[item.expected]);
}
"""
    result = subprocess.run(
        ["node", "-e", script],
        input=json.dumps(cases),
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr


def test_report_filename_is_one_url_component(tmp_path):
    filename = "neutral #?%&ż.html"
    (tmp_path / filename).write_text("neutral report")
    markup = dashboard.reports_card(tmp_path, dt.datetime.now(dt.timezone.utc), 8883)
    links = Attributes(markup).links
    target = next(link for link in links if urlsplit(link).path != "/reports/")
    parsed = urlsplit(target)
    assert parsed.query == parsed.fragment == ""
    assert unquote(parsed.path.removeprefix("/reports/")) == filename


@pytest.mark.parametrize(
    "error",
    [
        PermissionError("denied <neutral>"),
        FileNotFoundError("disappeared <neutral>"),
        OSError("inspection failed <neutral>"),
    ],
)
def test_report_inspection_failure_is_unavailable_not_empty(
    tmp_path, monkeypatch, error
):
    target = tmp_path / "neutral.html"
    target.write_text("neutral")
    original = Path.stat

    def inspect(path, *args, **kwargs):
        if path == target:
            raise error
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", inspect)
    markup = dashboard.reports_card(tmp_path, dt.datetime.now(dt.timezone.utc), 8883)
    assert "Reports unavailable" in markup
    assert "no reports generated yet" not in markup
    assert "&lt;neutral&gt;" in markup and "<neutral>" not in markup


def test_report_render_retains_metadata_without_a_racy_second_read(
    tmp_path, monkeypatch
):
    target = tmp_path / "neutral.html"
    target.write_text("neutral")
    original = Path.stat
    observed = []

    def inspect(path, *args, **kwargs):
        if path == target:
            if observed:
                raise FileNotFoundError("removed after observation")
            observed.append(True)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", inspect)
    markup = dashboard.reports_card(tmp_path, dt.datetime.now(dt.timezone.utc), 8883)
    assert "/reports/neutral.html" in markup and "Recent reports" in markup


def test_report_empty_and_wrong_type_root_are_distinct(tmp_path):
    now = dt.datetime.now(dt.timezone.utc)
    assert "no reports generated yet" in dashboard.reports_card(tmp_path, now, 8883)
    target = tmp_path / "ordinary-file"
    target.write_text("neutral")
    assert "Reports unavailable" in dashboard.reports_card(target, now, 8883)


def test_browser_port_rewrite_retains_report_paths():
    script = shell.SHELL_SCRIPT.removeprefix("\n<script>").removesuffix("</script>\n")
    fixture = r"""
const assert = require('node:assert/strict');
const links = [{href:'http://127.0.0.1:8883/reports/neutral%23.html',dataset:{port:'8883'}},{href:'http://127.0.0.1:8881/',dataset:{port:'8881'}}];
global.location = {protocol:'http:',hostname:'neutral.tailnet.invalid'};
global.localStorage = {getItem:()=>null};
global.document = {documentElement:{dataset:{},style:{}},querySelectorAll:()=>links,getElementById:()=>null};
"""
    expected = r"""
assert.equal(links[0].href,'http://neutral.tailnet.invalid:8883/reports/neutral%23.html');
assert.equal(links[1].href,'http://neutral.tailnet.invalid:8881/');
"""
    result = subprocess.run(
        ["node", "-e", fixture + script + expected],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr
