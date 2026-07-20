import json
import logging
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.db.models import Sum, Count, Q, Avg
from django.db import models
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from accounts.models import Center, User, DirectorCenterAccess
from education.models import Group, Payment, Attendance, TeacherIncome
from billing.models import SubscriptionPlan, CenterSubscription, PromoCode, PlanFeature, SubscriptionOrder
from billing.services import (
    apply_plan_to_center,
    invalidate_center_limit_cache,
    resolve_center_student_limit,
    superadmin_apply_subscription,
    sync_center_from_active_subscription,
)
from core.center_features import CENTER_UI_FEATURE_DEFAULTS
from billing.models import CenterSubscription

logger = logging.getLogger(__name__)

def is_superadmin(user):
    return user.is_authenticated and user.is_superuser

@login_required
@require_http_methods(["GET"])
def center_stats_api(request, center_id):
    if not is_superadmin(request.user):
        return HttpResponseForbidden("Faqat superadmin uchun")

    center = get_object_or_404(Center, pk=center_id)
    today = timezone.localdate()
    
    try:
        # --- 1. KPI Cards ---
        students_qs = User.objects.filter(role='student', center=center, is_archived=False)
        total_students = students_qs.count()
        active_students = students_qs.filter(is_active=True).count()
        
        last_30_days = today - timedelta(days=30)
        new_students_30d = students_qs.filter(date_joined__date__gte=last_30_days).count()
        
        groups_qs = Group.objects.filter(center=center)
        total_groups = groups_qs.count()
        active_groups = total_groups 

        teachers_count = User.objects.filter(role='teacher', center=center).count()

        payments_qs = Payment.objects.filter(center=center)
        total_revenue = payments_qs.aggregate(s=Sum('summa'))['s'] or 0
        
        first_day_this_month = today.replace(day=1)
        monthly_revenue = payments_qs.filter(paid_date__gte=first_day_this_month).aggregate(s=Sum('summa'))['s'] or 0
        
        avg_payment = payments_qs.aggregate(a=Avg('summa'))['a'] or 0
        
        total_debt = 0 
        
        # Calculate Expenses (Teacher salaries + Other expenses)
        teacher_expenses = TeacherIncome.objects.filter(group__center=center).aggregate(s=Sum('amount'))['s'] or 0
        
        # ✅ Fetch from Expense model
        from store.models import Expense
        other_expenses = Expense.objects.filter(center=center).aggregate(s=Sum('summa'))['s'] or 0
        
        total_expenses = teacher_expenses + other_expenses
        net_profit = total_revenue - total_expenses
        
        attendances_30d = Attendance.objects.filter(center=center, date__gte=last_30_days)
        present_count = attendances_30d.filter(present=True).count()
        total_att_count = attendances_30d.count()
        attendance_rate = (present_count / total_att_count * 100) if total_att_count else 0

        kpi = {
            "total_students": total_students,
            "active_students": active_students,
            "new_students_30d": new_students_30d,
            "total_groups": total_groups,
            "active_groups": active_groups,
            "total_teachers": teachers_count,
            "monthly_revenue": monthly_revenue,
            "total_revenue": total_revenue,
            "total_expenses": total_expenses,
            "net_profit": net_profit,
            "total_debt": total_debt,
            "avg_payment": int(avg_payment),
            "attendance_rate": round(attendance_rate, 1)
        }

        # --- 2. Charts ---
        revenue_chart = []
        for i in range(5, -1, -1):
            target_year = today.year
            target_month = today.month - i
            while target_month <= 0:
                target_month += 12
                target_year -= 1
            d = today.replace(year=target_year, month=target_month, day=1)

            y, m = d.year, d.month
            month_start = d
            if m == 12:
                next_month = d.replace(year=y+1, month=1, day=1)
            else:
                next_month = d.replace(month=m+1, day=1)
                
            rev = payments_qs.filter(paid_date__gte=month_start, paid_date__lt=next_month).aggregate(s=Sum('summa'))['s'] or 0
            revenue_chart.append({
                "label": month_start.strftime("%b %Y"),
                "value": rev
            })

        students_chart = []
        for i in range(5, -1, -1):
            target_year = today.year
            target_month = today.month - i
            while target_month <= 0:
                target_month += 12
                target_year -= 1
            d = today.replace(year=target_year, month=target_month, day=1)

            y, m = d.year, d.month
            month_start = d
            if m == 12:
                next_month = d.replace(year=y+1, month=1, day=1)
            else:
                next_month = d.replace(month=m+1, day=1)
                
            from django.utils.timezone import make_aware
            import datetime
            
            # Convert date to aware datetime for field comparison
            ms_aware = make_aware(datetime.datetime.combine(month_start, datetime.time.min))
            nm_aware = make_aware(datetime.datetime.combine(next_month, datetime.time.min))
            
            cnt = students_qs.filter(date_joined__gte=ms_aware, date_joined__lt=nm_aware).count()
            students_chart.append({
                "label": month_start.strftime("%b %Y"),
                "value": cnt
            })

        return JsonResponse({
            "kpi": kpi,
            "charts": {
                "revenue": revenue_chart,
                "students": students_chart
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@login_required
@require_http_methods(["GET"])
def center_students_api(request, center_id):
    if not is_superadmin(request.user):
        return HttpResponseForbidden("Faqat superadmin uchun")
    
    center = get_object_or_404(Center, pk=center_id)
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '')
    
    qs = User.objects.filter(role='student', center=center, is_archived=False).select_related('center')
    
    if search:
        qs = qs.filter(Q(ism__icontains=search) | Q(familya__icontains=search) | Q(telefon1__icontains=search))
    
    if status == 'active':
        qs = qs.filter(is_active=True)
    elif status == 'blocked':
        qs = qs.filter(is_active=False)
        
    qs = qs[:100]
    
    data = []
    for u in qs:
        # We manually query groups for each student due to simple API structure
        groups = u.enrollments.all().values_list('group__nom', flat=True)
        last_pay = Payment.objects.filter(student=u).order_by('-paid_date').first()
        
        data.append({
            "id": u.id,
            "full_name": u.get_full_name(),
            "phone": u.telefon1,
            "groups": list(groups),
            "status": "Active" if u.is_active else "Blocked",
            "balance": 0, 
            "last_payment": last_pay.paid_date.strftime("%Y-%m-%d") if last_pay else "-",
            "joined_at": u.date_joined.strftime("%Y-%m-%d"),
        })
        
    return JsonResponse({"students": data})
    
@login_required
@require_http_methods(["GET"])
def center_groups_api(request, center_id):
    if not is_superadmin(request.user):
        return HttpResponseForbidden("Faqat superadmin uchun")
    
    center = get_object_or_404(Center, pk=center_id)
    qs = Group.objects.filter(center=center).select_related('oqituvchi', 'category_obj')
    
    data = []
    for g in qs:
        data.append({
            "id": g.id,
            "name": g.nom,
            "teacher": g.oqituvchi.get_full_name() if g.oqituvchi else "-",
            "category": g.category_obj.name if g.category_obj else "-",
            "students_count": g.enrollments.filter(is_active=True).count(),
            "status": "Faol",
        })
        
    return JsonResponse({"groups": data})

@login_required
@require_http_methods(["GET"])
def center_payments_api(request, center_id):
    if not is_superadmin(request.user):
        return HttpResponseForbidden("Faqat superadmin uchun")
    
    center = get_object_or_404(Center, pk=center_id)
    qs = Payment.objects.filter(center=center).select_related('student').order_by('-paid_date')[:100]
    
    data = []
    for p in qs:
        data.append({
            "id": p.id,
            "student_name": p.student.get_full_name() if p.student else "Noma'lum",
            "amount": p.summa,
            "date": p.paid_date.strftime("%Y-%m-%d"),
            "method": p.get_pay_type_display() if hasattr(p, 'get_pay_type_display') else "Naqd"
        })
        
    return JsonResponse({"payments": data})

import logging
logger = logging.getLogger(__name__)


# ============ NEW APIS FOR EDIT/CREATE ============

@login_required
@require_http_methods(["GET"])
def center_detail_api(request, center_id):
    if not is_superadmin(request.user):
        return HttpResponseForbidden("Faqat superadmin uchun")
    
    center = get_object_or_404(Center, pk=center_id)
    director = User.objects.filter(center=center, role='director').first()
    student_limit_state = resolve_center_student_limit(center, actor=request.user, include_usage=True)
    
    # Fetch full plan data for plan selector (including feature_codes)
    from billing.models import PlanFeature
    db_plan_objects = SubscriptionPlan.objects.filter(active=True).prefetch_related('plan_features')
    plans = []
    for p in db_plan_objects:
        plans.append({
            "code": p.code,
            "title": p.title,
            "monthly_price": p.monthly_price,
            "max_students": p.max_students,
            "max_groups": getattr(p, 'max_groups', 30),
            "max_users": p.max_users,
            "is_popular": p.is_popular,
            "discount_percent": p.discount_percent or 0,
            "feature_codes": list(p.plan_features.values_list('code', flat=True)),
        })

    # Fallback: add standard plan choices not in DB
    existing_codes = [p['code'] for p in plans]
    standard_defaults = {"FREE": 0, "STANDARD": 300000, "PREMIUM": 500000, "PRO": 1000000}
    for code, label in Center.Plan.choices:
        if code not in existing_codes:
            plans.append({
                "code": code, "title": label,
                "monthly_price": standard_defaults.get(code, 0),
                "max_students": 100, "max_groups": 30, "max_users": 5,
                "is_popular": False, "discount_percent": 0, "feature_codes": [],
            })


    # Feature codes from the center's ACTIVE subscription plan (M2M)
    feature_codes = []
    active_sub = None
    try:
        # CenterSubscription da is_active degan field yo'q — status='ACTIVE' ishlatamiz
        active_sub = CenterSubscription.objects.filter(
            center=center,
            status=CenterSubscription.Status.ACTIVE,
        ).select_related('plan').order_by('-expires_at').first()
        if active_sub and active_sub.plan:
            feature_codes = list(active_sub.plan.plan_features.values_list('code', flat=True))
    except Exception:
        # Fallback to features JSONField keys that are True
        if center.features:
            ui_feature_keys = set(CENTER_UI_FEATURE_DEFAULTS.keys())
            feature_codes = [k for k, v in center.features.items() if v and k not in ui_feature_keys]

    # Tarif va muddat ma'lumotini ACTIVE subscription dan olamiz — yagona source of truth.
    # Center.plan va Center.expires_at eski cache bo'lishi mumkin, lekin
    # CenterSubscription — haqiqiy holat.
    sub_plan_code = active_sub.plan.code if active_sub else center.plan
    sub_expires   = active_sub.expires_at if active_sub else center.expires_at
    sub_monthly   = active_sub.plan.monthly_price if active_sub else center.monthly_price

    # Send all needed info for edit form
    return JsonResponse({
        "id": center.id,
        "name": center.name,
        "address": center.address,
        "phone": center.phone,
        # Plan va muddat — subscriptiondan (source of truth)
        "plan_code": sub_plan_code,
        "status": center.status,
        "monthly_price": sub_monthly,
        "payment_day": center.payment_day,
        "max_students": center.max_students,
        "resolved_student_limit": student_limit_state["limit"],
        "resolved_student_limit_source": student_limit_state["source"],
        "resolved_student_limit_source_label": student_limit_state["source_label"],
        "current_students": student_limit_state["current_count"],
        "features": center.features or {},
        "feature_codes": feature_codes,          # ← M2M codes
        "expires_at": sub_expires.strftime("%Y-%m-%d") if sub_expires else None,
        "capacity_limit": center.capacity_limit,
        
        # Promo fields
        "promo_code": center.promo_code,
        "discount_amount": center.discount_amount,
        "discount_percent": center.discount_percent,
        "promo_start": center.promo_start.strftime("%Y-%m-%d") if center.promo_start else None,
        "promo_end": center.promo_end.strftime("%Y-%m-%d") if center.promo_end else None,
        
        # Director info
        "director": {
            "id": director.id if director else None,
            "ism": director.ism if director else "",
            "familya": director.familya if director else "",
            "email": director.email if director else "",
            "phone": director.telefon1 if director else "",
            "passport": director.passport_id if director else "",
            "jshr": director.jshr if director else "",
        },
        "available_plans": plans
    })



@login_required
@require_http_methods(["POST"])
def center_update_api(request, center_id):
    if not is_superadmin(request.user):
        return JsonResponse({"success": False, "error": "Faqat superadmin uchun"}, status=403)
        
    center = get_object_or_404(Center, pk=center_id)
    
    try:
        # FormData or JSON
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST

        # 1. Update Center
        center.name = data.get('name', center.name)
        center.address = data.get('address', center.address)
        center.phone = data.get('phone', center.phone)
        center.status = data.get('status', center.status)
        center.plan = data.get('plan', center.plan)
        
        center.monthly_price = int(data.get('monthly_price') or center.monthly_price or 0)
        center.payment_day = int(data.get('payment_day') or center.payment_day or 5)
        
        expires_str = data.get('expires_at')
        if expires_str:
            center.expires_at = expires_str
        else:
            center.expires_at = None
            
        # Promo code fields
        center.promo_code = data.get('promo_code', center.promo_code)
        center.discount_amount = int(data.get('discount_amount') or 0)
        center.discount_percent = int(data.get('discount_percent') or 0)
        
        p_start = data.get('promo_start')
        if p_start: center.promo_start = p_start
        else: center.promo_start = None
        
        p_end = data.get('promo_end')
        if p_end: center.promo_end = p_end
        else: center.promo_end = None
        
        # Features (Handle both JSON string and dict)
        # Core featurelar har doim True — o'chirib bo'lmaydi
        CORE_FEATURE_CODES = {'dashboard', 'students', 'attendance', 'finance'}
        features = data.get('features')
        if features:
            if isinstance(features, str):
                try:
                    features = json.loads(features)
                except Exception:
                    features = None
            if isinstance(features, dict):
                for core_key in CORE_FEATURE_CODES:
                    features[core_key] = True
                center.features = features
        
        # Validate Capacity Limit
        try:
            current_limit_state = resolve_center_student_limit(center, actor=request.user)
            new_exec_limit = int(data.get('capacity_limit') or current_limit_state['limit'])
            if new_exec_limit < 1:
                return JsonResponse({"success": False, "error": "Limit kamida 1 bo'lishi kerak"}, status=400)
            center.capacity_limit = new_exec_limit
        except (ValueError, TypeError):
            return JsonResponse({"success": False, "error": "Limit noto'g'ri formatda"}, status=400)
        
        # Non-subscription fields: name, address, phone, status, promo etc.
        center.save()

        # ── Subscription sync ──────────────────────────────────────────────
        # Superadmin plan/expires_at o'zgartirsa, CenterSubscription va Center
        # IKKALASI ham SINXRON bo'lishi kerak.
        # superadmin_apply_subscription — yagona source of truth funksiyasi:
        #   1. Eski ACTIVE sub → EXPIRED
        #   2. Yangi ACTIVE sub yaratadi
        #   3. Center fieldlarini yangi subdan sync qiladi
        plan_code_from_form = data.get('plan', '').strip().upper()
        expires_str         = data.get('expires_at', '').strip()

        if plan_code_from_form and expires_str:
            # Admin ham plan ham sanani o'zgartirdi → full apply
            new_plan_obj = SubscriptionPlan.objects.filter(
                code=plan_code_from_form, active=True
            ).first()
            if new_plan_obj:
                try:
                    superadmin_apply_subscription(
                        center=center,
                        new_plan=new_plan_obj,
                        expires_at=expires_str,
                        actor=request.user,
                    )
                except Exception as sync_err:
                    logger.warning("superadmin_apply_subscription failed: %s", sync_err)

        elif expires_str:
            # Faqat sana o'zgardi — mavjud ACTIVE sub ning expires_at ni yangilang
            from django.utils.dateparse import parse_datetime, parse_date
            import datetime as dt_module
            raw_dt = parse_datetime(expires_str)
            if not raw_dt:
                raw_d = parse_date(expires_str)
                if raw_d:
                    raw_dt = timezone.make_aware(
                        dt_module.datetime.combine(raw_d, dt_module.time.min)
                    )
            if raw_dt:
                if timezone.is_naive(raw_dt):
                    raw_dt = timezone.make_aware(raw_dt)
                active_sub = CenterSubscription.objects.filter(
                    center=center,
                    status=CenterSubscription.Status.ACTIVE,
                ).order_by('-expires_at').first()
                if active_sub:
                    active_sub.expires_at = raw_dt
                    active_sub.save(update_fields=['expires_at'])
                    # Center fieldini ham yangilaymiz
                    center.expires_at = raw_dt
                    center.save(update_fields=['expires_at'])

        elif plan_code_from_form:
            # Faqat plan o'zgardi, sana o'zgarmadi
            active_sub = CenterSubscription.objects.filter(
                center=center,
                status=CenterSubscription.Status.ACTIVE,
            ).select_related('plan').order_by('-expires_at').first()
            if active_sub:
                new_plan_obj = SubscriptionPlan.objects.filter(
                    code=plan_code_from_form, active=True
                ).first()
                if new_plan_obj and active_sub.plan_id != new_plan_obj.pk:
                    # Plan o'zgardi — expires_at ni saqlab, plan'ni almashtiramiz
                    superadmin_apply_subscription(
                        center=center,
                        new_plan=new_plan_obj,
                        expires_at=active_sub.expires_at,
                        actor=request.user,
                    )

        invalidate_center_limit_cache(center)


        # 2. Update Director
        director = User.objects.filter(center=center, role='director').first()
        if director:
            director.ism = data.get('director_ism', director.ism)
            director.familya = data.get('director_familya', director.familya)
            
            new_email = data.get('director_email')
            if new_email and new_email != director.email:
                if User.objects.filter(email=new_email).exists():
                    return JsonResponse({"success": False, "error": f"Email {new_email} allaqachon mavjud!"}, status=400)
                director.email = new_email
            
            director.passport_id = data.get('director_passport', director.passport_id)
            director.jshr = data.get('director_jshr', director.jshr)
            
            new_pass = data.get('director_password')
            if new_pass:
                director.set_password(new_pass)
                
            director.save()
        else:
            # Create if not exists
            dir_email = data.get('director_email', '').strip().lower()
            if dir_email:
                if not User.objects.filter(email=dir_email).exists():
                    User.objects.create_user(
                        email=dir_email,
                        password=data.get('director_password', '12345678'),
                        ism=data.get('director_ism', 'Director'),
                        familya=data.get('director_familya', ''),
                        telefon1=data.get('director_phone', ''),
                        passport_id=data.get('director_passport', ''),
                        jshr=data.get('director_jshr', ''),
                        role='director',
                        center=center,
                        is_staff=True 
                    )

        return JsonResponse({"success": True, "message": "Markaz va direktor ma'lumotlari yangilandi"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def center_delete_api(request, center_id):
    if not is_superadmin(request.user):
        return JsonResponse({"success": False, "error": "Faqat superadmin uchun"}, status=403)
        
    center = get_object_or_404(Center, pk=center_id)
    
    # ✅ HIMOYA: System center'ni o'chirish mumkin emas!
    if getattr(center, 'is_system', False):
        return JsonResponse({
            "success": False, 
            "error": "❌ Bu asosiy tizim markazi! O'chirish mumkin emas."
        }, status=400)
    
    center.is_deleted = True
    center.status = Center.STATUS_BLOCKED
    center.save()
    
    logger.info(f"AUDIT: User {request.user.id} soft-deleted Center {center.id} ({center.name})")
    
    return JsonResponse({"success": True, "message": "Markaz o'chirildi (Soft Delete)"})


@login_required
@require_http_methods(["POST"])
def center_archive_api(request, center_id):
    if not is_superadmin(request.user):
        return JsonResponse({"success": False, "error": "Faqat superadmin uchun"}, status=403)
        
    center = get_object_or_404(Center, pk=center_id)
    action = request.POST.get("action", "archive")

    if action == "restore":
        center.status = Center.STATUS_ACTIVE
        msg = "Markaz arxivdan chiqarildi"
    else:
        center.status = Center.STATUS_ARCHIVED
        msg = "Markaz arxivlandi"
    
    center.save()
    logger.info(f"AUDIT: User {request.user.id} {action}d Center {center.id}")
    
    return JsonResponse({"success": True, "message": msg})


@login_required
@require_http_methods(["POST"])
def center_create_api(request):
    if not is_superadmin(request.user):
        return JsonResponse({"success": False, "error": "Faqat superadmin uchun"}, status=403)
    
    try:
        # FormData or JSON
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST

        name = data.get('name')
        if not name:
            return JsonResponse({"success": False, "error": "Nom majburiy"}, status=400)
            
        # Parse features
        features = data.get('features', {})
        if isinstance(features, str):
            try:
                features = json.loads(features)
            except:
                features = {}

        # Validate Director Email first to prevent partial creation
        dir_email = data.get('director_email', '').strip().lower()
        if dir_email and User.objects.filter(email=dir_email).exists():
            return JsonResponse({"success": False, "error": f"Email {dir_email} allaqachon mavjud!"}, status=400)

        # 1. Create Center
        submitted_limit = int(data.get('capacity_limit') or data.get('max_students') or 100)

        # Filial sifatida yaratish uchun parent_center_id qo'llab-quvvatlanadi
        parent_center_id = data.get('parent_center_id')
        parent_center_obj = None
        if parent_center_id:
            try:
                parent_center_obj = Center.objects.get(pk=int(parent_center_id), is_deleted=False)
                # Root markazni aniqlaymiz (filial zanjirlari bo'lishi mumkin)
                parent_center_obj = parent_center_obj.get_root_center()
            except (Center.DoesNotExist, ValueError):
                parent_center_obj = None

        c = Center.objects.create(
            name=name,
            address=data.get('address', ''),
            phone=data.get('phone', ''),
            plan=data.get('plan', 'FREE'),
            max_students=submitted_limit,
            capacity_limit=submitted_limit,
            monthly_price=int(data.get('monthly_price') or 0),
            payment_day=int(data.get('payment_day') or 5),
            features=features,
            parent_center=parent_center_obj,  # filial bo'lsa root markazga bog'lanadi
            # Promo
            promo_code=data.get('promo_code'),
            discount_amount=int(data.get('discount_amount') or 0),
            discount_percent=int(data.get('discount_percent') or 0),
            promo_start=data.get('promo_start') or None,
            promo_end=data.get('promo_end') or None
        )

        # Filial bo'lsa: alohida subscription yaratilmaydi, asosiy markaznikini meros oladi
        if parent_center_obj:
            CenterSubscription.objects.filter(center=c).delete()

            # Root markazning barcha direktorlariga filialga kirish huquqi beriladi
            # 1) user.center = root_center bo'lgan direktorlar
            for director in User.objects.filter(
                center=parent_center_obj, role='director', is_active=True
            ):
                access_obj, _ = DirectorCenterAccess.objects.get_or_create(
                    director=director, center=c,
                    defaults={"is_active": True, "granted_by": request.user}
                )
                if not access_obj.is_active:
                    access_obj.is_active = True
                    access_obj.save(update_fields=["is_active"])

            # 2) DirectorCenterAccess orqali root markazga kirish huquqi bor direktorlar
            for root_access in DirectorCenterAccess.objects.filter(
                center=parent_center_obj, is_active=True
            ).select_related("director"):
                access_obj, _ = DirectorCenterAccess.objects.get_or_create(
                    director=root_access.director, center=c,
                    defaults={"is_active": True, "granted_by": request.user}
                )
                if not access_obj.is_active:
                    access_obj.is_active = True
                    access_obj.save(update_fields=["is_active"])
        else:
            # Handle Trial
            trial_days = data.get('trial_days')
            if trial_days and int(trial_days) > 0:
                c.trial_ends = timezone.localdate() + timedelta(days=int(trial_days))
                c.save()

            plan_code = (data.get('plan') or '').strip().upper()
            selected_plan = SubscriptionPlan.objects.filter(code=plan_code, active=True).first()
            if selected_plan:
                expires_raw = (data.get('expires_at') or '').strip()
                expires_at = expires_raw or (timezone.now() + timedelta(days=30))
                superadmin_apply_subscription(
                    center=c,
                    new_plan=selected_plan,
                    expires_at=expires_at,
                    actor=request.user,
                )
                c.refresh_from_db()

        # 2. Create Director (if provided)
        if dir_email:
            # Email check already done above
            User.objects.create_user(
                email=dir_email,
                password=data.get('director_password', '12345678'),
                ism=data.get('director_ism', 'Director'),
                familya=data.get('director_familya', ''),
                telefon1=data.get('director_phone', ''),
                passport_id=data.get('director_passport', ''),
                jshr=data.get('director_jshr', ''),
                role='director',
                center=c,
                is_staff=True 
            )

        logger.info(f"AUDIT: User {request.user.id} created Center {c.id} ({c.name})")
        invalidate_center_limit_cache(c)
        
        return JsonResponse({"success": True, "message": "Markaz yaratildi", "id": c.id})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_http_methods(["GET"])
def plan_list_api(request):
    if not is_superadmin(request.user):
        return HttpResponseForbidden("Faqat superadmin uchun")

    show_all = request.GET.get("all") == "1"
    qs = SubscriptionPlan.objects.all() if show_all else SubscriptionPlan.objects.filter(active=True)
    plans = qs.order_by("tier", "monthly_price")
    data = []
    for p in plans:
        feature_codes = list(p.plan_features.filter(is_active=True).values_list("code", flat=True))
        subs_count = p.centersubscription_set.filter(status="ACTIVE").count()
        data.append({
            "id": p.id,
            "code": p.code,
            "title": p.title,
            "tier": p.tier,
            "monthly_price": p.monthly_price,
            "price_3m": p.price_3m,
            "price_6m": p.price_6m,
            "price_9m": p.price_9m,
            "price_12m": p.price_12m,
            "max_students": p.max_students,
            "max_branches": p.max_branches,
            "is_popular": p.is_popular,
            "is_recommended": getattr(p, "is_recommended", False),
            "caption": p.caption,
            "feature_codes": feature_codes,
            "active": p.active,
            "active_subs": subs_count,
        })
    return JsonResponse({"plans": data})


@login_required
@require_http_methods(["GET"])
def features_list_api(request):
    """Faqat faol va tegishli PlanFeaturelarni kategoriyalar bo'yicha qaytaradi.
    Legacy (ikonsiz) featurelar ko'rsatilmaydi."""
    if not is_superadmin(request.user):
        return HttpResponseForbidden("Faqat superadmin uchun")

    from collections import defaultdict
    # Faqat icon bor va is_active=True bo'lgan featurelar
    features = (
        PlanFeature.objects
        .filter(is_active=True)
        .exclude(icon="")
        .order_by("category", "order", "name")
    )

    IMPL_LABELS = {
        "READY":   "Tayyor",
        "PARTIAL": "Qisman tayyor",
        "PLANNED": "Rejada",
    }
    IMPL_COLORS = {
        "READY":   "#22c55e",
        "PARTIAL": "#f59e0b",
        "PLANNED": "#6366f1",
    }

    categories = defaultdict(list)
    for f in features:
        categories[f.category].append({
            "id": f.id,
            "code": f.code,
            "name": f.name,
            "icon": f.icon,
            "description": f.description_uz or f.description,
            "category": f.category,
            "category_display": f.get_category_display(),
            "is_core": f.is_core,
            "order": f.order,
            "impl_status": f.implementation_status,
            "impl_label": IMPL_LABELS.get(f.implementation_status, f.implementation_status),
            "impl_color": IMPL_COLORS.get(f.implementation_status, "#6b7280"),
        })

    CATEGORY_ORDER = ["core", "finance", "marketing", "team", "advanced"]
    CATEGORY_META = {
        "core":      {"label": "🏠 Asosiy Modullar",      "desc": "Bepul — barcha tariflarda mavjud"},
        "finance":   {"label": "💰 Moliya va Hisobot",    "desc": "STANDART tarifdan boshlab"},
        "marketing": {"label": "🎯 Marketing va SMS",     "desc": "STANDART tarifdan boshlab"},
        "team":      {"label": "👥 Jamoa va Filiallar",   "desc": "PREMIUM tarifdan boshlab"},
        "advanced":  {"label": "⚡ Kengaytirilgan",       "desc": "PREMIUM / PRO tarifdan boshlab"},
    }
    result = []
    for cat in CATEGORY_ORDER:
        if cat in categories:
            meta = CATEGORY_META.get(cat, {"label": cat, "desc": ""})
            result.append({
                "category": cat,
                "label": meta["label"],
                "desc": meta["desc"],
                "items": categories[cat],
            })

    return JsonResponse({"categories": result})


@login_required
@require_http_methods(["POST"])
def plan_create_api(request):
    if not is_superadmin(request.user):
        return JsonResponse({"success": False, "error": "Faqat superadmin uchun"}, status=403)
    
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST

        code = data.get('code', '').strip().upper()
        if not code:
            return JsonResponse({"success": False, "error": "Kod majburiy (masalan: GOLD)"}, status=400)
            
        if SubscriptionPlan.objects.filter(code=code).exists():
            return JsonResponse({"success": False, "error": f"Tarif kodi {code} allaqachon mavjud!"}, status=400)

        # Parse legacy features JSONField
        features = data.get('features', {})
        if isinstance(features, str):
            try:
                features = json.loads(features)
            except:
                features = {}

        plan = SubscriptionPlan.objects.create(
            code=code,
            title=data.get('title', code),
            monthly_price=int(data.get('monthly_price') or 0),
            price_3m=int(data.get('price_3m') or 0) if data.get('price_3m') else None,
            price_6m=int(data.get('price_6m') or 0) if data.get('price_6m') else None,
            price_9m=int(data.get('price_9m') or 0) if data.get('price_9m') else None,
            price_12m=int(data.get('price_12m') or 0) if data.get('price_12m') else None,
            max_students=int(data.get('max_students') or 0),
            max_branches=int(data.get('max_branches') or 0),  # 0=cheksiz
            max_groups=9999,
            max_users=9999,
            is_popular=data.get('is_popular') == 'true' or data.get('is_popular') is True,
            discount_percent=int(data.get('discount_percent') or 0),
            caption=data.get('caption', ''),
            features=features,
            active=True
        )
        
        # M2M feature_codes
        feature_codes = data.get('feature_codes', [])
        if isinstance(feature_codes, str):
            try:
                feature_codes = json.loads(feature_codes)
            except:
                feature_codes = []
        if feature_codes:
            features_qs = PlanFeature.objects.filter(code__in=feature_codes)
            plan.plan_features.set(features_qs)
        
        return JsonResponse({"success": True, "message": "Tarif yaratildi", "id": plan.id})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def plan_update_api(request, plan_id):
    if not is_superadmin(request.user):
        return JsonResponse({"success": False, "error": "Faqat superadmin uchun"}, status=403)
    
    plan = get_object_or_404(SubscriptionPlan, pk=plan_id)
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST

        plan.title = data.get('title', plan.title)
        if data.get('tier') is not None:
            plan.tier = int(data.get('tier') or plan.tier)
        plan.monthly_price = int(data.get('monthly_price') or 0)
        plan.price_3m = int(data.get('price_3m') or 0) if data.get('price_3m') else None
        plan.price_6m = int(data.get('price_6m') or 0) if data.get('price_6m') else None
        plan.price_9m = int(data.get('price_9m') or 0) if data.get('price_9m') else None
        plan.price_12m = int(data.get('price_12m') or 0) if data.get('price_12m') else None
        plan.max_students = int(data.get('max_students') or 0)
        plan.max_branches = int(data.get('max_branches') or 0)  # 0=cheksiz
        plan.max_groups = 9999
        plan.max_users = 9999
        
        # Handle boolean properly from formData or JSON
        is_pop = data.get('is_popular')
        if isinstance(is_pop, str):
            plan.is_popular = (is_pop.lower() == 'true')
        else:
            plan.is_popular = bool(is_pop)

        is_rec = data.get('is_recommended')
        if is_rec is not None:
            if isinstance(is_rec, str):
                plan.is_recommended = (is_rec.lower() == 'true')
            else:
                plan.is_recommended = bool(is_rec)

        active_val = data.get('active')
        if active_val is not None:
            if isinstance(active_val, str):
                plan.active = (active_val.lower() == 'true')
            else:
                plan.active = bool(active_val)

        plan.discount_percent = int(data.get('discount_percent') or 0)
        plan.caption = data.get('caption', '')
        
        # Parse legacy features JSONField
        features = data.get('features')
        if features is not None:
             if isinstance(features, str):
                 try:
                     plan.features = json.loads(features)
                 except:
                     plan.features = {}
             else:
                 plan.features = features
        
        plan.save()
        
        # M2M feature_codes update
        feature_codes = data.get('feature_codes')
        if feature_codes is not None:
            if isinstance(feature_codes, str):
                try:
                    feature_codes = json.loads(feature_codes)
                except:
                    feature_codes = []
            if isinstance(feature_codes, list):
                features_qs = PlanFeature.objects.filter(code__in=feature_codes)
                plan.plan_features.set(features_qs)
        
        return JsonResponse({"success": True, "message": "Tarif yangilandi"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def plan_delete_api(request, plan_id):
    if not is_superadmin(request.user):
        return JsonResponse({"success": False, "error": "Faqat superadmin uchun"}, status=403)

    plan = get_object_or_404(SubscriptionPlan, pk=plan_id)

    try:
        # Barcha PROTECT FK modellarini tekshir
        center_subs  = plan.centersubscription_set.count()
        user_subs    = plan.user_subscriptions.count()
        orders       = plan.subscriptionorder_set.count()
        requests     = plan.subscription_requests.count()
        total_refs   = center_subs + user_subs + orders + requests
        active_subs  = plan.centersubscription_set.filter(status="ACTIVE").count()

        if total_refs > 0:
            parts = []
            if center_subs: parts.append(f"{center_subs} ta markaz obunasi")
            if user_subs:   parts.append(f"{user_subs} ta foydalanuvchi obunasi")
            if orders:      parts.append(f"{orders} ta buyurtma")
            if requests:    parts.append(f"{requests} ta so'rov")
            detail = ", ".join(parts)
            return JsonResponse({
                "success": False,
                "blocked_permanent": True,
                "total_refs": total_refs,
                "active_subs": active_subs,
                "detail": detail,
                "message": (
                    f"Bu tarifga bog'liq yozuvlar bor: {detail}. "
                    "Bog'liq yozuvlari bor tarifni o'chirib bo'lmaydi. "
                    "Tarifni \"To'xtatish\" orqali yashiring."
                ),
            }, status=409)

        plan_title = plan.title
        plan.delete()
        return JsonResponse({"success": True, "message": f'"{plan_title}" tarifi o\'chirildi.'})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


# ============ PROMOCODE APIS ============

@login_required
@require_http_methods(["GET"])
def promo_list_api(request):
    if not is_superadmin(request.user):
        return HttpResponseForbidden("Faqat superadmin uchun")
    
    promos = PromoCode.objects.filter(active=True).order_by("-created_at")
    data = []
    for p in promos:
        data.append({
            "id": p.id,
            "code": p.code,
            "percent_off": p.percent_off,
            "used_count": p.used_count,
            "max_uses": p.max_uses,
            "once_per_center": p.once_per_center,
            "starts_at": p.starts_at.strftime("%Y-%m-%d") if p.starts_at else None,
            "ends_at": p.ends_at.strftime("%Y-%m-%d") if p.ends_at else None,
        })
    return JsonResponse({"promos": data})


@login_required
@require_http_methods(["POST"])
def promo_create_api(request):
    if not is_superadmin(request.user):
        return JsonResponse({"success": False, "error": "Faqat superadmin uchun"}, status=403)
    
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST

        code = data.get('code', '').strip().upper()
        if not code:
            return JsonResponse({"success": False, "error": "Kod majburiy"}, status=400)
            
        if PromoCode.objects.filter(code=code).exists():
            return JsonResponse({"success": False, "error": f"Promokod {code} allaqachon mavjud!"}, status=400)

        once_val = data.get('once_per_center')
        once_per_center = once_val is True or once_val == 'true'

        PromoCode.objects.create(
            code=code,
            percent_off=int(data.get('percent_off') or 0),
            max_uses=int(data.get('max_uses')) if data.get('max_uses') else None,
            once_per_center=once_per_center,
            starts_at=data.get('starts_at') or None,
            ends_at=data.get('ends_at') or None,
            active=True
        )
        
        return JsonResponse({"success": True, "message": "Promokod yaratildi"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def promo_update_api(request, promo_id):
    if not is_superadmin(request.user):
        return JsonResponse({"success": False, "error": "Faqat superadmin uchun"}, status=403)
    
    promo = get_object_or_404(PromoCode, pk=promo_id)
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST

        promo.percent_off = int(data.get('percent_off') or 0)
        max_uses = data.get('max_uses')
        promo.max_uses = int(max_uses) if max_uses else None
        
        once_val = data.get('once_per_center')
        promo.once_per_center = once_val is True or once_val == 'true'
        promo.starts_at = data.get('starts_at') or None
        promo.ends_at = data.get('ends_at') or None
        
        promo.save()
        
        return JsonResponse({"success": True, "message": "Promokod yangilandi"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def promo_delete_api(request, promo_id):
    if not is_superadmin(request.user):
        return JsonResponse({"success": False, "error": "Faqat superadmin uchun"}, status=403)
    
    promo = get_object_or_404(PromoCode, pk=promo_id)
    try:
        promo.active = False
        promo.save()
        return JsonResponse({"success": True, "message": "Promokod o'chirildi"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


# ============ GLOBAL ANALYTICS APIS ============

@login_required
@require_http_methods(["GET"])
def payment_history_api(request):
    """Barcha to'langan obunalarni (SaaS tushumlari) qaytaradi."""
    if not is_superadmin(request.user):
        return HttpResponseForbidden("Faqat superadmin uchun")

    from django.utils import timezone
    from datetime import datetime, time, timedelta
    from django.db.models.functions import TruncMonth
    from core.perf_cache import TTL_MEDIUM, perf_cache_get_or_set

    per_page_raw = (request.GET.get("per_page") or "10").strip()
    allowed_page_sizes = (10, 20, 50)
    try:
        per_page = int(per_page_raw)
    except (TypeError, ValueError):
        per_page = 10
    if per_page not in allowed_page_sizes:
        per_page = 10

    page_raw = (request.GET.get("page") or "1").strip()
    try:
        page_number = int(page_raw)
    except (TypeError, ValueError):
        page_number = 1
    if page_number < 1:
        page_number = 1

    def _build_payload():
        paid_orders = SubscriptionOrder.objects.filter(
            status="PAID",
            center__is_demo=False,
        )

        today = timezone.localdate()
        first_day_this_month = today.replace(day=1)
        first_day_this_month_dt = timezone.make_aware(
            datetime.combine(first_day_this_month, time.min)
        )

        # KPI: 2 aggregate o'rniga bitta (total + this month)
        agg = paid_orders.aggregate(
            total_revenue=Sum("final_price"),
            this_month_revenue=Sum(
                "final_price",
                filter=models.Q(paid_at__gte=first_day_this_month_dt),
            ),
        )
        total_subscribers = (
            paid_orders.values("center").distinct().count()
        )
        kpi = {
            "total_revenue": agg["total_revenue"] or 0,
            "this_month_revenue": agg["this_month_revenue"] or 0,
            "total_subscribers": total_subscribers,
        }

        # Chart: 6 oy → 1 query (TruncMonth), loop ichida 6 aggregate emas
        chart_start = (first_day_this_month - timedelta(days=160)).replace(day=1)
        chart_start_dt = timezone.make_aware(datetime.combine(chart_start, time.min))
        def _month_key(v):
            if v is None:
                return None
            if hasattr(v, "date"):
                v = v.date()
            try:
                return v.replace(day=1)
            except Exception:
                return v

        month_rows = {}
        for row in (
            paid_orders.filter(paid_at__gte=chart_start_dt)
            .annotate(m=TruncMonth("paid_at"))
            .values("m")
            .annotate(rev=Sum("final_price"))
        ):
            key = _month_key(row.get("m"))
            if key is None:
                continue
            month_rows[key] = int(row["rev"] or 0)
        revenue_chart = []
        for i in range(5, -1, -1):
            target_year = today.year
            target_month = today.month - i
            while target_month <= 0:
                target_month += 12
                target_year -= 1
            month_start_date = today.replace(
                year=target_year, month=target_month, day=1
            )
            revenue_chart.append({
                "label": month_start_date.strftime("%b %Y"),
                "value": month_rows.get(month_start_date, 0),
            })

        qs = paid_orders.select_related("center", "plan").order_by("-paid_at", "-id")
        paginator = Paginator(qs, per_page)
        page_obj = paginator.get_page(page_number)

        data = []
        for order in page_obj.object_list:
            paid_dt = timezone.localtime(order.paid_at or order.created_at)
            data.append({
                "id": order.id,
                "center_name": order.center.name,
                "center_slug": order.center.slug,
                "plan_code": order.plan.code,
                "plan_title": order.plan.title,
                "duration": order.duration_months,
                "amount": order.final_price,
                "paid_at": paid_dt.strftime("%d.%m.%Y %H:%M"),
            })

        plan_distribution = list(
            paid_orders.values("plan__title", "plan__code")
            .annotate(count=Count("id"), total_revenue=Sum("final_price"))
            .order_by("-count")
        )

        return {
            "payments": data,
            "kpi": kpi,
            "chart": revenue_chart,
            "plan_stats": plan_distribution,
            "pagination": {
                "page": page_obj.number,
                "per_page": per_page,
                "total_pages": paginator.num_pages,
                "total_count": paginator.count,
                "has_previous": page_obj.has_previous(),
                "has_next": page_obj.has_next(),
            },
        }

    payload = perf_cache_get_or_set(
        f"sa_payments_api:p={page_number}:pp={per_page}",
        _build_payload,
        ttl=TTL_MEDIUM,
    )
    return JsonResponse(payload)


# ══════════════════════════════════════════════════════════════════════════
# TARIF MATRITSASI (data-driven feature boshqaruvi) — faqat superadmin
# ══════════════════════════════════════════════════════════════════════════

def _rule_enabled_state(plan, feature, rule_map, m2m_codes):
    """Katak holati: PlanFeatureRule bo'lsa o'sha, aks holda M2M'dan (mavjud reallik)."""
    r = rule_map.get((plan.id, feature.id))
    if r is not None:
        return r.enabled, r.limit_value
    return (feature.code in m2m_codes.get(plan.id, set())), None


@login_required
@require_http_methods(["POST"])
def feature_rule_update(request):
    """Matritsa katagini o'zgartirish: (plan, feature) enabled va/yoki limit_value.

    CORE feature o'zgartirilmaydi. M2M `plan_features` sinxron saqlanadi.
    """
    if not is_superadmin(request.user):
        return HttpResponseForbidden("Faqat superadmin uchun")
    from billing.models import PlanFeatureRule, PlanFeature
    try:
        data = json.loads(request.body or "{}")
        plan = SubscriptionPlan.objects.get(pk=data["plan_id"])
        feature = PlanFeature.objects.get(code=data["feature_code"])
    except (KeyError, ValueError, TypeError, SubscriptionPlan.DoesNotExist, PlanFeature.DoesNotExist):
        return HttpResponseBadRequest("Noto'g'ri so'rov")

    if feature.is_core or feature.type == PlanFeature.FeatureType.CORE:
        return JsonResponse({"success": False, "error": "CORE feature qulflab/o'chirib bo'lmaydi"}, status=400)

    rule, _ = PlanFeatureRule.objects.get_or_create(plan=plan, feature=feature)
    if "enabled" in data:
        rule.enabled = bool(data["enabled"])
    if "limit_value" in data:
        lv = data["limit_value"]
        if lv in (None, "", "∞", "inf", "cheksiz"):
            rule.limit_value = None
        else:
            try:
                rule.limit_value = max(0, int(lv))
            except (ValueError, TypeError):
                return HttpResponseBadRequest("limit_value raqam bo'lishi kerak")
    rule.save()

    # M2M sinxron — center_has_feature M2M o'qiydi
    if rule.enabled:
        plan.plan_features.add(feature)
    else:
        plan.plan_features.remove(feature)

    return JsonResponse({
        "success": True,
        "enabled": rule.enabled,
        "limit_value": rule.limit_value,
    })


@login_required
@require_http_methods(["POST"])
def feature_create(request):
    """Yangi PlanFeature yaratish (matritsaga yangi qator)."""
    if not is_superadmin(request.user):
        return HttpResponseForbidden("Faqat superadmin uchun")
    from django.utils.text import slugify
    from billing.models import PlanFeature
    try:
        data = json.loads(request.body or "{}")
    except (ValueError, TypeError):
        return HttpResponseBadRequest("Noto'g'ri JSON")

    name = (data.get("name_uz") or data.get("name") or "").strip()
    if not name:
        return JsonResponse({"success": False, "error": "Nom kiritilishi shart"}, status=400)
    code = (data.get("code") or slugify(name).replace("-", "_"))[:50]
    if not code:
        return JsonResponse({"success": False, "error": "Kod yaratib bo'lmadi"}, status=400)
    if PlanFeature.objects.filter(code=code).exists():
        return JsonResponse({"success": False, "error": f"'{code}' kodi allaqachon mavjud"}, status=400)

    category = data.get("category") or PlanFeature.Category.ADVANCED
    ftype = data.get("type") or PlanFeature.FeatureType.BOOLEAN
    if ftype == PlanFeature.FeatureType.CORE:
        # Panel orqali CORE yaratishga yo'l qo'ymaymiz (xavfsizlik)
        ftype = PlanFeature.FeatureType.BOOLEAN
    feature = PlanFeature.objects.create(
        code=code, name=name, name_uz=name,
        category=category, type=ftype, is_core=False,
        icon=data.get("icon", ""), is_active=True,
        order=(PlanFeature.objects.filter(category=category).count() + 1) * 10,
    )
    return JsonResponse({"success": True, "code": feature.code, "name": feature.name_uz or feature.name})


@login_required
@require_http_methods(["POST"])
def plan_set_popular(request):
    """Bitta tarifni 'ommabop' qilib belgilaydi, qolganlaridan olib tashlaydi."""
    if not is_superadmin(request.user):
        return HttpResponseForbidden("Faqat superadmin uchun")
    try:
        data = json.loads(request.body or "{}")
        plan_id = int(data["plan_id"])
    except (KeyError, ValueError, TypeError):
        return HttpResponseBadRequest("Noto'g'ri so'rov")
    if not SubscriptionPlan.objects.filter(pk=plan_id).exists():
        return HttpResponseBadRequest("Tarif topilmadi")
    SubscriptionPlan.objects.filter(is_popular=True).exclude(pk=plan_id).update(is_popular=False)
    SubscriptionPlan.objects.filter(pk=plan_id).update(is_popular=True)
    return JsonResponse({"success": True})


@login_required
@require_http_methods(["POST"])
def plan_price_update(request):
    """Faqat tarif oylik narxini yangilaydi (boshqa maydonlarga TEGMAYDI)."""
    if not is_superadmin(request.user):
        return HttpResponseForbidden("Faqat superadmin uchun")
    try:
        data = json.loads(request.body or "{}")
        plan = SubscriptionPlan.objects.get(pk=int(data["plan_id"]))
        price = max(0, int(data["monthly_price"]))
    except (KeyError, ValueError, TypeError, SubscriptionPlan.DoesNotExist):
        return HttpResponseBadRequest("Noto'g'ri so'rov")
    plan.monthly_price = price
    plan.price = price  # legacy maydon bilan sinxron
    plan.save(update_fields=["monthly_price", "price"])
    return JsonResponse({"success": True, "monthly_price": plan.monthly_price})
