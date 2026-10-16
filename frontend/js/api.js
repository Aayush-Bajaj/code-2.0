/**
 * api.js — Resilient Fetch Client for Carbon Passport API
 * Includes timeout, automatic retry, and fallback to local demo data if offline.
 */

const API_TIMEOUT_MS = 60000; // 60s for OCR/Vision uploads

async function request(url, options = {}, retries = 1) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), API_TIMEOUT_MS);

  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  try {
    const res = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers,
    });
    clearTimeout(id);

    if (!res.ok) {
      const errBody = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(errBody.detail || `HTTP Error ${res.status}`);
    }
    return await res.json();
  } catch (err) {
    clearTimeout(id);
    if (retries > 0) {
      return request(url, options, retries - 1);
    }
    throw err;
  }
}

export const api = {
  // Upload Bills or Machinery Media
  async uploadFiles(fileList, mediaHint = "auto") {
    const formData = new FormData();
    for (const f of fileList) {
      formData.append("files", f);
    }
    return await request(`/api/upload?media_hint=${encodeURIComponent(mediaHint)}`, {
      method: "POST",
      body: formData,
    });
  },

  // Calculate EmissionLines from confirmed bills and machine detections
  async calculate(bills, gensets) {
    return await request("/api/calculate", {
      method: "POST",
      body: JSON.stringify({ bills, gensets }),
    });
  },

  // Fetch factor provenance and datasheets
  async getMetaSources() {
    try {
      return await request("/meta/sources");
    } catch (err) {
      console.warn("Backend /meta/sources offline, using fallback", err);
      return null;
    }
  },

  // Fetch factor-derived equivalents (litres diesel, kWh grid)
  async getMetaEquivalents(co2e_kg) {
    try {
      return await request(`/meta/equivalents?co2e_kg=${encodeURIComponent(co2e_kg)}`);
    } catch (err) {
      console.warn("Backend /meta/equivalents offline, computing via local factors", err);
      const diesel = co2e_kg / 2.68;
      const grid = co2e_kg / 0.716;
      return {
        co2e_kg,
        diesel_litres: Math.round(diesel * 10) / 10,
        diesel_factor: 2.68,
        diesel_text: `Same as burning ${diesel.toLocaleString("en-IN", { maximumFractionDigits: 1 })} litres of diesel fuel`,
        grid_kwh: Math.round(grid * 10) / 10,
        grid_factor: 0.716,
        grid_text: `Equivalent to ${grid.toLocaleString("en-IN", { maximumFractionDigits: 1 })} kWh of grid electricity`,
      };
    }
  },

  // Simulate What-If Scenario
  async simulateScenario(baselineLines, inputs) {
    return await request("/api/scenarios/simulate", {
      method: "POST",
      body: JSON.stringify({
        baseline_lines: baselineLines,
        inputs: inputs,
      }),
    });
  },

  // Generate Report
  async generateReport(payload) {
    return await request("/report", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getReportPdfUrl(reportId) {
    return `/report/${encodeURIComponent(reportId)}/pdf`;
  },
};
