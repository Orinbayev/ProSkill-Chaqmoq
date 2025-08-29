from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def guruhlar(request):
    return render(request, "education/guruhlar.html", {})

@login_required
def men_guruhlarim(request):
    return render(request, "education/men_guruhlarim.html", {})
