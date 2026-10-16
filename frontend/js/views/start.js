/**
 * start.js — Start Screen / Hero View
 * Clean enterprise landing: Start custom factory assessment or inspect verified sample dataset.
 */

import { store } from "../store.js";
import { t } from "../i18n.js";

export function renderStartView() {
  const container = document.createElement("div");
  container.className = "fade-in";

  container.innerHTML = `
    <div style="text-align: center; max-width: 880px; margin: var(--space-4) auto var(--space-12);">
      
      <!-- Enterprise Subtitle Badge -->
      <div style="display:inline-flex; align-items:center; gap:8px; background:var(--brand-primary-light); color:var(--brand-primary); padding:6px 14px; border-radius:var(--radius-full); font-size:var(--text-xs); font-weight:700; letter-spacing:0.02em; margin-bottom:var(--space-5); border:1px solid rgba(18, 60, 53, 0.12);">
        <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background:var(--brand-accent);"></span>
        <span>Built for Indian MSME Suppliers & Exporters · CBAM & BRSR Readiness</span>
      </div>
      
      <!-- Main Hero Headline -->
      <h1 style="font-size: clamp(2.25rem, 5.5vw, 3.5rem); font-weight: 800; letter-spacing: -0.035em; margin-bottom: var(--space-4); line-height: 1.15; color: var(--text-primary);">
        ${t("start_hero_title")}
      </h1>
      
      <!-- Supporting Subtitle -->
      <p style="font-size: var(--text-base); color: var(--text-secondary); margin-bottom: var(--space-8); line-height: 1.65; max-width: 720px; margin-left: auto; margin-right: auto;">
        ${t("start_hero_subtitle")}
      </p>

      <!-- Primary Action Buttons -->
      <div style="display: flex; flex-wrap: wrap; justify-content: center; gap: var(--space-3); margin-bottom: var(--space-8);">
        <button id="hero-upload-btn" class="btn btn-primary btn-lg pulse-subtle" style="padding: 0 var(--space-6);">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          <span>Start Factory Assessment</span>
        </button>

        <button id="hero-demo-btn" class="btn btn-secondary btn-lg" style="padding: 0 var(--space-6);">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>
          </svg>
          <span>View Benchmark Factory (Sharma Auto)</span>
        </button>
      </div>

      <!-- Trust Metrics / Compliance Checklist -->
      <div style="display:flex; justify-content:center; flex-wrap:wrap; gap:var(--space-6); font-size:var(--text-xs); color:var(--text-secondary); font-weight:500;">
        <span style="display:inline-flex; align-items:center; gap:6px;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--brand-accent)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
          Deterministic calculation (Zero AI halluncinations)
        </span>
        <span style="display:inline-flex; align-items:center; gap:6px;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--brand-accent)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
          100% Cryptographic Evidence Trail
        </span>
        <span style="display:inline-flex; align-items:center; gap:6px;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--brand-accent)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
          IPCC 2006, CEA v22 & DEFRA Registry
        </span>
      </div>
    </div>

    <!-- 3-Step Enterprise Workflow Cards -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: var(--space-6); max-width: 1080px; margin: 0 auto;">
      
      <!-- Step 1 Card -->
      <div class="card" style="position: relative; overflow: hidden; border-top: 3px solid var(--brand-primary);">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-4);">
          <div style="width: 42px; height: 42px; border-radius: var(--radius-lg); background: var(--brand-primary-light); color: var(--brand-primary); display: flex; align-items: center; justify-content: center;">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
              <polyline points="10 9 9 9 8 9"/>
            </svg>
          </div>
          <span style="font-family: var(--font-mono); font-size: 11px; font-weight: 700; color: var(--text-muted); background: var(--bg-muted); padding: 2px 8px; border-radius: var(--radius-sm);">STEP 01</span>
        </div>
        <h3 style="font-size: var(--text-base); margin-bottom: var(--space-2);">${t("step1_title")}</h3>
        <p style="font-size: var(--text-xs); color: var(--text-secondary); line-height: 1.6;">${t("step1_desc")}</p>
      </div>

      <!-- Step 2 Card -->
      <div class="card" style="position: relative; overflow: hidden; border-top: 3px solid var(--color-amber);">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-4);">
          <div style="width: 42px; height: 42px; border-radius: var(--radius-lg); background: var(--color-amber-light); color: var(--color-amber); display: flex; align-items: center; justify-content: center;">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="3"/>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
            </svg>
          </div>
          <span style="font-family: var(--font-mono); font-size: 11px; font-weight: 700; color: var(--text-muted); background: var(--bg-muted); padding: 2px 8px; border-radius: var(--radius-sm);">STEP 02</span>
        </div>
        <h3 style="font-size: var(--text-base); margin-bottom: var(--space-2);">${t("step2_title")}</h3>
        <p style="font-size: var(--text-xs); color: var(--text-secondary); line-height: 1.6;">${t("step2_desc")}</p>
      </div>

      <!-- Step 3 Card -->
      <div class="card" style="position: relative; overflow: hidden; border-top: 3px solid var(--brand-accent);">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-4);">
          <div style="width: 42px; height: 42px; border-radius: var(--radius-lg); background: var(--brand-accent-light); color: var(--brand-accent-hover); display: flex; align-items: center; justify-content: center;">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/>
              <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/>
              <path d="M4 22h16"/>
              <path d="M10 14.66V17c0 .55-.45 1-1 1H7c-.55 0-1-.45-1-1v-2.34"/>
              <path d="M18 14.66V17c0 .55-.45 1-1 1h-2c-.55 0-1-.45-1-1v-2.34"/>
              <path d="M18 2H6v7a6 6 0 0 0 12 0V2z"/>
            </svg>
          </div>
          <span style="font-family: var(--font-mono); font-size: 11px; font-weight: 700; color: var(--text-muted); background: var(--bg-muted); padding: 2px 8px; border-radius: var(--radius-sm);">STEP 03</span>
        </div>
        <h3 style="font-size: var(--text-base); margin-bottom: var(--space-2);">${t("step3_title")}</h3>
        <p style="font-size: var(--text-xs); color: var(--text-secondary); line-height: 1.6;">${t("step3_desc")}</p>
      </div>
    </div>

    <!-- Smart Energy & Electricity Calculator Section -->
    <div style="max-width: 1080px; margin: var(--space-8) auto 0;">
      <section class="smart-energy-section">
        <div style="display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:var(--space-6);">
          <div style="display:flex; align-items:flex-start; gap:var(--space-4); max-width:740px;">
            <!-- Energy / Leaf / Lightning Icon Badge -->
            <div class="smart-energy-icon-wrap">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
              </svg>
            </div>
            <div style="display:flex; flex-direction:column; gap:4px; text-align:left;">
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
    </div>
  `;

  // Attach button events
  container.querySelector("#hero-upload-btn").addEventListener("click", () => {
    window.location.hash = "#/upload";
  });

  container.querySelector("#hero-demo-btn").addEventListener("click", () => {
    store.loadDemo();
    window.location.hash = "#/results";
  });

  return container;
}
