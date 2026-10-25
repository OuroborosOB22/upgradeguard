"use strict";
document.addEventListener("DOMContentLoaded", function () {
  var toggle = document.getElementById("theme");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem("theme", next); } catch (e) {}
    });
  }
  var tabs = document.querySelectorAll("[data-tab]");
  Array.prototype.forEach.call(tabs, function (tab) {
    tab.addEventListener("click", function () {
      Array.prototype.forEach.call(tabs, function (other) {
        var active = other === tab;
        other.setAttribute("aria-selected", String(active));
        document.getElementById("tab-" + other.dataset.tab).hidden = !active;
      });
    });
  });
});
