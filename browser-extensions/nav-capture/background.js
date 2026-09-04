const ENDPOINT = "http://127.0.0.1:8767";

async function post(path, body) {
  const response = await fetch(`${ENDPOINT}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return response.ok;
}

async function linkContext(tabId, info, tab) {
  let captured = {};
  try {
    captured = await chrome.tabs.sendMessage(tabId, { type: "link-context" });
  } catch {
    // Browser-owned pages do not have a content script.
  }
  return {
    source_url: captured.source_url || info.pageUrl || tab.url || null,
    source_title: captured.source_title || tab.title || null,
    target_url: captured.target_url || info.linkUrl || null,
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
  if (!message?.path || !message.body) return false;
  post(message.path, message.body)
    .then(() => sendResponse({ ok: true }))
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
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({ id: "defer-link", title: "Defer link", contexts: ["link"] });
    chrome.contextMenus.create({ id: "defer-link-with-note", title: "Defer link with note", contexts: ["link"] });
    chrome.contextMenus.create({ id: "agent-action", title: "Ask agent about selection", contexts: ["selection"] });
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
  if (info.menuItemId === "agent-action") {
    const instruction = await promptInPage(tab.id, "Instruction for agent");
    if (instruction === null) return;
    post("/v1/agent-action", {
      page_url: info.pageUrl || tab.url || null,
      page_title: tab.title || null,
      selection_text: info.selectionText || "",
      instruction,
      ts: Date.now() / 1000,
    }).catch(() => {});
  }
});
