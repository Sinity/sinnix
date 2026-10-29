#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
helper="${HELPER:-$script_dir/scripts/sinnix-chatgpt-conversations}"

HELPER="$helper" node <<'NODE'
const fs = require('fs');
const vm = require('vm');
const helper = fs.readFileSync(process.env.HELPER, 'utf8');
const source = helper.match(/read -r -d '' NATIVE_TRANSCRIPT_JS <<'JS' \|\| true\n([\s\S]*?)\nJS\n/)[1];
const domSource = helper.match(/read -r -d '' DOM_HELPERS_JS <<'JS' \|\| true\n([\s\S]*?)\nJS\n/)[1];

async function run({session, conversation, dom = []}) {
  const calls = [];
  const context = {
    URL,
    AbortSignal,
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
  context.chatgptDom = vm.runInNewContext(domSource, context);
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
  const user = { dataset: { contentSearchUnitKey: 'fallback-turn-0:0:user' } };
  const answer = { dataset: { contentSearchUnitKey: 'fallback-turn-0:2:assistant', chatgptSearchMessageIds: 'answer-1 answer-1' } };
  const unrelated = { dataset: { contentSearchUnitKey: 'sidebar' } };
  const domHelpers = vm.runInNewContext(domSource, { document: { querySelectorAll: selector =>
    selector === '[data-message-author-role]' ? [] : [user, answer, unrelated] } });
  if (domHelpers.turns().map(domHelpers.role).join(',') !== 'user,assistant' || domHelpers.id(answer) !== 'answer-1') throw new Error('current UI role/id fallback missing');
  let selectedClicks = 0, unrelatedClicks = 0, previewClicks = 0;
  const container = {parentElement: null, querySelector: () => ({click: () => unrelatedClicks++}), querySelectorAll: () => [1, 2]};
  const card = {parentElement: container, querySelector: () => ({click: () => selectedClicks++}), querySelectorAll: () => [1]};
  const preview = {parentElement: card, click: () => previewClicks++, getAttribute: () => 'Open preview of atlas.html'};
  if (domHelpers.downloadControl(preview) !== 'download' || selectedClicks !== 1 || unrelatedClicks || previewClicks) throw new Error('download escaped selected file card');
  preview.parentElement = container;
  if (domHelpers.downloadControl(preview) !== 'preview' || unrelatedClicks || previewClicks !== 1) throw new Error('ambiguous card must fall back to selected preview');
  preview.parentElement = card;
  preview.getAttribute = () => 'Download bundle.zip';
  if (domHelpers.downloadControl(preview) !== 'download' || selectedClicks !== 1 || previewClicks !== 2) throw new Error('direct link was replaced by an unrelated preview download');
  console.log('chatgpt-conversations native fixture tests: PASS');
})().catch(error => { console.error(error.stack || error); process.exit(1); });
NODE

NATIVE_HELPER="$(dirname -- "$helper")/download-native.mjs" node --input-type=module <<'NODE'
import vm from 'node:vm';
import {pathToFileURL} from 'node:url';
const {matchesDownload, validateRequests, downloadExpression} = await import(pathToFileURL(process.env.NATIVE_HELPER));
for (const [name, candidate, expected] of [
  ['report.txt', 'report (2).txt', true], ['report(1).txt', 'report(1) (2).txt', true],
  ['report[2].zip', 'report[2] (1).zip', true], ['LICENSE', 'LICENSE (1)', true],
  ['report.txt', 'report.txt.crdownload', false], ['report.txt', 'report-other.txt', false],
]) if (matchesDownload(name, candidate) !== expected) throw Error('Download filename identity failed');
const link = {kind: 'link', name: 'report.txt', message_id: 'message-1', sandbox_path: '/mnt/data/report.txt'};
validateRequests([link]);
for (const bad of [[], [{...link, name: '../report.txt'}], [link, link], [{...link, expected_bytes: -1}]]) {
  let rejected = false; try {validateRequests(bad);} catch {rejected = true;}
  if (!rejected) throw Error('Invalid request accepted');
}
async function run(item, status = 200) {
  const calls = [], anchor = {click() {this.clicked = true;}, remove() {this.removed = true;}};
  const result = await vm.runInNewContext(downloadExpression(item, 'conversation-1'), {
    URL, URLSearchParams, AbortSignal,
    location: {href: 'https://chatgpt.com/c/conversation-1', origin: 'https://chatgpt.com'},
    document: {createElement: () => anchor, body: {append() {}}},
    fetch: async (url, options) => {
      calls.push({url, options});
      return url === '/api/auth/session'
        ? {ok: true, json: async () => ({accessToken: 'private-token', account: {id: 'account-1'}})}
        : {ok: status === 200, status, json: async () => ({download_url: 'https://chatgpt.com/backend-api/estuary/content?sig=private-signature', file_name: item.name, file_size_bytes: 8})};
    },
  });
  if (JSON.stringify(result).match(/private-token|private-signature/)) throw Error('Credential disclosed');
  return {result, calls, anchor};
}
const generated = await run(link);
if (!generated.result.started || !generated.anchor.clicked || !generated.anchor.removed || !generated.calls[1].url.includes('message_id=message-1')) throw Error('Native link request failed');
const upload = await run({kind: 'upload', name: 'input.zip', file_id: 'file_input'});
if (upload.calls[1].url !== '/backend-api/files/file_input/download') throw Error('Native upload request failed');
const missing = await run(link, 404);
if (missing.result.started || missing.result.error !== 'file_http_404' || missing.anchor.clicked) throw Error('Unavailable file was downloaded');
console.log('chatgpt-conversations native download fixtures: PASS');
NODE

# Exercise the public download command against a fake DOM and private directory.
fixture=$(mktemp -d)
trap 'rm -rf -- "$fixture"' EXIT
mkdir -p "$fixture/bin" "$fixture/downloads" "$fixture/work"
ln -s "$(dirname -- "$helper")/download-native.mjs" "$fixture/native-symlink.mjs"
printf '%s\n' '[]' >"$fixture/invalid-requests.json"
if node "$fixture/native-symlink.mjs" ignored "$fixture/invalid-requests.json" "$fixture/unused-destination" >"$fixture/native-entry.out" 2>"$fixture/native-entry.err"; then
  printf '%s\n' 'native entrypoint skipped execution through skill symlink' >&2
  exit 1
fi
if ! grep -Fq 'Requests must be a nonempty array' "$fixture/native-entry.err"; then
  cat "$fixture/native-entry.err" >&2
  exit 1
fi
cat >"$fixture/bin/xdg-user-dir" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$FIXTURE_DOWNLOADS"
SH
cat >"$fixture/bin/chrome" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
expression="$4"
if [[ $expression == *'delete window.__sinnixNativeTranscriptV3'* ]]; then
  printf '%s\n' true
elif [[ $expression == *'return { total: serialized.length'* ]]; then
  case "$FIXTURE_SCENARIO" in
    native-fail) exit 37 ;;
    native-term)
      # The native reader is inside a command substitution. The directory
      # records the allocating subshell rather than this transport's parent.
      for entry in "$TMPDIR"/sinnix-chatgpt-native.*; do
        owner=${entry##*/sinnix-chatgpt-native.}; owner=${owner%%.*}
        kill -TERM "$owner"
      done
      exit 0 ;;
  esac
  jq -nc --arg chunk '{"messages":[],"title":"fixture"}' '{total:1,next_start:1,chunk:$chunk}'
elif [[ $expression == *'schema: "sinnix-chatgpt-generated-artifacts-v1"'* ]]; then
  jq -nc --arg name "$FIXTURE_NAME" '{files: [{name: $name}]}'
elif [[ $expression == *'const buttons ='* ]]; then
  if [[ $FIXTURE_SCENARIO == download-term ]]; then
    for entry in "$TMPDIR"/sinnix-chatgpt-download.*; do
      owner=${entry##*/sinnix-chatgpt-download.}; owner=${owner%%.*}
      kill -TERM "$owner"
    done
    exit 0
  elif [[ $FIXTURE_SCENARIO == direct ]]; then
    printf '%s' expected >"$FIXTURE_DOWNLOADS/$FIXTURE_NAME"
    printf '%s\n' download
  else
    printf '%s\n' preview
  fi
elif [[ $expression == *'const button = document.querySelector('* ]]; then
  case "$FIXTURE_SCENARIO" in
  prefix) printf '%s' unrelated >"$FIXTURE_DOWNLOADS/${FIXTURE_NAME%.*}-unrelated.${FIXTURE_NAME##*.}" ;;
  collision) printf '%s' expected >"$FIXTURE_DOWNLOADS/${FIXTURE_NAME%.*} (2).${FIXTURE_NAME##*.}" ;;
  extensionless) printf '%s' expected >"$FIXTURE_DOWNLOADS/$FIXTURE_NAME (1)" ;;
  ambiguous)
    printf '%s' expected >"$FIXTURE_DOWNLOADS/$FIXTURE_NAME"
    printf '%s' other >"$FIXTURE_DOWNLOADS/${FIXTURE_NAME%.*} (1).${FIXTURE_NAME##*.}"
    ;;
  empty) : >"$FIXTURE_DOWNLOADS/$FIXTURE_NAME" ;;
  *) printf '%s' expected >"$FIXTURE_DOWNLOADS/$FIXTURE_NAME" ;;
  esac
  printf '%s\n' true
else
  printf '%s\n' closed >>"$FIXTURE_DOWNLOADS/../$FIXTURE_SCENARIO.viewer"
  printf '%s\n' true
fi
SH
cat >"$fixture/bin/sleep" <<'SH'
#!/usr/bin/env bash
if [[ $FIXTURE_SCENARIO == prefix ]]; then
  printf '%s' expected >"$FIXTURE_DOWNLOADS/$FIXTURE_NAME"
else
  /usr/bin/env sleep "$@"
fi
SH
# Capture the real sleep path before putting the fake transport on PATH.
real_sleep=$(command -v sleep)
sed -i "s|/usr/bin/env sleep|$real_sleep|" "$fixture/bin/sleep"
# Synthetic transports must also run where /usr/bin/env is absent.
sed -i "1c#!$(command -v bash)" "$fixture/bin/xdg-user-dir" "$fixture/bin/chrome" "$fixture/bin/sleep"
chmod +x "$fixture/bin/xdg-user-dir" "$fixture/bin/chrome" "$fixture/bin/sleep"

run_download_case() {
  local scenario="$1" name="$2" expected="$3" status=0
  local directory="$fixture/downloads/$scenario"
  mkdir -p "$directory"
  if [[ $scenario == collision ]]; then
    printf '%s' preexisting >"$directory/${name%.*} (1).${name##*.}"
  fi
  env PATH="$fixture/bin:$PATH" TMPDIR="$fixture/work" \
    SINNIX_CHROME_CONTROL="$fixture/bin/chrome" \
    FIXTURE_DOWNLOADS="$directory" FIXTURE_NAME="$name" FIXTURE_SCENARIO="$scenario" \
    bash "$helper" download synthetic-page "$name" >"$fixture/$scenario.json" 2>"$fixture/$scenario.err" || status=$?
  if [[ $scenario == ambiguous ]]; then
    test "$status" != 0
    grep -Fq 'multiple completed downloads' "$fixture/$scenario.err"
    test ! -s "$fixture/$scenario.json"
    test -s "$fixture/downloads/$scenario.viewer"
  else
    if [[ $status != 0 ]]; then
      printf 'download fixture %s exited %s\n' "$scenario" "$status" >&2
      cat "$fixture/$scenario.err" >&2
      return 1
    fi
    if ! jq -e --arg path "$directory/$expected" '.path == $path' "$fixture/$scenario.json" >/dev/null; then
      cat "$fixture/$scenario.json" >&2
      return 1
    fi
    jq -e --arg sha256 "$(sha256sum <"$directory/$expected" | cut -d' ' -f1)" \
      '.sha256 == $sha256 and (.sha256 | test("^[0-9a-f]{64}$"))' "$fixture/$scenario.json" >/dev/null
  fi
}

run_download_case prefix report.txt report.txt
run_download_case collision report.txt 'report (2).txt'
run_download_case extensionless LICENSE 'LICENSE (1)'
run_download_case ambiguous report.txt ''
run_download_case empty empty.txt empty.txt
run_download_case newline $'report\npart.txt' $'report\npart.txt'
run_download_case direct bundle.zip bundle.zip
test ! -e "$fixture/downloads/direct.viewer"

# Exercise assembly success, transport failure, and catchable cancellation.
for scenario in native-ok native-fail native-term; do
  status=0
  env TMPDIR="$fixture/work" SINNIX_CHROME_CONTROL="$fixture/bin/chrome" \
    FIXTURE_SCENARIO="$scenario" bash "$helper" full synthetic-page \
    >"$fixture/$scenario.json" 2>"$fixture/$scenario.err" || status=$?
  case "$scenario" in
  native-ok)
    test "$status" -eq 0
    jq -e '.page_id == "synthetic-page"' "$fixture/$scenario.json"
    ;;
  native-fail) test "$status" -eq 37 ;;
  native-term) test "$status" -eq 143 ;;
  esac
  test -z "$(find "$fixture/work" -mindepth 1 -print -quit)"
done
status=0
env PATH="$fixture/bin:$PATH" TMPDIR="$fixture/work" \
  SINNIX_CHROME_CONTROL="$fixture/bin/chrome" FIXTURE_SCENARIO=download-term \
  FIXTURE_NAME=cancel.txt FIXTURE_DOWNLOADS="$fixture/downloads" \
  bash "$helper" download synthetic-page cancel.txt >"$fixture/cancel.out" 2>"$fixture/cancel.err" || status=$?
test "$status" -eq 143
test -z "$(find "$fixture/work" -mindepth 1 -print -quit)"

mkdir -p "$fixture/locate"
printf '%s' original >"$fixture/locate/report.txt"
env SINNIX_CHROME_CONTROL="$fixture/bin/chrome" bash "$helper" locate report.txt --root "$fixture/locate" >"$fixture/located.json"
jq -e '.query == "report.txt" and (.matches | length) == 1' "$fixture/located.json" >/dev/null
env SINNIX_CHROME_CONTROL="$fixture/bin/chrome" bash "$helper" locate absent.txt --root "$fixture/locate" >"$fixture/absent.json"
jq -e '.matches == []' "$fixture/absent.json" >/dev/null
test -z "$(find "$fixture/work" -mindepth 1 -print -quit)"
printf '%s\n' 'chatgpt-conversations download fixture tests: PASS'
