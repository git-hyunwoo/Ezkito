from django.urls import path
from . import views

app_name = "imagetools"

urlpatterns = [
    path("", views.home, name="home"),

    path("resize/", views.resize, name="resize"),
    path("bg-remove/", views.bg_remove, name="bg_remove"),
    path("bg-color/", views.bg_color, name="bg_color"),
    path("compress/", views.compress, name="compress"),

    path("crop/", views.crop, name="crop"),
    path("rotate/", views.rotate, name="rotate"),
]
