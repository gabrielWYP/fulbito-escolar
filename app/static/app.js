// Copa Escolar de Fulbito - interacciones mínimas (sin dependencias)
(function () {
  "use strict";

  // --- Tema claro/oscuro con persistencia ---
  var root = document.documentElement;
  var KEY = "fulbito-theme";
  try {
    var saved = localStorage.getItem(KEY);
    if (saved === "light" || saved === "dark") {
      root.setAttribute("data-theme", saved);
    } else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
      root.setAttribute("data-theme", "dark");
    }
  } catch (e) { /* localStorage no disponible */ }

  var toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem(KEY, next); } catch (e) { /* ignore */ }
    });
  }

  // --- Pestañas (tabs) accesibles ---
  var tabs = Array.prototype.slice.call(document.querySelectorAll(".tab"));
  var panels = Array.prototype.slice.call(document.querySelectorAll(".tab-panel"));
  function activate(name) {
    tabs.forEach(function (t) {
      var on = t.getAttribute("data-tab") === name;
      t.classList.toggle("active", on);
      t.setAttribute("aria-selected", on ? "true" : "false");
    });
    panels.forEach(function (p) {
      p.classList.toggle("active", p.getAttribute("data-panel") === name);
    });
  }
  tabs.forEach(function (t) {
    t.addEventListener("click", function () { activate(t.getAttribute("data-tab")); });
  });
})();
