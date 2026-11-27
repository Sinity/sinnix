const ENDPOINT = "http://127.0.0.1:8767";
const LINK_RETRY = "retry-links";
const HISTORY_RETRY = "retry-history-visits";
const HISTORY_PROFILE = "history-profile";
const sendingLinks = new Set();
let historyDrain;

async function post(path, body, signal) {
  const response = await fetch(`${ENDPOINT}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  return response.ok;
}

async function deliverLink(key, payload) {
  if (sendingLinks.has(key)) return;
  sendingLinks.add(key);
  try {
    if (!(await post("/v1/link-event", payload, AbortSignal.timeout(10_000)))) {
      throw new Error("Link capture refused");
    }
    await chrome.storage.local.remove(key);
  } catch {
    if (!(await chrome.alarms.get(LINK_RETRY))) {
      await chrome.alarms.create(LINK_RETRY, { delayInMinutes: 1 });
    }
  } finally {
    sendingLinks.delete(key);
  }
}

async function deliverPendingLinks() {
  const pending = await chrome.storage.local.get(null);
  for (const [key, payload] of Object.entries(pending)) {
    if (key.startsWith("link:")) await deliverLink(key, payload);
  }
}

async function drainHistory() {
  const state = await chrome.storage.local.get(null);
  const pending = Object.entries(state).filter(([key]) => key.startsWith("history:"));
  if (!pending.length) return;
  const profile = state[HISTORY_PROFILE] ?? crypto.randomUUID().replaceAll("-", "");
  if (!state[HISTORY_PROFILE]) await chrome.storage.local.set({ [HISTORY_PROFILE]: profile });

  for (const [key, item] of pending) {
    let visits = item.visits;
    if (!visits) {
      try {
        visits = (await chrome.history.getVisits({ url: item.url })).filter(
          visit => visit.id === item.id && visit.visitTime === item.lastVisitTime,
        );
      } catch {
        continue;
      }
      if (!visits.length) continue;
      // Preserve the API reply before delivery. It may no longer be readable
      // from Chrome after a failed request or a browser restart.
      await chrome.storage.local.set({ [key]: { ...item, visits } });
    }
    try {
      for (const visit of visits) {
        if (!(await post("/v1/history-visit", { profile, url: item.url, visit }, AbortSignal.timeout(10_000)))) {
          throw new Error("History capture refused");
        }
      }
    } catch {
      // This reply is still queued. Continue with independent candidates.
      continue;
    }
    await chrome.storage.local.remove(key);
  }
}

async function resumeHistory() {
  if (!(await chrome.alarms.get(HISTORY_RETRY))) {
    await chrome.alarms.create(HISTORY_RETRY, { periodInMinutes: 1 });
  }
  historyDrain ??= drainHistory().finally(() => { historyDrain = undefined; });
  return historyDrain;
}

function reportHistoryError() {
  console.warn("Could not persist or resume Chrome history capture");
}

chrome.history.onVisited.addListener(({ id, url, lastVisitTime }) => {
  if (!url || !Number.isFinite(lastVisitTime)) return;
  return chrome.storage.local.set({ [`history:${crypto.randomUUID()}`]: { id, url, lastVisitTime } })
    .then(resumeHistory)
    .catch(reportHistoryError);
});

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && Object.entries(changes).some(([key, change]) =>
    key.startsWith("link:") && change.newValue
  )) {
    void deliverPendingLinks();
  }
});
chrome.runtime.onStartup.addListener(() => {
  void deliverPendingLinks();
  return resumeHistory().catch(reportHistoryError);
});
chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === LINK_RETRY) return deliverPendingLinks();
  if (alarm.name === HISTORY_RETRY) return resumeHistory().catch(reportHistoryError);
});

async function linkContext(tabId, info, tab) {
  let captured = {};
  try {
    captured = await chrome.tabs.sendMessage(tabId, { type: "link-context" });
  } catch {
    // Browser-owned pages do not have a content script.
  }
  return {
    source_url: info.pageUrl || captured.source_url || tab.url || null,
    source_title: tab.title || captured.source_title || null,
    target_url: info.linkUrl || captured.target_url || null,
    target_title: captured.target_title || null,
    anchor_text: captured.anchor_text || null,
    ts: Date.now() / 1000,
  };
}

async function promptInPage(tabId, message) {
  const result = await chrome.scripting.executeScript({
    target: { tabId },
    func: (promptMessage) => window.prompt(promptMessage, ""),
    args: [message],
  });
  return result[0]?.result;
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message?.body || !["/v1/link-event", "/v1/reading-stack/push"].includes(message.path)) return false;
  post(message.path, message.body)
    .then((ok) => sendResponse({ ok }))
    .catch(() => sendResponse({ ok: false }));
  return true;
});

chrome.commands.onCommand.addListener(async (command) => {
  if (command !== "push-current-page") return;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.url) return;
  post("/v1/reading-stack/push", {
    target_url: tab.url,
    target_title: tab.title || tab.url,
    anchor_text: tab.title || null,
    source_url: null,
    source_title: null,
    ts: Date.now() / 1000,
  }).catch(() => {});
});

chrome.runtime.onInstalled.addListener(() => {
  void deliverPendingLinks();
  void resumeHistory().catch(reportHistoryError);
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({ id: "defer-link", title: "Defer link", contexts: ["link"] });
    chrome.contextMenus.create({ id: "defer-link-with-note", title: "Defer link with note", contexts: ["link"] });
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (!tab?.id) return;
  if (info.menuItemId === "defer-link" || info.menuItemId === "defer-link-with-note") {
    const payload = await linkContext(tab.id, info, tab);
    if (info.menuItemId === "defer-link-with-note") {
      const note = await promptInPage(tab.id, "Why defer this link?");
      if (note === null) return;
      payload.note = note;
    }
    post("/v1/reading-stack/push", payload).catch(() => {});
    return;
  }
});
