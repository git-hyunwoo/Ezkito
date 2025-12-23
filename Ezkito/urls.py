"""
URL configuration for Ezkito project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

"""
[urls.py] file is the first step of making every functions of this project

app explanation
    1. Ezkito
        - Ezkito is the root app of this whole project
        - every single move or functions start from here 
    2. core
        - core is the app represents main page
    3. convert
        - convert is the app represents do functions for converting files
          such as image, text, pdf, video, etc files
    4. imagetools
        - imagetools is the app for editing image files such as resizing, removing background,
          applying background colors,  file compressions
"""

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path("convert/", include("convert.urls")),
    # ✅ imagetools (namespace 등록 핵심)
    path("image/", include(("imagetools.urls", "imagetools"), namespace="imagetools")),
]
