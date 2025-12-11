import io
import os
import tempfile
import zipfile
import subprocess
from typing import List, Tuple

from django.shortcuts import render
from django.http import FileResponse, HttpRequest, HttpResponse

from PIL import Image  # pip install pillow

# Optional libraries (install if needed)
try:
    from pdf2image import convert_from_bytes
except ImportError:
    convert_from_bytes = None

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
except ImportError:
    canvas = None
    A4 = None


# ============================================================
# Allowed conversion pairs (must match menu / frontend)
# ============================================================
ALLOWED_CONVERSIONS = {
    # Image ↔ Image
    ("png", "jpg"),
    ("png", "jpeg"),
    ("jpg", "png"),
    ("jpg", "jpeg"),
    ("jpeg", "png"),
    ("jpeg", "jpg"),

    # Image → PDF
    ("png", "pdf"),
    ("jpg", "pdf"),
    ("jpeg", "pdf"),

    # Document → PDF
    ("docx", "pdf"),
    ("pptx", "pdf"),
    ("xlsx", "pdf"),
    ("txt", "pdf"),

    # PDF → Image
    ("pdf", "png"),
    ("pdf", "jpg"),
    ("pdf", "jpeg"),

    # Video → Audio
    ("mp4", "mp3"),
    ("mp4", "wav"),
    ("mov", "mp3"),
    ("avi", "mp3"),
    ("mkv", "mp3"),

    # Audio → Video
    ("mp3", "mp4"),
    ("wav", "mp4"),
    ("m4a", "mp4"),
    ("aac", "mp4"),
    ("ogg", "mp4"),
}

IMAGE_FORMATS = {"png", "jpg", "jpeg"}
DOC_FORMATS = {"docx", "pptx", "xlsx"}
VIDEO_FORMATS = {"mp4", "mov", "avi", "mkv"}
AUDIO_FORMATS = {"mp3", "wav", "m4a", "aac", "ogg"}


# ============================================================
# Main converter view
# ============================================================
def file_converter(request: HttpRequest, from_fmt: str | None = None, to_fmt: str | None = None) -> HttpResponse:
    """
    Main file converter view.

    Handles:
        - Required field validation (from/to/formats/files)
        - Image → PDF (merge / separate)
        - Image → Image (png/jpg/jpeg)
        - DOCX/PPTX/XLSX → PDF (via LibreOffice)
        - TXT → PDF (via reportlab)
        - PDF → Image (via pdf2image)
        - Video → Audio (via ffmpeg)
        - Audio → Video (via ffmpeg + static background)
    """

    error_message = None
    success_message = None

    # -----------------------------
    # 1) Determine default formats
    # -----------------------------
    if request.method == "POST":
        from_format = request.POST.get("from_format", "").lower()
        to_format = request.POST.get("to_format", "").lower()
        pdf_mode = request.POST.get("pdf_mode", "merge")
    else:
        # path params have priority, then query string (?from=png&to=pdf)
        from_format = (from_fmt or request.GET.get("from", "")).lower()
        to_format = (to_fmt or request.GET.get("to", "")).lower()
        pdf_mode = request.GET.get("pdf_mode", "merge") or "merge"

    # -----------------------------
    # 2) POST: actual conversion
    # -----------------------------
    if request.method == "POST":
        files = request.FILES.getlist("files")

        # 2-1. Required from/to
        if not from_format or not to_format:
            if not from_format and not to_format:
                error_message = "Please select both source and target formats."
            elif not from_format:
                error_message = "Please select a source format."
            else:
                error_message = "Please select a target format."

            return _render(request, error_message, success_message, from_format, to_format, pdf_mode)

        # 2-2. Validate allowed combination
        if (from_format, to_format) not in ALLOWED_CONVERSIONS:
            error_message = f"Conversion from {from_format.upper()} to {to_format.upper()} is not supported."
            return _render(request, error_message, success_message, from_format, to_format, pdf_mode)

        # 2-3. Validate files
        if not files:
            error_message = "Please upload at least one file."
            return _render(request, error_message, success_message, from_format, to_format, pdf_mode)

        # 2-4. Validate file extensions (all uploaded must match from_format)
        invalid_files: List[str] = []
        for f in files:
            if "." not in f.name:
                invalid_files.append(f.name)
                continue
            ext = f.name.rsplit(".", 1)[-1].lower()
            if ext != from_format:
                invalid_files.append(f.name)

        if invalid_files:
            invalid_str = ", ".join(invalid_files)
            error_message = f"The following files do not match .{from_format}: {invalid_str}"
            return _render(request, error_message, success_message, from_format, to_format, pdf_mode)

        # Base name for output (first file)
        base_name = files[0].name.rsplit(".", 1)[0]

        # -------------------------------------------------
        # 5. Image → PDF
        # -------------------------------------------------
        if from_format in IMAGE_FORMATS and to_format == "pdf":
            try:
                if pdf_mode == "separate":
                    # 각각 PDF
                    if len(files) == 1:
                        pdf_buffer = _single_image_to_pdf(files[0])
                        filename = f"{base_name}_ezkito.pdf"
                        return FileResponse(
                            pdf_buffer,
                            as_attachment=True,
                            filename=filename,
                            content_type="application/pdf",
                        )
                    else:
                        # 여러 개 → 개별 PDF ZIP
                        zip_buffer = _convert_images_to_separate_pdfs_zip(files)
                        filename = f"{base_name}_separated_ezkito.zip"
                        return FileResponse(
                            zip_buffer,
                            as_attachment=True,
                            filename=filename,
                            content_type="application/zip",
                        )
                else:
                    # merge mode
                    pdf_buffer = _merge_images_into_single_pdf(files)
                    filename = f"{base_name}_merged_ezkito.pdf" if len(files) > 1 else f"{base_name}_ezkito.pdf"
                    return FileResponse(
                        pdf_buffer,
                        as_attachment=True,
                        filename=filename,
                        content_type="application/pdf",
                    )
            except Exception as e:
                error_message = f"An error occurred during image to PDF conversion: {e}"
                return _render(request, error_message, success_message, from_format, to_format, pdf_mode)

        # -------------------------------------------------
        # 6. Image → Image (PNG/JPG/JPEG)
        # -------------------------------------------------
        if from_format in IMAGE_FORMATS and to_format in IMAGE_FORMATS:
            try:
                if len(files) == 1:
                    img_buffer, out_name, mime = _convert_single_image_to_image(files[0], to_format)
                    return FileResponse(
                        img_buffer,
                        as_attachment=True,
                        filename=out_name,
                        content_type=mime,
                    )
                else:
                    zip_buffer, zip_name = _convert_images_to_images_zip(files, to_format, base_name)
                    return FileResponse(
                        zip_buffer,
                        as_attachment=True,
                        filename=zip_name,
                        content_type="application/zip",
                    )
            except Exception as e:
                error_message = f"An error occurred during image to image conversion: {e}"
                return _render(request, error_message, success_message, from_format, to_format, pdf_mode)

        # -------------------------------------------------
        # 7. Document → PDF (LibreOffice)
        # -------------------------------------------------
        if from_format in DOC_FORMATS and to_format == "pdf":
            try:
                if len(files) == 1:
                    pdf_buffer, filename = _office_single_to_pdf(files[0])
                    return FileResponse(
                        pdf_buffer,
                        as_attachment=True,
                        filename=filename,
                        content_type="application/pdf",
                    )
                else:
                    zip_buffer, zip_name = _office_files_to_pdf_zip(files, base_name)
                    return FileResponse(
                        zip_buffer,
                        as_attachment=True,
                        filename=zip_name,
                        content_type="application/zip",
                    )
            except Exception as e:
                error_message = f"An error occurred during document to PDF conversion: {e}"
                return _render(request, error_message, success_message, from_format, to_format, pdf_mode)

        # -------------------------------------------------
        # 8. TXT → PDF (reportlab)
        # -------------------------------------------------
        if from_format == "txt" and to_format == "pdf":
            try:
                if len(files) == 1:
                    pdf_buffer, filename = _txt_single_to_pdf(files[0])
                    return FileResponse(
                        pdf_buffer,
                        as_attachment=True,
                        filename=filename,
                        content_type="application/pdf",
                    )
                else:
                    zip_buffer, zip_name = _txt_files_to_pdf_zip(files, base_name)
                    return FileResponse(
                        zip_buffer,
                        as_attachment=True,
                        filename=zip_name,
                        content_type="application/zip",
                    )
            except Exception as e:
                error_message = f"An error occurred during TXT to PDF conversion: {e}"
                return _render(request, error_message, success_message, from_format, to_format, pdf_mode)

        # -------------------------------------------------
        # 9. PDF → Image (pdf2image)
        # -------------------------------------------------
        if from_format == "pdf" and to_format in IMAGE_FORMATS:
            if convert_from_bytes is None:
                error_message = "pdf2image is not installed. Please install it to use PDF to image conversion."
                return _render(request, error_message, success_message, from_format, to_format, pdf_mode)

            try:
                zip_buffer, zip_name = _pdfs_to_images_zip(files, to_format, base_name)
                return FileResponse(
                    zip_buffer,
                    as_attachment=True,
                    filename=zip_name,
                    content_type="application/zip",
                )
            except Exception as e:
                error_message = f"An error occurred during PDF to image conversion: {e}"
                return _render(request, error_message, success_message, from_format, to_format, pdf_mode)

        # -------------------------------------------------
        # 10. Video → Audio (ffmpeg)
        # -------------------------------------------------
        if from_format in VIDEO_FORMATS and to_format in AUDIO_FORMATS:
            try:
                return _handle_video_to_audio(request, files, from_format, to_format, base_name)
            except Exception as e:
                error_message = f"An error occurred during video to audio conversion: {e}"
                return _render(request, error_message, success_message, from_format, to_format, pdf_mode)

        # -------------------------------------------------
        # 11. Audio → Video (ffmpeg + static background)
        # -------------------------------------------------
        if from_format in AUDIO_FORMATS and to_format in VIDEO_FORMATS:
            try:
                return _handle_audio_to_video(request, files, from_format, to_format, base_name)
            except Exception as e:
                error_message = f"An error occurred during audio to video conversion: {e}"
                return _render(request, error_message, success_message, from_format, to_format, pdf_mode)

        # -------------------------------------------------
        # 12. Fallback (should not reach here)
        # -------------------------------------------------
        error_message = "This conversion path is not implemented yet."
        return _render(request, error_message, success_message, from_format, to_format, pdf_mode)

    # -----------------------------
    # 3) GET: just render form
    # -----------------------------
    return _render(request, error_message, success_message, from_format, to_format, pdf_mode)


# ============================================================
# Rendering helpers
# ============================================================
def _render(request, error_message, success_message, from_format, to_format, pdf_mode):
    context = {
        "error_message": error_message,
        "success_message": success_message,
        "from_format": from_format,
        "to_format": to_format,
        "pdf_mode": pdf_mode,
    }
    return render(request, "convert/file_converter.html", context)


def _render_landing(request, title: str, description: str, from_default: str, to_default: str):
    """
    Landing-page-style renderer that pre-selects from/to.
    """
    context = {
        "page_title": title,
        "page_description": description,
        "error_message": None,
        "success_message": None,
        "from_format": from_default,
        "to_format": to_default,
        "pdf_mode": "merge",
    }
    return render(request, "convert/file_converter.html", context)


# ============================================================
# Image helpers
# ============================================================
def _open_image_from_uploaded(f):
    """Open a Django UploadedFile as a Pillow Image in RGB mode."""
    img = Image.open(f)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def _single_image_to_pdf(f):
    """Convert a single uploaded image to a one-page PDF."""
    img = _open_image_from_uploaded(f)
    buffer = io.BytesIO()
    img.save(buffer, format="PDF")
    buffer.seek(0)
    return buffer


def _merge_images_into_single_pdf(files: List):
    """Merge multiple uploaded images into a single multi-page PDF."""
    images = []
    for f in files:
        img = _open_image_from_uploaded(f)
        images.append(img)

    if not images:
        raise ValueError("No images provided")

    buffer = io.BytesIO()
    first, *rest = images
    first.save(buffer, format="PDF", save_all=True, append_images=rest)
    buffer.seek(0)
    return buffer


def _convert_images_to_separate_pdfs_zip(files: List):
    """Each image -> its own PDF; all PDFs zipped."""
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            base = f.name.rsplit(".", 1)[0]
            pdf_buffer = _single_image_to_pdf(f)
            zf.writestr(f"{base}_ezkito.pdf", pdf_buffer.getvalue())
    mem_zip.seek(0)
    return mem_zip


def _convert_single_image_to_image(f, to_format: str) -> Tuple[io.BytesIO, str, str]:
    """Convert one image to another format."""
    img = _open_image_from_uploaded(f)
    buffer = io.BytesIO()
    img.save(buffer, format=to_format.upper())
    buffer.seek(0)

    base = f.name.rsplit(".", 1)[0]
    filename = f"{base}_ezkito.{to_format}"
    mime = f"image/{'jpeg' if to_format == 'jpg' else to_format}"
    return buffer, filename, mime


def _convert_images_to_images_zip(files: List, to_format: str, base_name: str):
    """Multiple images → multiple converted images inside ZIP."""
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            img = _open_image_from_uploaded(f)
            buffer = io.BytesIO()
            img.save(buffer, format=to_format.upper())
            buffer.seek(0)
            original_base = f.name.rsplit(".", 1)[0]
            out_name = f"{original_base}_ezkito.{to_format}"
            zf.writestr(out_name, buffer.getvalue())
    mem_zip.seek(0)
    zip_name = f"{base_name}_images_ezkito.zip"
    return mem_zip, zip_name


# ============================================================
# Office (DOCX/PPTX/XLSX) helpers – LibreOffice
# ============================================================
def _save_uploaded_to_temp(uploaded, suffix: str) -> str:
    """Save uploaded file to a temp path and return the path."""
    tmp_dir = tempfile.mkdtemp(prefix="ezkito_")
    path = os.path.join(tmp_dir, f"input{suffix}")
    with open(path, "wb") as f:
        for chunk in uploaded.chunks():
            f.write(chunk)
    return path


def _office_single_to_pdf(uploaded):
    """Convert a single DOCX/PPTX/XLSX file to PDF using LibreOffice."""
    if uploaded.name.lower().endswith(".docx"):
        suffix = ".docx"
    elif uploaded.name.lower().endswith(".pptx"):
        suffix = ".pptx"
    else:
        suffix = ".xlsx"

    in_path = _save_uploaded_to_temp(uploaded, suffix)
    out_dir = os.path.dirname(in_path)

    cmd = [
        "soffice",
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        out_dir,
        in_path,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    base = os.path.splitext(os.path.basename(uploaded.name))[0]
    out_path = os.path.join(out_dir, f"input.pdf")

    with open(out_path, "rb") as f:
        data = f.read()
    buffer = io.BytesIO(data)
    buffer.seek(0)

    filename = f"{base}_ezkito.pdf"
    return buffer, filename


def _office_files_to_pdf_zip(files: List, base_name: str):
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for uploaded in files:
            pdf_buffer, filename = _office_single_to_pdf(uploaded)
            zf.writestr(filename, pdf_buffer.getvalue())
    mem_zip.seek(0)
    zip_name = f"{base_name}_office_ezkito.zip"
    return mem_zip, zip_name


# ============================================================
# TXT → PDF helpers (reportlab)
# ============================================================
def _txt_single_to_pdf(uploaded):
    if canvas is None or A4 is None:
        raise RuntimeError("reportlab is not installed.")

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    text_obj = c.beginText(40, height - 50)
    for line in uploaded.read().decode("utf-8", errors="ignore").splitlines():
        text_obj.textLine(line)
    c.drawText(text_obj)
    c.showPage()
    c.save()

    buffer.seek(0)
    base = uploaded.name.rsplit(".", 1)[0]
    filename = f"{base}_ezkito.pdf"
    return buffer, filename


def _txt_files_to_pdf_zip(files: List, base_name: str):
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for uploaded in files:
            pdf_buffer, filename = _txt_single_to_pdf(uploaded)
            zf.writestr(filename, pdf_buffer.getvalue())
    mem_zip.seek(0)
    zip_name = f"{base_name}_txt_ezkito.zip"
    return mem_zip, zip_name


# ============================================================
# PDF → Image helpers (pdf2image)
# ============================================================
def _pdfs_to_images_zip(files: List, to_format: str, base_name: str):
    if convert_from_bytes is None:
        raise RuntimeError("pdf2image is not installed.")

    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for uploaded in files:
            pdf_bytes = uploaded.read()
            pages = convert_from_bytes(pdf_bytes)
            doc_base = uploaded.name.rsplit(".", 1)[0]
            for idx, page in enumerate(pages, start=1):
                img_buffer = io.BytesIO()
                page.save(img_buffer, format=to_format.upper())
                img_buffer.seek(0)
                out_name = f"{doc_base}_page{idx}_ezkito.{to_format}"
                zf.writestr(out_name, img_buffer.getvalue())

    mem_zip.seek(0)
    zip_name = f"{base_name}_images_ezkito.zip"
    return mem_zip, zip_name


# ============================================================
# Video / Audio helpers (ffmpeg)
# ============================================================
def _check_ffmpeg_available():
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except Exception:
        raise RuntimeError("ffmpeg is not installed or not found in PATH.")


def _handle_video_to_audio(request, files: List, from_format: str, to_format: str, base_name: str) -> HttpResponse:
    _check_ffmpeg_available()

    # Single file → single audio
    if len(files) == 1:
        uploaded = files[0]
        with tempfile.TemporaryDirectory(prefix="ezkito_va_") as tmpdir:
            in_path = os.path.join(tmpdir, uploaded.name)
            with open(in_path, "wb") as f:
                for chunk in uploaded.chunks():
                    f.write(chunk)

            out_base = uploaded.name.rsplit(".", 1)[0]
            out_name = f"{out_base}_ezkito.{to_format}"
            out_path = os.path.join(tmpdir, out_name)

            cmd = ["ffmpeg", "-y", "-i", in_path, out_path]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            with open(out_path, "rb") as f:
                data = f.read()
            buffer = io.BytesIO(data)
            buffer.seek(0)

            if to_format == "mp3":
                mime = "audio/mpeg"
            elif to_format == "wav":
                mime = "audio/wav"
            else:
                mime = "audio/octet-stream"

            return FileResponse(
                buffer,
                as_attachment=True,
                filename=out_name,
                content_type=mime,
            )

    # Multiple files → ZIP
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf, tempfile.TemporaryDirectory(prefix="ezkito_va_zip_") as tmpdir:
        for uploaded in files:
            in_path = os.path.join(tmpdir, uploaded.name)
            with open(in_path, "wb") as f:
                for chunk in uploaded.chunks():
                    f.write(chunk)

            out_base = uploaded.name.rsplit(".", 1)[0]
            out_name = f"{out_base}_ezkito.{to_format}"
            out_path = os.path.join(tmpdir, out_name)

            cmd = ["ffmpeg", "-y", "-i", in_path, out_path]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            with open(out_path, "rb") as f:
                zf.writestr(out_name, f.read())

    mem_zip.seek(0)
    zip_name = f"{base_name}_audio_ezkito.zip"
    return FileResponse(
        mem_zip,
        as_attachment=True,
        filename=zip_name,
        content_type="application/zip",
    )


def _handle_audio_to_video(request, files: List, from_format: str, to_format: str, base_name: str) -> HttpResponse:
    _check_ffmpeg_available()

    # we will create a simple solid-color background image (1280x720)
    def create_bg_image(path: str):
        img = Image.new("RGB", (1280, 720), (0, 123, 255))  # EzKito blue-ish
        img.save(path, format="PNG")

    if len(files) == 1:
        uploaded = files[0]
        with tempfile.TemporaryDirectory(prefix="ezkito_av_") as tmpdir:
            bg_path = os.path.join(tmpdir, "bg.png")
            create_bg_image(bg_path)

            in_path = os.path.join(tmpdir, uploaded.name)
            with open(in_path, "wb") as f:
                for chunk in uploaded.chunks():
                    f.write(chunk)

            out_base = uploaded.name.rsplit(".", 1)[0]
            out_name = f"{out_base}_ezkito.{to_format}"
            out_path = os.path.join(tmpdir, out_name)

            cmd = [
                "ffmpeg",
                "-y",
                "-loop", "1",
                "-i", bg_path,
                "-i", in_path,
                "-shortest",
                "-c:v", "libx264",
                "-c:a", "aac",
                "-pix_fmt", "yuv420p",
                out_path,
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            with open(out_path, "rb") as f:
                data = f.read()
            buffer = io.BytesIO(data)
            buffer.seek(0)

            mime = "video/mp4"  # currently only mp4 as target
            return FileResponse(
                buffer,
                as_attachment=True,
                filename=out_name,
                content_type=mime,
            )

    # Multiple audios → multiple MP4s in a ZIP
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf, tempfile.TemporaryDirectory(prefix="ezkito_av_zip_") as tmpdir:
        bg_path = os.path.join(tmpdir, "bg.png")
        create_bg_image(bg_path)

        for uploaded in files:
            in_path = os.path.join(tmpdir, uploaded.name)
            with open(in_path, "wb") as f:
                for chunk in uploaded.chunks():
                    f.write(chunk)

            out_base = uploaded.name.rsplit(".", 1)[0]
            out_name = f"{out_base}_ezkito.{to_format}"
            out_path = os.path.join(tmpdir, out_name)

            cmd = [
                "ffmpeg",
                "-y",
                "-loop", "1",
                "-i", bg_path,
                "-i", in_path,
                "-shortest",
                "-c:v", "libx264",
                "-c:a", "aac",
                "-pix_fmt", "yuv420p",
                out_path,
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            with open(out_path, "rb") as f:
                zf.writestr(out_name, f.read())

    mem_zip.seek(0)
    zip_name = f"{base_name}_video_ezkito.zip"
    return FileResponse(
        mem_zip,
        as_attachment=True,
        filename=zip_name,
        content_type="application/zip",
    )


# ============================================================
# Landing pages (SEO-friendly URLs)
# ============================================================
def landing_png_to_pdf(request):
    return _render_landing(
        request,
        title="Convert PNG to PDF — Online Image to PDF | EzKito",
        description="Convert PNG images to PDF instantly. Fast, secure, and easy to use.",
        from_default="png",
        to_default="pdf",
    )


def landing_jpg_to_pdf(request):
    return _render_landing(
        request,
        title="Convert JPG to PDF — Online Image to PDF | EzKito",
        description="Convert JPG images to PDF instantly. Fast, secure, and easy to use.",
        from_default="jpg",
        to_default="pdf",
    )


def landing_pdf_to_jpg(request):
    return _render_landing(
        request,
        title="Convert PDF to JPG — Extract Images from PDF | EzKito",
        description="Extract JPG images from any PDF document instantly. Fast, secure, and no account required.",
        from_default="pdf",
        to_default="jpg",
    )


def landing_docx_to_pdf(request):
    return _render_landing(
        request,
        title="Convert DOCX to PDF — Word to PDF Online | EzKito",
        description="Convert Word documents (DOCX) to PDF with one click. Free, reliable, and accurate formatting.",
        from_default="docx",
        to_default="pdf",
    )
