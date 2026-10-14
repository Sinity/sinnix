"""Execute terminal view JavaScript with hostile metadata and a strict DOM."""
import re
import subprocess
from sinnix_ops_reducer import terminals


def test_captured_metadata_uses_text_nodes_and_encoded_history_paths():
    script = re.search(r"<script>(.*?)</script>", terminals.INDEX_HTML, re.S).group(1)
    fixture = r"""
const assert = require('node:assert/strict');
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.style = {}; }
  set innerHTML(value) { throw new Error('HTML parser used: ' + value); }
  append(...values) { this.children.push(...values); }
  appendChild(value) { this.append(value); }
  replaceChildren(...values) { this.children = values; }
  addEventListener() {}
}
const ids = new Map();
global.document = { createElement: tag => new Element(tag), getElementById: id => {
  if (!ids.has(id)) ids.set(id, new Element(id)); return ids.get(id);
}};
const hostile = '<img src=x onerror="throw 1">&"';
const filename = 'neutral"/<script>.ansi';
global.fetch = async url => ({ json: async () => url.endsWith('/history')
  ? [{ ansi_file: filename, captured_at: hostile, title: hostile }]
  : [{ title: hostile, cwd: hostile, kitty_pid: 1, window_id: 2 }] });
global.localStorage = { getItem: () => JSON.stringify([hostile]) };
global.setInterval = () => {};
"""
    assertions = r"""
(async () => {
 await load();
 assert.equal(ids.get('list').children[0].children[0].textContent, hostile);
 assert.equal(ids.get('list').children[0].children[1].textContent, hostile);
 renderHistDatalist(1, 2);
 assert.equal(ids.get('sendhist').children[0].value, hostile);
 showLive(1, 2);
 assert.equal(ids.get('view').children[0].src, '/terminals/v1/windows/1/2/content');
 showStream(1, 2);
 assert.equal(ids.get('view').children[0].src, '/terminals/v1/live/1/2/');
 await showHistory(1, 2);
 const link = ids.get('view').children[0].children[0].children[0];
 assert.equal(link.textContent, hostile + ' -- ' + hostile);
 assert.equal(link.href, '/terminals/v1/windows/1/2/history/' + encodeURIComponent(filename));
 assert.equal(link.rel, 'noopener');
 localStorage.getItem = () => '{}';
 assert.deepEqual(loadHist(1, 2), []);
 localStorage.getItem = () => '[1, \"neutral\"]';
 assert.deepEqual(loadHist(1, 2), ['neutral']);
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
    result = subprocess.run(['node', '-e', fixture + script + assertions], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
