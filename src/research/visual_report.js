/* RiffBand Visual Report — JavaScript for TOC + anchors + theme */
(function() {

/* ── Theme Toggle ──────────────────────────────── */
window.toggleTheme = function() {
  var html = document.documentElement;
  html.dataset.theme = html.dataset.theme === "dark" ? "light" : "dark";
  localStorage.setItem("theme", html.dataset.theme);
};

(function() {
  var saved = localStorage.getItem("theme");
  if (saved) document.documentElement.dataset.theme = saved;
})();

/* ── Anchor Links ──────────────────────────────── */
(function() {
  var headings = document.querySelectorAll(".prose h1, .prose h2, .prose h3, .prose h4");
  headings.forEach(function(h) {
    if (!h.id) return;
    var anchor = document.createElement("a");
    anchor.href = "#" + h.id;
    anchor.className = "heading-anchor";
    anchor.setAttribute("aria-label", "Link to this section");
    anchor.innerHTML = " #";
    anchor.style.cssText = "opacity:0;font-size:0.8em;text-decoration:none;transition:opacity 0.15s;margin-left:4px;";
    h.appendChild(anchor);
    h.addEventListener("mouseenter", function() { anchor.style.opacity = "1"; });
    h.addEventListener("mouseleave", function() { anchor.style.opacity = "0"; });
  });
})();

/* ── TOC Scroll Highlight ─────────────────────── */
(function() {
  var tocLinks = document.querySelectorAll(".toc a");
  var sections = [];
  tocLinks.forEach(function(link) {
    var href = link.getAttribute("href");
    if (!href || !href.startsWith("#")) return;
    var target = document.getElementById(href.slice(1));
    if (target) sections.push({ link: link, target: target });
  });

  if (sections.length === 0) return;

  function onScroll() {
    var scrollTop = window.scrollY + 80;
    var active = null;
    for (var i = sections.length - 1; i >= 0; i--) {
      if (sections[i].target.offsetTop <= scrollTop) {
        active = sections[i];
        break;
      }
    }
    sections.forEach(function(s) { s.link.classList.remove("active"); });
    if (active) active.link.classList.add("active");
  }

  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
})();

/* ── Smooth Scroll ────────────────────────────── */
(function() {
  document.addEventListener("click", function(e) {
    var link = e.target.closest("a");
    if (!link) return;
    var href = link.getAttribute("href");
    if (!href || !href.startsWith("#")) return;
    var target = document.getElementById(href.slice(1));
    if (!target) return;
    e.preventDefault();
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    history.pushState(null, "", href);
  });
})();

})();
