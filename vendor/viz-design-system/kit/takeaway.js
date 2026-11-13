/* Page kit, release 2.2.0: takeaway figure motion. Load in <head> without defer, after kit/kit.js.
   When motion is allowed (prefers-reduced-motion: no-preference) and IntersectionObserver exists, it adds tk-js to <html>
   at once, so a figure already in view never paints finished and then restarts. On DOMContentLoaded it adds tk-ready and
   plays each .takeaway figure once (adds tk-play) when 15% of it is in view. If tk-ready has not arrived 3 s after the
   script ran, it drops tk-js and the figures stay finished. Without tk-js (reduced motion, no IntersectionObserver, no
   script) every figure is static and complete. */
(function (root) {
  "use strict";
  var doc = root && root.document;
  var html = doc && doc.documentElement;
  if (!html || !root.matchMedia || !("IntersectionObserver" in root)) return;
  if (!root.matchMedia("(prefers-reduced-motion: no-preference)").matches) return;
  var THRESHOLD = 0.15;
  html.classList.add("tk-js");
  root.setTimeout(function () {
    if (!html.classList.contains("tk-ready")) html.classList.remove("tk-js");
  }, 3000);

  function init() {
    // Disarmed after 3 s: the figures stay in their final state and never play.
    if (!html.classList.contains("tk-js")) return;
    html.classList.add("tk-ready");
    var figures = doc.querySelectorAll(".takeaway");
    if (!figures.length) return;
    var observer = new root.IntersectionObserver(function (entries) {
      for (var i = 0; i < entries.length; i++) {
        var entry = entries[i];
        // The first report after observe() comes at any ratio; play only once 15% is in view.
        if (entry.isIntersecting && entry.intersectionRatio >= THRESHOLD - 0.001) {
          entry.target.classList.add("tk-play");
          observer.unobserve(entry.target);
        }
      }
    }, {threshold: THRESHOLD});
    for (var i = 0; i < figures.length; i++) observer.observe(figures[i]);
  }

  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", init);
  else init();
})(typeof window !== "undefined" ? window : this);
