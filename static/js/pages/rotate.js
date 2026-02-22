// --- CSRF helper (Django cookie) ---
  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
  }
  const csrftoken = getCookie('csrftoken');

  const fileInput = document.getElementById("rotFile");
  const previewImg = document.getElementById("rotPreview");
  const empty = document.getElementById("rotEmpty");
  const meta = document.getElementById("rotMeta");

  const loading = document.getElementById("rotLoading");
  const resetBtn = document.getElementById("rotReset");
  const downloadBtn = document.getElementById("rotDownloadBtn");

  const actionButtons = Array.from(document.querySelectorAll("[data-action]"));

  let originalFile = null;      // File object
  let currentBlob = null;       // Blob (latest processed image)
  let currentObjectUrl = null;  // preview url for currentBlob or original

  function revokePreviewUrl() {
    if (currentObjectUrl) {
      URL.revokeObjectURL(currentObjectUrl);
      currentObjectUrl = null;
    }
  }

  function setPreviewFromBlob(blob) {
    revokePreviewUrl();
    currentObjectUrl = URL.createObjectURL(blob);
    previewImg.src = currentObjectUrl;
    empty.style.display = "none";
  }

  function setPreviewFromFile(file) {
    revokePreviewUrl();
    currentObjectUrl = URL.createObjectURL(file);
    previewImg.src = currentObjectUrl;
    empty.style.display = "none";
  }

  function setEnabled(enabled) {
    actionButtons.forEach(btn => btn.disabled = !enabled);
    resetBtn.disabled = !enabled;
    downloadBtn.disabled = !enabled;
  }

  async function applyAction(action) {
    if (!originalFile) return;

    // Send either the latest processed blob or the original file
    const source = currentBlob ? new File([currentBlob], originalFile.name, { type: currentBlob.type || originalFile.type }) : originalFile;

    const fd = new FormData();
    fd.append("file", source);
    fd.append("action", action);

    loading.style.display = "flex";
    setEnabled(false);

    try {
      const resp = await fetch(window.location.href, {
        method: "POST",
        headers: { "X-CSRFToken": csrftoken },
        body: fd
      });

      if (!resp.ok) throw new Error(resp.status);

      const blob = await resp.blob();
      currentBlob = blob;
      setPreviewFromBlob(blob);
      meta.textContent = `Applied: ${action}`;
    } catch (err) {
      console.error(err);
      alert("Apply failed. Check server logs.");
      meta.textContent = "Failed ❌";
    } finally {
      loading.style.display = "none";
      setEnabled(true);
    }
  }

  fileInput.addEventListener("change", () => {
    currentBlob = null;

    if (!fileInput.files || fileInput.files.length === 0) {
      originalFile = null;
      meta.textContent = "No image selected";
      empty.style.display = "grid";
      setEnabled(false);
      return;
    }

    originalFile = fileInput.files[0];
    setPreviewFromFile(originalFile);

    meta.textContent = `Loaded: ${originalFile.name} (${Math.round(originalFile.size / 1024)} KB)`;
    setEnabled(true);
  });

  actionButtons.forEach(btn => {
    btn.addEventListener("click", () => applyAction(btn.dataset.action));
  });

  resetBtn.addEventListener("click", () => {
    if (!originalFile) return;
    currentBlob = null;
    setPreviewFromFile(originalFile);
    meta.textContent = "Reset to original";
  });

  downloadBtn.addEventListener("click", async () => {
    if (!originalFile) return;

    // If user never applied anything, download original as-is
    const blobToDownload = currentBlob || originalFile;
    const base = originalFile.name.replace(/\.[^/.]+$/, "");
    const ext = originalFile.name.includes(".") ? originalFile.name.split(".").pop() : "png";

    const a = document.createElement("a");
    const url = URL.createObjectURL(blobToDownload);
    a.href = url;
    a.download = currentBlob ? `${base}_edited.${ext}` : originalFile.name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  });

  // Start disabled
  setEnabled(false);
