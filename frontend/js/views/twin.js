/**
 * twin.js — Digital Twin What-If Decarbonisation Simulator View (Pass 2)
 *
 * Features:
 *  - Live API calls to POST /api/scenarios/simulate (debounced 600 ms)
 *  - All 5 levers: solar, genset, idle, electric forklift, rail-shift
 *  - Animated CO2e reduction counter with CSS flip
 *  - Ranked levers table with inline payback bars
 *  - Offline fallback: compute rough estimate locally if backend unavailable
 *  - "Reset to baseline" button resets all levers to 0
 */
import { store } from "../store.js";
import { api } from "../api.js";

// ─── debounce helper ─────────────────────────────────────────────────────────
function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

// ─── local rough fallback (never used for reporting, only UX continuity) ─────
function localFallback(baselineLines, inputs) {
  const totalCo2e = baselineLines.reduce((s, l) => s + l.co2e_kg, 0);
  const totalLow   = baselineLines.reduce((s, l) => s + l.low_kg, 0);
  const totalHigh  = baselineLines.reduce((s, l) => s + l.high_kg, 0);

  // Very rough heuristic (front-end only, not reported)
  const solarFrac  = (inputs.solar_share_pct  || 0) / 100;
  const gensetFrac = (inputs.genset_hours_reduction_pct || 0) / 100;
  const railFrac   = (inputs.rail_shift_pct   || 0) / 100;
  const forklift   = inputs.electric_forklift ? 1 : 0;
  const idleFrac   = (inputs.idle_hours_reduction_pct || 0) / 100;

  const scope2Co2e = baselineLines.filter(l => l.scope === 2).reduce((s, l) => s + l.co2e_kg, 0);
  const scope1Co2e = baselineLines.filter(l => l.scope === 1).reduce((s, l) => s + l.co2e_kg, 0);
  const scope3Co2e = baselineLines.filter(l => l.scope === 3).reduce((s, l) => s + l.co2e_kg, 0);

  const newCo2e = Math.max(0,
    scope2Co2e * (1 - solarFrac * 0.85) +
    scope1Co2e * (1 - gensetFrac * 0.6) * (forklift ? 0.85 : 1) * (1 - idleFrac * 0.4) +
    scope3Co2e * (1 - railFrac * 0.70)
  );
  const deltaCo2e = totalCo2e - newCo2e;
  const deltaPct  = totalCo2e > 0 ? (deltaCo2e / totalCo2e) * 100 : 0;

  return {
    baseline_co2e_kg: totalCo2e,
    baseline_low_kg:  totalLow,
    baseline_high_kg: totalHigh,
    new_co2e_kg:      newCo2e,
    new_low_kg:       newCo2e * (totalLow / (totalCo2e || 1)),
    new_high_kg:      newCo2e * (totalHigh / (totalCo2e || 1)),
    delta_co2e_kg:    deltaCo2e,
    delta_pct:        deltaPct,
    inr_saved_per_month: deltaCo2e * 5.5,   // rough ₹5.5 per kg CO2e avoided
    capex_inr:        null,
    payback_months:   null,
    ranked_levers:    [
      {
        rank: 1,
        lever: "Rooftop Solar PV",
        co2e_reduction_kg: scope2Co2e * solarFrac * 0.85,
        delta_pct: totalCo2e > 0 ? ((scope2Co2e * solarFrac * 0.85) / totalCo2e) * 100 : 0,
        inr_saved_per_month: scope2Co2e * solarFrac * 0.85 * 5.5,
        capex_inr: solarFrac > 0 ? 120000 * (inputs.solar_share_pct / 20) : 0,
        payback_months: solarFrac > 0 ? 48.0 : 0,
      },
      {
        rank: 2,
        lever: "Genset Hours Reduction (grid replacement)",
        co2e_reduction_kg: scope1Co2e * gensetFrac * 0.6,
        delta_pct: totalCo2e > 0 ? ((scope1Co2e * gensetFrac * 0.6) / totalCo2e) * 100 : 0,
        inr_saved_per_month: scope1Co2e * gensetFrac * 0.6 * 6.0,
        capex_inr: 0,
        payback_months: 0,
      },
      {
        rank: 3,
        lever: "Idle Hours Reduction (genset management)",
        co2e_reduction_kg: scope1Co2e * idleFrac * 0.4,
        delta_pct: totalCo2e > 0 ? ((scope1Co2e * idleFrac * 0.4) / totalCo2e) * 100 : 0,
        inr_saved_per_month: scope1Co2e * idleFrac * 0.4 * 6.0,
        capex_inr: 0,
        payback_months: 0,
      },
      {
        rank: 4,
        lever: "Electric Forklift Conversion",
        co2e_reduction_kg: forklift ? scope1Co2e * 0.15 : 0,
        delta_pct: forklift && totalCo2e > 0 ? ((scope1Co2e * 0.15) / totalCo2e) * 100 : 0,
        inr_saved_per_month: forklift ? 12000 : 0,
        capex_inr: forklift ? 450000 : 0,
        payback_months: forklift ? 37.5 : 0,
      },
      {
        rank: 5,
        lever: "Rail Freight Mode Shift",
        co2e_reduction_kg: scope3Co2e * railFrac * 0.70,
        delta_pct: totalCo2e > 0 ? ((scope3Co2e * railFrac * 0.70) / totalCo2e) * 100 : 0,
        inr_saved_per_month: scope3Co2e * railFrac * 0.70 * 4.0,
        capex_inr: 0,
        payback_months: 0,
      },
    ],
    assumptions_used: {},
    _offline_estimate: true,
  };
}

// ─── render a horizontal payback bar ─────────────────────────────────────────
function paybackBar(months, maxMonths = 84) {
  if (months == null) return `<span style="color:var(--text-muted);font-size:var(--text-xs);">Free savings</span>`;
  if (months === 0) return `<span style="color:var(--brand-accent);font-weight:600;font-size:var(--text-xs);">Immediate (No capex)</span>`;
  const pct = Math.min(100, (months / maxMonths) * 100);
  const color = months < 24 ? "var(--brand-accent)" : months < 48 ? "var(--color-amber)" : "var(--color-rose)";
  return `
    <div style="display:flex;align-items:center;gap:var(--space-2);">
      <div style="flex:1;height:6px;background:var(--bg-muted);border-radius:var(--radius-full);overflow:hidden;">
        <div style="width:${pct}%;height:100%;background:${color};border-radius:var(--radius-full);transition:width 0.5s ease;"></div>
      </div>
      <span style="font-family:var(--font-mono);font-size:10px;color:var(--text-muted);white-space:nowrap;">${months.toFixed(1)} mo</span>
    </div>`;
}

// ─── render the ranked levers table ──────────────────────────────────────────
function renderLeversTable(levers) {
  if (!levers || levers.length === 0) {
    return `<p style="color:var(--text-muted);font-size:var(--text-xs);padding:var(--space-4) 0;">Run a simulation to see ranked levers.</p>`;
  }
  const rows = levers.map((lv, i) => {
    const isInactive = !lv.co2e_reduction_kg || lv.co2e_reduction_kg <= 0;
    const saving = lv.inr_saved_per_month != null && lv.inr_saved_per_month > 0
      ? `₹${lv.inr_saved_per_month.toLocaleString("en-IN", {maximumFractionDigits:0})}/mo`
      : "₹0/mo";
    const capex = lv.capex_inr != null && lv.capex_inr > 0
      ? `₹${lv.capex_inr.toLocaleString("en-IN", {maximumFractionDigits:0})}`
      : "₹0";
    const deltaPct = lv.delta_pct != null && lv.delta_pct > 0 ? lv.delta_pct.toFixed(1) : "0.0";
    const rankBadge = i === 0
      ? `<span class="badge" style="background:var(--brand-accent-light);color:var(--brand-accent-hover);border:1px solid var(--brand-accent-subtle);">#1 TOP ROI</span>`
      : `<span class="badge" style="background:var(--bg-muted);color:var(--text-secondary);border:1px solid var(--border-medium);">#${i+1}</span>`;
    const paybackDisplay = isInactive
      ? `<span style="color:var(--text-muted);font-size:var(--text-xs);">Lever at 0%</span>`
      : paybackBar(lv.payback_months);

    return `
      <tr>
        <td>
          <div style="display:flex;align-items:center;gap:8px;">
            ${rankBadge}
            <span style="font-weight:600;color:var(--text-primary);">${lv.lever}</span>
          </div>
        </td>
        <td style="font-family:var(--font-mono);font-weight:700;color:${isInactive ? 'var(--text-muted)' : 'var(--brand-accent)'};">−${deltaPct}%</td>
        <td style="font-family:var(--font-mono);">${saving}</td>
        <td style="font-family:var(--font-mono);">${capex}</td>
        <td style="min-width:140px;">${paybackDisplay}</td>
      </tr>`;
  }).join("");

  return `
    <div class="table-responsive">
      <table class="data-table">
        <thead>
          <tr>
            <th>Decarbonisation Lever</th>
            <th>CO2e Reduction</th>
            <th>Monthly Savings</th>
            <th>Estimated Capex</th>
            <th>Payback Period</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

// ─── Main view render ─────────────────────────────────────────────────────────
export function renderTwinView() {
  const container = document.createElement("div");
  container.className = "fade-in";

  const state = store.getState();
  const baselineLines = state.baselineLines;
  const baseline = baselineLines.reduce((s, l) => s + l.co2e_kg, 0);
  const inputs = { ...state.scenarioInputs };

  container.innerHTML = `
    <div style="max-width: 1160px; margin: 0 auto;">
      <!-- Header -->
      <div style="display:flex; flex-wrap:wrap; justify-content:space-between; align-items:flex-end; gap:var(--space-4); margin-bottom:var(--space-8);">
        <div>
          <div style="font-size:11px; color:var(--brand-accent); text-transform:uppercase; font-weight:700; letter-spacing:0.06em; margin-bottom:4px;">
            Digital Twin Simulation Engine
          </div>
          <h1 style="font-size:var(--text-3xl); font-weight:800; color:var(--text-primary); letter-spacing:-0.03em; margin-bottom:6px;">
            Factory Decarbonisation Scenario Planner
          </h1>
          <p style="color:var(--text-secondary); font-size:var(--text-sm); max-width:650px;">
            Adjust operational levers in real time. Payback and emissions reductions are computed deterministically by the calculation engine.
          </p>
        </div>
        <div style="display:flex; gap:var(--space-2);">
          <button id="twin-reset-btn" class="btn btn-secondary btn-sm">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
            Reset Levers
          </button>
          <button id="twin-back-btn" class="btn btn-secondary btn-sm">
            ← Results Dashboard
          </button>
        </div>
      </div>

      <!-- Main grid: sliders left, live result right -->
      <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap:var(--space-6); margin-bottom:var(--space-6);">

        <!-- Levers Card -->
        <div class="card" style="box-shadow:var(--shadow-sm);">
          <div class="card-header">
            <div style="display:flex; align-items:center; gap:8px;">
              <h3 style="font-size:var(--text-base); font-weight:700;">Operational Levers</h3>
            </div>
            <span id="sim-status-badge" class="badge" style="background:var(--bg-muted);color:var(--text-muted);border:1px solid var(--border-subtle);">Idle</span>
          </div>

          <div style="display:flex; flex-direction:column; gap:var(--space-4);">

            <!-- Solar -->
            <div class="lever-group" id="lg-solar">
              <div style="display:flex; justify-content:space-between; align-items:center; font-size:var(--text-xs); margin-bottom:8px;">
                <label for="solar-slider" style="font-weight:600; color:var(--text-primary); display:inline-flex; align-items:center; gap:6px;">
                  <span style="color:var(--color-amber);">☀️</span> Rooftop Solar PV (Share of Grid Electricity)
                </label>
                <b id="solar-val" style="font-family:var(--font-mono); font-size:var(--text-xs); color:var(--brand-primary);">${inputs.solar_share_pct}%</b>
              </div>
              <input type="range" id="solar-slider" class="lever-slider" min="0" max="60" step="5" value="${inputs.solar_share_pct}" style="width:100%;" aria-label="Solar share percent" />
              <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--text-muted);font-family:var(--font-mono);margin-top:4px;"><span>0%</span><span>Max 60% Capacity</span></div>
            </div>

            <!-- Genset -->
            <div class="lever-group" id="lg-genset">
              <div style="display:flex; justify-content:space-between; align-items:center; font-size:var(--text-xs); margin-bottom:8px;">
                <label for="genset-slider" style="font-weight:600; color:var(--text-primary); display:inline-flex; align-items:center; gap:6px;">
                  <span style="color:var(--scope-1);">⚡</span> DG Genset Runtime Reduction (Grid Transition)
                </label>
                <b id="genset-val" style="font-family:var(--font-mono); font-size:var(--text-xs); color:var(--brand-primary);">${inputs.genset_hours_reduction_pct}%</b>
              </div>
              <input type="range" id="genset-slider" class="lever-slider" min="0" max="80" step="5" value="${inputs.genset_hours_reduction_pct}" style="width:100%;" aria-label="Genset hours reduction percent" />
              <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--text-muted);font-family:var(--font-mono);margin-top:4px;"><span>0%</span><span>Max 80% Reduction</span></div>
            </div>

            <!-- Idle Hours -->
            <div class="lever-group" id="lg-idle">
              <div style="display:flex; justify-content:space-between; align-items:center; font-size:var(--text-xs); margin-bottom:8px;">
                <label for="idle-slider" style="font-weight:600; color:var(--text-primary); display:inline-flex; align-items:center; gap:6px;">
                  <span>⏱️</span> Machinery Idle Hours Elimination
                </label>
                <b id="idle-val" style="font-family:var(--font-mono); font-size:var(--text-xs); color:var(--brand-primary);">${inputs.idle_hours_reduction_pct}%</b>
              </div>
              <input type="range" id="idle-slider" class="lever-slider" min="0" max="50" step="5" value="${inputs.idle_hours_reduction_pct}" style="width:100%;" aria-label="Idle hours reduction percent" />
              <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--text-muted);font-family:var(--font-mono);margin-top:4px;"><span>0%</span><span>Max 50% Reduction</span></div>
            </div>

            <!-- Rail Freight -->
            <div class="lever-group" id="lg-rail">
              <div style="display:flex; justify-content:space-between; align-items:center; font-size:var(--text-xs); margin-bottom:8px;">
                <label for="rail-slider" style="font-weight:600; color:var(--text-primary); display:inline-flex; align-items:center; gap:6px;">
                  <span style="color:var(--scope-3);">🚆</span> Logistics Freight Mode Shift (Road to Rail)
                </label>
                <b id="rail-val" style="font-family:var(--font-mono); font-size:var(--text-xs); color:var(--brand-primary);">${inputs.rail_shift_pct}%</b>
              </div>
              <input type="range" id="rail-slider" class="lever-slider" min="0" max="50" step="5" value="${inputs.rail_shift_pct}" style="width:100%;" aria-label="Rail shift percent" />
              <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--text-muted);font-family:var(--font-mono);margin-top:4px;"><span>0%</span><span>Max 50% Share</span></div>
            </div>

            <!-- Electric Forklift -->
            <div style="padding-top:var(--space-3); border-top:1px solid var(--border-subtle);">
              <label style="display:flex; align-items:center; gap:var(--space-3); cursor:pointer;">
                <div id="forklift-toggle-wrap" style="position:relative;width:44px;height:24px;flex-shrink:0;">
                  <input type="checkbox" id="forklift-toggle" ${inputs.electric_forklift ? "checked" : ""} style="opacity:0;position:absolute;inset:0;cursor:pointer;z-index:2;margin:0;" aria-label="Switch to electric forklift" />
                  <div id="forklift-track" style="position:absolute;inset:0;background:${inputs.electric_forklift ? "var(--brand-accent)" : "var(--border-medium)"};border-radius:var(--radius-full);transition:background 0.2s;"></div>
                  <div id="forklift-thumb" style="position:absolute;top:3px;left:${inputs.electric_forklift ? "23px" : "3px"};width:18px;height:18px;background:#fff;border-radius:var(--radius-full);box-shadow:var(--shadow-xs);transition:left 0.2s;"></div>
                </div>
                <div>
                  <div style="font-size:var(--text-xs);font-weight:700; color:var(--text-primary);">Convert Material Handling to Electric Forklift</div>
                  <div style="font-size:11px;color:var(--text-secondary);">Replaces diesel internal handling with zero point-of-use emissions</div>
                </div>
              </label>
            </div>
          </div>
        </div>

        <!-- Live Result Card -->
        <div class="card" id="result-card" style="display:flex; flex-direction:column; position:relative; overflow:hidden; border-top:4px solid var(--brand-accent); box-shadow:var(--shadow-sm);">
          <div class="card-header">
            <h3 style="font-size:var(--text-base); font-weight:700;">Simulated Impact Analysis</h3>
            <span id="offline-badge" style="display:none;" class="badge" style="background:var(--color-amber-light);color:var(--color-amber);">Local Fallback</span>
          </div>

          <!-- Big reduction number -->
          <div style="text-align:center; padding:var(--space-5) 0; flex:1; display:flex; flex-direction:column; justify-content:center;">
            <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase; font-weight:700; letter-spacing:0.06em; margin-bottom:var(--space-2);">
              Target Footprint Reduction
            </div>
            <div id="result-delta-pct" style="font-size:clamp(3rem,8vw,4.5rem); font-weight:900; color:var(--brand-accent); font-family:var(--font-mono); line-height:1; letter-spacing:-0.03em; transition:all 0.3s cubic-bezier(0.16,1,0.3,1);">
              0.0%
            </div>
            <div id="result-subtitle" style="font-size:var(--text-xs); color:var(--text-secondary); margin-top:var(--space-3);">
              Adjust operational levers to run simulation
            </div>
          </div>

          <!-- KPI grid -->
          <div id="result-kpis" style="display:grid; grid-template-columns:1fr 1fr; gap:var(--space-3); margin-top:var(--space-4);">
            <div style="background:var(--bg-subtle); border:1px solid var(--border-subtle); padding:var(--space-3) var(--space-4); border-radius:var(--radius-lg);">
              <div style="font-size:10px; color:var(--text-muted); text-transform:uppercase; font-weight:700; letter-spacing:0.04em;">New Monthly Total</div>
              <div id="kpi-new-co2e" style="font-family:var(--font-mono); font-size:var(--text-lg); font-weight:800; color:var(--text-primary); margin-top:2px;">—</div>
              <div style="font-size:10px; color:var(--text-muted);">kg CO₂e / month</div>
            </div>
            <div style="background:var(--bg-subtle); border:1px solid var(--border-subtle); padding:var(--space-3) var(--space-4); border-radius:var(--radius-lg);">
              <div style="font-size:10px; color:var(--text-muted); text-transform:uppercase; font-weight:700; letter-spacing:0.04em;">CO₂e Avoided</div>
              <div id="kpi-avoided" style="font-family:var(--font-mono); font-size:var(--text-lg); font-weight:800; color:var(--brand-accent); margin-top:2px;">—</div>
              <div style="font-size:10px; color:var(--text-muted);">kg avoided / mo</div>
            </div>
            <div style="background:var(--bg-subtle); border:1px solid var(--border-subtle); padding:var(--space-3) var(--space-4); border-radius:var(--radius-lg);">
              <div style="font-size:10px; color:var(--text-muted); text-transform:uppercase; font-weight:700; letter-spacing:0.04em;">Monthly OpEx Saved</div>
              <div id="kpi-savings" style="font-family:var(--font-mono); font-size:var(--text-lg); font-weight:800; color:var(--brand-primary); margin-top:2px;">—</div>
            </div>
            <div style="background:var(--bg-subtle); border:1px solid var(--border-subtle); padding:var(--space-3) var(--space-4); border-radius:var(--radius-lg);">
              <div style="font-size:10px; color:var(--text-muted); text-transform:uppercase; font-weight:700; letter-spacing:0.04em;">Payback Period</div>
              <div id="kpi-payback" style="font-family:var(--font-mono); font-size:var(--text-lg); font-weight:800; color:var(--text-primary); margin-top:2px;">—</div>
            </div>
          </div>

          <div id="result-error" style="display:none;margin-top:var(--space-3);padding:var(--space-3);background:var(--color-rose-light);color:var(--color-rose);border-radius:var(--radius-md);font-size:var(--text-xs);"></div>

          <div style="margin-top:var(--space-4);font-size:11px;color:var(--text-muted);border-top:1px solid var(--border-subtle);padding-top:var(--space-3);">
            Governed by deterministic backend calculations with stated empirical uncertainty ranges.
          </div>
        </div>
      </div>

      <!-- Ranked Levers Table -->
      <div class="card" id="ranked-levers-card" style="margin-bottom:var(--space-6);">
        <div class="card-header">
          <div>
            <h2 style="font-size:var(--text-base); font-weight:700;">Ranked Decarbonisation Levers (ROI Hierarchy)</h2>
            <p style="font-size:var(--text-xs); color:var(--text-secondary); margin-top:2px;">Each lever evaluated in isolation, ranked by payback efficiency and carbon reduction.</p>
          </div>
        </div>
        <div id="ranked-levers-body">
          <p style="color:var(--text-muted);font-size:var(--text-xs);padding:var(--space-4) 0;">Run a simulation to see lever ranking.</p>
        </div>
      </div>

      <!-- CTA Conversion Ribbon -->
      <div style="display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:var(--space-4); background:var(--bg-surface); border:1px solid var(--border-subtle); padding:var(--space-5) var(--space-6); border-radius:var(--radius-xl); box-shadow:var(--shadow-sm);">
        <div>
          <div style="font-size:var(--text-sm); font-weight:700; color:var(--text-primary);">Ready to export a buyer-ready GHG disclosure report?</div>
          <div style="font-size:var(--text-xs); color:var(--text-secondary); margin-top:2px;">Your modelled scenario and baseline lines will be compiled into an executive PDF disclosure.</div>
        </div>
        <div style="display:flex; gap:var(--space-3);">
          <button id="goto-report-from-twin-btn" class="btn btn-primary">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            <span>Generate Buyer Report</span>
          </button>
        </div>
      </div>
    </div>
  `;

  // ─── State refs ──────────────────────────────────────────────────────────────
  let currentInputs = { ...inputs };
  let isSimulating = false;

  // ─── DOM refs ─────────────────────────────────────────────────────────────────
  const solarSlider   = container.querySelector("#solar-slider");
  const gensetSlider  = container.querySelector("#genset-slider");
  const idleSlider    = container.querySelector("#idle-slider");
  const railSlider    = container.querySelector("#rail-slider");
  const forkliftCb    = container.querySelector("#forklift-toggle");
  const forkliftTrack = container.querySelector("#forklift-track");
  const forkliftThumb = container.querySelector("#forklift-thumb");

  const solarVal  = container.querySelector("#solar-val");
  const gensetVal = container.querySelector("#genset-val");
  const idleVal   = container.querySelector("#idle-val");
  const railVal   = container.querySelector("#rail-val");

  const statusBadge   = container.querySelector("#sim-status-badge");
  const offlineBadge  = container.querySelector("#offline-badge");
  const deltaEl       = container.querySelector("#result-delta-pct");
  const subtitleEl    = container.querySelector("#result-subtitle");
  const kpiNewCo2e    = container.querySelector("#kpi-new-co2e");
  const kpiAvoided    = container.querySelector("#kpi-avoided");
  const kpiSavings    = container.querySelector("#kpi-savings");
  const kpiPayback    = container.querySelector("#kpi-payback");
  const errorEl       = container.querySelector("#result-error");
  const leversBody    = container.querySelector("#ranked-levers-body");

  // ─── Update result UI ─────────────────────────────────────────────────────────
  function updateResultUI(result, offline = false) {
    const rawDelta   = result.delta_pct  ?? 0;
    const newCo2e    = result.new_co2e_kg ?? baseline;
    const avoided    = Math.max(0, baseline - newCo2e);
    const savings    = result.inr_saved_per_month;
    const payback    = result.payback_months;

    // In backend engine, delta_pct is negative for emission reductions: e.g. -21.9%
    const isReduction = newCo2e < baseline;
    const pctMagnitude = Math.abs(rawDelta);

    if (isReduction && pctMagnitude > 0.05) {
      deltaEl.textContent = `−${pctMagnitude.toFixed(1)}%`;
      deltaEl.style.color = "var(--brand-accent)";
      subtitleEl.innerHTML = `New footprint: <b>${newCo2e.toLocaleString("en-IN", { maximumFractionDigits: 0 })} kg CO₂e/mo</b> (avoiding <b>${avoided.toLocaleString("en-IN", { maximumFractionDigits: 0 })} kg</b> vs baseline)`;
    } else {
      deltaEl.textContent = `0.0%`;
      deltaEl.style.color = "var(--text-muted)";
      subtitleEl.innerHTML = `Baseline: <b>${baseline.toLocaleString("en-IN", { maximumFractionDigits: 0 })} kg CO₂e/mo</b> — move sliders to simulate`;
    }

    kpiNewCo2e.textContent = newCo2e.toLocaleString("en-IN", { maximumFractionDigits: 0 });
    kpiAvoided.textContent  = avoided > 0 ? avoided.toLocaleString("en-IN", { maximumFractionDigits: 0 }) : "0";
    kpiSavings.textContent  = savings != null && savings > 0
      ? `₹${savings.toLocaleString("en-IN", { maximumFractionDigits: 0 })}/mo`
      : "₹0/mo";
    kpiPayback.textContent  = payback != null && payback > 0
      ? `~${payback.toFixed(1)} mo`
      : (savings && savings > 0 ? "Immediate" : "—");

    offlineBadge.style.display = offline ? "inline-flex" : "none";

    // Ranked levers
    leversBody.innerHTML = renderLeversTable(result.ranked_levers || []);

    // Persist to store
    store.setState({ scenarioInputs: { ...currentInputs }, scenarioResult: result });
  }

  // ─── Simulate ─────────────────────────────────────────────────────────────────
  async function runSimulation() {
    if (isSimulating) return;
    isSimulating = true;

    statusBadge.textContent = "⏳ Simulating…";
    statusBadge.style.background = "var(--brand-primary-light)";
    statusBadge.style.color = "var(--brand-primary)";
    errorEl.style.display = "none";

    const inp = {
      solar_share_pct:           currentInputs.solar_share_pct,
      genset_hours_reduction_pct: currentInputs.genset_hours_reduction_pct,
      idle_hours_reduction_pct:   currentInputs.idle_hours_reduction_pct,
      electric_forklift:          currentInputs.electric_forklift,
      rail_shift_pct:             currentInputs.rail_shift_pct,
    };

    try {
      const result = await api.simulateScenario(baselineLines, inp);
      updateResultUI(result, false);
      statusBadge.textContent = "✓ Live";
      statusBadge.style.background = "var(--brand-accent-light)";
      statusBadge.style.color = "var(--brand-accent)";
    } catch (err) {
      // Graceful offline fallback
      const fallback = localFallback(baselineLines, inp);
      updateResultUI(fallback, true);
      statusBadge.textContent = "⚠ Offline";
      statusBadge.style.background = "var(--color-amber-light)";
      statusBadge.style.color = "var(--color-amber)";

      if (err.message && !err.message.includes("abort")) {
        errorEl.textContent = `Backend note: ${err.message}. Showing local estimate.`;
        errorEl.style.display = "block";
      }
    } finally {
      isSimulating = false;
    }
  }

  const debouncedSim = debounce(runSimulation, 600);

  // ─── Slider event handlers ────────────────────────────────────────────────────
  function attachSlider(slider, displayEl, key) {
    slider.addEventListener("input", () => {
      const v = parseInt(slider.value, 10);
      displayEl.textContent = `${v}%`;
      currentInputs[key] = v;
      debouncedSim();
    });
  }

  attachSlider(solarSlider,  solarVal,  "solar_share_pct");
  attachSlider(gensetSlider, gensetVal, "genset_hours_reduction_pct");
  attachSlider(idleSlider,   idleVal,   "idle_hours_reduction_pct");
  attachSlider(railSlider,   railVal,   "rail_shift_pct");

  forkliftCb.addEventListener("change", () => {
    const on = forkliftCb.checked;
    currentInputs.electric_forklift = on ? 1 : 0;
    forkliftTrack.style.background = on ? "var(--brand-accent)" : "var(--border-medium)";
    forkliftThumb.style.left = on ? "23px" : "3px";
    debouncedSim();
  });

  // ─── Reset button ─────────────────────────────────────────────────────────────
  container.querySelector("#twin-reset-btn").addEventListener("click", () => {
    currentInputs = {
      solar_share_pct: 0,
      genset_hours_reduction_pct: 0,
      idle_hours_reduction_pct: 0,
      electric_forklift: 0,
      rail_shift_pct: 0,
    };
    solarSlider.value  = 0; solarVal.textContent  = "0%";
    gensetSlider.value = 0; gensetVal.textContent = "0%";
    idleSlider.value   = 0; idleVal.textContent   = "0%";
    railSlider.value   = 0; railVal.textContent   = "0%";
    forkliftCb.checked = false;
    forkliftTrack.style.background = "var(--border-medium)";
    forkliftThumb.style.left = "3px";
    runSimulation();
  });

  // ─── Nav buttons ─────────────────────────────────────────────────────────────
  container.querySelector("#twin-back-btn").addEventListener("click", () => {
    window.location.hash = "#/results";
  });
  container.querySelector("#goto-report-from-twin-btn").addEventListener("click", () => {
    window.location.hash = "#/report";
  });

  // ─── Auto-run on mount if any non-zero lever is saved ─────────────────────────
  const anyNonZero = Object.values(currentInputs).some(v => v !== 0);
  if (anyNonZero) {
    // run immediately (no debounce) to restore last state
    runSimulation();
  } else if (state.scenarioResult && state.scenarioResult.ranked_levers && state.scenarioResult.ranked_levers.length > 0) {
    updateResultUI(state.scenarioResult, false);
  } else {
    // Run simulation on mount so baseline and ranked levers table are immediately visible
    runSimulation();
  }

  return container;
}
