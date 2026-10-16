/**
 * results.js — Main Results Dashboard View
 * Displays huge animated total, range band, yearly toggle, scope doughnut,
 * EmissionLines table with range bars, Data Confidence gauge, and evidence triggers.
 */

import { store } from "../store.js";
import { api } from "../api.js";
import { renderScopeDonut } from "../charts/donut.js";
import { renderRangeBar } from "../charts/rangeBar.js";
import { openEvidenceDrawer } from "../ui/drawer.js";
import { t } from "../i18n.js";

export function renderResultsView() {
  const container = document.createElement("div");
  container.className = "fade-in";

  const state = store.getState();
  const totals = store.getTotals();
  const confidence = store.getDataConfidence();
  const isYearly = state.periodView === "year";
  const periodLabel = isYearly ? "Annualized Baseline (12 Months)" : "Monthly Baseline (March 2024)";

  const co2eFormatted = totals.total.co2e.toLocaleString("en-IN", { maximumFractionDigits: 1 });
  const lowFormatted = totals.total.low.toLocaleString("en-IN", { maximumFractionDigits: 1 });
  const highFormatted = totals.total.high.toLocaleString("en-IN", { maximumFractionDigits: 1 });

  function renderTableRows(lines, multiplier) {
    return lines.map((line) => {
      const co2e = (line.co2e_kg * multiplier).toLocaleString("en-IN", { maximumFractionDigits: 1 });
      const low = line.low_kg * multiplier;
      const high = line.high_kg * multiplier;
      const val = line.co2e_kg * multiplier;

      return `
        <tr>
          <td>
            <div style="font-weight:600; color:var(--text-primary);">${line.category}</div>
            ${line.flags?.includes("MAINTENANCE_WIDENED_RANGE")
              ? `<div style="margin-top:3px;"><span class="badge badge-smoke-heavy">⚠️ Plume Opacity Maintenance Flag</span></div>`
              : ""}
          </td>
          <td>
            <span class="badge badge-scope${line.scope}">Scope ${line.scope}</span>
          </td>
          <td style="font-family:var(--font-mono); font-size:var(--text-xs);">
            <b>${(line.activity_value * multiplier).toLocaleString("en-IN")}</b> ${line.activity_unit}
          </td>
          <td>
            <!-- Evidence Trigger Button -->
            <button class="btn-evidence-chip line-evidence-btn" data-line-id="${line.id}" title="Click to view full 7-step calculation evidence">
              ${co2e} kg
            </button>
          </td>
          <td>
            ${renderRangeBar(low, val, high, "kg")}
          </td>
          <td style="text-align:right;">
            <button class="btn btn-secondary btn-sm line-evidence-btn" data-line-id="${line.id}">
              Audit Trail
            </button>
          </td>
        </tr>
      `;
    }).join("");
  }

  container.innerHTML = `
    <!-- Top Header & Period View Toggle -->
    <div style="display:flex; flex-wrap:wrap; justify-content:space-between; align-items:flex-end; gap:var(--space-4); margin-bottom:var(--space-8);">
      <div>
        <div style="font-size:11px; color:var(--brand-accent); text-transform:uppercase; font-weight:700; letter-spacing:0.06em; margin-bottom:4px;">
          Enterprise Activity Footprint
        </div>
        <h1 style="font-size:var(--text-3xl); font-weight:800; color:var(--text-primary); letter-spacing:-0.03em; margin-bottom:6px;">
          ${state.facilityName}
        </h1>
        <div style="display:flex; align-items:center; flex-wrap:wrap; gap:var(--space-3); font-size:var(--text-xs); color:var(--text-secondary);">
          <span style="display:inline-flex; align-items:center; gap:4px;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
            ${state.facilityLocation}
          </span>
          <span style="color:var(--border-strong);">•</span>
          <span style="display:inline-flex; align-items:center; gap:4px;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
            <span id="hero-period-label">${periodLabel}</span>
          </span>
        </div>
      </div>

      <!-- Year / Month Segmented Switcher -->
      <div style="display:inline-flex; align-items:center; background:var(--bg-muted); padding:3px; border:1px solid var(--border-subtle); border-radius:var(--radius-lg); box-shadow:var(--shadow-xs);">
        <button id="toggle-monthly-btn" class="btn btn-sm ${!isYearly ? 'btn-primary' : 'btn-secondary'}" style="${!isYearly ? 'box-shadow:var(--shadow-xs);' : 'border:none; background:transparent;'}">
          Monthly Baseline
        </button>
        <button id="toggle-yearly-btn" class="btn btn-sm ${isYearly ? 'btn-primary' : 'btn-secondary'}" style="${isYearly ? 'box-shadow:var(--shadow-xs);' : 'border:none; background:transparent;'}">
          ${t("yearly_view")} (x12)
        </button>
      </div>
    </div>

    <!-- Hero Stats Grid -->
    <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap:var(--space-6); margin-bottom:var(--space-8);">
      
      <!-- Big Total Footprint Card -->
      <div class="card" style="display:flex; flex-direction:column; justify-content:space-between; position:relative; overflow:hidden;">
        <div>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:var(--space-3);">
            <span style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.06em;">
              ${t("total_footprint")}
            </span>
            <span id="hero-period-badge" class="badge badge-scope2" style="font-family:var(--font-mono);">
              ${isYearly ? "tCO2e / yr" : "kg CO2e / mo"}
            </span>
          </div>

          <div style="font-size:clamp(2.5rem, 6vw, 3.5rem); font-weight:800; color:var(--brand-primary); line-height:1; margin-bottom:var(--space-3); font-family:var(--font-mono); letter-spacing:-0.03em;">
            <span id="hero-co2e-val" class="count-up-number">${co2eFormatted}</span>
            <span id="hero-unit-label" style="font-size:var(--text-base); font-weight:600; color:var(--text-muted); letter-spacing:normal;">kg CO<sub>2</sub>e</span>
          </div>

          <!-- Uncertainty Range Band Pill -->
          <div style="display:flex; align-items:center; gap:var(--space-2); background:var(--bg-subtle); border:1px solid var(--border-subtle); padding:6px 12px; border-radius:var(--radius-md); font-size:var(--text-xs); color:var(--text-secondary);">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
            <span><b>Uncertainty Band:</b></span>
            <span id="hero-low-val" style="font-family:var(--font-mono); font-weight:700; color:var(--text-primary);">${lowFormatted}</span>
            <span>to</span>
            <span id="hero-high-val" style="font-family:var(--font-mono); font-weight:700; color:var(--text-primary);">${highFormatted}</span>
            <span>kg</span>
          </div>
        </div>

        <!-- Equivalent Activity Box (API Derived Only) -->
        <div id="equivalents-box" style="margin-top:var(--space-5); padding-top:var(--space-3); border-top:1px solid var(--border-subtle); font-size:var(--text-xs); color:var(--text-secondary);">
          <div style="display:flex; align-items:center; gap:6px;">
            <span>⚡ Calculating activity equivalents...</span>
          </div>
        </div>
      </div>

      <!-- Data Confidence Score Card -->
      <div class="card" style="display:flex; flex-direction:column; justify-content:space-between;">
        <div>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:var(--space-3);">
            <span style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.06em;">
              ${t("data_confidence")}
            </span>
            <button id="confidence-info-btn" style="background:none; border:none; padding:0; font-size:var(--text-xs); color:var(--text-secondary); cursor:pointer; display:inline-flex; align-items:center; gap:4px; text-decoration:underline; text-underline-offset:2px;" title="${confidence.formula}">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
              Calculation basis
            </button>
          </div>

          <div style="display:flex; align-items:baseline; gap:var(--space-3); margin-bottom:var(--space-3);">
            <span class="confidence-score">${confidence.score}%</span>
            <span class="badge" style="background:var(--brand-accent-light); color:var(--brand-accent-hover); border:1px solid var(--brand-accent-subtle);">
              ${confidence.label}
            </span>
          </div>

          <div class="confidence-progress" style="margin-bottom:var(--space-4);">
            <div class="confidence-progress-fill" style="width: ${confidence.score}%;"></div>
          </div>

          <div style="display:flex; flex-direction:column; gap:8px; font-size:var(--text-xs); color:var(--text-secondary);">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span style="display:inline-flex; align-items:center; gap:6px;">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--brand-accent)" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                Verified Utility Invoices
              </span>
              <b style="font-family:var(--font-mono); color:var(--text-primary);">${confidence.breakdown.billScore} / 40 pts</b>
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span style="display:inline-flex; align-items:center; gap:6px;">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--brand-accent)" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                SHA-256 Hashes Verified
              </span>
              <b style="font-family:var(--font-mono); color:var(--text-primary);">${confidence.breakdown.hashScore} / 35 pts</b>
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span style="display:inline-flex; align-items:center; gap:6px;">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--brand-accent)" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                Uncertainty Range Tightness
              </span>
              <b style="font-family:var(--font-mono); color:var(--text-primary);">${confidence.breakdown.rangeScore} / 25 pts</b>
            </div>
          </div>
        </div>

        <div style="margin-top:var(--space-4); font-size:11px; color:var(--text-muted); border-top:1px solid var(--border-subtle); padding-top:var(--space-2);">
          Governance: Empirically verified through cryptographic file hashes and utility certificates.
        </div>
      </div>

      <!-- Scope Breakdown Donut Chart -->
      <div class="card" style="display:flex; flex-direction:column;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:var(--space-2);">
          <span style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.06em;">
            GHG Protocol Breakdown
          </span>
          <span class="badge badge-scope1">Scope 1 · 2 · 3</span>
        </div>
        <div style="position:relative; flex:1; min-height:190px;">
          <canvas id="scope-donut-canvas"></canvas>
        </div>
      </div>

    </div>

    <!-- Emission Lines Table (Every Number is Clickable Evidence) -->
    <div class="card" style="margin-bottom:var(--space-8); padding:0; overflow:hidden;">
      <div style="padding:var(--space-5) var(--space-6); border-bottom:1px solid var(--border-subtle); background:var(--bg-subtle);">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:var(--space-2);">
          <div>
            <h2 style="font-size:var(--text-base); font-weight:700; margin-bottom:2px;">Detailed Emissions Inventory</h2>
            <p style="font-size:var(--text-xs); color:var(--text-secondary); margin:0;">
              Every row is linked to an auditable 7-step cryptographic proof trail. Click any value to inspect.
            </p>
          </div>
          <span class="badge" style="background:var(--bg-surface); border:1px solid var(--border-medium); color:var(--text-secondary); font-family:var(--font-mono);">
            ${state.baselineLines.length} Verified Sources
          </span>
        </div>
      </div>

      <div class="table-responsive" style="border:none; border-radius:0;">
        <table class="data-table">
          <thead>
            <tr>
              <th>Emission Stream</th>
              <th>Scope Classification</th>
              <th>Activity Volume</th>
              <th>Calculated Footprint</th>
              <th>Uncertainty Range Band</th>
              <th style="text-align:right;">Audit Trail</th>
            </tr>
          </thead>
          <tbody id="emissions-tbody">
            ${renderTableRows(state.baselineLines, totals.multiplier)}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Smart Energy & Electricity Calculator Section -->
    <section class="smart-energy-section" style="margin-bottom:var(--space-6);">
      <div style="display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:var(--space-6);">
        <div style="display:flex; align-items:flex-start; gap:var(--space-4); max-width:740px;">
          <!-- Energy / Leaf / Lightning Icon Badge -->
          <div class="smart-energy-icon-wrap">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
            </svg>
          </div>
          <div style="display:flex; flex-direction:column; gap:4px;">
            <div class="smart-energy-eyebrow">
              <span>Energy Intelligence</span>
              <span style="opacity:0.4;">•</span>
              <span>Cost &amp; Solar Optimization</span>
            </div>
            <h2 class="smart-energy-title">
              Smart Energy &amp; Electricity Calculator
            </h2>
            <p class="smart-energy-desc">
              Take control of your energy consumption. Estimate electricity costs, analyze appliance usage, explore solar savings, and understand your environmental impact with our intelligent energy calculator.
            </p>
          </div>
        </div>

        <!-- CTA Button -->
        <div style="display:flex; align-items:center;">
          <a href="https://smartenergycalculator.netlify.app/" target="_blank" rel="noopener noreferrer" class="smart-energy-cta-btn">
            <span>Explore Smart Energy Calculator &rarr;</span>
          </a>
        </div>
      </div>
    </section>

    <!-- Bottom Action Bar -->
    <div style="display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:var(--space-4); background:var(--bg-surface); border:1px solid var(--border-subtle); padding:var(--space-5) var(--space-6); border-radius:var(--radius-xl); box-shadow:var(--shadow-sm);">
      <div>
        <div style="font-size:var(--text-sm); font-weight:700; color:var(--text-primary);">Explore Decarbonisation Pathways & Reports</div>
        <div style="font-size:var(--text-xs); color:var(--text-secondary); margin-top:2px;">Simulate solar rooftop and electrification ROI in Digital Twin, or generate compliant disclosures.</div>
      </div>
      <div style="display:flex; gap:var(--space-3);">
        <button id="goto-twin-btn" class="btn btn-secondary">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
          <span>Digital Twin Simulator</span>
        </button>
        <button id="goto-report-btn" class="btn btn-primary">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          <span>Generate Buyer Report</span>
        </button>
      </div>
    </div>
  `;

  // Attach Evidence Click Listeners
  function attachEvidenceListeners() {
    container.querySelectorAll(".line-evidence-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const lineId = btn.getAttribute("data-line-id");
        openEvidenceDrawer(lineId);
      });
    });
  }
  attachEvidenceListeners();

  // Fetch /meta/equivalents asynchronously
  function fetchEquivalents(co2eVal) {
    api.getMetaEquivalents(co2eVal).then((eq) => {
      const eqBox = container.querySelector("#equivalents-box");
      if (eqBox && eq) {
        eqBox.innerHTML = `
          <div style="display:flex; flex-direction:column; gap:4px; font-size:11px;">
            <div style="display:flex; align-items:center; gap:6px;">
              <span style="color:var(--scope-1);">•</span>
              <span>Equal to burning <b>${eq.diesel_litres.toLocaleString("en-IN", { maximumFractionDigits: 1 })} litres</b> of diesel fuel</span>
            </div>
            <div style="display:flex; align-items:center; gap:6px;">
              <span style="color:var(--brand-accent);">•</span>
              <span>Equivalent to <b>${eq.grid_kwh.toLocaleString("en-IN", { maximumFractionDigits: 1 })} kWh</b> of grid electricity</span>
            </div>
          </div>
        `;
      }
    });
  }

  // Reactive UI update function when Month/Year mode toggles
  function updatePeriodUI() {
    const curState = store.getState();
    const curTotals = store.getTotals();
    const curYearly = curState.periodView === "year";
    const curLabel = curYearly ? "Annualized Baseline (12 Months)" : "Monthly Baseline (March 2024)";

    // Update header label and badge
    const periodLabelEl = container.querySelector("#hero-period-label");
    if (periodLabelEl) periodLabelEl.textContent = curLabel;

    const badgeEl = container.querySelector("#hero-period-badge");
    if (badgeEl) badgeEl.textContent = curYearly ? "tCO2e / yr" : "kg CO2e / mo";

    // Update buttons
    const btnMonth = container.querySelector("#toggle-monthly-btn");
    const btnYear = container.querySelector("#toggle-yearly-btn");
    if (btnMonth && btnYear) {
      if (!curYearly) {
        btnMonth.className = "btn btn-sm btn-primary";
        btnMonth.style.boxShadow = "var(--shadow-xs)";
        btnMonth.style.background = "";
        btnYear.className = "btn btn-sm btn-secondary";
        btnYear.style.boxShadow = "";
        btnYear.style.border = "none";
        btnYear.style.background = "transparent";
      } else {
        btnMonth.className = "btn btn-sm btn-secondary";
        btnMonth.style.boxShadow = "";
        btnMonth.style.border = "none";
        btnMonth.style.background = "transparent";
        btnYear.className = "btn btn-sm btn-primary";
        btnYear.style.boxShadow = "var(--shadow-xs)";
        btnYear.style.background = "";
      }
    }

    // Update hero numbers
    const co2eEl = container.querySelector("#hero-co2e-val");
    if (co2eEl) co2eEl.textContent = curTotals.total.co2e.toLocaleString("en-IN", { maximumFractionDigits: 1 });

    const lowEl = container.querySelector("#hero-low-val");
    if (lowEl) lowEl.textContent = curTotals.total.low.toLocaleString("en-IN", { maximumFractionDigits: 1 });

    const highEl = container.querySelector("#hero-high-val");
    if (highEl) highEl.textContent = curTotals.total.high.toLocaleString("en-IN", { maximumFractionDigits: 1 });

    // Update table rows
    const tbody = container.querySelector("#emissions-tbody");
    if (tbody) {
      tbody.innerHTML = renderTableRows(curState.baselineLines, curTotals.multiplier);
      attachEvidenceListeners();
    }

    // Update Donut Chart
    const canvas = container.querySelector("#scope-donut-canvas");
    if (canvas) {
      renderScopeDonut(canvas, curTotals.scope1.co2e, curTotals.scope2.co2e, curTotals.scope3.co2e);
    }

    // Update equivalents box
    fetchEquivalents(curTotals.total.co2e);
  }

  // Attach Month/Year Toggle Events
  container.querySelector("#toggle-monthly-btn")?.addEventListener("click", () => {
    if (store.getState().periodView !== "month") {
      store.setState({ periodView: "month" });
      updatePeriodUI();
    }
  });

  container.querySelector("#toggle-yearly-btn")?.addEventListener("click", () => {
    if (store.getState().periodView !== "year") {
      store.setState({ periodView: "year" });
      updatePeriodUI();
    }
  });

  // Calculation Basis Modal/Alert
  container.querySelector("#confidence-info-btn")?.addEventListener("click", () => {
    alert(
      "Data Confidence Score Formula:\\n\\n" +
      "• 40% Verified Utility Invoices: Share of emissions backed by verified bills\\n" +
      "• 35% SHA-256 Hashes: Cryptographic verification of original evidence files\\n" +
      "• 25% Uncertainty Range Tightness: Tighter uncertainty bounds indicate higher measurement precision\\n\\n" +
      "Total Score = " + confidence.score + "% (" + confidence.label + ")\\n" +
      "Breakdown: " + confidence.breakdown.billScore + "/40 + " + confidence.breakdown.hashScore + "/35 + " + confidence.breakdown.rangeScore + "/25"
    );
  });

  // Navigation Buttons
  container.querySelector("#goto-twin-btn")?.addEventListener("click", () => {
    window.location.hash = "#/twin";
  });
  container.querySelector("#goto-report-btn")?.addEventListener("click", () => {
    window.location.hash = "#/report";
  });

  // Initial Equivalents Fetch
  fetchEquivalents(totals.total.co2e);

  // Mount Donut Chart after DOM attachment
  setTimeout(() => {
    const canvas = container.querySelector("#scope-donut-canvas");
    if (canvas) {
      renderScopeDonut(canvas, totals.scope1.co2e, totals.scope2.co2e, totals.scope3.co2e);
    }
  }, 50);

  return container;
}
