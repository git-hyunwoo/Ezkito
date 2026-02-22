// Elements
  const fileInput = document.getElementById("fileInput");
  const dropzone = document.getElementById("dropzone");
  const chooseBtn = document.getElementById("chooseBtn");
  const thumbs = document.getElementById("thumbs");
  const fileSummary = document.getElementById("fileSummary");

  const mode = document.getElementById("mode");
  const whBox = document.getElementById("whBox");
  const percentBox = document.getElementById("percentBox");

  const widthInput = document.getElementById("width");
  const heightInput = document.getElementById("height");
  const percentInput = document.getElementById("percent");
  const keepRatio = document.getElementById("keepRatio");

  const mainPreview = document.getElementById("mainPreview");
  const emptyPreview = document.getElementById("emptyPreview");
  const origInfo = document.getElementById("origInfo");
  const newInfo = document.getElementById("newInfo");

  const submitBtn = document.getElementById("submitBtn");
  const clearBtn = document.getElementById("clearBtn");

  // State
  let objectUrls = [];
  let originalW = null;
  let originalH = null;
  let isSyncing = false;

  function revokeAllObjectUrls() {
    objectUrls.forEach(u => URL.revokeObjectURL(u));
    objectUrls = [];
  }

  function bytesToHuman(bytes) {
    if (!bytes && bytes !== 0) return "-";
    const units = ["B","KB","MB","GB"];
    let i = 0;
    let v = bytes;
    while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
    return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
  }

  function setModeUI() {
    if (mode.value === "percent") {
      whBox.style.display = "none";
      percentBox.style.display = "block";
    } else {
      whBox.style.display = "block";
      percentBox.style.display = "none";
    }
    updateEstimation();
  }

  function computeNewSize() {
    if (!originalW || !originalH) return null;

    if (mode.value === "percent") {
      const p = parseInt(percentInput.value || "0", 10);
      if (!p || p <= 0) return null;
      return {
        w: Math.max(1, Math.round(originalW * p / 100)),
        h: Math.max(1, Math.round(originalH * p / 100)),
      };
    }

    const w = parseInt(widthInput.value || "0", 10);
    const h = parseInt(heightInput.value || "0", 10);
    if ((!w || w <= 0) && (!h || h <= 0)) return null;

    if (keepRatio.checked) {
      if (w > 0 && (!h || h <= 0)) return { w, h: Math.max(1, Math.round(originalH * (w / originalW))) };
      if (h > 0 && (!w || w <= 0)) return { w: Math.max(1, Math.round(originalW * (h / originalH))), h };
      return { w: w > 0 ? w : originalW, h: h > 0 ? h : originalH };
    }

    return { w: w > 0 ? w : originalW, h: h > 0 ? h : originalH };
  }

  function updateEstimation() {
    const est = computeNewSize();
    if (!originalW || !originalH) {
      origInfo.textContent = "-";
      newInfo.textContent = "-";
      submitBtn.disabled = (fileInput.files.length === 0);
      return;
    }

    origInfo.textContent = `${originalW} × ${originalH}px`;

    if (!est) {
      newInfo.textContent = "-";
      submitBtn.disabled = true;
      return;
    }

    newInfo.textContent = `${est.w} × ${est.h}px`;
    submitBtn.disabled = (fileInput.files.length === 0);
  }

  function renderThumbs(files) {
    thumbs.innerHTML = "";
    if (!files || files.length === 0) {
      thumbs.style.display = "none";
      fileSummary.textContent = "";
      return;
    }

    thumbs.style.display = "flex";

    const totalBytes = Array.from(files).reduce((acc, f) => acc + (f.size || 0), 0);
    fileSummary.textContent = `${files.length} file(s) • ${bytesToHuman(totalBytes)}`;

    const maxThumbs = 10;
    const shown = Array.from(files).slice(0, maxThumbs);

    shown.forEach((f, idx) => {
      const url = URL.createObjectURL(f);
      objectUrls.push(url);

      const img = document.createElement("img");
      img.className = "thumb";
      img.src = url;
      img.alt = f.name;
      img.title = f.name;

      img.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        setMainPreview(idx);
      });

      thumbs.appendChild(img);
    });

    if (files.length > maxThumbs) {
      const more = document.createElement("div");
      more.className = "small text-muted align-self-center ms-1";
      more.textContent = `+${files.length - maxThumbs} more`;
      thumbs.appendChild(more);
    }
  }

  function setMainPreview(index) {
    const files = fileInput.files;
    if (!files || files.length === 0) return;

    const f = files[index] || files[0];
    const url = URL.createObjectURL(f);
    objectUrls.push(url);

    mainPreview.src = url;
    mainPreview.style.display = "block";
    emptyPreview.style.display = "none";

    const img = new Image();
    img.onload = function () {
      originalW = img.naturalWidth;
      originalH = img.naturalHeight;
      clearBtn.disabled = false;
      updateEstimation();
    };
    img.src = url;
  }

  function clearAll() {
    revokeAllObjectUrls();
    fileInput.value = "";
    originalW = null;
    originalH = null;

    thumbs.innerHTML = "";
    thumbs.style.display = "none";
    fileSummary.textContent = "";

    mainPreview.removeAttribute("src");
    mainPreview.style.display = "none";
    emptyPreview.style.display = "block";

    origInfo.textContent = "-";
    newInfo.textContent = "-";

    submitBtn.disabled = true;
    clearBtn.disabled = true;
  }

  function syncOtherSide(changed) {
    if (!keepRatio.checked) return;
    if (!originalW || !originalH) return;
    if (mode.value !== "wh") return;
    if (isSyncing) return;

    isSyncing = true;
    try {
      const w = parseInt(widthInput.value || "0", 10);
      const h = parseInt(heightInput.value || "0", 10);

      if (changed === "w" && w > 0) {
        if (!h || h <= 0) heightInput.value = Math.max(1, Math.round(originalH * (w / originalW)));
      } else if (changed === "h" && h > 0) {
        if (!w || w <= 0) widthInput.value = Math.max(1, Math.round(originalW * (h / originalH)));
      }
    } finally {
      isSyncing = false;
    }
  }

  // Events
  chooseBtn.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("click", (e) => {
    if (e.target === chooseBtn) return;
    fileInput.click();
  });

  ["dragenter", "dragover"].forEach(evt => {
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach(evt => {
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", (e) => {
    const dt = e.dataTransfer;
    if (!dt || !dt.files || dt.files.length === 0) return;
    fileInput.files = dt.files;
    handleFilesChanged();
  });

  function handleFilesChanged() {
    revokeAllObjectUrls();
    renderThumbs(fileInput.files);

    if (fileInput.files.length > 0) {
      setMainPreview(0);
      submitBtn.disabled = false;
    } else {
      clearAll();
    }
  }

  fileInput.addEventListener("change", handleFilesChanged);

  mode.addEventListener("change", setModeUI);
  keepRatio.addEventListener("change", () => {
    syncOtherSide(widthInput.value ? "w" : "h");
    updateEstimation();
  });

  widthInput.addEventListener("input", () => { syncOtherSide("w"); updateEstimation(); });
  heightInput.addEventListener("input", () => { syncOtherSide("h"); updateEstimation(); });
  percentInput.addEventListener("input", updateEstimation);

  clearBtn.addEventListener("click", clearAll);

  // Init
  setModeUI();
  updateEstimation();
