(function () {
  var saved = null;
  try { saved = localStorage.getItem("theme"); } catch (e) {}
  if (saved !== "light" && saved !== "dark") {
    saved = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }
  document.documentElement.setAttribute("data-theme", saved);
})();
