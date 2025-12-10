import io
import os
import tempfile
import zipfile
import subprocess
from typing import List

from django.shortcuts import render
from django.http import FileResponse

from PIL import Image  # pip install pillow


# Allowed conversion pairs (메뉴와 반드시 맞춰야 하는 셋)
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
}

IMAGE_FORMATS = {"png", "jpg", "jpeg"}
DOC_FORMATS = {"docx", "pptx", "xlsx"}


def file_converter(request, from_fmt=None, to_fmt=None):
    """
    Main file converter view.

    Handles:
        - Required field validation (from/to/formats/files)
        - Image → PDF (merge / separate)
        - Image → Image (png/jpg/jpeg)
        - DOCX/PPTX/XLSX → PDF (via LibreOffice)
        - TXT → PDF (via reportlab)
        - PDF → Image (via pdf2image)

    from_fmt, to_fmt:
        /convert/png_to_pdf/file_convert/ 처럼 path 파라미터로 들어온 기본 포맷 값.
    """

    error_message = None
    success_message = None

    # -----------------------------
    # 1) 포맷 기본값 결정 (GET / path)
    # -----------------------------
    if request.method == "POST":
        from_format = request.POST.get("from_format", "").lower()
        to_format = request.POST.get("to_format", "").lower()
        pdf_mode = request.POST.get("pdf_mode", "merge")
    else:
        # path 파라미터가 우선, 없으면 쿼리스트링 (?from=png&to=pdf)
        from_format = (from_fmt or request.GET.get("from", "")).lower()
        to_format = (to_fmt or request.GET.get("to", "")).lower()
        pdf_mode = request.GET.get("pdf_mode", "merge") or "merge"

    # -----------------------------
    # 2) POST 요청(실제 변환 처리)
    # -----------------------------
    if request.method == "POST":
        files = request.FILES.getlist("files")

        # 1. Required field validation for from/to
        if not from_format or not to_format:
            if not from_format and not to_format:
                error_message = "Please select both source and target formats."
            elif not from_format:
                error_message = "Please select a source format."
            else:
                error_message = "Please select a target format."

            return _render(request, error_message, success_message, from_format, to_format, pdf_mode)

        # 2. Validate allowed combination
        if (from_format, to_format) not in ALLOWED_CONVERSIONS:
            error_message = f"Conversion from {from_format.upper()} to {to_format.upper()} is not supported."
            return _render(request, error_message, success_message, from_format, to_format, pdf_mode)

        # 3. Validate files
        if not files:
            error_message = "Please upload at least one file."
            return _render(request, error_message, success_message, from_format, to_format, pdf_mode)

        # 4. Validate file extensions
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

        # ---------------------------
        # 5. Image → PDF
        # ---------------------------
        if from_format in IMAGE_FORMATS and to_format == "pdf":
            try:
                if pdf_mode == "separate":
                    if len(files) == 1:
                        # Single image → one PDF
                        pdf_buffer = _single_image_to_pdf(files[0])
                        filename = f"{base_name}_ezkito.pdf"
                        return FileResponse(
                            pdf_buffer,
                            as_attachment=True,
                            filename=filename,
                            content_type="application/pdf",
                        )
                    else:
                        # Multiple images → multiple PDFs inside ZIP
                        zip_buffer = _convert_images_to_separate_pdfs_zip(files)
                        filename = f"{base_name}_separated_ezkito.zip"
                        return FileResponse(
                            zip_buffer,
                            as_attachment=True,
                            filename=filename,
                            content_type="application/zip",
                        )
                else:
                    # Merge mode (default)
                    pdf_buffer = _merge_images_into_single_pdf(files)
                    if len(files) == 1:
                        filename = f"{base_name}_ezkito.pdf"
                    else:
                        filename = f"{base_name}_merged_ezkito.pdf"

                    return FileResponse(
                        pdf_buffer,
                        as_attachment=True,
                        filename=filename,
                        content_type="application/pdf",
                    )

            except Exception as e:
                error_message = f"An error occurred during image to PDF conversion: {e}"
                return _render(request, error_message, success_message, from_format, to_format, pdf_mode)

        # ---------------------------
        # 6. Image → Image (PNG/JPG/JPEG)
        # ---------------------------
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

        # ---------------------------
        # 7. DOCX / PPTX / XLSX → PDF (LibreOffice)
        # ---------------------------
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

        # ---------------------------
        # 8. TXT → PDF (reportlab)
        # ---------------------------
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

        # ---------------------------
        # 9. PDF → Image (pdf2image)
        # ---------------------------
        if from_format == "pdf" and to_format in IMAGE_FORMATS:
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

        # ---------------------------
        # 10. Fallback (should not normally reach here)
        # ---------------------------
        success_message = (
            f"Validation passed, but conversion for {from_format.upper()} → "
            f"{to_format.upper()} is not implemented yet."
        )

    # GET 요청이거나, 검증 실패 후 다시 그리는 경우
    return _render(request, error_message, success_message, from_format, to_format, pdf_mode)


def _render(request, error, success, from_fmt, to_fmt, pdf_mode):
    return render(
        request,
        "convert/file_converter.html",
        {
            "error_message": error,
            "success_message": success,
            "from_format": from_fmt,
            "to_format": to_fmt,
            "pdf_mode": pdf_mode,
        },
    )


# =========================
# Image helpers
# =========================

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


def _merge_images_into_single_pdf(files):
    """Merge multiple uploaded images into a single multi-page PDF."""
    images = [_open_image_from_uploaded(f) for f in files]

    if not images:
        raise ValueError("No valid images provided.")

    buffer = io.BytesIO()
    first, *rest = images

    if rest:
        first.save(buffer, format="PDF", save_all=True, append_images=rest)
    else:
        first.save(buffer, format="PDF")

    buffer.seek(0)
    return buffer


def _convert_images_to_separate_pdfs_zip(files):
    """
    Convert each uploaded image to its own one-page PDF,
    then package all PDFs into an in-memory ZIP file.
    """
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for f in files:
            img = _open_image_from_uploaded(f)
            pdf_bytes = io.BytesIO()
            img.save(pdf_bytes, format="PDF")
            pdf_bytes.seek(0)

            base_name = f.name.rsplit(".", 1)[0]
            pdf_filename = f"{base_name}_ezkito.pdf"

            zip_file.writestr(pdf_filename, pdf_bytes.read())

    zip_buffer.seek(0)
    return zip_buffer


def _convert_single_image_to_image(f, to_ext: str):
    """
    Convert a single image to another image format (png/jpg/jpeg).
    Returns (buffer, filename, mime_type).
    """
    img = _open_image_from_uploaded(f)

    buffer = io.BytesIO()
    format_map = {
        "jpg": "JPEG",
        "jpeg": "JPEG",
        "png": "PNG",
    }
    pil_format = format_map.get(to_ext, to_ext.upper())
    img.save(buffer, format=pil_format)
    buffer.seek(0)

    base_name = f.name.rsplit(".", 1)[0]
    filename = f"{base_name}_ezkito.{to_ext}"

    if to_ext in ("jpg", "jpeg"):
        mime = "image/jpeg"
    else:
        mime = f"image/{to_ext}"

    return buffer, filename, mime


def _convert_images_to_images_zip(files, to_ext: str, base_prefix: str):
    """
    Convert multiple images to another image format and return a ZIP.
    """
    zip_buffer = io.BytesIO()

    format_map = {
        "jpg": "JPEG",
        "jpeg": "JPEG",
        "png": "PNG",
    }
    pil_format = format_map.get(to_ext, to_ext.upper())

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for f in files:
            img = _open_image_from_uploaded(f)
            img_buffer = io.BytesIO()
            img.save(img_buffer, format=pil_format)
            img_buffer.seek(0)

            base_name = f.name.rsplit(".", 1)[0]
            out_name = f"{base_name}_ezkito.{to_ext}"
            zip_file.writestr(out_name, img_buffer.read())

    zip_buffer.seek(0)
    zip_name = f"{base_prefix}_converted_ezkito.zip"
    return zip_buffer, zip_name


# =========================
# Office (DOCX/PPTX/XLSX) → PDF (LibreOffice)
# =========================

def _office_file_to_pdf_buffer(uploaded_file):
    """
    Use LibreOffice in headless mode to convert an office file to PDF.
    Requires LibreOffice installed and available in PATH.
    """
    try:
        import pathlib
    except ImportError:
        raise RuntimeError("pathlib is required for office conversion.")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, uploaded_file.name)

        # Save uploaded file to temp path
        with open(input_path, "wb") as dst:
            for chunk in uploaded_file.chunks():
                dst.write(chunk)

        # Run LibreOffice
        try:
            subprocess.run(
                [
                    "libreoffice",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    tmpdir,
                    input_path,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            raise RuntimeError(
                "LibreOffice is required for DOCX/PPTX/XLSX conversion but was not found on the system."
            )
        except subprocess.CalledProcessError:
            raise RuntimeError("LibreOffice failed to convert the document to PDF.")

        pdf_name = pathlib.Path(input_path).with_suffix(".pdf").name
        pdf_path = os.path.join(tmpdir, pdf_name)

        if not os.path.exists(pdf_path):
            raise RuntimeError("Converted PDF file not found after LibreOffice conversion.")

        with open(pdf_path, "rb") as pf:
            data = pf.read()

    buffer = io.BytesIO(data)
    buffer.seek(0)
    return buffer


def _office_single_to_pdf(uploaded_file):
    buffer = _office_file_to_pdf_buffer(uploaded_file)
    base_name = uploaded_file.name.rsplit(".", 1)[0]
    filename = f"{base_name}_ezkito.pdf"
    return buffer, filename


def _office_files_to_pdf_zip(files, base_prefix: str):
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for f in files:
            pdf_buffer = _office_file_to_pdf_buffer(f)
            pdf_buffer.seek(0)
            base_name = f.name.rsplit(".", 1)[0]
            pdf_filename = f"{base_name}_ezkito.pdf"
            zip_file.writestr(pdf_filename, pdf_buffer.read())

    zip_buffer.seek(0)
    zip_name = f"{base_prefix}_converted_ezkito.zip"
    return zip_buffer, zip_name


# =========================
# TXT → PDF (reportlab)
# =========================

def _txt_file_to_pdf_buffer(uploaded_file):
    """
    Convert a TXT file to a single-page PDF using reportlab.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError:
        raise RuntimeError(
            "reportlab is required for TXT → PDF conversion. "
            "Install it with 'pip install reportlab'."
        )

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    text_obj = c.beginText(40, height - 40)

    content = uploaded_file.read().decode("utf-8", errors="ignore").splitlines()
    for line in content:
        text_obj.textLine(line)

    c.drawText(text_obj)
    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer


def _txt_single_to_pdf(uploaded_file):
    buffer = _txt_file_to_pdf_buffer(uploaded_file)
    base_name = uploaded_file.name.rsplit(".", 1)[0]
    filename = f"{base_name}_ezkito.pdf"
    return buffer, filename


def _txt_files_to_pdf_zip(files, base_prefix: str):
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for f in files:
            pdf_buffer = _txt_file_to_pdf_buffer(f)
            pdf_buffer.seek(0)
            base_name = f.name.rsplit(".", 1)[0]
            pdf_filename = f"{base_name}_ezkito.pdf"
            zip_file.writestr(pdf_filename, pdf_buffer.read())

    zip_buffer.seek(0)
    zip_name = f"{base_prefix}_converted_ezkito.zip"
    return zip_buffer, zip_name


# =========================
# PDF → Image (pdf2image)
# =========================

def _pdfs_to_images_zip(files, to_ext: str, base_prefix: str):
    """
    Convert one or more PDFs to images (one image per page),
    and return a ZIP file containing all generated images.
    """
    try:
        from pdf2image import convert_from_bytes
    except ImportError:
        raise RuntimeError(
            "pdf2image is required for PDF → image conversion. "
            "Install it with 'pip install pdf2image' and make sure poppler is installed."
        )

    zip_buffer = io.BytesIO()

    format_map = {
        "jpg": "JPEG",
        "jpeg": "JPEG",
        "png": "PNG",
    }
    pil_format = format_map.get(to_ext, to_ext.upper())

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for f in files:
            pdf_bytes = f.read()
            images = convert_from_bytes(pdf_bytes)

            base_name = f.name.rsplit(".", 1)[0]
            for page_num, img in enumerate(images, start=1):
                img_buffer = io.BytesIO()
                img.save(img_buffer, format=pil_format)
                img_buffer.seek(0)

                out_name = f"{base_name}_page{page_num}_ezkito.{to_ext}"
                zip_file.writestr(out_name, img_buffer.read())

    zip_buffer.seek(0)
    zip_name = f"{base_prefix}_converted_ezkito.zip"
    return zip_buffer, zip_name


# =========================
# Landing pages (SEO / Marketing)
# =========================

def _render_landing(request, title, description, from_default, to_default):
    """
    공용 랜딩 템플릿 렌더링 헬퍼.
    from_default / to_default 는 랜딩에서 변환 페이지로 넘어갈 때 기본값으로 사용.
    """
    return render(
        request,
        "convert/landing_base.html",
        {
            "title": title,
            "description": description,
            "from_default": from_default,
            "to_default": to_default,
        },
    )


def landing_png_to_pdf(request):
    return _render_landing(
        request,
        title="Convert PNG to PDF Online — Free & Fast | EzKito",
        description="Convert PNG images to PDF instantly with EzKito. Free, fast, and no signup required.",
        from_default="png",
        to_default="pdf",
    )


def landing_jpg_to_pdf(request):
    return _render_landing(
        request,
        title="Convert JPG to PDF Online — Easy & Free | EzKito",
        description="Turn JPG images into high-quality PDF files in seconds. 100% free and privacy-friendly.",
        from_default="jpg",
        to_default="pdf",
    )


def landing_pdf_to_jpg(request):
    return _render_landing(
        request,
        title="Convert PDF to JPG — Extract Images Easily | EzKito",
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
