// --- CSRF helper (Django cookie) ---
  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
  }
  const csrftoken = getCookie('csrftoken');

  const fileInput = document.getElementById("cropFile");
  const img = document.getElementById("cropPreview");
  const empty = document.getElementById("cropEmpty");
  const meta = document.getElementById("cropMeta");

  const resetBtn = document.getElementById("cropReset");
  const downloadBtn = document.getElementById("cropDownloadBtn");
  const loading = document.getElementById("cropLoading");

  let cropper = null;
  let imgUrl = null;

  function destroyCropper() {
    if (cropper) {
      cropper.destroy();
      cropper = null;
    }
  }

  function updateMeta(prefix = "Crop") {
    if (!cropper) return;
    const d = cropper.getData(true);
    meta.textContent = `${prefix}: x=${Math.round(d.x)}, y=${Math.round(d.y)}, w=${Math.round(d.width)}, h=${Math.round(d.height)}`;
  }

  fileInput.addEventListener("change", () => {
    destroyCropper();
    if (imgUrl) URL.revokeObjectURL(imgUrl);
    imgUrl = null;

    if (!fileInput.files || fileInput.files.length === 0) {
      empty.style.display = "grid";
      meta.textContent = "No image selected";
      resetBtn.disabled = true;
      downloadBtn.disabled = true;
      return;
    }

    const f = fileInput.files[0];
    imgUrl = URL.createObjectURL(f);

    img.onload = () => {
      empty.style.display = "none";

      destroyCropper();
      cropper = new Cropper(img, {
        viewMode: 1,
        autoCropArea: 0.8,
        responsive: true,
        background: false,
        dragMode: "move",
        ready() {
          meta.textContent = `Loaded: ${f.name} (${Math.round(f.size / 1024)} KB)`;
        },
        cropend() { updateMeta("Crop"); },
        zoom() { updateMeta("Crop"); }
      });

      resetBtn.disabled = false;
      downloadBtn.disabled = false;
    };

    img.onerror = () => {
      empty.style.display = "grid";
      meta.textContent = "Failed to preview this image format. Try PNG/JPG.";
      resetBtn.disabled = true;
      downloadBtn.disabled = true;
      destroyCropper();
    };

    img.src = imgUrl;
  });

  resetBtn.addEventListener("click", () => {
    if (!cropper) return;
    cropper.reset();
    updateMeta("Reset");
  });

  downloadBtn.addEventListener("click", async () => {
    if (!cropper || !fileInput.files || fileInput.files.length === 0) return;

    const f = fileInput.files[0];
    const d = cropper.getData(true);

    const fd = new FormData();
    fd.append("file", f);
    fd.append("x", Math.round(d.x));
    fd.append("y", Math.round(d.y));
    fd.append("w", Math.round(d.width));
    fd.append("h", Math.round(d.height));

    loading.style.display = "flex";
    downloadBtn.disabled = true;

    try {
      const resp = await fetch(window.location.href, {
        method: "POST",
        headers: { "X-CSRFToken": csrftoken },
        body: fd
      });

      if (!resp.ok) throw new Error(resp.status);

      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);

      const base = f.name.replace(/\.[^/.]+$/, "");
      const a = document.createElement("a");
      a.href = url;
      a.download = `${base}_cropped.png`;
      document.body.appendChild(a);
      a.click();
      a.remove();

      URL.revokeObjectURL(url);
      meta.textContent = "Downloaded ✅";
    } catch (err) {
      console.error(err);
      meta.textContent = "Failed ❌";
      alert("Crop failed. Check server logs.");
    } finally {
      loading.style.display = "none";
      downloadBtn.disabled = false;
    }
  });
