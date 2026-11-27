import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

let contextMenuHandler;
let relayHandler;
let storageHandler;
let alarmHandler;
let responseOK = true;
const requests = [];
const pending = new Map();
const alarms = new Map();

globalThis.fetch = async (url, options) => {
  requests.push({ url, payload: JSON.parse(options.body) });
  return { ok: responseOK };
};

globalThis.chrome = {
  alarms: {
    get: async name => alarms.get(name),
    create: async (name, options) => { alarms.set(name, options); },
    onAlarm: { addListener(handler) { alarmHandler = handler; } },
  },
  commands: { onCommand: { addListener() {} } },
  contextMenus: {
    create() {},
    removeAll(callback) { callback(); },
    onClicked: { addListener(handler) { contextMenuHandler = handler; } },
  },
  runtime: {
    onInstalled: { addListener() {} },
    onMessage: { addListener(handler) { relayHandler = handler; } },
    onStartup: { addListener() {} },
  },
  storage: {
    local: {
      get: async () => Object.fromEntries(pending),
      remove: async key => { pending.delete(key); },
    },
    onChanged: { addListener(handler) { storageHandler = handler; } },
  },
  scripting: { executeScript: async () => [{ result: null }] },
  tabs: {
    query: async () => [],
    sendMessage: async () => ({
      source_url: "https://stale-frame.example/",
      source_title: "Stale frame",
      target_url: "https://stale-target.example/",
      anchor_text: "Stale target",
    }),
  },
};

const [, , backgroundScript, expectedPort, contentScript] = process.argv;

await import(backgroundScript);

await contextMenuHandler(
  {
    menuItemId: "defer-link",
    pageUrl: "https://page.example/",
    linkUrl: "https://context-link.example/",
  },
  { id: 1, title: "Page title", url: "https://tab.example/" },
);

assert.equal(requests.length, 1);
assert.equal(requests[0].url, `http://127.0.0.1:${expectedPort}/v1/reading-stack/push`);
assert.equal(requests[0].payload.target_url, "https://context-link.example/");
assert.equal(requests[0].payload.source_url, "https://page.example/");

// Exercise the content producer separately from the background relay.
const handlers = {};
const messages = [];
const captured = [];
let contextHandler;
vm.runInNewContext(fs.readFileSync(contentScript, "utf8"), {
  document: { title: "Neutral page", addEventListener: (name, fn) => { handlers[name] = fn; } },
  location: { href: "https://source.example/" },
  chrome: {
    runtime: {
      sendMessage: (message) => { messages.push(message); return Promise.resolve(); },
      onMessage: { addListener: (fn) => { contextHandler = fn; } },
    },
    storage: { local: { set: async entries => { captured.push(...Object.entries(entries)); } } },
  },
  crypto: globalThis.crypto,
  Date,
});
const anchor = { tagName: "A", href: "https://target.example/", textContent: "Target" };
let prevented = 0;
function event(isTrusted) {
  return { isTrusted, target: anchor, button: 1,
    preventDefault: () => { prevented++; }, stopPropagation() {} };
}
for (const kind of ["click", "auxclick", "contextmenu"]) handlers[kind](event(false));
assert.equal(messages.length, 0);
assert.equal(captured.length, 0);
assert.equal(prevented, 0);
let context;
contextHandler({ type: "link-context" }, {}, (value) => { context = value; });
assert.equal(Object.keys(context).length, 0);
handlers.click(event(true));
handlers.auxclick(event(true));
assert.equal(messages.length, 1);
assert.equal(captured.length, 2);
assert.equal(captured[0][1].trigger, "click");
assert.equal(captured[1][1].trigger, "middle-click");
assert.equal(messages[0].path, "/v1/reading-stack/push");
assert.equal(prevented, 1);
handlers.contextmenu(event(true));
handlers.contextmenu({ ...event(false), target: { ...anchor, href: "https://forged.example/" } });
contextHandler({ type: "link-context" }, {}, (value) => { context = value; });
assert.equal(context.target_url, anchor.href);

const [key, payload] = captured[0];
assert.match(payload.capture_id, /^[a-f0-9]{32}$/);
assert.equal(key, `link:${payload.capture_id}`);
assert.notEqual(captured[1][0], key);
pending.set(key, payload);
responseOK = false;
storageHandler({ [key]: { newValue: payload } }, "local");
await new Promise(resolve => setImmediate(resolve));
assert.equal(pending.get(key), payload);
assert.equal(alarms.get("retry-links").delayInMinutes, 1);
const firstAttempt = requests.at(-1);
assert.equal(firstAttempt.url, `http://127.0.0.1:${expectedPort}/v1/link-event`);
responseOK = true;
alarms.delete("retry-links");
await alarmHandler({ name: "retry-links" });
assert.equal(pending.has(key), false);
assert.deepEqual(requests.at(-1), firstAttempt);

// An HTTP refusal is a failed relay, even when fetch itself resolves.
for (const ok of [true, false]) {
  responseOK = ok;
  const reply = await new Promise((resolve) => {
    assert.equal(relayHandler({ path: "/v1/link-event", body: {} }, {}, resolve), true);
  });
  assert.equal(reply.ok, ok);
}
globalThis.fetch = async () => { throw new Error("neutral transport failure"); };
const failedReply = await new Promise((resolve) => {
  relayHandler({ path: "/v1/link-event", body: {} }, {}, resolve);
});
assert.equal(failedReply.ok, false);
