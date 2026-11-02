// On narrow screens, start with the table of contents collapsed so the docs come first.
(function () {
  const toc = document.querySelector(".docs-toc");
  if (toc && window.matchMedia("(max-width: 900px)").matches) toc.open = false;
})();
