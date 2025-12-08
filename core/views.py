from django.shortcuts import render


def home(request):
    """
    Ezkito 메인 홈 화면
    """
    return render(request, "core/home.html")


