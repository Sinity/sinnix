// ==UserScript==
// @name         Cookie Nag Zapper
// @namespace    https://realm.sinnix/qutebrowser
// @version      0.1
// @description  Hide generic cookie / consent overlays on frequently visited sites.
// @match        *://*/*
// @run-at       document-idle
// @grant        none
// ==/UserScript==

(function () {
  const selectors = [
    '[class*="cookie"]',
    '[id*="cookie"]',
    '[class*="consent"]',
    '[id*="consent"]',
    '[aria-label*="cookie"]',
    '[aria-label*="consent"]',
    '[data-testid*="cookie"]',
    '[data-testid*="consent"]',
    'div[class*="gdpr"]',
  ];

  const nuke = () => {
    selectors.forEach((selector) => {
      document.querySelectorAll(selector).forEach((el) => {
        el.style.setProperty('display', 'none', 'important');
        el.style.setProperty('visibility', 'hidden', 'important');
      });
    });
    document.body.style.overflow = 'auto';
  };

  const observer = new MutationObserver(nuke);
  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
  });

  nuke();
})();
