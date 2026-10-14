"""Browser-decoded action arguments and report filename URLs."""
import datetime as dt
import json
import subprocess
from html.parser import HTMLParser
from types import SimpleNamespace
from urllib.parse import unquote, urlsplit

from sinnix_ops_reducer.pages import dashboard, pressure, queue, services


class Attributes(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.handlers = []
        self.links = []
        self.feed(markup)
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if 'onclick' in values: self.handlers.append(values['onclick'])
        if tag == 'a': self.links.append(values.get('href'))


def test_action_arguments_survive_browser_attribute_decoding():
    unit = "neutral\\x2dunit');globalThis.injected=true;//.service"
    value = "neutral'\\value&\""
    snippets = [
        (services.lifecycle_controls(unit, True, True, False), [('act', ['start', 'unit', unit])]),
        (services.policy_controls(unit, {'MemoryHigh': value}), [('setPolicy', [unit, 'MemoryHigh', value]), ('act', ['reset_policy', 'unit', unit])]),
        (queue.job_row({'job_id': unit, 'terminal': False}, dt.datetime.now(dt.timezone.utc)), [('act', ['interrupt', 'job_id', unit])]),
        (pressure.scheduled_card([SimpleNamespace(unit=unit,timer='neutral.timer',active=True,next_seconds=None,last_seconds=None,last_duration_seconds=None)], {unit}), [('parkUnit', [unit])]),
    ]
    cases = []
    for markup, expected in snippets:
        handlers = Attributes(markup).handlers
        assert len(handlers) == len(expected)
        cases.extend({'handler': handler, 'expected': wanted} for handler, wanted in zip(handlers, expected))
    script = r"""
const assert = require('node:assert/strict');
const cases = JSON.parse(require('node:fs').readFileSync(0,'utf8'));
for (const item of cases) {
 globalThis.injected = false;
 const calls = [], button = {};
 const spy = name => (...args) => { assert.equal(args.pop(), button); calls.push([name,args]); };
 new Function('act','setPolicy','parkUnit',item.handler).call(button,spy('act'),spy('setPolicy'),spy('parkUnit'));
 assert.equal(globalThis.injected,false);
 assert.deepEqual(calls,[item.expected]);
}
"""
    result = subprocess.run(['node','-e',script],input=json.dumps(cases),capture_output=True,text=True,timeout=5)
    assert result.returncode == 0, result.stderr


def test_report_filename_is_one_url_component(tmp_path):
    filename = 'neutral #?%&ż.html'
    (tmp_path / filename).write_text('neutral report')
    markup = dashboard.reports_card(tmp_path, dt.datetime.now(dt.timezone.utc))
    links = Attributes(markup).links
    target = next(link for link in links if link != '/reports/')
    parsed = urlsplit(target)
    assert parsed.query == parsed.fragment == ''
    assert unquote(parsed.path.removeprefix('/reports/')) == filename
