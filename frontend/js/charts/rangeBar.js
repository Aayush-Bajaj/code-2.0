/**
 * rangeBar.js — Lightweight uncertainty range bar component.
 * Displays calculated value point with low-to-high uncertainty band.
 */

export function renderRangeBar(low, val, high, unit = "kg") {
  const minVal = Math.max(0, low * 0.9);
  const maxVal = high * 1.1;
  const span = maxVal - minVal || 1;

  const lowPct = Math.max(0, Math.min(100, ((low - minVal) / span) * 100));
  const highPct = Math.max(0, Math.min(100, ((high - minVal) / span) * 100));
  const valPct = Math.max(0, Math.min(100, ((val - minVal) / span) * 100));
  const widthPct = Math.max(4, highPct - lowPct);

  return `
    <div class="mini-range-bar-container" title="Uncertainty Range: ${low.toLocaleString()} to ${high.toLocaleString()} ${unit}">
      <div class="mini-range-bar-track">
        <div class="mini-range-bar-fill" style="left: ${lowPct}%; width: ${widthPct}%;"></div>
        <div class="mini-range-bar-marker" style="left: ${valPct}%;"></div>
      </div>
      <div class="mini-range-bar-labels">
        <span>Low: ${low.toLocaleString("en-IN", { maximumFractionDigits: 0 })}</span>
        <span>High: ${high.toLocaleString("en-IN", { maximumFractionDigits: 0 })}</span>
      </div>
    </div>
  `;
}
