const PRESETS = [
    "#ffffff", "#000000", "#f8f9fa", "#e9ecef", "#dee2e6",
    "#ff0000", "#ff6b6b", "#ffa94d", "#ffd43b", "#69db7c",
    "#38d9a9", "#3bc9db", "#4dabf7", "#5c7cfa", "#845ef7",
    "#be4bdb", "#f06595", "#06595f", "#adb5bd", "#495057",
  ];

  const presetGrid = document.getElementById("presetGrid");
  const hexInput = document.getElementById("hexInput");
  const hexBadge = document.getElementById("hexBadge");
  const colorDot = document.getElementById("colorDot");
  const colorHidden = document.getElementById("colorHidden");
  const pickrSwatch = document.getElementById("pickrSwatch");
  const pickrBtn = document.getElementById("pickrBtn");

  const filesInput = document.getElementById("bgFiles");
  const statusEl = document.getElementById("status");

  const origImg = document.getElementById("origImg");
  const origEmpty = document.getElementById("origEmpty");
  const resultImg = document.getElementById("resultImg");
  const resultEmpty = document.getElementById("resultEmpty");
  const loading = document.getElementById("loading");
  const resultWrap = document.getElementById("resultWrap");

  let origUrl = null;

  function normalizeHex(v){
    if (!v) return null;
    v = v.trim();
    if (!v.startsWith("#")) v = "#" + v;
    if (!/^#[0-9a-fA-F]{6}$/.test(v)) return null;
    return v.toLowerCase();
  }

  function setSelectedColor(hex){
    const n = normalizeHex(hex);
    if (!n) return;

    hexInput.value = n;
    hexBadge.textContent = n;
    colorDot.style.background = n;
    pickrSwatch.style.background = n;
    colorHidden.value = n;

    document.querySelectorAll(".swatch").forEach(el => {
      el.classList.toggle("selected", el.dataset.hex === n);
    });

    // set background color in preview wrap
    resultWrap.style.backgroundColor = n;

    if (filesInput.files && filesInput.files.length === 1) {
      renderClientPreview(filesInput.files[0], n);
    }
  }

  function buildSwatches(){
    presetGrid.innerHTML = "";
    PRESETS.forEach(hex => {
      const d = document.createElement("div");
      d.className = "swatch";
      d.style.background = hex;
      d.dataset.hex = hex.toLowerCase();
      d.title = hex;
      d.addEventListener("click", () => setSelectedColor(hex));
      presetGrid.appendChild(d);
    });
  }

  async function renderClientPreview(file, bgHex){
    loading.style.display = "flex";
    statusEl.textContent = "Rendering preview…";

    const img = new Image();
    img.decoding = "async";
    const url = URL.createObjectURL(file);
    img.src = url;

    await new Promise((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () => reject(new Error("Failed to load image"));
    });

    const maxW = 1200;
    const scale = Math.min(1, maxW / img.width);
    const w = Math.max(1, Math.round(img.width * scale));
    const h = Math.max(1, Math.round(img.height * scale));

    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;

    const ctx = canvas.getContext("2d");
    ctx.fillStyle = bgHex;
    ctx.fillRect(0, 0, w, h);
    ctx.drawImage(img, 0, 0, w, h);

    const dataUrl = canvas.toDataURL("image/png");

    URL.revokeObjectURL(url);

    resultImg.src = dataUrl;
    resultImg.style.display = "block";
    resultEmpty.style.display = "none";

    loading.style.display = "none";
    statusEl.textContent = "Ready";
  }

  filesInput.addEventListener("change", () => {
    if (origUrl) URL.revokeObjectURL(origUrl);
    origUrl = null;

    origImg.style.display = "none";
    resultImg.style.display = "none";
    origEmpty.style.display = "grid";
    resultEmpty.style.display = "grid";

    if (!filesInput.files || filesInput.files.length === 0) {
      statusEl.textContent = "Waiting for file…";
      return;
    }

    origUrl = URL.createObjectURL(filesInput.files[0]);
    origImg.src = origUrl;
    origImg.style.display = "block";
    origEmpty.style.display = "none";

    if (filesInput.files.length === 1) {
      statusEl.textContent = "Preview enabled";
      setSelectedColor(colorHidden.value);
    } else {
      statusEl.textContent = `${filesInput.files.length} files selected (ZIP export). Preview shows the first file only.`;
      resultWrap.style.backgroundColor = colorHidden.value;
      resultEmpty.style.display = "grid";
    }
  });

  hexInput.addEventListener("input", (e) => {
    const n = normalizeHex(e.target.value);
    if (n) {
      setSelectedColor(n);
      pickr.setColor(n, true);
    }
  });

  // Build palette
  buildSwatches();

  // Pickr init (advanced picker)
  const pickr = Pickr.create({
    el: '#pickrBtn',
    theme: 'classic',
    default: '#06595f',
    useAsButton: true,
    lockOpacity: true,
    swatches: PRESETS,
    components: {
      preview: true,
      opacity: false,
      hue: true,
      interaction: {
        hex: true,
        rgba: true,
        input: true,
        save: true,
        clear: false
      }
    }
  });

  pickr.on('change', (color) => {
    const hex = color.toHEXA().toString().toLowerCase();
    setSelectedColor(hex);
  });

  pickr.on('save', (color) => {
    const hex = color.toHEXA().toString().toLowerCase();
    setSelectedColor(hex);
    pickr.hide();
  });

  // init default
  setSelectedColor("#06595f");
