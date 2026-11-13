/* Page kit, release 2.0.0: theme control only.
   Follows the system setting by default ("auto": no data-theme attribute). Each press of a
   [data-theme-toggle] button moves auto -> light -> dark -> auto and sets data-theme on <html>.
   The choice is remembered in localStorage when storage works; every access is wrapped in try/catch.
   ?theme=light|dark|auto in the URL applies for that load only (used for captures).
   Load in <head> without defer so the stored theme applies before first paint. */
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else if (root && root.document) api.install(root, root.document);
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  var KEY = "viz-theme";
  var MODES = ["auto", "light", "dark"];
  var LABEL = "Theme";

  function valid(mode) { return MODES.indexOf(mode) >= 0; }

  function fromQuery(win) {
    try {
      var q = new URLSearchParams(win.location.search).get("theme");
      return valid(q) ? q : null;
    } catch (e) { return null; }
  }

  function stored(win) {
    try {
      var v = win.localStorage.getItem(KEY);
      return valid(v) ? v : null;
    } catch (e) { return null; }
  }

  function remember(win, mode) {
    try { win.localStorage.setItem(KEY, mode); } catch (e) { /* storage unavailable: the choice lasts for this page only */ }
  }

  function apply(doc, mode) {
    if (mode === "light" || mode === "dark") doc.documentElement.setAttribute("data-theme", mode);
    else doc.documentElement.removeAttribute("data-theme");
  }

  function next(mode) { return MODES[(MODES.indexOf(mode) + 1) % MODES.length]; }

  function install(win, doc) {
    var state = { mode: fromQuery(win) || stored(win) || "auto" };
    apply(doc, state.mode);
    function label(button) { button.textContent = LABEL + ": " + state.mode; }
    function bind() {
      var buttons = doc.querySelectorAll("[data-theme-toggle]");
      for (var i = 0; i < buttons.length; i++) {
        label(buttons[i]);
        buttons[i].addEventListener("click", function () {
          state.mode = next(state.mode);
          apply(doc, state.mode);
          remember(win, state.mode);
          for (var j = 0; j < buttons.length; j++) label(buttons[j]);
        });
      }
      doc.documentElement.setAttribute("data-kit-ready", "true");
    }
    if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", bind);
    else bind();
    return state;
  }

  return { VERSION: "2.0.0", KEY: KEY, MODES: MODES, LABEL: LABEL, next: next, apply: apply, install: install };
});
