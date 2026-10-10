import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

let contextMenuHandler;
let relayHandler;
let responseOK = true;
const requests = [];

globalThis.fetch = async (url, options) => {
  requests.push({ url, payload: JSON.parse(options.body) });
  return { ok: responseOK };
};

globalThis.chrome = {
  commands: { onCommand: { addListener() {} } },
  contextMenus: {
    create() {},
    removeAll(callback) { callback(); },
    onClicked: { addListener(handler) { contextMenuHandler = handler; } },
  },
  runtime: {
    onInstalled: { addListener() {} },
    onMessage: { addListener(handler) { relayHandler = handler; } },
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
let contextHandler;
vm.runInNewContext(fs.readFileSync(contentScript, "utf8"), {
  document: { title: "Neutral page", addEventListener: (name, fn) => { handlers[name] = fn; } },
  location: { href: "https://source.example/" },
  chrome: { runtime: {
    sendMessage: (message) => { messages.push(message); return Promise.resolve(); },
    onMessage: { addListener: (fn) => { contextHandler = fn; } },
  } },
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
assert.equal(prevented, 0);
let context;
contextHandler({ type: "link-context" }, {}, (value) => { context = value; });
assert.equal(Object.keys(context).length, 0);
handlers.click(event(true));
handlers.auxclick(event(true));
assert.equal(messages.length, 3);
assert.equal(messages[0].body.trigger, "click");
assert.equal(messages[1].body.trigger, "middle-click");
assert.equal(messages[2].path, "/v1/reading-stack/push");
assert.equal(prevented, 1);
handlers.contextmenu(event(true));
handlers.contextmenu({ ...event(false), target: { ...anchor, href: "https://forged.example/" } });
contextHandler({ type: "link-context" }, {}, (value) => { context = value; });
assert.equal(context.target_url, anchor.href);

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
