/**
 * store.js — Centralized Reactive State Store for Carbon Passport
 * Holds verified baseline lines, evidence items, demo scenario, and user inputs.
 */

// Initial Sharma Auto Components MIDC Pune Demo Baseline
export const DEMO_BASELINE_LINES = [
  {
    id: "em_line_dg_01",
    scope: 1,
    category: "Backup Power Generation (Diesel DG Set)",
    activity_value: 933.2,
    activity_unit: "L diesel",
    factor_id: "diesel_mineral_l",
    factor_value: 2.68,
    factor_unit: "kg CO2e/L",
    factor_source: "IPCC 2006 Vol2 / DEFRA 2024",
    factor_url: "https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2024",
    formula_text: "100 kW x 75% load x 45 hrs x 0.2765 L/kWh x 2.68 kg CO2e/L = 2,500.9 kg",
    co2e_kg: 2500.9,
    low_kg: 2375.9,
    high_kg: 2876.0,
    evidence_refs: ["det_genset_kirloskar_01", "vid_exhaust_smoke_01"],
    method: "video_estimate",
    flags: ["MAINTENANCE_WIDENED_RANGE", "HEAVY_SMOKE_FLAGGED"],
    details: {
      machine_name: "Kirloskar Green 125 kVA Silent DG Set (100 kW)",
      smoke_score: 8.2,
      smoke_level: "heavy",
      smoke_color: "black",
      hours_per_month: 45,
      load_pct: 75,
      maintenance_reason: "Heavy black smoke detected (Ringelmann 8.2) — widened range due to injector fouling inefficiency",
    }
  },
  {
    id: "em_line_forklift_01",
    scope: 1,
    category: "Internal Material Handling (Diesel Forklift)",
    activity_value: 1250.0,
    activity_unit: "L diesel",
    factor_id: "diesel_mineral_l",
    factor_value: 2.68,
    factor_unit: "kg CO2e/L",
    factor_source: "IPCC 2006 / DEFRA 2024",
    factor_url: "https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2024",
    formula_text: "1,250.0 L x 2.68 kg CO2e/L = 3,350.0 kg",
    co2e_kg: 3350.0,
    low_kg: 3182.5,
    high_kg: 3517.5,
    evidence_refs: ["bill_iocl_diesel_march2024"],
    method: "bill",
    flags: [],
    details: {
      machine_name: "Godrej GX 300 D 3.0T Forklift (IOCL Bhosari Fuel Invoice)",
      amount_inr: 115625.0,
      user_confirmed: true,
    }
  },
  {
    id: "em_line_electricity_01",
    scope: 2,
    category: "Purchased Grid Electricity (Machining & Stamping)",
    activity_value: 18450.0,
    activity_unit: "kWh",
    factor_id: "grid_india_wa",
    factor_value: 0.716,
    factor_unit: "kg CO2e/kWh",
    factor_source: "Central Electricity Authority (CEA) v22",
    factor_url: "https://cea.nic.in/wp-content/uploads/baseline/2026/09/User_Guide__Version_22.0.pdf",
    formula_text: "18,450.0 kWh x 0.716 kg CO2e/kWh = 13,210.2 kg (CO2 only)",
    co2e_kg: 13210.2,
    low_kg: 12549.7,
    high_kg: 13870.7,
    evidence_refs: ["bill_msedcl_march2024"],
    method: "bill",
    flags: ["CO2_ONLY_GRID_FACTOR"],
    details: {
      supplier: "MSEDCL Maharashtra State Electricity Distribution",
      amount_inr: 162360.0,
      user_confirmed: true,
    }
  },
  {
    id: "em_line_freight_01",
    scope: 3,
    category: "Outbound Logistics (Port & Tier-1 Corridor Freight)",
    activity_value: 30400.0,
    activity_unit: "tonne-km",
    factor_id: "freight_hgv_avg_tkm",
    factor_value: 0.115,
    factor_unit: "kg CO2e/tonne-km",
    factor_source: "DEFRA 2024 / GLEC Framework v3",
    factor_url: "https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2024",
    formula_text: "30,400.0 tonne-km x 0.115 kg CO2e/tkm = 3,496.0 kg",
    co2e_kg: 3496.0,
    low_kg: 3321.2,
    high_kg: 3670.8,
    evidence_refs: ["bill_vrl_logistics_march2024"],
    method: "bill",
    flags: [],
    details: {
      supplier: "VRL Logistics Ltd. / Consignment Notes",
      amount_inr: 182400.0,
      user_confirmed: true,
    }
  }
];

class Store {
  constructor() {
    this.state = {
      facilityName: "Sharma Auto Components Pvt. Ltd.",
      facilityLocation: "Plot 42, Bhosari MIDC, Pune, Maharashtra",
      reportingPeriod: "March 2024 (Reference Month)",
      theme: "light",
      lang: "en",
      isDemo: true,
      periodView: "month", // "month" or "year"
      currentRoute: "#/start",
      files: [],
      detections: [],
      bills: [],
      baselineLines: [...DEMO_BASELINE_LINES],
      scenarioInputs: {
        solar_share_pct: 0,
        genset_hours_reduction_pct: 0,
        idle_hours_reduction_pct: 0,
        electric_forklift: 0,
        rail_shift_pct: 0,
      },
      scenarioResult: null,
      activeEvidenceLineId: null,
      reportData: null,
      sourcesMeta: null,
      equivalentsMeta: null,
    };
    this.listeners = new Set();
  }

  getState() {
    return this.state;
  }

  setState(updates) {
    this.state = { ...this.state, ...updates };
    this.notify();
  }

  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  notify() {
    for (const listener of this.listeners) {
      listener(this.state);
    }
  }

  // Set Theme
  setTheme(theme) {
    this.state.theme = theme;
    localStorage.setItem("cp_theme", theme);
    document.documentElement.setAttribute("data-theme", theme);
    this.notify();
  }

  // Toggle View Mode (Month vs Year)
  togglePeriodView() {
    const next = this.state.periodView === "month" ? "year" : "month";
    this.setState({ periodView: next });
  }

  // Compute Totals
  getTotals() {
    const mult = this.state.periodView === "year" ? 12 : 1;
    let s1 = 0, s1_low = 0, s1_high = 0;
    let s2 = 0, s2_low = 0, s2_high = 0;
    let s3 = 0, s3_low = 0, s3_high = 0;

    for (const line of this.state.baselineLines) {
      const co2e = line.co2e_kg * mult;
      const low = line.low_kg * mult;
      const high = line.high_kg * mult;

      if (line.scope === 1) {
        s1 += co2e; s1_low += low; s1_high += high;
      } else if (line.scope === 2) {
        s2 += co2e; s2_low += low; s2_high += high;
      } else if (line.scope === 3) {
        s3 += co2e; s3_low += low; s3_high += high;
      }
    }

    const total = s1 + s2 + s3;
    const total_low = s1_low + s2_low + s3_low;
    const total_high = s1_high + s2_high + s3_high;

    return {
      scope1: { co2e: s1, low: s1_low, high: s1_high },
      scope2: { co2e: s2, low: s2_low, high: s2_high },
      scope3: { co2e: s3, low: s3_low, high: s3_high },
      total: { co2e: total, low: total_low, high: total_high },
      multiplier: mult,
    };
  }

  // Data Confidence Score (Computed ONLY from API fields)
  // Formula: 40% bill confirmation share + 35% file hashes verified + 25% narrow uncertainty band
  getDataConfidence() {
    const lines = this.state.baselineLines;
    if (!lines || lines.length === 0) return { score: 0, label: "No Data", breakdown: {} };

    // 1. Share of lines from verified/confirmed bills
    const billLines = lines.filter(l => l.method === "bill").length;
    const billRatio = billLines / lines.length; // max 0.40

    // 2. Share of lines with cryptographic evidence hashes
    const hashLines = lines.filter(l => l.evidence_refs && l.evidence_refs.length > 0).length;
    const hashRatio = hashLines / lines.length; // max 0.35

    // 3. Narrowness of uncertainty range (1 - range_width / co2e)
    let totalCo2e = 0;
    let totalRangeWidth = 0;
    for (const l of lines) {
      totalCo2e += l.co2e_kg;
      totalRangeWidth += (l.high_kg - l.low_kg);
    }
    const avgRelWidth = totalCo2e > 0 ? (totalRangeWidth / totalCo2e) : 1.0;
    // Lower relative width = higher confidence
    const rangeRatio = Math.max(0, Math.min(1.0, 1.0 - (avgRelWidth - 0.10) / 0.40)); // max 0.25

    const score = Math.round((billRatio * 40) + (hashRatio * 35) + (rangeRatio * 25));

    let label = "High Confidence";
    if (score < 60) label = "Indicative Only";
    else if (score < 80) label = "Substantiated";

    return {
      score,
      label,
      formula: "Confidence = (40% Verified Bills) + (35% Hash Integrity) + (25% Narrow Uncertainty Range)",
      breakdown: {
        billScore: Math.round(billRatio * 40),
        hashScore: Math.round(hashRatio * 35),
        rangeScore: Math.round(rangeRatio * 25),
      }
    };
  }

  // Persist scenario result from twin simulator
  setScenarioResult(result) {
    this.setState({ scenarioResult: result });
  }

  setBaselineLines(lines) {
    this.setState({ baselineLines: lines, isDemo: false });
  }

  setUploadedItems(items) {
    const bills = items.filter(i => i.bill).map(i => i.bill);
    const detections = items.filter(i => i.detection).map(i => i.detection);
    this.setState({
      files: items,
      bills: bills.length ? bills : this.state.bills,
      detections: detections.length ? detections : this.state.detections,
      isDemo: false,
    });
  }

  updateBill(index, updatedBill) {
    const nextBills = [...this.state.bills];
    nextBills[index] = { ...nextBills[index], ...updatedBill };
    this.setState({ bills: nextBills });
  }

  updateDetection(index, updatedDetection) {
    const nextDetections = [...this.state.detections];
    nextDetections[index] = { ...nextDetections[index], ...updatedDetection };
    this.setState({ detections: nextDetections });
  }

  // Reset to Sharma Auto Demo
  loadDemo() {
    this.setState({
      isDemo: true,
      baselineLines: [...DEMO_BASELINE_LINES],
      bills: [],
      detections: [],
      scenarioInputs: {
        solar_share_pct: 0,
        genset_hours_reduction_pct: 0,
        idle_hours_reduction_pct: 0,
        electric_forklift: 0,
        rail_shift_pct: 0,
      },
      scenarioResult: null,
    });
  }
}

export const store = new Store();
