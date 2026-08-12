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

// ---------------------------------------------------------------------------
// TabTracker: per-tab back/forward navigation DAG, ported from the
// operator's own May-2025 prototype (/realm/data/exports/repos/mine/
// my-chrome-extension, MV2, console.log-only). That prototype already
// modeled itself as an MV2 *non-persistent* event page (background:
// {persistent: false}), which is the same "may be torn down between
// events" contract an MV3 service worker has -- its load/init-from-storage
// path on startup already handles cold starts correctly and needed no
// redesign. Two things DID need changing for MV3:
//   1. `startAutoSave()`'s periodic setInterval-based flush cannot be
//      trusted -- an MV3 worker can be killed between ticks with no
//      guarantee the interval ever fires again. Replaced with an
//      immediate chrome.storage.local write right after every mutating
//      event, not a batched/debounced one.
//   2. Output was console.log only, discarded on every worker restart.
//      Every meaningful DAG mutation (new entry, back/forward step,
//      reload, closed-tab recovery) now also POSTs to the local capture
//      daemon -> the "browser-tab-history" lane. Kept as a SEPARATE lane
//      from "browser-nav-edges" (content.js's click-edge capture,
//      elsewhere in this extension) deliberately: the two are different
//      shapes -- nav-edges is a flat source->target+anchor_text event log,
//      tab-history is a stateful per-tab DAG with transition
//      classification (typed/link/reload/forward_back/closed-tab-
//      recovered) that only makes sense read as a sequence per tab.
//      Merging them into one schema would force one to fake fields the
//      other doesn't have; two lanes, two schemas, both real.
// content.js's own link-click capture already covers "the operator
// engaged with a link" at the DOM layer -- the old prototype's
// content.js (anchor-click + DOM_LOADED messages) was NOT ported: it
// would just be a second, redundant click observer feeding a
// console.log that no longer exists. TabTracker below runs entirely off
// chrome.tabs/chrome.webNavigation, no content-script cooperation
// needed.

const CONFIG = {
  MAX_TAB_HISTORY_SIZE: 100,
  MAX_CLOSED_TABS: 100,
  INIT_RETRY_MS: 200,
};

const STORAGE_KEYS = {
  CLOSED_TAB_HISTORY: "closedTabHistory",
  LAST_SESSION_HISTORY: "lastSessionTabHistory",
};

const TRANSITION_TYPES = {
  MANUAL: ["typed", "auto_bookmark", "generated", "start_page", "keyword", "keyword_generated"],
};

function postTabHistoryEvent(event, tabId, record) {
  const entry = record.entries[record.currentEntry];
  fetch(`${ENDPOINT}/v1/tab-history`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      event, // "navigate" | "back" | "forward" | "reload" | "new_tab" | "closed_tab_recovered"
      tab_id: tabId,
      transition_type: entry ? entry[0] : null,
      url: entry ? entry[1] : null,
      entry_index: record.currentEntry,
      entry_count: record.entries.length,
      ts: Date.now() / 1000,
    }),
  }).catch(() => {});
}

class TabTracker {
  constructor() {
    this.currentTabId = 0;
    this.previousTabId = 0;
    this.tabHistory = {};
    this.closedTabHistory = [];
    this.isInitialized = { tabs: false, loading: false, activeTab: false };
  }

  async initialize() {
    try {
      await this.loadStoredData();
      await this.initializeTabData();
      await this.waitForInitialization();
      this.setupEventListeners();
    } catch (error) {
      console.error("Failed to initialize TabTracker:", error);
    }
  }

  async loadStoredData() {
    return new Promise((resolve) => {
      chrome.storage.local.get(
        [STORAGE_KEYS.CLOSED_TAB_HISTORY, STORAGE_KEYS.LAST_SESSION_HISTORY],
        (data) => {
          try {
            if (data[STORAGE_KEYS.CLOSED_TAB_HISTORY]) {
              this.closedTabHistory = this.validateTabRecords(data[STORAGE_KEYS.CLOSED_TAB_HISTORY]);
            }
            if (data[STORAGE_KEYS.LAST_SESSION_HISTORY]) {
              this.mergeLastSessionHistory(data[STORAGE_KEYS.LAST_SESSION_HISTORY]);
            }
          } catch (error) {
            console.error("Error processing stored data:", error);
          }
          this.isInitialized.loading = true;
          resolve();
        }
      );
    });
  }

  validateTabRecords(records) {
    if (!Array.isArray(records)) return [];
    return records.filter(
      (record) =>
        record &&
        Array.isArray(record.entries) &&
        typeof record.currentEntry === "number" &&
        record.currentEntry >= 0 &&
        record.currentEntry < record.entries.length &&
        record.entries.every(
          (e) => Array.isArray(e) && e.length === 2 && typeof e[0] === "string" && typeof e[1] === "string"
        )
    );
  }

  mergeLastSessionHistory(sessionHistory) {
    if (typeof sessionHistory !== "object" || !sessionHistory) return;
    const sortedKeys = Object.keys(sessionHistory)
      .map(Number)
      .filter((k) => !isNaN(k))
      .sort((a, b) => a - b);
    for (const key of sortedKeys) {
      const record = sessionHistory[key];
      if (this.isValidTabRecord(record)) this.closedTabHistory.unshift(record);
    }
  }

  isValidTabRecord(record) {
    return (
      record &&
      Array.isArray(record.entries) &&
      typeof record.currentEntry === "number" &&
      record.currentEntry >= 0 &&
      record.currentEntry < record.entries.length
    );
  }

  async initializeTabData() {
    await this.waitForCondition(() => this.isInitialized.loading);
    try {
      const [activeTab] = await this.queryTabs({ active: true, currentWindow: true });
      if (activeTab) {
        this.currentTabId = this.previousTabId = activeTab.id;
        this.isInitialized.activeTab = true;
      }
      const allTabs = await this.queryTabs({});
      for (const tab of allTabs) await this.initializeTab(tab);
      this.isInitialized.tabs = true;
    } catch (error) {
      console.error("Failed to initialize tab data:", error);
    }
  }

  async initializeTab(tab) {
    const tabId = tab.id;
    const url = tab.url;
    const recoveredHistory = this.recoverTabHistory(url);
    if (recoveredHistory >= 0) {
      this.tabHistory[tabId] = this.closedTabHistory[recoveredHistory];
      this.closedTabHistory.splice(recoveredHistory, 1);
      postTabHistoryEvent("closed_tab_recovered", tabId, this.tabHistory[tabId]);
    } else {
      this.tabHistory[tabId] = { entries: [["typed", url]], currentEntry: 0 };
    }
    this.persist();
  }

  recoverTabHistory(url) {
    for (let i = 0; i < this.closedTabHistory.length; i++) {
      const record = this.closedTabHistory[i];
      if (record.entries[record.currentEntry][1] === url) return i;
    }
    return -1;
  }

  async waitForInitialization() {
    await this.waitForCondition(
      () => this.isInitialized.tabs && this.isInitialized.loading && this.isInitialized.activeTab
    );
  }

  async waitForCondition(condition, timeout = 10000) {
    const start = Date.now();
    while (!condition()) {
      if (Date.now() - start > timeout) throw new Error("Initialization timeout");
      await new Promise((r) => setTimeout(r, CONFIG.INIT_RETRY_MS));
    }
  }

  setupEventListeners() {
    chrome.tabs.onActivated.addListener((info) => {
      this.previousTabId = this.currentTabId;
      this.currentTabId = info.tabId;
    });
    chrome.webNavigation.onCommitted.addListener(this.handleNavigation.bind(this));
    chrome.tabs.onRemoved.addListener(this.handleTabRemoved.bind(this));
    chrome.tabs.onReplaced.addListener(this.handleTabReplaced.bind(this));
  }

  handleNavigation(details) {
    if (details.frameId !== 0) return;
    try {
      const isForwardBack = details.transitionQualifiers?.includes("forward_back");
      if (isForwardBack) {
        this.handleForwardBackNavigation(details.tabId, details.transitionType, details.url);
      } else if (details.transitionType === "reload") {
        this.handleReloadedTab(details.tabId, details.url);
      } else if (!this.tabHistory[details.tabId]) {
        this.handleNewTab(details.tabId, details.transitionType, details.url);
      } else {
        this.handleNormalNavigation(details.tabId, details.transitionType, details.url);
      }
    } catch (error) {
      console.error("Error handling navigation:", error);
    }
  }

  handleTabRemoved(tabId) {
    if (!this.tabHistory[tabId]) return;
    this.closedTabHistory.unshift(this.tabHistory[tabId]);
    delete this.tabHistory[tabId];
    if (this.closedTabHistory.length > CONFIG.MAX_CLOSED_TABS) this.closedTabHistory.pop();
    this.persist();
  }

  handleTabReplaced(addedTabId, removedTabId) {
    if (!this.tabHistory[removedTabId]) return;
    this.tabHistory[addedTabId] = this.tabHistory[removedTabId];
    delete this.tabHistory[removedTabId];
    this.persist();
  }

  handleForwardBackNavigation(tabId, transitionType, url) {
    if (!this.tabHistory[tabId]) {
      this.resetTabHistory(tabId, url, transitionType);
      postTabHistoryEvent("navigate", tabId, this.tabHistory[tabId]);
      this.persist();
      return;
    }
    const record = this.tabHistory[tabId];
    const previousUrl = record.currentEntry > 0 ? record.entries[record.currentEntry - 1][1] : "";
    const nextUrl = record.currentEntry + 1 < record.entries.length ? record.entries[record.currentEntry + 1][1] : "";
    let event;
    if (previousUrl === nextUrl || (url !== previousUrl && url !== nextUrl)) {
      this.resetTabHistory(tabId, url, transitionType);
      event = "navigate";
    } else if (url === previousUrl) {
      record.currentEntry--;
      event = "back";
    } else {
      record.currentEntry++;
      event = "forward";
    }
    postTabHistoryEvent(event, tabId, this.tabHistory[tabId]);
    this.persist();
  }

  handleReloadedTab(tabId, url) {
    if (this.tabHistory[tabId]) {
      postTabHistoryEvent("reload", tabId, this.tabHistory[tabId]);
      return;
    }
    const recoveredIndex = this.recoverTabHistory(url);
    if (recoveredIndex >= 0) {
      this.tabHistory[tabId] = this.closedTabHistory[recoveredIndex];
      this.closedTabHistory.splice(recoveredIndex, 1);
      postTabHistoryEvent("closed_tab_recovered", tabId, this.tabHistory[tabId]);
    } else {
      this.resetTabHistory(tabId, url);
      postTabHistoryEvent("reload", tabId, this.tabHistory[tabId]);
    }
    this.persist();
  }

  async handleNewTab(tabId, transitionType, url) {
    const tab = await this.getTab(tabId);
    if (!tab) return;
    this.tabHistory[tabId] = { entries: [], currentEntry: -1 };
    if (!tab.url.startsWith("chrome://newtab")) {
      const sourceId = tabId !== this.currentTabId ? this.currentTabId : this.previousTabId;
      if (this.tabHistory[sourceId]) {
        const sourceRecord = this.tabHistory[sourceId];
        this.tabHistory[tabId].entries = [...sourceRecord.entries.slice(0, sourceRecord.currentEntry + 1)];
        this.tabHistory[tabId].currentEntry = sourceRecord.currentEntry;
      }
    }
    this.addNewEntry(tabId, transitionType, url);
    this.pruneTabHistory(tabId);
    postTabHistoryEvent("new_tab", tabId, this.tabHistory[tabId]);
    this.persist();
  }

  handleNormalNavigation(tabId, transitionType, url) {
    const record = this.tabHistory[tabId];
    if (record.entries[record.currentEntry][1] === url) return;
    this.addNewEntry(tabId, transitionType, url);
    this.pruneTabHistory(tabId);
    postTabHistoryEvent("navigate", tabId, this.tabHistory[tabId]);
    this.persist();
  }

  addNewEntry(tabId, transitionType, url) {
    const record = this.tabHistory[tabId];
    record.entries.splice(record.currentEntry + 1);
    record.entries.push([transitionType, url]);
    record.currentEntry++;
  }

  resetTabHistory(tabId, url, transitionType = "typed") {
    this.tabHistory[tabId] = { entries: [[transitionType, url]], currentEntry: 0 };
  }

  pruneTabHistory(tabId) {
    const record = this.tabHistory[tabId];
    const excess = record.entries.length - CONFIG.MAX_TAB_HISTORY_SIZE;
    if (excess > 0 && record.currentEntry >= excess) {
      record.entries.splice(0, excess);
      record.currentEntry -= excess;
    }
  }

  isManualTransition(t) {
    return TRANSITION_TYPES.MANUAL.includes(t);
  }

  // Write-on-mutation, not a periodic timer (see header comment) -- an
  // MV3 service worker may not survive to the next tick of a setInterval.
  persist() {
    chrome.storage.local.set({
      [STORAGE_KEYS.CLOSED_TAB_HISTORY]: this.closedTabHistory,
      [STORAGE_KEYS.LAST_SESSION_HISTORY]: this.tabHistory,
    });
  }

  queryTabs(query) {
    return new Promise((resolve, reject) => {
      chrome.tabs.query(query, (tabs) => {
        if (chrome.runtime.lastError) reject(chrome.runtime.lastError);
        else resolve(tabs);
      });
    });
  }

  getTab(tabId) {
    return new Promise((resolve) => {
      chrome.tabs.get(tabId, (tab) => {
        if (chrome.runtime.lastError) resolve(null);
        else resolve(tab);
      });
    });
  }
}

new TabTracker().initialize();
