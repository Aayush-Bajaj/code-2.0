/**
 * report.js — Buyer-Ready GHG Disclosure Report Preview (Pass 2)
 *
 * Upgrades from Pass 1:
 *  - Reads real computed totals from store (no hardcoded numbers)
 *  - Shows scenario result summary if one was run in the Digital Twin
 *  - Download PDF calls real POST /report API
 *  - Evidence chips on real computed numbers
 *  - Framework alignment section: CBAM, SEBI BRSR, GHG Protocol
 */
import { store } from "../store.js";
import { api } from "../api.js";
import { openEvidenceDrawer } from "../ui/drawer.js";

function fmtKg(v, decimals = 0) {
  if (v == null) return "—";
  return v.toLocaleString("en-IN", { maximumFractionDigits: decimals });
}
function fmtInr(v) {
  if (v == null) return "—";
  return `₹${v.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

export function renderReportView() {
  const container = document.createElement("div");
  container.className = "fade-in";

  const state  = store.getState();
  const totals = store.getTotals();
  const scen   = state.scenarioResult;

  // Real totals from engine lines
  const total  = totals.total.co2e;
  const low    = totals.total.low;
  const high   = totals.total.high;
  const scope1 = totals.scope1.co2e;
  const scope2 = totals.scope2.co2e;
  const scope3 = totals.scope3.co2e;

  const dateTxt = new Date().toLocaleDateString("en-IN", { year: "numeric", month: "long", day: "numeric" });

  // Scenario summary section (only if a simulation has been run)
  const scenHtml = scen ? `
    <div style="margin-bottom:var(--space-6);">
      <h3 style="font-size:var(--text-base); margin-bottom:var(--space-2);">4. Decarbonisation Scenario (Digital Twin Result)</h3>
      <div style="background:var(--brand-accent-light); border-left:4px solid var(--brand-accent); padding:var(--space-4); border-radius:var(--radius-md); font-size:var(--text-sm); line-height:1.6;">
        <p>A forward-looking scenario was modelled using the Carbon Passport Digital Twin. 
        The scenario reduces the estimated monthly footprint from 
        <b>${fmtKg(scen.baseline_co2e_kg)} kg CO₂e</b> to 
        <b>${fmtKg(scen.new_co2e_kg)} kg CO₂e</b>, a reduction of 
        <b>${scen.delta_pct != null ? Math.abs(scen.delta_pct).toFixed(1) : "?"}%</b> 
        (${fmtKg(scen.delta_co2e_kg)} kg CO₂e avoided / month).
        </p>
        ${scen.inr_saved_per_month != null ? `
        <div style="display:flex;gap:var(--space-6);margin-top:var(--space-3);font-size:var(--text-xs);">
          <div><b>Monthly INR savings:</b> ${fmtInr(scen.inr_saved_per_month)}</div>
          ${scen.capex_inr != null ? `<div><b>Estimated capex:</b> ${fmtInr(scen.capex_inr)}</div>` : ""}
          ${scen.payback_months != null ? `<div><b>Payback:</b> ~${scen.payback_months.toFixed(1)} months</div>` : ""}
        </div>` : ""}
        <p style="font-size:11px;color:var(--text-muted);margin-top:var(--space-2);">
          ⚠ Forward-looking. Actual results depend on implementation. Payback calculated from backend/twin assumptions only.
        </p>
      </div>
    </div>` : "";

  // Scope breakdown rows from real lines
  const scopeRows = state.baselineLines.map(line => `
    <div style="display:flex; justify-content:space-between; align-items:center; padding:var(--space-2) 0; border-bottom:1px solid var(--border-subtle);">
      <div>
        <span class="badge badge-scope${line.scope}" style="margin-right:6px;">Scope ${line.scope}</span>
        <span style="font-size:var(--text-xs);">${line.category}</span>
        ${line.flags && line.flags.includes("MAINTENANCE_WIDENED_RANGE") ? `<span class="badge badge-smoke-heavy" style="margin-left:4px;">⚠️ Maint.</span>` : ""}
      </div>
      <button class="btn-evidence-chip report-evidence-btn" data-line-id="${line.id}">
        ${fmtKg(line.co2e_kg, 1)} kg
      </button>
    </div>
  `).join("");

  container.innerHTML = `
    <div style="max-width: 920px; margin: 0 auto;">
      <!-- Page Header -->
      <div style="display:flex; flex-wrap:wrap; justify-content:space-between; align-items:flex-end; margin-bottom:var(--space-8); gap:var(--space-4);">
        <div>
          <div style="font-size:11px; color:var(--brand-accent); text-transform:uppercase; font-weight:700; letter-spacing:0.06em; margin-bottom:4px;">
            GHG Corporate Standard Disclosure
          </div>
          <h1 style="font-size:var(--text-3xl); font-weight:800; color:var(--text-primary); letter-spacing:-0.03em;">
            Buyer-Ready Carbon Passport Report
          </h1>
          <p style="color:var(--text-secondary); font-size:var(--text-sm); margin-top:4px;">
            EU CBAM Declarant Alignment · SEBI BRSR Core (P6) · GHG Protocol Corporate Standard
          </p>
        </div>
        <div style="display:flex; gap:var(--space-2);">
          <button id="report-back-btn" class="btn btn-secondary btn-sm">
            ← Results
          </button>
          <button id="download-pdf-btn" class="btn btn-primary btn-sm">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            Download Verified PDF
          </button>
        </div>
      </div>

      <!-- Report Document Card (Executive Formal Layout) -->
      <div class="card" style="padding:var(--space-8) var(--space-10); background:var(--bg-surface); border:1px solid var(--border-medium); box-shadow:var(--shadow-md); border-radius:var(--radius-2xl);">

        <!-- Letterhead Banner -->
        <div style="display:flex; justify-content:space-between; align-items:flex-start; border-bottom:1px solid var(--border-medium); padding-bottom:var(--space-5); margin-bottom:var(--space-6);">
          <div>
            <div style="display:flex; align-items:center; gap:8px; font-size:11px; font-weight:700; color:var(--brand-primary); letter-spacing:0.06em; text-transform:uppercase;">
              <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:var(--brand-accent);"></span>
              <span>Carbon Passport Enterprise · Verified Supply Chain Disclosure</span>
            </div>
            <h2 style="font-size:var(--text-2xl); font-weight:800; color:var(--text-primary); letter-spacing:-0.02em; margin-top:6px;">
              ${state.facilityName}
            </h2>
            <div style="display:flex; align-items:center; gap:var(--space-3); font-size:var(--text-xs); color:var(--text-muted); margin-top:4px;">
              <span>📍 ${state.facilityLocation}</span>
              <span>•</span>
              <span>📅 ${state.reportingPeriod}</span>
            </div>
          </div>
          <div style="text-align:right;">
            <span class="badge" style="background:var(--brand-accent-light); color:var(--brand-accent-hover); border:1px solid var(--brand-accent-subtle); font-size:11px;">
              ✓ 100% Cryptographic Trail
            </span>
            <div style="font-size:11px; font-family:var(--font-mono); color:var(--text-muted); margin-top:6px;">Generated: ${dateTxt}</div>
          </div>
        </div>

        <!-- Section 1: Executive Summary -->
        <div style="margin-bottom:var(--space-8);">
          <div style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.06em; margin-bottom:4px;">Section 1.0</div>
          <h3 style="font-size:var(--text-base); font-weight:700; margin-bottom:var(--space-3); color:var(--text-primary);">Executive Footprint Summary</h3>
          <p style="font-size:var(--text-sm); line-height:1.7; color:var(--text-secondary);">
            This disclosure document summarizes the empirical greenhouse gas (GHG) activity inventory for 
            <b>${state.facilityName}</b>. The assessed gross monthly enterprise carbon footprint is
            <button class="btn-evidence-chip report-evidence-btn" data-line-id="${state.baselineLines[0]?.id || ''}" style="vertical-align:middle; margin:0 4px;">
              ${fmtKg(total, 1)} kg CO₂e / month
            </button>
            with an uncertainty range of
            <span style="font-family:var(--font-mono); font-size:var(--text-xs); font-weight:700; color:var(--text-primary);">
              ${fmtKg(low, 0)} – ${fmtKg(high, 0)} kg
            </span>.
            Scope coverage adheres strictly to the GHG Protocol Corporate Standard across direct combustion, grid electricity, and logistics freight.
          </p>

          <!-- Summary KPI Row -->
          <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:var(--space-3); margin-top:var(--space-5);">
            <div style="background:var(--bg-subtle); border:1px solid var(--border-subtle); border-top:3px solid var(--scope-1); padding:var(--space-3) var(--space-4); border-radius:var(--radius-lg);">
              <div style="font-size:10px; color:var(--text-muted); text-transform:uppercase; font-weight:700; letter-spacing:0.04em;">Scope 1 (Direct Fuel)</div>
              <div style="font-family:var(--font-mono); font-size:var(--text-xl); font-weight:800; color:var(--text-primary); margin-top:3px;">${fmtKg(scope1, 0)}</div>
              <div style="font-size:10px; color:var(--text-muted);">kg CO₂e / mo</div>
            </div>
            <div style="background:var(--bg-subtle); border:1px solid var(--border-subtle); border-top:3px solid var(--scope-2); padding:var(--space-3) var(--space-4); border-radius:var(--radius-lg);">
              <div style="font-size:10px; color:var(--text-muted); text-transform:uppercase; font-weight:700; letter-spacing:0.04em;">Scope 2 (Electricity)</div>
              <div style="font-family:var(--font-mono); font-size:var(--text-xl); font-weight:800; color:var(--text-primary); margin-top:3px;">${fmtKg(scope2, 0)}</div>
              <div style="font-size:10px; color:var(--text-muted);">kg CO₂e / mo</div>
            </div>
            <div style="background:var(--bg-subtle); border:1px solid var(--border-subtle); border-top:3px solid var(--scope-3); padding:var(--space-3) var(--space-4); border-radius:var(--radius-lg);">
              <div style="font-size:10px; color:var(--text-muted); text-transform:uppercase; font-weight:700; letter-spacing:0.04em;">Scope 3 (Logistics)</div>
              <div style="font-family:var(--font-mono); font-size:var(--text-xl); font-weight:800; color:var(--text-primary); margin-top:3px;">${fmtKg(scope3, 0)}</div>
              <div style="font-size:10px; color:var(--text-muted);">kg CO₂e / mo</div>
            </div>
            <div style="background:var(--brand-primary-light); border:1px solid rgba(18, 60, 53, 0.15); border-top:3px solid var(--brand-primary); padding:var(--space-3) var(--space-4); border-radius:var(--radius-lg);">
              <div style="font-size:10px; color:var(--brand-primary); text-transform:uppercase; font-weight:700; letter-spacing:0.04em;">Total Enterprise</div>
              <div style="font-family:var(--font-mono); font-size:var(--text-xl); font-weight:800; color:var(--brand-primary); margin-top:3px;">${fmtKg(total, 0)}</div>
              <div style="font-size:10px; color:var(--brand-primary); opacity:0.8;">kg CO₂e / mo</div>
            </div>
          </div>
        </div>

        <!-- Section 2: Emission Line Breakdown -->
        <div style="margin-bottom:var(--space-8);">
          <div style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.06em; margin-bottom:4px;">Section 2.0</div>
          <h3 style="font-size:var(--text-base); font-weight:700; margin-bottom:var(--space-2); color:var(--text-primary);">Emissions Inventory — Line-by-Line Evidence</h3>
          <p style="font-size:var(--text-xs); color:var(--text-secondary); margin-bottom:var(--space-4);">
            Every figure below is cryptographically anchored to utility bills, OCR text, or machine nameplate video. Click any figure to inspect its 7-step calculation lineage.<br/>
            Methodology: <code>Emissions (kg CO₂e) = Activity Volume × Verified Factor</code> [GHG Protocol Corporate Standard, Chapter 4]
          </p>
          <div style="border:1px solid var(--border-medium); border-radius:var(--radius-lg); padding:var(--space-2) var(--space-4); background:var(--bg-surface);">
            ${scopeRows}
            <div style="display:flex; justify-content:space-between; align-items:center; padding:var(--space-3) 0; margin-top:var(--space-2); border-top:2px solid var(--border-medium);">
              <span style="font-size:var(--text-sm); font-weight:700; color:var(--text-primary);">Total Assessed Footprint</span>
              <span style="font-family:var(--font-mono); font-size:var(--text-base); font-weight:800; color:var(--brand-primary);">
                ${fmtKg(total, 1)} kg CO₂e
              </span>
            </div>
          </div>
        </div>

        <!-- Section 3: Framework Alignment -->
        <div style="margin-bottom:var(--space-8);">
          <div style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.06em; margin-bottom:4px;">Section 3.0</div>
          <h3 style="font-size:var(--text-base); font-weight:700; margin-bottom:var(--space-3); color:var(--text-primary);">Regulatory & Supply Chain Disclosure Alignment</h3>
          <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:var(--space-4); font-size:var(--text-xs);">
            <div style="background:var(--bg-subtle); border:1px solid var(--border-subtle); padding:var(--space-4); border-radius:var(--radius-lg);">
              <div style="font-weight:700; color:var(--text-primary); margin-bottom:4px; display:inline-flex; align-items:center; gap:6px;">
                <span class="badge" style="background:#E0E7FF; color:#3730A3;">EU CBAM</span>
                <span>Regulation 2023/956</span>
              </div>
              <p style="color:var(--text-secondary); line-height:1.55; margin-top:6px;">
                Direct Scope 1 emissions calculated per activity unit. Supports EU importers and customs declarants with verifiable supplier data sheets.
              </p>
            </div>
            <div style="background:var(--bg-subtle); border:1px solid var(--border-subtle); padding:var(--space-4); border-radius:var(--radius-lg);">
              <div style="font-weight:700; color:var(--text-primary); margin-bottom:4px; display:inline-flex; align-items:center; gap:6px;">
                <span class="badge" style="background:#D1FAE5; color:#065F46;">SEBI BRSR</span>
                <span>Core Principle 6 (P6)</span>
              </div>
              <p style="color:var(--text-secondary); line-height:1.55; margin-top:6px;">
                Absolute Scope 1 & 2 emissions reported with authoritative emission factor provenance (CEA v22 & DEFRA). Aligned with top 1,000 listed value chains.
              </p>
            </div>
            <div style="background:var(--bg-subtle); border:1px solid var(--border-subtle); padding:var(--space-4); border-radius:var(--radius-lg);">
              <div style="font-weight:700; color:var(--text-primary); margin-bottom:4px; display:inline-flex; align-items:center; gap:6px;">
                <span class="badge" style="background:#FEF3C7; color:#92400E;">GHG PROTOCOL</span>
                <span>Corporate Standard</span>
              </div>
              <p style="color:var(--text-secondary); line-height:1.55; margin-top:6px;">
                Deterministic multiplication: activity volume × empirical coefficient, with explicitly stated uncertainty boundaries. Zero LLM hallucinations.
              </p>
            </div>
          </div>
        </div>

        <!-- Section 4: Scenario (if available) -->
        ${scenHtml}

        <!-- Legal Disclaimer & Audit Metadata -->
        <div style="padding-top:var(--space-5); border-top:1px solid var(--border-medium); font-size:11px; color:var(--text-muted); line-height:1.65;">
          <strong>Governance Notice:</strong> This disclosure constitutes an operational activity baseline derived from empirical utility records and visual telemetry with low-to-high uncertainty bounds. It supports buyer sustainability framework questionnaires (CBAM, BRSR, CDP). It does not substitute for third-party accredited audit verification. Emission factors sourced from IPCC AR6, CEA v22, and DEFRA 2024.
          <br/><br/>
          <span id="report-hash-stamp" style="font-family:var(--font-mono); font-size:10px; word-break:break-all;"></span>
        </div>
      </div>

      <!-- Bottom Download Ribbon -->
      <div style="display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:var(--space-4); background:var(--bg-surface); border:1px solid var(--border-subtle); padding:var(--space-5) var(--space-6); border-radius:var(--radius-xl); box-shadow:var(--shadow-sm); margin-top:var(--space-6);">
        <div>
          <div style="font-size:var(--text-sm); font-weight:700; color:var(--text-primary);">Export official report document</div>
          <div style="font-size:var(--text-xs); color:var(--text-secondary); margin-top:2px;">PDF includes complete mathematical proofs, line item evidence hashes, and sensor calibration metrics.</div>
        </div>
        <div id="pdf-status-msg" style="display:none; font-size:var(--text-xs); font-family:var(--font-mono); color:var(--text-muted);"></div>
      </div>
    </div>
  `;

  // ─── Button events ────────────────────────────────────────────────────────────
  container.querySelector("#report-back-btn").addEventListener("click", () => {
    window.location.hash = "#/results";
  });

  container.querySelector("#download-pdf-btn").addEventListener("click", async () => {
    const btn = container.querySelector("#download-pdf-btn");
    const statusMsg = container.querySelector("#pdf-status-msg");
    btn.textContent = "⏳ Generating PDF…";
    btn.disabled = true;
    statusMsg.style.display = "none";

    try {
      const res = await api.generateReport({
        facility_name:   state.facilityName,
        reporting_period: state.reportingPeriod,
        emission_lines:   state.baselineLines,
        scenario_result:  state.scenarioResult,
        force_fallback_template: false,
      });

      const reportId = res.facts_snapshot?.report_id;
      if (reportId) {
        window.open(api.getReportPdfUrl(reportId), "_blank");
        statusMsg.textContent = `✓ Report ${reportId} generated successfully.`;
        statusMsg.style.color = "var(--brand-accent)";
      } else {
        throw new Error("No report_id in response");
      }
    } catch (err) {
      // Try fallback template
      try {
        const fallback = await api.generateReport({
          facility_name:   state.facilityName,
          reporting_period: state.reportingPeriod,
          emission_lines:   state.baselineLines,
          scenario_result:  state.scenarioResult,
          force_fallback_template: true,
        });
        const fid = fallback.facts_snapshot?.report_id;
        if (fid) {
          window.open(api.getReportPdfUrl(fid), "_blank");
          statusMsg.textContent = `✓ PDF ready (template mode — RAG citations may be limited).`;
          statusMsg.style.color = "var(--color-amber)";
        }
      } catch (err2) {
        statusMsg.textContent = `⚠ PDF backend unavailable: ${err2.message}`;
        statusMsg.style.color = "var(--color-rose)";
      }
    } finally {
      btn.textContent = "📄 Download PDF";
      btn.disabled = false;
      statusMsg.style.display = "block";
    }
  });

  // ─── Evidence chip clicks ─────────────────────────────────────────────────────
  container.querySelectorAll(".report-evidence-btn").forEach((chip) => {
    chip.addEventListener("click", () => {
      const lineId = chip.getAttribute("data-line-id");
      if (lineId) openEvidenceDrawer(lineId);
    });
  });

  return container;
}
