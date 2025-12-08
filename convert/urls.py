from django.urls import path
from . import views

app_name = "convert"

urlpatterns = [
    path("file-convert/", views.file_converter, name="file_converter"),
]
