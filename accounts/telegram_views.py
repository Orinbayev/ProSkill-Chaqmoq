from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.http import JsonResponse
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
    # MUHIM: update_fields — aks holda o'qituvchi uchun post_save signal (handle_rate_change)
    # barcha davomatlarni qayta hisoblab, minglab query hosil qiladi (94s N+1 bug).
    user.save(update_fields=["reset_code", "reset_code_expire_at", "reset_code_used"])

    
    return render(request, "accounts/connect_telegram.html", {
        "code": code,
        "bot_username": settings.TELEGRAM_BOT_USERNAME
    })


@login_required
def telegram_link_status(request):
    """Sahifa polling qiladi: botда kod kiritilса (reset_code_used=True) → 'linked': true.
    Sayt shu javobni ko'rib avtomatik profil bo'limiga qaytadi."""
    from accounts.models import User
    u = (
        User.objects
        .only("id", "reset_code_used", "is_telegram_linked")
        .get(id=request.user.id)
    )
    linked = bool(u.reset_code_used and u.is_telegram_linked)
    return JsonResponse({"linked": linked})
