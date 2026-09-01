#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
helper="$script_dir/scripts/sinnix-chatgpt-conversations"

HELPER="$helper" node <<'NODE'
const fs = require('fs');
const vm = require('vm');
const helper = fs.readFileSync(process.env.HELPER, 'utf8');
const source = helper.match(/read -r -d '' NATIVE_TRANSCRIPT_JS <<'JS' \|\| true\n([\s\S]*?)\nJS\n/)[1];

async function run({session, conversation, dom = []}) {
  const calls = [];
  const context = {
    URL,
    location: { href: 'https://chatgpt.com/c/conversation-1', pathname: '/c/conversation-1' },
    document: { querySelectorAll: () => dom.map(({role, text, id}) => ({
      dataset: { messageAuthorRole: role, messageId: id || '' }, innerText: text,
    })) },
    fetch: async (url, options = {}) => {
      calls.push({ url, options });
      const body = url === '/api/auth/session' ? session : conversation;
      return { ok: body !== null, status: body === null ? 404 : 200, json: async () => body };
    },
  };
  const result = await vm.runInNewContext(source, context);
  return { result, calls };
}

(async () => {
  const payload = {
    conversation_id: 'conversation-1', current_node: 'leaf',
    mapping: {
      root: { id: 'root', parent: null, message: null },
      user: { id: 'user', parent: 'root', message: { id: 'u1', author: { role: 'user' }, create_time: 2, content: { parts: ['first'] }, metadata: {} } },
      branch: { id: 'branch', parent: 'root', message: { id: 'b1', author: { role: 'user' }, create_time: 3, content: { parts: ['other'] }, metadata: {} } },
      leaf: { id: 'leaf', parent: 'user', message: { id: 'a1', author: { role: 'assistant' }, create_time: 4, content: { parts: ['answer'] }, metadata: { attachments: [{ id: 'file-1', name: 'x.txt' }] } } },
    },
  };
  const native = await run({ session: { accessToken: 'secret-token', account: { id: 'account-1' } }, conversation: payload });
  const messages = native.result.messages.map(message => message.provider_id);
  if (messages.join(',') !== 'u1,a1') throw new Error(`branch order: ${messages}`);
  const request = native.calls[1];
  if (request.options.headers.Authorization !== 'Bearer secret-token' || request.options.headers['ChatGPT-Account-Id'] !== 'account-1') throw new Error('native auth headers missing');
  if (JSON.stringify(native.result).includes('secret-token')) throw new Error('credential disclosed in result');
  if (native.result.fidelity !== 'native' || native.result.mapping_node_count !== 4) throw new Error('native evidence missing');
  if (native.result.all_mapping_nodes.find(node => node.provider_id === 'b1')?.message.text !== 'other') throw new Error('inactive branch not preserved');
  const inactive = native.result.all_messages.find(message => message.provider_id === 'b1');
  if (inactive?.content?.parts?.[0] !== 'other' || inactive?.author?.role !== 'user') throw new Error('complete inactive message not preserved');

  const degraded = await run({ session: null, conversation: null, dom: [{ role: 'user', text: 'visible', id: 'dom-1' }] });
  if (degraded.result.fidelity !== 'dom_degraded' || degraded.result.provenance.complete !== false || degraded.result.messages.length !== 1) throw new Error('degraded fallback missing');
  console.log('chatgpt-conversations native fixture tests: PASS');
})().catch(error => { console.error(error.stack || error); process.exit(1); });
NODE
