// A refresh starts at the top of the page. Browsers otherwise restore the old scroll position
// and jump back to any #section in the address bar. Links opened fresh, such as /docs#roadmap,
// still go to their section: only reloads are reset. Loaded in <head> so it runs first.
(function () {
  if ("scrollRestoration" in history) history.scrollRestoration = "manual";
  var nav = performance.getEntriesByType && performance.getEntriesByType("navigation")[0];
  if (!nav || nav.type !== "reload") return;
  if (location.hash) history.replaceState(null, "", location.pathname + location.search);
  var top = function () { window.scrollTo({ top: 0, left: 0, behavior: "instant" }); };
  top();
  window.addEventListener("DOMContentLoaded", top);
  window.addEventListener("load", top);
})();
