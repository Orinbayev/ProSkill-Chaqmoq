# core/middleware.py
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse, NoReverseMatch
from accounts.models import Center


def _safe_reverse(*names: str, default: str = "/") -> str:
    """
    Bir nechta url name'larni ketma-ket reverse qilib ko‘radi.
    Birortasi ishlasa -> o‘sha url
    Hech biri ishlamasa -> default
    """
    for name in names:
        try:
            return reverse(name)
        except NoReverseMatch:
            continue
        except Exception:
            continue
    return default


class TenantMiddleware:
    """
    - request.center ni session.active_center_id bo‘yicha o‘rnatadi
    - superadmin active center tanlamagan bo‘lsa -> center pickerga yuboradi
    - redirect loop bo‘lmasin (allowed paths)
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # ✅ URL'larni xavfsiz topamiz (bir nechta name sinab ko‘ramiz)
        p_center_picker = _safe_reverse("accounts:center_picker", default="/hisob/center-picker/")
        p_center_switch = _safe_reverse("accounts:center_switch", default="/hisob/center-switch/")

        # logout ba'zan "logout", ba'zan "accounts:logout" bo'lishi mumkin
        p_logout = _safe_reverse("logout", "accounts:logout", default="/logout/")

        # login ba'zan "login", ba'zan "accounts:login"
        p_login = _safe_reverse("login", "accounts:login", default="/accounts/login/")

        p_home = "/"
        p_superadmin = _safe_reverse("accounts:superadmin_dashboard", default="/hisob/superadmin/")

        allowed_prefixes = (
            p_center_picker,
            p_center_switch,
            p_logout,
            p_login,
            p_home,
            p_superadmin,
            "/hisob/api/",
            "/hisob/centers/",
            "/admin/",
            "/static/",
            "/media/",
        )

        path = request.path or "/"

        # default
        request.center = None

        if request.user.is_authenticated:
            # ✅ oddiy userlar: center userdan olinadi
            if not request.user.is_superuser:
                user_center = getattr(request.user, "center", None)
                
                # ✅ MUAMMO 2: Markazning status va limitini tekshirish
                if user_center:
                    # ✅ Billing sahifalarini topamiz
                    p_billing_plans = _safe_reverse("billing:plans", default="/billing/plans/")
                    p_billing_blocked = _safe_reverse("billing:blocked", default="/billing/blocked/")
                    p_billing_order = _safe_reverse("billing:order_create", default="/billing/order/create/")
                    
                    billing_allowed = (
                        p_billing_plans,
                        p_billing_blocked,
                        p_billing_order,
                        "/billing/",
                        p_logout,
                        p_login,
                        "/static/",
                        "/media/",
                    )
                    
                    # ✅ MUAMMO 1: Pul tugasa avtomatik BLOCKED qilish
                    from django.utils import timezone
                    if user_center.expires_at and timezone.now() >= user_center.expires_at:
                        if user_center.status == Center.STATUS_ACTIVE:
                            # Avtomatik block qilamiz (bir marta)
                            user_center.status = Center.STATUS_BLOCKED
                            user_center.save(update_fields=['status'])
                    
                    # Status tekshirish
                    if user_center.status == Center.STATUS_BLOCKED:
                        # ✅ Faqat billing sahifalariga ruxsat beramiz
                        if not path.startswith(billing_allowed):
                            messages.warning(request, f"⚠️ Markazingiz bloklangan. To'lovni amalga oshiring.")
                            return redirect(p_billing_plans)
                        
                        # Blocked center'ni request'ga qo'yamiz (billing sahifalarida kerak bo'ladi)
                        request.center = user_center
                    else:
                        # Student limit tekshirish (faqat student role uchun)
                        if request.user.role == 'student':
                            from education.models import Enrollment
                            current_students = Enrollment.objects.filter(
                                group__center=user_center,
                                student__is_archived=False
                            ).values('student').distinct().count()
                            
                            if user_center.max_students > 0 and current_students >= user_center.max_students:
                                # Agar current user allaqachon ro'yxatda bo'lsa ruxsat beramiz
                                is_enrolled = Enrollment.objects.filter(
                                    group__center=user_center,
                                    student=request.user
                                ).exists()
                                
                                if not is_enrolled:
                                    messages.error(request, f"❌ Markaz o'quvchilar limiti ({user_center.max_students}) to'lgan.")
                                    return redirect(p_logout)
                        
                        request.center = user_center

            else:
                # ✅ superadmin: center sessiondan olinadi
                active_center_id = request.session.get("active_center_id")
                if active_center_id:
                    center = Center.objects.filter(id=active_center_id).first()
                    
                    # ✅ MUAMMO 1: Superadmin rejimida ham avtomatik expiration tekshirish
                    if center:
                        from django.utils import timezone
                        if center.expires_at and timezone.now() >= center.expires_at:
                            if center.status == Center.STATUS_ACTIVE:
                                center.status = Center.STATUS_BLOCKED
                                center.save(update_fields=['status'])
                    
                    # ✅ MUAMMO 2: Superadmin uchun ham status tekshirish
                    if center and center.status != Center.STATUS_ACTIVE:
                        messages.warning(request, f"⚠️ Tanlangan markaz faol emas (Status: {center.status})")
                        if not path.startswith(allowed_prefixes):
                            return redirect(p_center_picker)
                    else:
                        request.center = center
                else:
                    # ✅ active center yo'q -> faqat allow-list bo'lmasa pickerga yuboramiz
                    if not path.startswith(allowed_prefixes):
                        messages.info(request, "Davom etish uchun avval Active Center tanlang.")
                        return redirect(p_center_picker)

        return self.get_response(request)
