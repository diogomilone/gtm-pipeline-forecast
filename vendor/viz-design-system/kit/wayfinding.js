/* Page kit, release 2.2.1: wayfinding. Load in <head> with defer, after kit/kit.js.
   - Section bar (.kit-section-bar): marks the link of the section in view with aria-current="true" and draws reading
     progress on .kit-progress (--kit-p from 0 to 1). On a narrow bar the marked link is scrolled into view, only when
     the section changes.
   - Fold ([data-kit-fold="<selector>"], label in data-kit-fold-label): more than 8 matching items move into one
     details.kit-disclosure.kit-fold, which opens (with the target, when it is a details) when the URL hash points at an
     item inside it, on load and on every hash change.
   - Next study (nav[data-next-study]): only over http or https, fetches ../studies.json. A valid list is
     {"version": 1, "studies": [{"slug", "href", "title", "headline"}, ...]} with non-empty strings and http or https
     links. The page is the entry whose slug equals the first segment of location.pathname, so "/<slug>/",
     "/<slug>/index.html" and "/<slug>/report.html" all match; only when no slug matches is each entry's href path compared
     with location.pathname (index.html, a .html ending and a trailing slash ignored). The next entry, cyclic, is linked
     with its href as given in one link (a.next-study-link) whose title and headline are written with textContent; the
     "All studies" link stays.
     Any failure, no match or a list of one keeps the link alone. data-next-study-state ends as "filled" or "fallback". */
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else if (root && root.document) api.install(root, root.document);
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  var FOLD_AFTER = 8;
  var FIELDS = ["slug", "href", "title", "headline"];

  function normalPath(path) {
    return String(path || "").replace(/(^|\/)index(\.html?)?$/, "$1").replace(/\.html?$/, "").replace(/\/+$/, "");
  }

  function firstSegment(path) {
    var segment = String(path || "").split("/").filter(Boolean)[0] || "";
    try { return decodeURIComponent(segment); } catch (e) { return segment; }
  }

  function validList(data) {
    if (!data || typeof data !== "object" || data.version !== 1 || !Array.isArray(data.studies)) return false;
    for (var i = 0; i < data.studies.length; i++) {
      var s = data.studies[i];
      if (!s || typeof s !== "object" || Array.isArray(s)) return false;
      for (var k = 0; k < FIELDS.length; k++) {
        var v = s[FIELDS[k]];
        if (typeof v !== "string" || !v.trim()) return false;
      }
    }
    return true;
  }

  // The study after the current page, cyclic, or null. pageUrl is location.href; listUrl is the studies.json URL that
  // relative hrefs resolve against (to check them and to compare paths; the link keeps the href as given).
  function nextStudy(data, pageUrl, listUrl) {
    if (!validList(data) || data.studies.length < 2) return null;
    var path = new URL(pageUrl).pathname;
    var links = [];
    for (var i = 0; i < data.studies.length; i++) {
      var url;
      try { url = new URL(data.studies[i].href, listUrl); } catch (e) { return null; }
      if (url.protocol !== "http:" && url.protocol !== "https:") return null;
      links.push(url);
    }
    var at = -1;
    var segment = firstSegment(path);
    for (var j = 0; j < links.length && segment; j++) {
      if (data.studies[j].slug === segment) { at = j; break; }
    }
    if (at < 0) {
      var here = normalPath(path);
      for (var h = 0; h < links.length; h++) {
        if (normalPath(links[h].pathname) === here) { at = h; break; }
      }
    }
    if (at < 0) return null;
    var n = (at + 1) % links.length;
    var s = data.studies[n];
    if (s.slug === data.studies[at].slug || normalPath(links[n].pathname) === normalPath(links[at].pathname)) return null;
    return {slug: s.slug, href: s.href, title: s.title, headline: s.headline};
  }

  function el(doc, tag, cls, text) {
    var e = doc.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function fillNext(doc, nav, study) {
    var hub = nav.querySelector("a");
    while (nav.firstChild) nav.removeChild(nav.firstChild);
    var card = el(doc, "div", "next-study-card");
    card.appendChild(el(doc, "p", "next-study-kicker", "Next study"));
    var link = el(doc, "a", "next-study-link");
    link.setAttribute("href", study.href);
    link.appendChild(el(doc, "span", "next-study-title", study.title));
    link.appendChild(el(doc, "span", "next-study-headline", study.headline));
    card.appendChild(link);
    if (hub) {
      var row = el(doc, "p", "next-study-links");
      row.appendChild(hub);
      card.appendChild(row);
    }
    nav.appendChild(card);
    nav.setAttribute("data-next-study-state", "filled");
  }

  function nextStudyBlocks(win, doc) {
    var navs = doc.querySelectorAll("[data-next-study]");
    if (!navs.length) return;
    var keep = function () {
      for (var i = 0; i < navs.length; i++) navs[i].setAttribute("data-next-study-state", "fallback");
    };
    var protocol = win.location.protocol;
    if ((protocol !== "http:" && protocol !== "https:") || typeof win.fetch !== "function") { keep(); return; }
    var listUrl = new URL("../studies.json", win.location.href).href;
    win.fetch(listUrl, {credentials: "same-origin"})
      .then(function (response) {
        if (!response.ok) throw new Error("studies.json: HTTP " + response.status);
        return response.json();
      })
      .then(function (data) {
        var study = nextStudy(data, win.location.href, listUrl);
        if (!study) { keep(); return; }
        for (var i = 0; i < navs.length; i++) fillNext(doc, navs[i], study);
      })
      .catch(keep);
  }

  function sectionBar(win, doc) {
    var bar = doc.querySelector(".kit-section-bar");
    if (!bar) return;
    var nav = bar.querySelector(".page-nav") || bar;
    var links = Array.prototype.slice.call(nav.querySelectorAll('a[href^="#"]'));
    var targets = links.map(function (a) {
      var id = a.getAttribute("href").slice(1);
      try { id = decodeURIComponent(id); } catch (e) { /* keep the raw id */ }
      return id ? doc.getElementById(id) : null;
    });
    var progress = bar.querySelector(".kit-progress");
    var last = -2;
    var ticking = false;
    function update() {
      ticking = false;
      var top = doc.documentElement;
      var pad = parseFloat(win.getComputedStyle(top).scrollPaddingTop) || 0;
      // A section is current once its top passes just under the stuck bar (or the scroll padding, if larger).
      var line = Math.max(bar.getBoundingClientRect().bottom, pad) + 24;
      var current = -1;
      for (var i = 0; i < targets.length; i++) {
        if (targets[i] && targets[i].getBoundingClientRect().top - line <= 0) current = i;
      }
      var max = top.scrollHeight - win.innerHeight;
      // At the very end of the page the last section in view is current, even when it is too short to reach the line.
      if (max > 0 && win.scrollY >= max - 2) {
        for (var k = targets.length - 1; k > current; k--) {
          if (targets[k] && targets[k].getBoundingClientRect().top < win.innerHeight) { current = k; break; }
        }
      }
      if (current !== last) {
        last = current;
        links.forEach(function (a, i) {
          if (i === current) a.setAttribute("aria-current", "true"); else a.removeAttribute("aria-current");
        });
        if (current >= 0 && nav.scrollWidth > nav.clientWidth) {
          var a = links[current].getBoundingClientRect();
          var n = nav.getBoundingClientRect();
          nav.scrollLeft = Math.max(0, nav.scrollLeft + (a.left + a.width / 2) - (n.left + nav.clientWidth / 2));
        }
      }
      if (progress) progress.style.setProperty("--kit-p", max > 0 ? Math.min(1, Math.max(0, win.scrollY / max)).toFixed(4) : "0");
    }
    win.addEventListener("scroll", function () {
      if (!ticking) { ticking = true; win.requestAnimationFrame(update); }
    }, {passive: true});
    win.addEventListener("resize", update);
    update();
  }

  function folds(win, doc) {
    var made = [];
    var boxes = doc.querySelectorAll("[data-kit-fold]");
    for (var b = 0; b < boxes.length; b++) {
      var box = boxes[b];
      var items;
      try { items = box.querySelectorAll(box.getAttribute("data-kit-fold")); } catch (e) { continue; }
      if (items.length <= FOLD_AFTER) continue;
      var details = el(doc, "details", "kit-disclosure kit-fold");
      details.appendChild(el(doc, "summary", null, box.getAttribute("data-kit-fold-label") || "All " + items.length + " items"));
      items[0].parentNode.insertBefore(details, items[0]);
      for (var i = 0; i < items.length; i++) details.appendChild(items[i]);
      made.push(details);
    }
    if (!made.length) return;
    function reveal() {
      var id = win.location.hash.slice(1);
      try { id = decodeURIComponent(id); } catch (e) { /* keep the raw id */ }
      var target = id && doc.getElementById(id);
      if (!target) return;
      for (var i = 0; i < made.length; i++) {
        if (made[i].contains(target)) {
          made[i].open = true;
          if (target.tagName === "DETAILS") target.open = true;
          target.scrollIntoView();
        }
      }
    }
    win.addEventListener("hashchange", reveal);
    reveal();
  }

  function install(win, doc) {
    var parts = [folds, sectionBar, nextStudyBlocks];
    for (var i = 0; i < parts.length; i++) {
      try { parts[i](win, doc); } catch (e) { /* one part failing leaves the others and the static page working */ }
    }
  }

  return {install: install, nextStudy: nextStudy, validList: validList, normalPath: normalPath, firstSegment: firstSegment,
          FOLD_AFTER: FOLD_AFTER};
});
