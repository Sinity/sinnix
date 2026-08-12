// Relays content-script events to the local capture daemon. Runs here (not
// in the content script) so a page's own CSP can't block the request -- a
// service worker's fetch is not subject to the visited page's connect-src.
const ENDPOINT = "http://127.0.0.1:8766";

// Manual "push the whole page I'm reading, not a link on it" -- distinct
// from the middle-click remap, which only ever fires on links. This is for
// "I've decided to defer THIS article" rather than "I noticed a link".
chrome.commands.onCommand.addListener(async (command) => {
  if (command !== "push-current-page") return;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.url) return;
  fetch(`${ENDPOINT}/v1/reading-stack/push`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      target_url: tab.url,
      anchor_text: tab.title,
      source_url: null,
      source_title: null,
      ts: Date.now() / 1000,
    }),
  }).catch(() => {});
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (!msg || !msg.path) return false;
  fetch(`${ENDPOINT}${msg.path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(msg.body),
  })
    .then(() => sendResponse({ ok: true }))
    .catch(() => sendResponse({ ok: false }));
  return true; // keep the message channel open for the async sendResponse
});
