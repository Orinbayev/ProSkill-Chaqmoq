import json
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.db.models import Sum, Count, Q, Avg
from django.db import models
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from accounts.models import Center, User
from education.models import Group, Payment, Attendance
from billing.models import SubscriptionPlan

def is_superadmin(user):
    return user.is_authenticated and user.is_superuser

@login_required
@require_http_methods(["GET"])
def center_stats_api(request, center_id):
    if not is_superadmin(request.user):
        return HttpResponseForbidden("Faqat superadmin uchun")

    center = get_object_or_404(Center, pk=center_id)
    today = timezone.localdate()
    
    # --- 1. KPI Cards ---
    students_qs = User.objects.filter(role='student', center=center)
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
    
    avg_payment = payments_qs.aggregate(a=models.Avg('summa'))['a'] if hasattr(models, 'Avg') else 0
    if not avg_payment and total_revenue > 0:
        count = payments_qs.count()
        avg_payment = total_revenue / count if count else 0

    total_debt = 0 
    
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
            
        cnt = students_qs.filter(date_joined__gte=month_start, date_joined__lt=next_month).count()
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

@login_required
@require_http_methods(["GET"])
def center_students_api(request, center_id):
    if not is_superadmin(request.user):
        return HttpResponseForbidden("Faqat superadmin uchun")
    
    center = get_object_or_404(Center, pk=center_id)
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '')
    
    qs = User.objects.filter(role='student', center=center).select_related('center')
    
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
        groups = u.enrollment_set.all().values_list('group__nom', flat=True)
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
    
    # Fetch plans from DB
    db_plans = list(SubscriptionPlan.objects.filter(active=True).values('code', 'title', 'monthly_price'))
    
    # Standard plans mapping for fallback
    standard_defaults = {
        "FREE": 0,
        "STANDARD": 300000,
        "PREMIUM": 500000,
        "PRO": 1000000
    }
    
    # Merge DB plans with standard choices if they don't exist in DB
    plans = db_plans[:]
    existing_codes = [p['code'] for p in db_plans]
    
    for code, label in Center.Plan.choices:
        if code not in existing_codes:
            plans.append({
                "code": code,
                "title": label,
                "monthly_price": standard_defaults.get(code, 0)
            })
    
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
        "expires_at": center.expires_at.strftime("%Y-%m-%d") if center.expires_at else None,
        
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
        return HttpResponseForbidden("Faqat superadmin uchun")
        
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
        
        # Features (Handle both JSON string and dict)
        features = data.get('features')
        if features:
            if isinstance(features, str):
                center.features = json.loads(features)
            else:
                center.features = features
        
        center.save()

        # 2. Update Director
        director = User.objects.filter(center=center, role='director').first()
        if director:
            director.ism = data.get('director_ism', director.ism)
            director.familya = data.get('director_familya', director.familya)
            
            new_email = data.get('director_email')
            if new_email and new_email != director.email:
                if not User.objects.filter(email=new_email).exists():
                    director.email = new_email
            
            director.passport_id = data.get('director_passport', director.passport_id)
            director.jshr = data.get('director_jshr', director.jshr)
            
            new_pass = data.get('director_password')
            if new_pass:
                director.set_password(new_pass)
                
            director.save()
        else:
            # Create if not exists? Optional.
            pass

        return JsonResponse({"success": True, "message": "Markaz va direktor ma'lumotlari yangilandi"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)

@login_required
@require_http_methods(["POST"])
def center_delete_api(request, center_id):
    if not is_superadmin(request.user):
        return HttpResponseForbidden("Faqat superadmin uchun")
        
    center = get_object_or_404(Center, pk=center_id)
    center.is_deleted = True
    center.status = Center.STATUS_BLOCKED
    center.save()
    
    logger.info(f"AUDIT: User {request.user.id} soft-deleted Center {center.id} ({center.name})")
    
    return JsonResponse({"success": True, "message": "Markaz o'chirildi (Soft Delete)"})

from django.utils.text import slugify

@login_required
@require_http_methods(["POST"])
def center_create_api(request):
    if not is_superadmin(request.user):
        return HttpResponseForbidden("Faqat superadmin uchun")
    
    try:
        data = json.loads(request.body)
        name = data.get('name')
        if not name:
            return HttpResponseBadRequest("Nom majburiy")
            
        # 1. Create Center
        c = Center.objects.create(
            name=name,
            address=data.get('address', ''),
            phone=data.get('phone', ''),
            plan=data.get('plan', 'FREE'),
            max_students=int(data.get('max_students', 100)),
            monthly_price=int(data.get('monthly_price', 0)),
            payment_day=int(data.get('payment_day', 5)),
            features=data.get('features', {})
        )
        
        # Handle Trial
        trial_days = data.get('trial_days')
        if trial_days and int(trial_days) > 0:
            c.trial_ends = timezone.localdate() + timedelta(days=int(trial_days))
            c.save()

        # 2. Create Director (if provided)
        dir_email = data.get('director_email', '').strip().lower()
        if dir_email:
            if User.objects.filter(email=dir_email).exists():
                # We return success True because Center IS created, but warn about user
                return JsonResponse({"success": True, "message": f"Markaz yaratildi, lekin email {dir_email} mavjudligi sababli direktor yaratilmadi.", "id": c.id})
            
            # Use create_user to ensure hashing and defaults
            director = User.objects.create_user(
                email=dir_email,
                password=data.get('director_password', '12345678'), # Plain text here, create_user hashes it
                ism=data.get('director_ism', 'Director'),
                familya=data.get('director_fam', ''),
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
        return HttpResponseBadRequest(str(e))
