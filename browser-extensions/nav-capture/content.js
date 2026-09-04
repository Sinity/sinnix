// sinnix-nav-capture content script.
//
// Two jobs, both firing on the SAME event class (a click on an <a>), because
// they're really the same underlying event -- "the operator engaged with a
// link" -- with the click TYPE deciding what happens next:
//
//   - Plain click / ctrl+click (opens a real new tab, or navigates): capture
//     the origin edge {source, target, anchor_text} and let the browser do
//     its normal thing. Purely observational, never preventDefault.
//   - Middle click / auxclick button 1 (used to mean "open in background
//     tab"): capture the SAME edge, but ALSO push to the reading stack and
//     preventDefault -- no tab opens. This is the middle-click remap the
//     operator asked for: the muscle-memory gesture that used to dump a link
//     into the disorganized tab pile now dumps it into a bounded, visible
//     stack instead. The click itself is unchanged; only its destination is.
//
// Every link click is captured (not just remapped ones) so the origin-chain
// graph is complete regardless of which gesture the operator used to follow
// a link -- "how did I get here" should work for a plain click too.

function nearestAnchor(node) {
  while (node && node.tagName !== "A") node = node.parentElement;
  return node;
}

function postEvent(path, body) {
  // Routed through the background service worker (chrome.runtime.sendMessage
  // -> fetch there), not fetched directly from this content script: a
  // page's own Content-Security-Policy (connect-src) can silently block a
  // content-script's fetch() to 127.0.0.1 on strict sites, but the
  // background worker's network requests are NOT subject to the page's CSP.
  // Fire-and-forget either way -- a capture daemon being down must never
  // block browsing.
  try {
    chrome.runtime.sendMessage({ path, body }).catch(() => {});
  } catch {
    /* extension context invalidated (reload mid-navigation) -- ignore */
  }
}

let contextLink = null;

function edgePayload(anchor) {
  return {
    source_url: location.href,
    source_title: document.title,
    target_url: anchor.href,
    anchor_text: (anchor.textContent || "").trim().slice(0, 500),
    ts: Date.now() / 1000,
  };
}

document.addEventListener(
  "contextmenu",
  (ev) => {
    const a = nearestAnchor(ev.target);
    contextLink = a && a.href ? edgePayload(a) : null;
  },
  { capture: true }
);

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "link-context") return;
  sendResponse(contextLink || {});
});

document.addEventListener(
  "click",
  (ev) => {
    const a = nearestAnchor(ev.target);
    if (!a || !a.href) return;
    postEvent("/v1/link-event", { ...edgePayload(a), trigger: "click" });
  },
  { capture: true }
);

document.addEventListener(
  "auxclick",
  (ev) => {
    if (ev.button !== 1) return; // middle button only
    const a = nearestAnchor(ev.target);
    if (!a || !a.href) return;
    const payload = edgePayload(a);
    postEvent("/v1/link-event", { ...payload, trigger: "middle-click" });
    postEvent("/v1/reading-stack/push", payload);
    ev.preventDefault();
    ev.stopPropagation();
  },
  { capture: true }
);
