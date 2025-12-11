// ==UserScript==
// @name         Medium Reader Mode
// @namespace    https://realm.sinnix/qutebrowser
// @version      0.1
// @description  Strip Medium overlays and switch to a clean reader-friendly layout.
// @match        *://*.medium.com/*/*
// @match        *://medium.com/*/*
// @run-at       document-end
// @grant        none
// ==/UserScript==

(function () {
  const hideSelectors = [
    'div[data-test-id="verification-prompt"]',
    'div[data-test-id="paywall-banner"]',
    'div[data-test-id="m-interstitial"]',
    'div[data-test-id="post-meter-banner"]',
    'div[data-testid="overlay"]',
    'div[data-testid="paywall"]',
    'aside',
    'footer',
  ];

  const applyReaderStyles = () => {
    document.body.style.overflow = 'auto';
    document.body.style.maxWidth = '72ch';
    document.body.style.margin = '2rem auto';
    document.body.style.padding = '0 1.5rem';
    document.body.style.fontSize = '18px';
    document.body.style.lineHeight = '1.7';
  };

  const nuke = () => {
    hideSelectors.forEach((selector) => {
      document.querySelectorAll(selector).forEach((el) => {
        el.remove();
      });
    });
    applyReaderStyles();
  };

  const observer = new MutationObserver(nuke);
  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
  });

  nuke();
})();
