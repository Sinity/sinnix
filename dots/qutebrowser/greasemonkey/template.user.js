// ==UserScript==
// @name         Site Specific Template
// @namespace    https://realm.sinnix/qutebrowser
// @version      0.1
// @description  Template script – copy, rename, and adjust @match / logic per site.
// @match        *://example.com/*
// @run-at       document-idle
// @grant        none
// ==/UserScript==

(function () {
  // Example: automatically expand hidden sections.
  document
    .querySelectorAll('[data-action="expand"], .expand-button')
    .forEach((button) => button.click());
})();
