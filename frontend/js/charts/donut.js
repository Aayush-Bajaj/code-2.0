/**
 * donut.js — Scope breakdown donut chart using locally bundled Chart.js
 */

let activeChart = null;

export function renderScopeDonut(canvasElement, s1, s2, s3) {
  if (!canvasElement) return;

  if (activeChart) {
    activeChart.destroy();
    activeChart = null;
  }

  // Ensure Chart.js is loaded
  if (typeof window.Chart === "undefined") {
    console.error("Local Chart.js not loaded");
    return;
  }

  const theme = document.documentElement.getAttribute("data-theme") || "light";
  const isDark = theme === "dark";
  const isProjector = theme === "projector";
  
  const textColor = isProjector ? "#FFFFFF" : (isDark ? "#F2F7F5" : "#172B28");
  const borderColor = isProjector ? "#000000" : (isDark ? "#111D1B" : "#FFFFFF");
  
  // Palette aligned with ClimateTech Enterprise Standards
  const colors = isProjector
    ? ["#FF9100", "#00FF88", "#D500F9"]
    : (isDark
      ? ["#FB923C", "#34D399", "#818CF8"]
      : ["#C2410C", "#123C35", "#4F46E5"]);

  const total = s1 + s2 + s3 || 1;
  const p1 = Math.round((s1 / total) * 100);
  const p2 = Math.round((s2 / total) * 100);
  const p3 = Math.round((s3 / total) * 100);

  activeChart = new window.Chart(canvasElement, {
    type: "doughnut",
    data: {
      labels: [
        `Scope 1 (Fuel): ${p1}%`,
        `Scope 2 (Grid): ${p2}%`,
        `Scope 3 (Freight): ${p3}%`,
      ],
      datasets: [
        {
          data: [s1, s2, s3],
          backgroundColor: colors,
          borderWidth: 2,
          borderColor: borderColor,
          hoverOffset: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            color: textColor,
            usePointStyle: true,
            pointStyle: "circle",
            font: {
              family: "'Inter', -apple-system, sans-serif",
              size: 11,
              weight: "600",
            },
            padding: 14,
            boxWidth: 8,
            boxHeight: 8,
          },
        },
        tooltip: {
          backgroundColor: isDark ? "#182B28" : "#172B28",
          titleColor: "#FFFFFF",
          bodyColor: "#F1F5F3",
          padding: 10,
          cornerRadius: 8,
          displayColors: true,
          boxPadding: 4,
          callbacks: {
            label(ctx) {
              const val = ctx.parsed || 0;
              const pct = Math.round((val / total) * 100);
              return ` ${val.toLocaleString("en-IN", { maximumFractionDigits: 1 })} kg CO2e (${pct}%)`;
            },
          },
        },
      },
      cutout: "70%",
    },
  });
}
