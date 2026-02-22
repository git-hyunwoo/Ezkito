// Allowed pairs on frontend (UX only).
    // MUST stay in sync with ALLOWED_CONVERSIONS in views.py.
    const allowedPairs = new Set([
        // Image ↔ Image
        "png->jpg", "png->jpeg",
        "jpg->png", "jpg->jpeg",
        "jpeg->png", "jpeg->jpg",

        // Image → PDF
        "png->pdf", "jpg->pdf", "jpeg->pdf",

        // Document → PDF
        "docx->pdf", "pptx->pdf", "xlsx->pdf", "txt->pdf",

        // PDF → Image
        "pdf->png", "pdf->jpg", "pdf->jpeg",

        // Video → Audio
        "mp4->mp3", "mp4->wav",
        "mov->mp3", "avi->mp3", "mkv->mp3",

        // Audio → Video
        "mp3->mp4", "wav->mp4", "m4a->mp4", "aac->mp4", "ogg->mp4",
    ]);

    const imageFormats = new Set(["png", "jpg", "jpeg"]);

    const fromSelect = document.getElementById("fromFormat");
    const toSelect = document.getElementById("toFormat");
    const pdfModeRow = document.getElementById("pdfModeRow");

    function updatePdfModeVisibility() {
        const from = fromSelect.value;
        const to = toSelect.value;

        if (imageFormats.has(from) && to === "pdf") {
            pdfModeRow.style.display = "flex";  // bootstrap row uses flex
        } else {
            pdfModeRow.style.display = "none";
        }
    }

    function filterToOptions() {
        const from = fromSelect.value;

        for (const option of toSelect.options) {
            if (option.value === "") {
                option.hidden = false;
                continue;
            }

            const key = `${from}->${option.value}`;
            const isAllowed = allowedPairs.has(key);

            option.hidden = !isAllowed;
        }

        // Select first visible option or placeholder
        let firstVisible = null;
        for (const option of toSelect.options) {
            if (!option.hidden && option.value !== "") {
                firstVisible = option;
                break;
            }
        }

        if (firstVisible) {
            firstVisible.selected = true;
        } else {
            const placeholder = toSelect.querySelector('option[value=""]');
            if (placeholder) placeholder.selected = true;
        }

        // After filtering, update PDF mode visibility
        updatePdfModeVisibility();
    }

    fromSelect.addEventListener("change", filterToOptions);
    toSelect.addEventListener("change", updatePdfModeVisibility);

    document.addEventListener("DOMContentLoaded", function () {
        filterToOptions();          // apply allowedPairs filtering
        updatePdfModeVisibility();  // correct initial pdf mode visibility
    });
