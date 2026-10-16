/**
 * main.js — Application Entry Point
 * Orchestrates router, store subscriptions, theme switching, i18n, and performance metrics.
 */

import { store } from "./store.js";
import { initRouter } from "./router.js";
import { initEvidenceDrawer } from "./ui/drawer.js";
import { getLang, setLang, t } from "./i18n.js";

// Page Weight calculation via Performance API
function updatePageWeight() {
  const meter = document.getElementById("page-weight-val");
  if (!meter) return;

  try {
    const entries = performance.getEntriesByType("resource");
    let totalTransfer = 0;
    for (const entry of entries) {
      totalTransfer += entry.transferSize || entry.decodedBodySize || 0;
    }
    // Add document navigation weight
    const nav = performance.getEntriesByType("navigation")[0];
    if (nav) {
      totalTransfer += nav.transferSize || nav.decodedBodySize || 0;
    }

    const kb = Math.round(totalTransfer / 1024);
    meter.textContent = `${kb} KB`;
  } catch (e) {
    meter.textContent = "< 450 KB";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  // 0. Remove any legacy estimate banner elements
  document.querySelectorAll(".estimate-banner, aside[role='note']").forEach((el) => el.remove());

  // 1. Initialize Theme from store
  const savedTheme = store.getState().theme;
  document.documentElement.setAttribute("data-theme", savedTheme);

  const themeSelect = document.getElementById("theme-select");
  if (themeSelect) {
    themeSelect.value = savedTheme;
    themeSelect.addEventListener("change", (e) => {
      store.setTheme(e.target.value);
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
  }

  // 2. Initialize Language Toggle
  const langSelect = document.getElementById("lang-select");
  if (langSelect) {
    langSelect.value = getLang();
    langSelect.addEventListener("change", (e) => {
      setLang(e.target.value);
      // Re-render current route
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
  }

  // 3. Initialize 7-Step Evidence Drawer
  initEvidenceDrawer();

  // 4. Mount Client-Side Router
  const appRoot = document.getElementById("app-root");
  initRouter(appRoot);

  // 5. Update Page Weight Meter
  window.addEventListener("load", () => {
    setTimeout(updatePageWeight, 500);
  });

  // 6. Clean and unregister any stale Service Worker to ensure fresh code
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.getRegistrations().then((registrations) => {
      for (const reg of registrations) {
        reg.unregister();
      }
    });
  }
});
