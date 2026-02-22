// static/js/pages/bg_remove.js
(() => {
  const ALLOWED_MIME = new Set(["image/png", "image/jpeg"]);
  const $ = (id) => document.getElementById(id);

  function showError(msg) {
    const box = $("errorBox");
    box.textContent = msg;
    box.classList.remove("d-none");
  }

  function clearError() {
    const box = $("errorBox");
    box.textContent = "";
    box.classList.add("d-none");
  }

  function setLoading(on) {
    $("submitBtn").disabled = on;
    $("btnSpinner").classList.toggle("d-none", !on);
    $("btnText").textContent = on ? "Processing..." : "Remove Background";
    $("statusText").textContent = on ? "Processing..." : "Idle";
    $("overlay").style.display = on ? "flex" : "none";
  }

  function resetPreview() {
    $("originalImg").style.display = "none";
    $("resultImg").style.display = "none";
    $("originalPlaceholder").style.display = "block";
    $("resultPlaceholder").style.display = "block";
    $("downloadBtn").classList.add("disabled");
    $("downloadBtn").href = "#";
  }

  function getFiles() {
    return Array.from($("fileInput").files || []);
  }

  function validate(files) {
    if (files.length === 0) return "Please upload at least one image.";
    if (files.some(f => !ALLOWED_MIME.has(f.type))) {
      return "Only JPG/PNG images are supported.";
    }
    return null;
  }

  function getCSRF() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  document.addEventListener("DOMContentLoaded", () => {
    const input = $("fileInput");
    const form = $("bgRemoveForm");

    resetPreview();

    // ✅ 파일 선택 → 원본 preview
    input.addEventListener("change", () => {
      clearError();
      resetPreview();

      const files = getFiles();
      const err = validate(files);
      if (err) {
        showError(err);
        input.value = "";
        return;
      }

      if (files.length === 1) {
        const url = URL.createObjectURL(files[0]);
        $("originalImg").src = url;
        $("originalImg").style.display = "block";
        $("originalPlaceholder").style.display = "none";
      }
    });

    // ✅ Clear 버튼 (submit 아님!)
    $("clearBtn").addEventListener("click", () => {
      input.value = "";
      clearError();
      resetPreview();
    });

    // ✅ Submit
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      clearError();

      const files = getFiles();
      const err = validate(files);
      if (err) {
        showError(err);
        return;
      }

      setLoading(true);

      try {
        const fd = new FormData(form);

        const res = await fetch(window.location.pathname, {
          method: "POST",
          headers: { "X-CSRFToken": getCSRF() },
          body: fd,
        });

        if (!res.ok) throw new Error("Server error");

        const type = res.headers.get("content-type") || "";

        // ZIP (multiple files)
        if (type.includes("zip")) {
          const blob = await res.blob();
          const a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          a.download = "ezkito_bg_removed.zip";
          a.click();
          return;
        }

        // PNG result
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);

        $("resultImg").src = url;
        $("resultImg").style.display = "block";
        $("resultPlaceholder").style.display = "none";

        const dl = $("downloadBtn");
        dl.href = url;
        dl.classList.remove("disabled");

      } catch (err) {
        showError(err.message || "Failed to process image.");
      } finally {
        setLoading(false);
      }
    });
  });
})();
