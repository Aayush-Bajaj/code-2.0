/**
 * cameraModal.js — Enterprise Live Camera Viewfinder & Ingestion Modal
 * Captures live invoices, utility receipts, or machinery smoke plumes using device camera.
 */

let modalBackdrop = null;
let videoEl = null;
let canvasEl = null;
let previewImg = null;
let currentStream = null;
let onCaptureCallback = null;
let currentMode = "auto"; // "auto", "bill", "machinery"
let capturedBlob = null;

export function initCameraModal() {
  if (document.getElementById("camera-modal-backdrop")) return;

  modalBackdrop = document.createElement("div");
  modalBackdrop.id = "camera-modal-backdrop";
  modalBackdrop.className = "camera-modal-backdrop";
  modalBackdrop.setAttribute("role", "dialog");
  modalBackdrop.setAttribute("aria-modal", "true");

  modalBackdrop.innerHTML = `
    <div class="camera-modal-card">
      <!-- Modal Header -->
      <div style="display:flex; justify-content:space-between; align-items:center; padding:var(--space-3) var(--space-5); border-bottom:1px solid rgba(255,255,255,0.1);">
        <div style="display:flex; align-items:center; gap:8px;">
          <span style="font-size:1.2rem;">📷</span>
          <b style="font-size:var(--text-sm);">Live Industrial Lens</b>
        </div>
        <!-- Mode Tabs -->
        <div style="display:flex; gap:4px; background:rgba(255,255,255,0.1); padding:2px; border-radius:var(--radius-full); font-size:11px;">
          <button id="cam-mode-bill" class="btn btn-sm btn-accent" style="padding:2px 8px; min-height:24px;">📄 Bill OCR</button>
          <button id="cam-mode-machinery" class="btn btn-sm btn-secondary" style="padding:2px 8px; min-height:24px; color:#fff; border:none; background:transparent;">🏭 Machinery & Smoke</button>
        </div>
        <button id="cam-close-btn" class="btn btn-sm btn-secondary" style="background:transparent; border:none; color:#94a3b8; font-size:1.2rem; cursor:pointer;">✕</button>
      </div>

      <!-- Viewfinder Viewport -->
      <div class="camera-viewfinder-box">
        <video id="camera-video" class="camera-video-stream" autoplay playsinline muted></video>
        <img id="camera-snapshot-preview" class="camera-snapshot-preview" alt="Snapshot Preview" />
        <canvas id="camera-canvas" class="camera-canvas-hidden"></canvas>
        <div id="camera-reticle" class="camera-reticle">
          <span id="reticle-label">Align document or nameplate within frame</span>
        </div>
      </div>

      <!-- Control Bar -->
      <div style="padding:var(--space-4) var(--space-6); background:#0b1120; display:flex; justify-content:space-between; align-items:center;">
        <div id="camera-status-text" style="font-size:11px; color:#94a3b8; max-width:200px;">
          Point at electricity bill, diesel slip, or generator.
        </div>
        <div id="capture-controls" style="display:flex; align-items:center; gap:var(--space-4);">
          <button id="camera-shutter" class="camera-shutter-btn" title="Snap Photo"></button>
        </div>
        <div id="review-controls" style="display:none; gap:var(--space-2);">
          <button id="camera-retake-btn" class="btn btn-secondary btn-sm" style="color:#fff; border-color:rgba(255,255,255,0.2);">🔄 Retake</button>
          <button id="camera-confirm-btn" class="btn btn-accent btn-sm">✓ Ingest Evidence</button>
        </div>
      </div>
    </div>
  `;

  document.body.appendChild(modalBackdrop);

  videoEl = modalBackdrop.querySelector("#camera-video");
  canvasEl = modalBackdrop.querySelector("#camera-canvas");
  previewImg = modalBackdrop.querySelector("#camera-snapshot-preview");

  // Mode buttons
  const billModeBtn = modalBackdrop.querySelector("#cam-mode-bill");
  const machModeBtn = modalBackdrop.querySelector("#cam-mode-machinery");
  const reticleLabel = modalBackdrop.querySelector("#reticle-label");

  billModeBtn.addEventListener("click", () => {
    currentMode = "bill";
    billModeBtn.className = "btn btn-sm btn-accent";
    machModeBtn.className = "btn btn-sm btn-secondary";
    machModeBtn.style.background = "transparent";
    machModeBtn.style.color = "#fff";
    machModeBtn.style.border = "none";
    reticleLabel.textContent = "Align invoice or bill within frame";
  });

  machModeBtn.addEventListener("click", () => {
    currentMode = "machinery";
    machModeBtn.className = "btn btn-sm btn-accent";
    billModeBtn.className = "btn btn-sm btn-secondary";
    billModeBtn.style.background = "transparent";
    billModeBtn.style.color = "#fff";
    billModeBtn.style.border = "none";
    reticleLabel.textContent = "Frame generator nameplate or exhaust plume";
  });

  // Close handlers
  modalBackdrop.querySelector("#cam-close-btn").addEventListener("click", closeCameraModal);
  modalBackdrop.addEventListener("click", (e) => {
    if (e.target === modalBackdrop) closeCameraModal();
  });

  // Shutter action
  modalBackdrop.querySelector("#camera-shutter").addEventListener("click", takeSnapshot);

  // Retake action
  modalBackdrop.querySelector("#camera-retake-btn").addEventListener("click", () => {
    previewImg.style.display = "none";
    videoEl.style.display = "block";
    modalBackdrop.querySelector("#capture-controls").style.display = "flex";
    modalBackdrop.querySelector("#review-controls").style.display = "none";
    modalBackdrop.querySelector("#camera-status-text").textContent = "Camera active. Ready for capture.";
  });

  // Confirm Ingest
  modalBackdrop.querySelector("#camera-confirm-btn").addEventListener("click", () => {
    if (capturedBlob && onCaptureCallback) {
      const filename = `camera_capture_${Date.now()}.jpg`;
      const file = new File([capturedBlob], filename, { type: "image/jpeg" });
      onCaptureCallback(file, currentMode);
    }
    closeCameraModal();
  });
}

function takeSnapshot() {
  if (!videoEl || !canvasEl) return;
  const w = videoEl.videoWidth || 1280;
  const h = videoEl.videoHeight || 720;

  canvasEl.width = w;
  canvasEl.height = h;
  const ctx = canvasEl.getContext("2d");
  ctx.drawImage(videoEl, 0, 0, w, h);

  canvasEl.toBlob((blob) => {
    capturedBlob = blob;
    const url = URL.createObjectURL(blob);
    previewImg.src = url;
    previewImg.style.display = "block";
    videoEl.style.display = "none";

    modalBackdrop.querySelector("#capture-controls").style.display = "none";
    modalBackdrop.querySelector("#review-controls").style.display = "flex";
    modalBackdrop.querySelector("#camera-status-text").textContent = "Frame captured. Review and confirm ingestion.";
  }, "image/jpeg", 0.95);
}

export async function openCameraModal(callback, fallbackInputEl) {
  initCameraModal();
  onCaptureCallback = callback;
  capturedBlob = null;

  modalBackdrop.querySelector("#camera-snapshot-preview").style.display = "none";
  videoEl.style.display = "block";
  modalBackdrop.querySelector("#capture-controls").style.display = "flex";
  modalBackdrop.querySelector("#review-controls").style.display = "none";
  modalBackdrop.querySelector("#camera-status-text").textContent = "Starting camera...";

  try {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error("Camera API not supported in this browser context");
    }

    currentStream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: "environment" },
        width: { ideal: 1920 },
        height: { ideal: 1080 }
      },
      audio: false
    });

    videoEl.srcObject = currentStream;
    await videoEl.play();
    modalBackdrop.classList.add("open");
    modalBackdrop.querySelector("#camera-status-text").textContent = "Camera live. Tap white shutter to snap.";
  } catch (err) {
    console.warn("Unable to open hardware camera stream:", err);
    // Graceful fallback to file picker
    if (fallbackInputEl) {
      fallbackInputEl.click();
    } else {
      alert("Camera access was not available or permitted. Please use the 'Browse Files' button to upload an image.");
    }
  }
}

export function closeCameraModal() {
  if (currentStream) {
    currentStream.getTracks().forEach((track) => track.stop());
    currentStream = null;
  }
  if (modalBackdrop) {
    modalBackdrop.classList.remove("open");
  }
}
