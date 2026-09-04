import assert from "node:assert/strict";

let contextMenuHandler;
const requests = [];

globalThis.fetch = async (url, options) => {
  requests.push({ url, payload: JSON.parse(options.body) });
  return { ok: true };
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
    onMessage: { addListener() {} },
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

const [, , backgroundScript, expectedPort] = process.argv;

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
