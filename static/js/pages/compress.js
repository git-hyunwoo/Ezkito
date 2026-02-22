// static/js/pages/compress.js
(() => {
  function $(id) {
    return document.getElementById(id);
  }

  function humanSize(bytes) {
    const units = ["B", "KB", "MB", "GB"];
    let v = bytes;
    let i = 0;
    while (v >= 1024 && i < units.length - 1) {
      v /= 1024;
      i += 1;
    }
    return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
  }

  function setQualityUI(q) {
    const labelEl = $("qualityLabel");
    const rangeEl = $("qualityRange");
    const numberEl = $("qualityNumber");
    const hiddenEl = $("qualityInput");

    const qq = Math.max(1, Math.min(95, parseInt(q, 10) || 75));

    rangeEl.value = String(qq);
    numberEl.value = String(qq);
    hiddenEl.value = String(qq);

    if (qq >= 85) {
      labelEl.textContent = "High quality";
      labelEl.className = "badge text-bg-success";
    } else if (qq >= 60) {
      labelEl.textContent = "Balanced";
      labelEl.className = "badge text-bg-primary";
    } else {
      labelEl.textContent = "Smaller size";
      labelEl.className = "badge text-bg-warning";
    }
  }

  function rebuildFileInput(filesArray) {
    const dt = new DataTransfer();
    filesArray.forEach((f) => dt.items.add(f));
    $("fileInput").files = dt.files;
  }

  function getFiles() {
    return Array.from($("fileInput").files || []);
  }

  function renderFileList() {
    const listEl = $("fileList");
    const hintEl = $("emptyFilesHint");
    const files = getFiles();

    listEl.innerHTML = "";
    if (files.length === 0) {
      hintEl.classList.remove("d-none");
      listEl.appendChild(hintEl);
      return;
    }

    hintEl.classList.add("d-none");
    listEl.appendChild(hintEl);

    const wrap = document.createElement("div");
    wrap.className = "d-flex flex-wrap";

    files.forEach((f, idx) => {
      const chip = document.createElement("div");
      chip.className = "file-chip";

      const name = document.createElement("span");
      name.className = "name";
      name.textContent = `${f.name} (${humanSize(f.size)})`;

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn btn-sm btn-link text-danger p-0";
      btn.textContent = "✕";
      btn.title = "Remove";
      btn.addEventListener("click", () => {
        const next = getFiles().filter((_, i) => i !== idx);
        rebuildFileInput(next);
        renderFileList();
      });

      chip.appendChild(name);
      chip.appendChild(btn);
      wrap.appendChild(chip);
    });

    listEl.appendChild(wrap);
  }

  document.addEventListener("DOMContentLoaded", () => {
    const dropzone = $("dropzone");
    const input = $("fileInput");

    // ===== Quality =====
    $("qualityRange").addEventListener("input", (e) => setQualityUI(e.target.value));
    $("qualityNumber").addEventListener("input", (e) => setQualityUI(e.target.value));
    setQualityUI(75);

    // ===== File select =====
    dropzone.addEventListener("click", () => input.click());

    input.addEventListener("change", () => {
      renderFileList();
    });

    // ===== Drag & Drop =====
    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });

    dropzone.addEventListener("dragleave", () => {
      dropzone.classList.remove("dragover");
    });

    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");

      const dropped = Array.from(e.dataTransfer.files || []).filter((f) =>
        /image\//i.test(f.type)
      );

      if (dropped.length === 0) return;

      const current = getFiles();
      rebuildFileInput(current.concat(dropped));
      renderFileList();
    });

    // ===== Clear =====
    $("clearFilesBtn").addEventListener("click", () => {
      rebuildFileInput([]);
      renderFileList();
    });

    // ===== Submit UX (핵심 수정 포인트) =====
    $("compressForm").addEventListener("submit", (e) => {
      const files = getFiles();
      if (files.length === 0) {
        e.preventDefault();
        alert("Please choose at least one image.");
        return;
      }

      const btn = $("submitBtn");
      const spinner = $("loadingSpinner");
      const text = $("submitText");

      // 로딩 UI ON
      btn.disabled = true;
      spinner.classList.remove("d-none");
      text.textContent = "Compressing...";

      // ✅ 중요:
      // Django FileResponse 다운로드는 페이지 전환이 없어서
      // 로딩 상태가 영구히 남을 수 있음 → 타이머로 강제 원복
      window.setTimeout(() => {
        btn.disabled = false;
        spinner.classList.add("d-none");
        text.textContent = "Compress";
      }, 3000);
    });

    renderFileList();
  });
})();
