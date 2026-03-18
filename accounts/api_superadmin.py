import json
import logging
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.db.models import Sum, Count, Q, Avg
from django.db import models
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from accounts.models import Center, User
from education.models import Group, Payment, Attendance, TeacherIncome
from billing.models import SubscriptionPlan, PromoCode, PlanFeature, SubscriptionOrder
from billing.services import apply_plan_to_center

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


    # Feature codes from the center's current subscription plan (M2M)
    feature_codes = []
    try:
        from billing.models import CenterSubscription
        sub = CenterSubscription.objects.filter(center=center, is_active=True).select_related('plan').first()
        if sub and sub.plan:
            feature_codes = list(sub.plan.plan_features.values_list('code', flat=True))
    except Exception:
        # Fallback to features JSONField keys that are True
        if center.features:
            feature_codes = [k for k, v in center.features.items() if v]

    # Send all needed info for edit form
    return JsonResponse({
        "id": center.id,
        "name": center.name,
        "address": center.address,
        "phone": center.phone,
        "plan_code": center.plan,
        "status": center.status,
        "monthly_price": center.monthly_price,
        "payment_day": center.payment_day,
        "max_students": center.max_students,
        "features": center.features or {},
        "feature_codes": feature_codes,          # ← M2M codes
        "expires_at": center.expires_at.strftime("%Y-%m-%d") if center.expires_at else None,
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
        features = data.get('features')
        if features:
            if isinstance(features, str):
                try:
                    center.features = json.loads(features)
                except:
                    pass
            else:
                center.features = features
        
        # Validate Capacity Limit
        try:
            new_exec_limit = int(data.get('capacity_limit') or center.capacity_limit or 100)
            if new_exec_limit < 1:
                return JsonResponse({"success": False, "error": "Limit kamida 1 bo'lishi kerak"}, status=400)
            center.capacity_limit = new_exec_limit
        except (ValueError, TypeError):
            return JsonResponse({"success": False, "error": "Limit noto'g'ri formatda"}, status=400)
        
        center.save()

        # ✅ Sync expires_at AND PLAN with CenterSubscription if it exists
        if hasattr(center, 'subscription'):
            sub = center.subscription
            
            # 1. Sync Plan if changed
            if sub.plan and sub.plan.code != center.plan:
                # Find the plan object
                new_plan_obj = SubscriptionPlan.objects.filter(code=center.plan).first()
                if new_plan_obj:
                    sub.plan = new_plan_obj
                    sub.save(update_fields=['plan'])
            
            # 2. Sync Expiry
            if center.expires_at:
                from django.utils.dateparse import parse_datetime, parse_date
                from datetime import datetime
                
                # Convert to datetime if string/date
                dt = None
                if isinstance(center.expires_at, str):
                    dt = parse_datetime(center.expires_at)
                    if not dt:
                        d = parse_date(center.expires_at)
                        if d:
                            dt = datetime.combine(d, datetime.min.time())
                            dt = timezone.make_aware(dt) if timezone.is_naive(dt) else dt
                else:
                    dt = center.expires_at
                    if not hasattr(dt, 'date'): # Is date
                         dt = datetime.combine(dt, datetime.min.time())
                    dt = timezone.make_aware(dt) if timezone.is_naive(dt) else dt
                
                if dt:
                    sub.expires_at = dt
                    sub.save(update_fields=['expires_at'])


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
        c = Center.objects.create(
            name=name,
            address=data.get('address', ''),
            phone=data.get('phone', ''),
            plan=data.get('plan', 'FREE'),
            max_students=int(data.get('max_students') or 100),
            monthly_price=int(data.get('monthly_price') or 0),
            payment_day=int(data.get('payment_day') or 5),
            features=features,
            # Promo
            promo_code=data.get('promo_code'),
            discount_amount=int(data.get('discount_amount') or 0),
            discount_percent=int(data.get('discount_percent') or 0),
            promo_start=data.get('promo_start') or None,
            promo_end=data.get('promo_end') or None
        )
        
        # Handle Trial
        trial_days = data.get('trial_days')
        if trial_days and int(trial_days) > 0:
            c.trial_ends = timezone.localdate() + timedelta(days=int(trial_days))
            c.save()

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
        
        return JsonResponse({"success": True, "message": "Markaz yaratildi", "id": c.id})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_http_methods(["GET"])
def plan_list_api(request):
    if not is_superadmin(request.user):
        return HttpResponseForbidden("Faqat superadmin uchun")
    
    plans = SubscriptionPlan.objects.filter(active=True).order_by("monthly_price")
    data = []
    for p in plans:
        # M2M feature codes
        feature_codes = list(p.plan_features.values_list("code", flat=True))
        data.append({
            "id": p.id,
            "code": p.code,
            "title": p.title,
            "monthly_price": p.monthly_price,
            "price_3m": p.price_3m,
            "price_6m": p.price_6m,
            "price_12m": p.price_12m,
            "max_students": p.max_students,
            "max_groups": getattr(p, 'max_groups', 30),
            "max_users": p.max_users,
            "is_popular": p.is_popular,
            "discount_percent": p.discount_percent,
            "caption": p.caption,
            "features": p.features,          # legacy JSONField
            "feature_codes": feature_codes,   # M2M feature codes
        })
    return JsonResponse({"plans": data})


@login_required
@require_http_methods(["GET"])
def features_list_api(request):
    """Barcha PlanFeaturelarni kategoriyalar bo'yicha qaytaradi."""
    if not is_superadmin(request.user):
        return HttpResponseForbidden("Faqat superadmin uchun")
    
    from collections import defaultdict
    features = PlanFeature.objects.all().order_by("category", "order", "name")
    
    categories = defaultdict(list)
    for f in features:
        categories[f.category].append({
            "id": f.id,
            "code": f.code,
            "name": f.name,
            "description": f.description,
            "category": f.category,
            "category_display": f.get_category_display(),
            "is_core": f.is_core,
            "order": f.order,
        })
    
    # Convert to ordered list of category groups
    CATEGORY_ORDER = ["core", "finance", "marketing", "team", "advanced"]
    CATEGORY_LABELS = dict(PlanFeature.Category.choices)
    result = []
    for cat in CATEGORY_ORDER:
        if cat in categories:
            result.append({
                "category": cat,
                "label": CATEGORY_LABELS.get(cat, cat),
                "items": categories[cat],
            })
    # Append any categories not in CATEGORY_ORDER
    for cat, items in categories.items():
        if cat not in CATEGORY_ORDER:
            result.append({"category": cat, "label": cat, "items": items})
    
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
        plan.monthly_price = int(data.get('monthly_price') or 0)
        plan.price_3m = int(data.get('price_3m') or 0) if data.get('price_3m') else None
        plan.price_6m = int(data.get('price_6m') or 0) if data.get('price_6m') else None
        plan.price_9m = int(data.get('price_9m') or 0) if data.get('price_9m') else None
        plan.price_12m = int(data.get('price_12m') or 0) if data.get('price_12m') else None
        plan.max_students = int(data.get('max_students') or 0)
        plan.max_groups = 9999
        plan.max_users = 9999
        
        # Handle boolean properly from formData or JSON
        is_pop = data.get('is_popular')
        if isinstance(is_pop, str):
            plan.is_popular = (is_pop.lower() == 'true')
        else:
             plan.is_popular = bool(is_pop)

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
        # Standard plans shouldn't be deleted usually, but user is boss.
        # Check if used? 
        plan.active = False # soft delete or deactivate
        plan.save()
        return JsonResponse({"success": True, "message": "Tarif o'chirildi (Active=False)"})
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
    
    # 1. Base query for all paid orders
    paid_orders = SubscriptionOrder.objects.filter(status='PAID')
    
    # 2. Key Metrics (KPIs)
    total_revenue = paid_orders.aggregate(s=Sum('final_price'))['s'] or 0
    
    from django.utils import timezone
    from datetime import datetime, time
    today = timezone.localdate()
    first_day_this_month = today.replace(day=1)
    first_day_this_month_dt = timezone.make_aware(datetime.combine(first_day_this_month, time.min))
    
    this_month_revenue = paid_orders.filter(paid_at__gte=first_day_this_month_dt).aggregate(s=Sum('final_price'))['s'] or 0
    total_subscribers = paid_orders.values('center').distinct().count()
    
    kpi = {
        "total_revenue": total_revenue,
        "this_month_revenue": this_month_revenue,
        "total_subscribers": total_subscribers,
    }
    
    # 3. Chart Data (Last 6 months)
    revenue_chart = []
    for i in range(5, -1, -1):
        target_year = today.year
        target_month = today.month - i
        while target_month <= 0:
            target_month += 12
            target_year -= 1
        month_start_date = today.replace(year=target_year, month=target_month, day=1)
        y, m = month_start_date.year, month_start_date.month
        if m == 12:
            next_month_date = month_start_date.replace(year=y+1, month=1, day=1)
        else:
            next_month_date = month_start_date.replace(month=m+1, day=1)

        month_start = timezone.make_aware(datetime.combine(month_start_date, time.min))
        next_month = timezone.make_aware(datetime.combine(next_month_date, time.min))
            
        rev = paid_orders.filter(paid_at__gte=month_start, paid_at__lt=next_month).aggregate(s=Sum('final_price'))['s'] or 0
        revenue_chart.append({
            "label": month_start_date.strftime("%b %Y"),
            "value": rev
        })
    
    # 4. Recent 100 Payments List
    qs = paid_orders.select_related('center', 'plan').order_by('-paid_at')[:100]
    
    data = []
    for order in qs:
        data.append({
            "id": order.id,
            "center_name": order.center.name,
            "center_slug": order.center.slug,
            "plan_code": order.plan.code,
            "plan_title": order.plan.title,
            "duration": order.duration_months,
            "amount": order.final_price,
            "paid_at": order.paid_at.strftime("%d.%m.%Y %H:%M") if order.paid_at else order.created_at.strftime("%d.%m.%Y %H:%M"),
        })
        
    # 5. Plan Distribution (Which plan sold how many times)
    plan_distribution = list(paid_orders.values('plan__title', 'plan__code').annotate(
        count=Count('id'),
        total_revenue=Sum('final_price')
    ).order_by('-count'))
        
    return JsonResponse({
        "payments": data,
        "kpi": kpi,
        "chart": revenue_chart,
        "plan_stats": plan_distribution
    })
