from django.urls import path
from . import views

app_name = "convert"

urlpatterns = [
    # 옛날 기본 진입용 URL (있어도 되고, 나중에 지워도 됨)
    path("file-convert/", views.file_converter, name="file_converter"),

    # from → to 조합으로 들어오는 동적 URL
    # 예: /convert/png_to_pdf/file_convert/
    path("<str:from_fmt>_to_<str:to_fmt>/file_convert/", views.file_converter, name="file_converter_fmt"),

    # SEO / 랜딩 페이지들
    path("png-to-pdf/", views.landing_png_to_pdf, name="landing_png_to_pdf"),
    path("jpg-to-pdf/", views.landing_jpg_to_pdf, name="landing_jpg_to_pdf"),
    path("pdf-to-jpg/", views.landing_pdf_to_jpg, name="landing_pdf_to_jpg"),
    path("docx-to-pdf/", views.landing_docx_to_pdf, name="landing_docx_to_pdf"),
]
