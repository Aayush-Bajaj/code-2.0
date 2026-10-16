/**
 * router.js — Client-Side Hash Router
 * Supports routes: #/start, #/upload, #/review, #/results, #/twin, #/report, #/methods
 * and deep link #/evidence/<line_id>
 */

import { renderStartView } from "./views/start.js?v=3.3";
import { renderUploadView } from "./views/upload.js?v=3.1";
import { renderReviewView } from "./views/review.js?v=3.1";
import { renderResultsView } from "./views/results.js?v=3.3";
import { renderTwinView } from "./views/twin.js?v=3.1";
import { renderReportView } from "./views/report.js?v=3.1";
import { renderMethodsView } from "./views/methods.js?v=3.1";
import { openEvidenceDrawer } from "./ui/drawer.js?v=3.1";

const routes = {
  "#/start": renderStartView,
  "#/upload": renderUploadView,
  "#/review": renderReviewView,
  "#/results": renderResultsView,
  "#/twin": renderTwinView,
  "#/report": renderReportView,
  "#/methods": renderMethodsView,
};


export function registerRoute(hash, viewFn) {
  routes[hash] = viewFn;
}

export function initRouter(mountPointElement) {
  function handleRoute() {
    let hash = window.location.hash || "#/start";

    // Handle deep-linked evidence drawer: #/evidence/<id>
    if (hash.startsWith("#/evidence/")) {
      const lineId = hash.replace("#/evidence/", "").trim();
      // Render results view as background if not already active
      mountPointElement.innerHTML = "";
      mountPointElement.appendChild(renderResultsView());
      updateActiveNav("#/results");
      openEvidenceDrawer(lineId);
      return;
    }

    // Default or Registered routes
    const viewFn = routes[hash] || routes["#/start"];
    mountPointElement.innerHTML = "";
    mountPointElement.appendChild(viewFn());
    updateActiveNav(hash);
    window.scrollTo(0, 0);
  }

  window.addEventListener("hashchange", handleRoute);
  handleRoute();
}

function updateActiveNav(activeHash) {
  document.querySelectorAll(".nav-link").forEach((link) => {
    if (link.getAttribute("href") === activeHash) {
      link.classList.add("active");
    } else {
      link.classList.remove("active");
    }
  });
}
