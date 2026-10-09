#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
helper="${HELPER:-$script_dir/scripts/sinnix-chatgpt-conversations}"

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

# Exercise the public download command against a fake DOM and private directory.
fixture=$(mktemp -d)
trap 'rm -rf -- "$fixture"' EXIT
mkdir -p "$fixture/bin" "$fixture/downloads" "$fixture/work"
cat >"$fixture/bin/xdg-user-dir" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$FIXTURE_DOWNLOADS"
SH
cat >"$fixture/bin/chrome" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
expression="$4"
if [[ $expression == *'schema: "sinnix-chatgpt-generated-artifacts-v1"'* ]]; then
  jq -nc --arg name "$FIXTURE_NAME" '{files: [{name: $name}]}'
elif [[ $expression == *'const buttons ='* ]]; then
  printf '%s\n' true
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
    test "$status" = 0
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
test -z "$(find "$fixture/work" -mindepth 1 -print -quit)"
printf '%s\n' 'chatgpt-conversations download fixture tests: PASS'
