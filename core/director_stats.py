from django.db.models import Sum, Count, F, Q, Avg
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.utils.timezone import localdate
import datetime
import json

def _get_growth(current, previous):
    if not previous or previous == 0:
        return 100 if current > 0 else 0
    return round(((current - previous) / previous) * 100, 1)

def _get_trend(current, previous):
    if current > previous:
        return "up"
    elif current < previous:
        return "down"
    return "stable"

def _build_director_stats(center):
    """
    Highly advanced analytics for Director/CEO.
    Calculates statistics for all models with growth and trends.
    """
    if not center:
        return {}

    from accounts.models import User, Center
    from education.models import Group, Enrollment, Payment, Attendance, Category
    from store.models import Product, PurchaseRequest, Sale, Expense, Lead
    
    today = localdate()
    first_day_this_month = today.replace(day=1)
    last_day_prev_month = first_day_this_month - datetime.timedelta(days=1)
    first_day_prev_month = last_day_prev_month.replace(day=1)

    # 1. CORE ENTITIES STATS
    def get_model_stats(queryset, date_field="created_at"):
        # For User model, use date_joined if created_at doesn't exist
        if queryset.model == User and date_field == "created_at":
            date_field = "date_joined"
            
        total = queryset.count()
        this_month = queryset.filter(**{f"{date_field}__year": today.year, f"{date_field}__month": today.month}).count()
        prev_month = queryset.filter(**{f"{date_field}__year": first_day_prev_month.year, f"{date_field}__month": first_day_prev_month.month}).count()
        
        growth = _get_growth(this_month, prev_month)
        trend = _get_trend(this_month, prev_month)
        
        return {
            "total": total,
            "this_month": this_month,
            "prev_month": prev_month,
            "growth": growth,
            "trend": trend
        }

    # Model Querysets (Tenant Isolated)
    students_qs = User.objects.filter(center=center, role="student", is_archived=False)
    teachers_qs = User.objects.filter(center=center, role="teacher")
    groups_qs = Group.objects.filter(center=center)
    leads_qs = Lead.objects.filter(center=center, is_archived=False)
    products_qs = Product.objects.filter(center=center)
    payments_qs = Payment.objects.filter(center=center)
    expenses_qs = Expense.objects.filter(center=center)

    stats_students = get_model_stats(students_qs, "date_joined")
    stats_teachers = get_model_stats(teachers_qs, "date_joined")
    stats_groups = get_model_stats(groups_qs, "tuzilgan")
    stats_leads = get_model_stats(leads_qs, "qoshilgan_sana")
    stats_products = get_model_stats(products_qs, "yaratilgan")

    # 2. FINANCIAL ANALYTICS
    total_income = payments_qs.aggregate(s=Sum("summa"))["s"] or 0
    income_this_month = payments_qs.filter(paid_date__year=today.year, paid_date__month=today.month).aggregate(s=Sum("summa"))["s"] or 0
    income_prev_month = payments_qs.filter(paid_date__year=first_day_prev_month.year, paid_date__month=first_day_prev_month.month).aggregate(s=Sum("summa"))["s"] or 0
    
    income_growth = _get_growth(income_this_month, income_prev_month)
    income_trend = _get_trend(income_this_month, income_prev_month)

    total_expense = expenses_qs.aggregate(s=Sum("summa"))["s"] or 0
    expense_this_month = expenses_qs.filter(sana__year=today.year, sana__month=today.month).aggregate(s=Sum("summa"))["s"] or 0
    
    # Debtors calculation
    debt_info = Enrollment.objects.filter(group__center=center, is_active=True).aggregate(
        total_debt=Sum(F('kurs_narhi') - F('jami_tolangan'), filter=Q(kurs_narhi__gt=F('jami_tolangan'))),
        debtors_count=Count('id', filter=Q(kurs_narhi__gt=F('jami_tolangan')))
    )
    total_debt = debt_info['total_debt'] or 0
    debtors_count = debt_info['debtors_count'] or 0

    # 3. SEGMENT ANALYTICS (Active vs Passive)
    # Eng faol guruhlar (O'quvchi soni bo'yicha)
    active_groups = groups_qs.annotate(
        std_count=Count('enrollments', distinct=True),
        total_paid=Sum('group_payments__summa')
    ).order_by('-std_count')[:5]
    inactive_groups = groups_qs.annotate(std_count=Count('enrollments', distinct=True)).order_by('std_count')[:5]

    # Eng ko'p to'lov qilgan guruh
    top_paying_group_obj = groups_qs.annotate(total_paid_sum=Sum('group_payments__summa')).order_by('-total_paid_sum').first()
    top_paying_group_name = top_paying_group_obj.nom if (top_paying_group_obj and top_paying_group_obj.total_paid_sum) else "—"
    
    # Eng ko'p qarzdor guruh
    top_debtor_group = groups_qs.annotate(
        total_debt=Sum(F('enrollments__kurs_narhi') - F('enrollments__jami_tolangan'), filter=Q(enrollments__kurs_narhi__gt=F('enrollments__jami_tolangan')))
    ).order_by('-total_debt').first()
    
    # 4. CHART DATA (Expanded Search)
    months_labels = []
    income_data = []
    expense_data = []
    student_growth_data = []

    # Get the last 6 months including this one
    current_date = today
    for i in range(5, -1, -1):
        # Calculate month and year manually to avoid complex timedelta issues
        month = (current_date.month - i - 1) % 12 + 1
        year = current_date.year + (current_date.month - i - 1) // 12
        
        d_name = datetime.date(year, month, 1).strftime("%b")
        months_labels.append(d_name)
        
        inc = payments_qs.filter(paid_date__year=year, paid_date__month=month).aggregate(s=Sum("summa"))["s"] or 0
        income_data.append(int(inc))
        
        exp = expenses_qs.filter(sana__year=year, sana__month=month).aggregate(s=Sum("summa"))["s"] or 0
        expense_data.append(int(exp))
        
        st_count = User.objects.filter(center=center, role="student", is_archived=False, date_joined__year=year, date_joined__month=month).count()
        student_growth_data.append(st_count)

    # 5. CATEGORY DISTRIBUTION (Show any categories if possible)
    category_data = Category.objects.filter(Q(center=center) | Q(center__isnull=True)).annotate(
        group_count=Count('groups', filter=Q(groups__center=center))
    ).order_by('-group_count').values('name', 'group_count')
    
    if not any(c['group_count'] > 0 for c in category_data):
        # Fallback if no counts found, just show names or empty
        cat_labels = [c['name'] for c in category_data[:5]]
        cat_series = [0] * len(cat_labels)
    else:
        # Filter only active ones if some data exists
        active_cats = [c for c in category_data if c['group_count'] > 0]
        cat_labels = [c['name'] for c in active_cats]
        cat_series = [c['group_count'] for c in active_cats]

    # Profit calculation
    profit_this_month = income_this_month - expense_this_month
    profit_margin = round((profit_this_month / income_this_month * 100), 1) if income_this_month > 0 else 0

    # Teacher Performance (By students count and income generated)
    teacher_performance = teachers_qs.annotate(
        std_count=Count('teacher_groups__enrollments', distinct=True),
        income=Sum('teacher_groups__group_payments__summa')
    ).order_by('-std_count')[:4]

    # Attendance Rate
    total_attendance = Attendance.objects.filter(group__center=center, date__year=today.year, date__month=today.month).count()
    present_attendance = Attendance.objects.filter(group__center=center, date__year=today.year, date__month=today.month, present=True).count()
    attendance_rate = round((present_attendance / total_attendance * 100), 1) if total_attendance > 0 else 0

    # Subscription Info
    subscription_info = {
        "plan": center.plan,
        "days_left": center.days_left,
        "is_expired": center.is_expired,
        "expires_at": center.expires_at.strftime("%Y-%m-%d") if center.expires_at else "—"
    }

    return {
        "stats": {
            "students": stats_students,
            "teachers": stats_teachers,
            "groups": stats_groups,
            "leads": stats_leads,
            "products": stats_products,
        },
        "subscription": subscription_info,
        "financials": {
            "total_income": int(total_income),
            "income_this_month": int(income_this_month),
            "income_growth": float(income_growth),
            "income_trend": income_trend,
            "total_expense": int(total_expense),
            "expense_this_month": int(expense_this_month),
            "profit_this_month": int(profit_this_month),
            "profit_margin": profit_margin,
            "total_debt": int(total_debt),
            "debtors_count": int(debtors_count),
            "avg_student_payment": int(income_this_month / stats_students['this_month']) if stats_students['this_month'] > 0 else 0,
        },
        "segments": {
            "top_paying_group": top_paying_group_name,
            "top_debtor_group": top_debtor_group.nom if top_debtor_group else "—",
            "active_groups": [
                {
                    "nom": g['nom'],
                    "std_count": int(g['std_count'] or 0),
                    "total_paid": int(g['total_paid'] or 0)
                } for g in active_groups.values('nom', 'std_count', 'total_paid')
            ],
            "inactive_groups": [
                {
                    "nom": g['nom'],
                    "std_count": int(g['std_count'] or 0)
                } for g in inactive_groups.values('nom', 'std_count')
            ],
            "teacher_ranking": [
                {
                    "name": t.get_full_name() or t.username,
                    "std_count": t.std_count,
                    "income": int(t.income or 0)
                } for t in teacher_performance
            ],
            "attendance_rate": float(attendance_rate),
        },
        "charts": {
            "labels": months_labels,
            "income": income_data,
            "expense": expense_data,
            "students": student_growth_data,
            "cat_labels": cat_labels,
            "cat_series": cat_series,
        }
    }
