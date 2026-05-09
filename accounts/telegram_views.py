from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
import secrets
import string
from datetime import timedelta

@login_required
def connect_telegram(request):
    user = request.user
    
    # Generate 6-digit code for linking
    code = ''.join(secrets.choice(string.digits) for _ in range(6))
    user.reset_code = code
    user.reset_code_expire_at = timezone.now() + timedelta(minutes=10)
    user.reset_code_used = False
    user.save()

    
    return render(request, "accounts/connect_telegram.html", {
        "code": code,
        "bot_username": settings.TELEGRAM_BOT_USERNAME
    })
