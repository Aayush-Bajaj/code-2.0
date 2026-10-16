/**
 * methods.js — Data and Methods View
 * Fetches and displays factor provenance from GET /meta/sources.
 * Displays assumptions status (verified vs needs_input) and how_to_fill instructions.
 */

import { api } from "../api.js";

export function renderMethodsView() {
  const container = document.createElement("div");
  container.className = "fade-in";

  container.innerHTML = `
    <div style="max-width: 1080px; margin: 0 auto; display:flex; flex-direction:column; gap:var(--space-6);">
      <!-- Header -->
      <div style="display:flex; flex-direction:column; gap:var(--space-2);">
        <div style="display:inline-flex; align-items:center; gap:8px; width:fit-content; padding:4px 10px; border-radius:var(--radius-full); background:var(--brand-accent-light); color:var(--brand-primary); font-size:var(--text-xs); font-weight:700; text-transform:uppercase; letter-spacing:0.05em;">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          Audited Provenance Registry
        </div>
        <h1 style="font-size: var(--text-3xl); font-weight: 800; color: var(--text-primary); letter-spacing:-0.03em; margin:0;">
          Data Provenance &amp; Calculation Methods
        </h1>
        <p style="color: var(--text-secondary); font-size:var(--text-base); margin:0; max-width:760px; line-height:1.6;">
          Complete mathematical transparency: every emission factor, formula coefficient, and engineering assumption originates strictly from authoritative registries, verified datasheets, or explicit facility parameters.
        </p>
      </div>

      <div id="sources-content" style="display:flex; flex-direction:column; gap:var(--space-6);">
        <div class="card" style="text-align:center; padding:var(--space-10); color:var(--text-muted); display:flex; flex-direction:column; align-items:center; justify-content:center; gap:var(--space-3);">
          <div class="loading-spinner" style="width:28px; height:28px; border:3px solid var(--border-subtle); border-top-color:var(--brand-accent); border-radius:50%; animation:spin 0.8s linear infinite;"></div>
          <span style="font-size:var(--text-sm); font-weight:500;">Loading verified emission factor registry from <code>/meta/sources</code>...</span>
        </div>
      </div>
    </div>
  `;

  // Fetch /meta/sources
  api.getMetaSources().then((data) => {
    const target = container.querySelector("#sources-content");
    if (!target) return;

    if (!data) {
      target.innerHTML = `
        <div class="card" style="border-left:4px solid var(--scope1-color); padding:var(--space-6);">
          <div style="font-weight:700; color:var(--text-primary); margin-bottom:4px;">Unable to load /meta/sources</div>
          <div style="font-size:var(--text-sm); color:var(--text-secondary);">The application is currently operating in offline mode. Baseline fallback parameters remain active.</div>
        </div>
      `;
      return;
    }

    target.innerHTML = `
      <!-- 1. Factor Registry -->
      <div class="card" style="display:flex; flex-direction:column; gap:var(--space-4);">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:var(--space-2);">
          <div>
            <h2 style="font-size:var(--text-xl); font-weight:700; color:var(--text-primary); margin:0 0 4px 0;">
              1. Authoritative Emission Factors
            </h2>
            <p style="font-size:var(--text-sm); color:var(--text-secondary); margin:0;">
              Calibrated from official CEA, IPCC, and DEFRA registries loaded from <code>data/factors/factors.csv</code>.
            </p>
          </div>
          <span class="badge" style="background:var(--brand-accent-light); color:var(--brand-primary); font-weight:600;">
            ${data.factors.length} Active Coefficients
          </span>
        </div>

        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th style="width:24%;">Factor Identifier</th>
                <th style="width:28%;">Activity Scope &amp; Name</th>
                <th style="width:20%;">Coefficient Value</th>
                <th style="width:20%;">Source &amp; Standard</th>
                <th style="width:8%;">Year</th>
              </tr>
            </thead>
            <tbody>
              ${data.factors.map(f => `
                <tr>
                  <td><code style="font-size:var(--text-xs); font-family:var(--font-mono); font-weight:600; color:var(--brand-primary);">${f.factor_id}</code></td>
                  <td style="font-weight:500; color:var(--text-primary);">${f.name}</td>
                  <td><b style="font-family:var(--font-mono); color:var(--text-primary);">${f.value}</b> <span style="font-size:var(--text-xs); color:var(--text-muted);">${f.unit}</span></td>
                  <td>
                    <a href="${f.source_url}" target="_blank" rel="noopener noreferrer" style="display:inline-flex; align-items:center; gap:4px; color:var(--brand-accent); font-weight:600; text-decoration:none;">
                      ${f.source_name}
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                    </a>
                  </td>
                  <td style="font-family:var(--font-mono); font-size:var(--text-xs); color:var(--text-muted);">${f.year}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>

      <!-- 2. Generator SFC Datasheets -->
      <div class="card" style="display:flex; flex-direction:column; gap:var(--space-4);">
        <div>
          <h2 style="font-size:var(--text-xl); font-weight:700; color:var(--text-primary); margin:0 0 4px 0;">
            2. Industrial Machinery &amp; Generator Datasheet Registry
          </h2>
          <p style="font-size:var(--text-sm); color:var(--text-secondary); margin:0;">
            Specific fuel consumption (SFC) lookup curves mapped directly to recognized manufacturer performance datasheets.
          </p>
        </div>

        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(320px, 1fr)); gap:var(--space-4);">
          ${data.generator_datasheets.map(ds => `
            <div style="background:var(--bg-muted); border:1px solid var(--border-subtle); padding:var(--space-4); border-radius:var(--radius-lg); display:flex; flex-direction:column; gap:var(--space-2);">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <div style="font-weight:700; color:var(--text-primary); font-size:var(--text-base);">${ds.model}</div>
                <span class="badge" style="background:var(--bg-surface); border:1px solid var(--border-subtle); font-family:var(--font-mono); font-size:var(--text-xs);">${ds.rated_capacity}</span>
              </div>
              
              <div style="display:flex; flex-direction:column; gap:4px; padding:var(--space-2) 0; border-top:1px dashed var(--border-subtle); border-bottom:1px dashed var(--border-subtle);">
                <div style="display:flex; justify-content:space-between; font-size:var(--text-xs);">
                  <span style="color:var(--text-secondary); font-weight:500;">75% Electrical Load:</span>
                  <span style="font-family:var(--font-mono); font-weight:600; color:var(--text-primary);">${ds.load_points[0]?.sfc_l_per_kwh} L/kWh (${ds.load_points[0]?.fuel_flow_lph} L/h)</span>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:var(--text-xs);">
                  <span style="color:var(--text-secondary); font-weight:500;">100% Electrical Load:</span>
                  <span style="font-family:var(--font-mono); font-weight:600; color:var(--text-primary);">${ds.load_points[1]?.sfc_l_per_kwh} L/kWh (${ds.load_points[1]?.fuel_flow_lph} L/h)</span>
                </div>
              </div>

              <div style="display:flex; justify-content:space-between; align-items:center; font-size:11px; color:var(--text-muted);">
                <span>Tolerance: <b>${ds.tolerance_pct}</b></span>
                <span style="text-align:right;">${ds.interpolation_rule}</span>
              </div>
            </div>
          `).join("")}
        </div>
      </div>

      <!-- 3. Assumptions Status (Never Hidden!) -->
      <div class="card" style="display:flex; flex-direction:column; gap:var(--space-4);">
        <div>
          <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:var(--space-2);">
            <h2 style="font-size:var(--text-xl); font-weight:700; color:var(--text-primary); margin:0;">
              3. Financial &amp; Operational Assumptions Status
            </h2>
            <span class="badge" style="background:var(--bg-muted); color:var(--text-secondary); font-size:11px;">
              AGENTS.md Strict Rule #2 Compliance
            </span>
          </div>
          <p style="font-size:var(--text-sm); color:var(--text-secondary); margin:4px 0 0 0;">
            Any unverified factory parameters are explicitly marked as <code>TODO_VERIFY</code>. The calculation engine halts rather than making unverified approximations.
          </p>
        </div>

        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th style="width:24%;">Assumption Parameter</th>
                <th style="width:18%;">Verification State</th>
                <th style="width:18%;">Assumed Baseline</th>
                <th style="width:40%;">Required Supporting Evidence</th>
              </tr>
            </thead>
            <tbody>
              ${data.assumptions.map(a => `
                <tr>
                  <td><code style="font-size:var(--text-xs); font-family:var(--font-mono); color:var(--brand-primary); font-weight:600;">${a.key}</code></td>
                  <td>
                    ${a.status === "verified"
                      ? `<span class="badge" style="background:rgba(16, 185, 129, 0.12); color:#047857; font-weight:700; border:1px solid rgba(16, 185, 129, 0.25);">
                          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" style="margin-right:3px; vertical-align:-1px;"><polyline points="20 6 9 17 4 12"/></svg>Verified
                         </span>`
                      : `<span class="badge" style="background:rgba(217, 119, 6, 0.12); color:#B45309; font-weight:700; border:1px solid rgba(217, 119, 6, 0.25);">
                          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" style="margin-right:3px; vertical-align:-1px;"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>Needs Input
                         </span>`}
                  </td>
                  <td style="font-family:var(--font-mono); font-size:var(--text-xs); font-weight:600;">
                    ${a.value !== null ? a.value : '<span style="color:#B45309;">TODO_VERIFY</span>'} <span style="font-weight:normal; color:var(--text-muted);">${a.unit}</span>
                  </td>
                  <td style="font-size:var(--text-xs); color:var(--text-secondary); line-height:1.5;">${a.how_to_fill}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>

      <!-- 4. Regulations & Standards for RAG -->
      <div class="card" style="display:flex; flex-direction:column; gap:var(--space-4);">
        <div>
          <h2 style="font-size:var(--text-xl); font-weight:700; color:var(--text-primary); margin:0 0 4px 0;">
            4. Regulatory Standards &amp; Vector RAG Corpus
          </h2>
          <p style="font-size:var(--text-sm); color:var(--text-secondary); margin:0;">
            Indexed in ChromaDB semantic vector storage for regulatory compliance verification and buyer disclosure mapping.
          </p>
        </div>

        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:var(--space-4);">
          ${data.regulations.map(r => `
            <div style="background:var(--bg-muted); border:1px solid var(--border-subtle); padding:var(--space-4); border-radius:var(--radius-lg); display:flex; flex-direction:column; gap:var(--space-2);">
              <div style="font-weight:700; color:var(--brand-primary); font-size:var(--text-base);">${r.title}</div>
              <div style="font-size:var(--text-xs); font-family:var(--font-mono); color:var(--brand-accent); font-weight:600;">${r.document}</div>
              <div style="font-size:var(--text-xs); color:var(--text-secondary); line-height:1.5; margin-top:2px;">${r.relevance}</div>
            </div>
          `).join("")}
        </div>
      </div>
    `;
  });

  return container;
}
