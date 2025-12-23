import io
import zipfile
from django.http import FileResponse, HttpRequest, HttpResponse
from django.shortcuts import render
from PIL import Image


# -------------------------
# Common helpers
# -------------------------
def _render(request: HttpRequest, template: str, **ctx) -> HttpResponse:
    base = {"error_message": None}
    base.update(ctx)
    return render(request, template, base)


def _open_image(uploaded) -> Image.Image:
    return Image.open(uploaded)


def _safe_format(img: Image.Image) -> str:
    fmt = (img.format or "PNG").upper()
    if fmt == "JPG":
        fmt = "JPEG"
    return fmt


def _ext_from_format(fmt: str) -> str:
    return "jpg" if fmt.upper() == "JPEG" else fmt.lower()


def _mime_from_ext(ext: str) -> str:
    if ext in ("jpg", "jpeg"):
        return "image/jpeg"
    if ext == "png":
        return "image/png"
    if ext == "webp":
        return "image/webp"
    return f"image/{ext}"


# -------------------------
# Pages
# -------------------------
def home(request: HttpRequest) -> HttpResponse:
    # templates/imagetools/home.html
    return _render(request, "imagetools/home.html")


# -------------------------
# 1) Resize
# -------------------------
def resize(request: HttpRequest) -> HttpResponse:
    """
    Resize images by:
      - width/height
      - percent
    Multiple files => ZIP
    """
    if request.method == "POST":
        files = request.FILES.getlist("files")
        mode = request.POST.get("mode", "wh")  # wh | percent
        keep_ratio = request.POST.get("keep_ratio") == "on"

        width = (request.POST.get("width") or "").strip()
        height = (request.POST.get("height") or "").strip()
        percent = (request.POST.get("percent") or "").strip()

        if not files:
            return _render(request, "imagetools/resize.html", error_message="Please upload at least one file.")

        try:
            if mode == "percent":
                p = int(percent)
                if p <= 0:
                    raise ValueError
            else:
                w = int(width) if width else 0
                h = int(height) if height else 0
                if w <= 0 and h <= 0:
                    raise ValueError
        except Exception:
            return _render(request, "imagetools/resize.html", error_message="Invalid resize values. Please check numbers.")

        def resize_one(up):
            img = _open_image(up)

            if mode == "percent":
                new_w = max(1, int(img.size[0] * p / 100))
                new_h = max(1, int(img.size[1] * p / 100))
            else:
                if keep_ratio:
                    if w > 0 and h <= 0:
                        new_w = w
                        new_h = max(1, int(img.size[1] * (w / img.size[0])))
                    elif h > 0 and w <= 0:
                        new_h = h
                        new_w = max(1, int(img.size[0] * (h / img.size[1])))
                    else:
                        new_w, new_h = w, h
                else:
                    new_w = w if w > 0 else img.size[0]
                    new_h = h if h > 0 else img.size[1]

            out_img = img.resize((new_w, new_h), Image.LANCZOS)

            fmt = _safe_format(img)
            if fmt == "JPEG":
                out_img = out_img.convert("RGB")

            buf = io.BytesIO()
            out_img.save(buf, format=fmt)
            buf.seek(0)

            base = up.name.rsplit(".", 1)[0]
            ext = _ext_from_format(fmt)
            filename = f"{base}_resized.{ext}"
            return buf.getvalue(), filename, _mime_from_ext(ext)

        if len(files) == 1:
            data, filename, mime = resize_one(files[0])
            return FileResponse(io.BytesIO(data), as_attachment=True, filename=filename, content_type=mime)

        zbuf = io.BytesIO()
        with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as zf:
            for up in files:
                data, filename, _ = resize_one(up)
                zf.writestr(filename, data)

        zbuf.seek(0)
        return FileResponse(zbuf, as_attachment=True, filename="resized_images.zip", content_type="application/zip")

    return _render(request, "imagetools/resize.html")


# -------------------------
# 2) Background Remove (optional: rembg)
# -------------------------
def bg_remove(request: HttpRequest) -> HttpResponse:
    """
    Remove background using rembg.
    Output: transparent PNG
    Multiple => ZIP
    """
    if request.method == "POST":
        files = request.FILES.getlist("files")
        if not files:
            return _render(request, "imagetools/bg_remove.html", error_message="Please upload at least one file.")

        try:
            from rembg import remove
        except Exception:
            return _render(
                request,
                "imagetools/bg_remove.html",
                error_message="This feature requires rembg. Install with: pip install rembg"
            )

        def remove_one(up):
            raw = up.read()
            out_bytes = remove(raw)  # PNG bytes with alpha
            base = up.name.rsplit(".", 1)[0]
            return out_bytes, f"{base}_nobg.png"

        if len(files) == 1:
            data, fname = remove_one(files[0])
            return FileResponse(io.BytesIO(data), as_attachment=True, filename=fname, content_type="image/png")

        zbuf = io.BytesIO()
        with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as zf:
            for up in files:
                data, fname = remove_one(up)
                zf.writestr(fname, data)

        zbuf.seek(0)
        return FileResponse(zbuf, as_attachment=True, filename="nobg_images.zip", content_type="application/zip")

    return _render(request, "imagetools/bg_remove.html")


# -------------------------
# 3) Add Background Color
# -------------------------
def bg_color(request: HttpRequest) -> HttpResponse:
    """
    Add solid background behind transparent images.
    Output: PNG or JPG
    Multiple => ZIP
    """
    if request.method == "POST":
        files = request.FILES.getlist("files")
        color = (request.POST.get("color") or "#ffffff").strip()
        out_fmt = (request.POST.get("out_format") or "png").lower()  # png|jpg

        if not files:
            return _render(request, "imagetools/bg_color.html", error_message="Please upload at least one file.")
        if out_fmt not in ("png", "jpg"):
            return _render(request, "imagetools/bg_color.html", error_message="Output format must be png or jpg.")

        try:
            c = color.lstrip("#")
            r = int(c[0:2], 16)
            g = int(c[2:4], 16)
            b = int(c[4:6], 16)
        except Exception:
            return _render(request, "imagetools/bg_color.html", error_message="Invalid HEX color. Example: #ffffff")

        def apply(img: Image.Image) -> Image.Image:
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            bg = Image.new("RGBA", img.size, (r, g, b, 255))
            bg.paste(img, (0, 0), img)
            return bg.convert("RGB") if out_fmt == "jpg" else bg

        def one(up):
            img = _open_image(up)
            out_img = apply(img)
            buf = io.BytesIO()
            if out_fmt == "jpg":
                out_img.save(buf, format="JPEG", quality=92, optimize=True)
                mime = "image/jpeg"
            else:
                out_img.save(buf, format="PNG", optimize=True)
                mime = "image/png"
            buf.seek(0)
            base = up.name.rsplit(".", 1)[0]
            return buf.getvalue(), f"{base}_bg.{out_fmt}", mime

        if len(files) == 1:
            data, fname, mime = one(files[0])
            return FileResponse(io.BytesIO(data), as_attachment=True, filename=fname, content_type=mime)

        zbuf = io.BytesIO()
        with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as zf:
            for up in files:
                data, fname, _ = one(up)
                zf.writestr(fname, data)

        zbuf.seek(0)
        return FileResponse(zbuf, as_attachment=True, filename="bg_color_images.zip", content_type="application/zip")

    return _render(request, "imagetools/bg_color.html")


# -------------------------
# 4) Compress
# -------------------------
def compress(request: HttpRequest) -> HttpResponse:
    """
    Compress images.
    JPEG uses quality (1~95)
    Others => saved as PNG optimize
    Multiple => ZIP
    """
    if request.method == "POST":
        files = request.FILES.getlist("files")
        quality = (request.POST.get("quality") or "75").strip()

        if not files:
            return _render(request, "imagetools/compress.html", error_message="Please upload at least one file.")

        try:
            q = int(quality)
            if q < 1 or q > 95:
                raise ValueError
        except Exception:
            return _render(request, "imagetools/compress.html", error_message="Quality must be a number between 1 and 95.")

        def one(up):
            img = _open_image(up)
            fmt = _safe_format(img)

            buf = io.BytesIO()
            if fmt == "JPEG":
                img = img.convert("RGB")
                img.save(buf, format="JPEG", quality=q, optimize=True)
                ext, mime = "jpg", "image/jpeg"
            else:
                if img.mode in ("RGBA", "LA"):
                    img = img.convert("RGBA")
                else:
                    img = img.convert("RGB")
                img.save(buf, format="PNG", optimize=True)
                ext, mime = "png", "image/png"

            buf.seek(0)
            base = up.name.rsplit(".", 1)[0]
            return buf.getvalue(), f"{base}_compressed.{ext}", mime

        if len(files) == 1:
            data, fname, mime = one(files[0])
            return FileResponse(io.BytesIO(data), as_attachment=True, filename=fname, content_type=mime)

        zbuf = io.BytesIO()
        with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as zf:
            for up in files:
                data, fname, _ = one(up)
                zf.writestr(fname, data)

        zbuf.seek(0)
        return FileResponse(zbuf, as_attachment=True, filename="compressed_images.zip", content_type="application/zip")

    return _render(request, "imagetools/compress.html")


# -------------------------
# 5) Crop (single file)
# -------------------------
def crop(request: HttpRequest) -> HttpResponse:
    """
    Crop a single image by x,y,w,h
    """
    if request.method == "POST":
        up = request.FILES.get("file")
        if not up:
            return _render(request, "imagetools/crop.html", error_message="Please upload a file.")

        try:
            x = int(request.POST.get("x", "0"))
            y = int(request.POST.get("y", "0"))
            w = int(request.POST.get("w", "0"))
            h = int(request.POST.get("h", "0"))
            if w <= 0 or h <= 0:
                raise ValueError
        except Exception:
            return _render(request, "imagetools/crop.html", error_message="Invalid crop values.")

        img = _open_image(up)

        left = max(0, x)
        top = max(0, y)
        right = min(img.size[0], x + w)
        bottom = min(img.size[1], y + h)

        if right <= left or bottom <= top:
            return _render(request, "imagetools/crop.html", error_message="Crop area is out of bounds.")

        out_img = img.crop((left, top, right, bottom))

        fmt = _safe_format(img)
        if fmt == "JPEG":
            out_img = out_img.convert("RGB")

        buf = io.BytesIO()
        out_img.save(buf, format=fmt)
        buf.seek(0)

        base = up.name.rsplit(".", 1)[0]
        ext = _ext_from_format(fmt)
        return FileResponse(buf, as_attachment=True, filename=f"{base}_cropped.{ext}", content_type=_mime_from_ext(ext))

    return _render(request, "imagetools/crop.html")


# -------------------------
# 6) Rotate / Flip (single file)
# -------------------------
def rotate(request: HttpRequest) -> HttpResponse:
    """
    Rotate/flip a single image.
    action:
      rotate90 / rotate180 / rotate270 / flipH / flipV
    """
    if request.method == "POST":
        up = request.FILES.get("file")
        action = request.POST.get("action", "rotate90")

        if not up:
            return _render(request, "imagetools/rotate.html", error_message="Please upload a file.")

        img = _open_image(up)

        if action == "rotate90":
            out_img = img.rotate(-90, expand=True)
        elif action == "rotate180":
            out_img = img.rotate(180, expand=True)
        elif action == "rotate270":
            out_img = img.rotate(-270, expand=True)
        elif action == "flipH":
            out_img = img.transpose(Image.FLIP_LEFT_RIGHT)
        elif action == "flipV":
            out_img = img.transpose(Image.FLIP_TOP_BOTTOM)
        else:
            return _render(request, "imagetools/rotate.html", error_message="Unknown action.")

        fmt = _safe_format(img)
        if fmt == "JPEG":
            out_img = out_img.convert("RGB")

        buf = io.BytesIO()
        out_img.save(buf, format=fmt)
        buf.seek(0)

        base = up.name.rsplit(".", 1)[0]
        ext = _ext_from_format(fmt)
        return FileResponse(buf, as_attachment=True, filename=f"{base}_{action}.{ext}", content_type=_mime_from_ext(ext))

    return _render(request, "imagetools/rotate.html")
