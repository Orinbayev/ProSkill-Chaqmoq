from django.core.cache import cache
from django.db.models import Sum, Count, F, Q, Avg
from django.db.models.functions import ExtractMonth, ExtractYear, TruncMonth, TruncDay
from django.utils import timezone
from datetime import timedelta, datetime, date
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
import logging

from accounts.models import User, Center
from education.models import Group, Enrollment, Payment, Attendance, Category
from store.models import Expense, Lead, Manba
from chaqmoq.models import Ledger

logger = logging.getLogger(__name__)

class DirectorDashboardAPIView(View):
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or getattr(request.user, 'role', None) in ('director', 'manager')):
            return JsonResponse({'error': 'Permission denied'}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        try:
            center = getattr(request, 'center', None) or request.user.center
            if not center:
                return JsonResponse({'error': 'Center not found'}, status=404)

            now = timezone.localtime(timezone.now())
            today = now.date()

            period = request.GET.get('period', 'this_month')
            date_from_str = request.GET.get('date_from', '').strip()
            date_to_str   = request.GET.get('date_to', '').strip()

            # ── Date range mode ──
            custom_range = False
            if date_from_str and date_to_str:
                try:
                    from datetime import date as _date
                    start_date = _date.fromisoformat(date_from_str)
                    end_date   = _date.fromisoformat(date_to_str)
                    if start_date <= end_date:
                        custom_range = True
                        period = f"custom:{date_from_str}:{date_to_str}"
                    else:
                        return JsonResponse({'error': 'date_from must be <= date_to'}, status=400)
                except ValueError:
                    return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

            if not custom_range:
                if period == 'this_month':
                    start_date = today.replace(day=1)
                    end_date = today
                elif period == 'last_month':
                    first_this = today.replace(day=1)
                    end_date = first_this - timedelta(days=1)
                    start_date = end_date.replace(day=1)
                elif period == '3_months':
                    start_date = today - timedelta(days=90)
                    end_date = today
                elif period == 'this_year':
                    start_date = today.replace(month=1, day=1)
                    end_date = today  # cap at today to avoid showing future zero-months
                elif period == 'last_year':
                    start_date = today.replace(year=today.year-1, month=1, day=1)
                    end_date = today.replace(year=today.year-1, month=12, day=31)
                elif period.isdigit() and 1 <= int(period) <= 12:
                    import calendar
                    m = int(period)
                    y = today.year
                    start_date = date(y, m, 1)
                    dr = calendar.monthrange(y, m)[1]
                    end_date = date(y, m, dr)
                elif period == 'all':
                    first_pay = Payment.objects.filter(center=center).order_by('paid_date').first()
                    if first_pay:
                        st_date = first_pay.paid_date.date() if hasattr(first_pay.paid_date, 'date') else first_pay.paid_date
                    else:
                        st_date = today.replace(month=1, day=1)
                    six_months_ago = today - timedelta(days=180)
                    start_date = min(st_date, six_months_ago).replace(day=1)
                    end_date = today
                else:
                    start_date = today.replace(day=1)
                    end_date = today

            cache_key = f"director_dashboard:v2:center:{center.id}:period:{period}"
            cached_payload = cache.get(cache_key)
            if cached_payload is not None:
                return JsonResponse(cached_payload)

            delta = (end_date - start_date).days + 1
            p_end = start_date - timedelta(days=1)
            p_start = p_end - timedelta(days=delta - 1)

            data = {
                'finance': self.get_finance_stats(center, start_date, end_date, p_start, p_end),
                'students': self.get_student_stats(center, start_date, end_date, p_start, p_end, today),
                'teachers': self.get_teacher_stats(center, start_date, end_date),
                'groups': self.get_group_stats(center, start_date, end_date),
                'charts': self.get_chart_data(center, period, start_date, end_date),
                'system': {
                    'last_updated': now.strftime('%H:%M:%S'),
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                }
            }
            data['marketing'] = data['charts']['marketing']
            data['plans'] = self.get_plans_stats(center, start_date, end_date)
            cache.set(cache_key, data, timeout=30)

            return JsonResponse(data)
        except Exception as e:
            import traceback
            logger.error(traceback.format_exc())
            return JsonResponse({'error': str(e)}, status=500)


    def calculate_growth(self, current, previous):
        if not previous or previous == 0:
            return 100 if current > 0 else 0
        return round(((float(current) - float(previous)) / float(previous)) * 100, 1)

    def get_finance_stats(self, center, start, end, p_start, p_end):
        payments = Payment.objects.filter(center=center, paid_date__range=(start, end))
        payments_prev = Payment.objects.filter(center=center, paid_date__range=(p_start, p_end))
        
        inc_this = payments.aggregate(s=Sum('summa'))['s'] or 0
        inc_prev = payments_prev.aggregate(s=Sum('summa'))['s'] or 0
        
        # New vs Returning Students
        all_prev_student_ids = Payment.objects.filter(center=center, paid_date__lt=start).values_list('student_id', flat=True).distinct()
        new_students_payments = payments.exclude(student_id__in=all_prev_student_ids).aggregate(s=Sum('summa'))['s'] or 0
        returning_students_payments = payments.filter(student_id__in=all_prev_student_ids).aggregate(s=Sum('summa'))['s'] or 0

        # Expenses & Teacher Shares (This Period)
        expenses = Expense.objects.filter(center=center, sana__date__range=(start, end))
        exp_real = expenses.aggregate(s=Sum('summa'))['s'] or 0
        
        teacher_shares = 0
        att_counts = Attendance.objects.filter(group__center=center, date__range=(start, end)).filter(
            Q(present=True) | Q(forced=True)
        ).values('group_id', 'student_id').annotate(c=Count('id'))
        att_map = {(a['group_id'], a['student_id']): a['c'] for a in att_counts}
        
        enrollments = Enrollment.objects.filter(group__center=center, is_active=True).select_related('group')
        for enr in enrollments:
            count = att_map.get((enr.group_id, enr.student_id), 0)
            if count > 0:
                teacher_shares += count * float(enr.group.dars_boshiga_tolov())

        total_exp = exp_real + teacher_shares
        profit = inc_this - total_exp

        # Growth calculations
        exp_prev_real = Expense.objects.filter(center=center, sana__date__range=(p_start, p_end)).aggregate(s=Sum('summa'))['s'] or 0
        teacher_shares_prev = 0
        att_counts_prev = Attendance.objects.filter(group__center=center, date__range=(p_start, p_end)).filter(
            Q(present=True) | Q(forced=True)
        ).values('group_id', 'student_id').annotate(c=Count('id'))
        att_map_prev = {(a['group_id'], a['student_id']): a['c'] for a in att_counts_prev}
        
        enrollments_prev = Enrollment.objects.filter(group__center=center, is_active=True).select_related('group')
        for enr in enrollments_prev:
            count = att_map_prev.get((enr.group_id, enr.student_id), 0)
            if count > 0:
                teacher_shares_prev += count * float(enr.group.dars_boshiga_tolov())
        
        total_exp_prev = exp_prev_real + teacher_shares_prev
        profit_prev = inc_prev - total_exp_prev

        # Breakdowns
        by_category = payments.values('group__category_obj__name').annotate(
            total=Sum('summa'), count=Count('id')
        ).order_by('-total')
        
        by_teacher = payments.values('group__oqituvchi__ism', 'group__oqituvchi__familya').annotate(
            total=Sum('summa')
        ).order_by('-total')
        
        by_type_raw = payments.values('payment_type').annotate(total=Sum('summa'))
        type_map = {'cash': 'Naqd', 'card': 'Karta', 'mixed': 'Aralash'}
        by_type = [{'name': type_map.get(t['payment_type'], t['payment_type']), 'value': t['total']} for t in by_type_raw]

        return {
            'income': int(inc_this),
            'income_prev_diff': int(inc_this - inc_prev),
            'income_growth': self.calculate_growth(inc_this, inc_prev),
            'expense': int(total_exp),
            'teacher_shares': int(teacher_shares),
            'profit': int(profit),
            'profit_growth': self.calculate_growth(profit, profit_prev),
            'avg_payment': round(inc_this / payments.count()) if payments.count() > 0 else 0,
            'breakdown': {
                'by_category': list(by_category),
                'by_teacher': list(by_teacher),
                'by_type': by_type,
                'new_vs_returning': [
                    {'name': 'Yangi talabalar', 'value': int(new_students_payments)},
                    {'name': 'Qayta to‘lovlar', 'value': int(returning_students_payments)}
                ]
            }
        }

    def get_student_stats(self, center, start, end, p_start, p_end, today):
        base_qs = User.objects.filter(center=center, role='student', is_archived=False)
        
        total_count = base_qs.count()
        active_enrollments = Enrollment.objects.filter(group__center=center, is_active=True, student__is_archived=False)
        active_count = active_enrollments.values('student').distinct().count()
        prev_active_count = Enrollment.objects.filter(group__center=center, is_active=True, student__is_archived=False, created_at__date__lt=start).values('student').distinct().count()
        
        from education.models import TuitionMonth, PaymentAllocation
        from django.db.models import OuterRef, Subquery, Sum, F
        from django.db.models.functions import Coalesce
        from education.services.tuition import tuition_month_fee_field
        
        cur_month = today.replace(day=1)
        
        # ✅ [FIX] ensure_all_tuition_months_since_start O'CHIRILDI!
        # Bu funksiya har dashboard ochilganda yangi TuitionMonth yozuvlar yaratib
        # qarzlarni avtomatik ko'paytirardi. Endi faqat MAVJUD yozuvlardan hisoblaymiz.
        
        fee_field = tuition_month_fee_field()
        
        # Faqat JORIY OY uchun (month=cur_month, not month__lte)
        total_fee_sub = TuitionMonth.objects.filter(
            enrollment=OuterRef("pk"), month=cur_month
        ).values("enrollment").annotate(s=Sum(fee_field)).values("s")
        
        total_paid_sub = PaymentAllocation.objects.filter(
            tuition_month__enrollment=OuterRef("pk"),
            tuition_month__month=cur_month
        ).values("tuition_month__enrollment").annotate(s=Sum("amount")).values("s")

        active_enrollments_filtered = active_enrollments.filter(group__is_archived=False)
        debt_qs = active_enrollments_filtered.annotate(
            f=Coalesce(Subquery(total_fee_sub), 0),
            p=Coalesce(Subquery(total_paid_sub), 0)
        ).annotate(d=F("f") - F("p")).filter(d__gt=0)
        
        debt_amount = debt_qs.aggregate(total=Sum("d"))["total"] or 0
        debtors_count = debt_qs.values('student').distinct().count()
        
        thirty_days_ago = today - timedelta(days=30)
        low_activity_candidates = base_qs.annotate(
            att_count=Count('attendance', filter=Q(attendance__date__gte=thirty_days_ago, attendance__present=True))
        ).order_by('att_count')[:10]

        low_list = []
        for s in low_activity_candidates:
            if s.att_count >= 8: # Filter out active students from this list
                continue
                
            enr = s.enrollments.filter(is_active=True).first()
            reasons = []
            att_pct = round((s.att_count / 12) * 100) if s.att_count < 12 else 100
            
            if s.att_count < 5:
                reasons.append(f"Davomat juda past ({att_pct}%)")
            if enr and enr.jami_tolangan < enr.kurs_narhi:
                reasons.append("To'lov kechikkan")
            if s.last_login and (timezone.now() - s.last_login).days > 10:
                reasons.append("10 kundan beri kirmagan")

            low_list.append({
                'id': s.id,
                'name': f"{s.ism} {s.familya}",
                'course': enr.group.nom if enr else "Guruhsiz",
                'status': att_pct, # Actual activity percentage
                'reason': ", ".join(reasons[:2]) if reasons else "Kam faol",
                'img': f"https://ui-avatars.com/api/?name={s.ism}+{s.familya}&background=random",
                'attendance_pct': f"{att_pct}%",
            })

        dropouts = User.objects.filter(center=center, role='student', is_archived=True).count()

        return {
            'total': total_count, # Real count for home dashboard
            'active_students': active_count,
            'growth': active_count - prev_active_count,
            'growth_pct': self.calculate_growth(active_count, prev_active_count),
            'debt_amount': int(debt_amount),
            'debtors_count': debtors_count,
            'low_activity': low_list[:5],
            'dropouts': dropouts
        }

    def get_teacher_stats(self, center, start, end):
        teachers = User.objects.filter(center=center, role='teacher').annotate(
            revenue=Sum('group__group_payments__summa', filter=Q(group__group_payments__paid_date__range=(start, end))),
            s_count=Count('group__enrollments', filter=Q(group__enrollments__is_active=True), distinct=True),
            g_count=Count('group', distinct=True)
        ).order_by('-revenue')
        
        fmt = lambda t: {
            'name': f"{t.ism} {t.familya}",
            'revenue': int(t.revenue or 0),
            'students': t.s_count,
            'groups': t.g_count,
            'course': "O'qituvchi", 
            'rating': 4.9, 
            'img': f"https://ui-avatars.com/api/?name={t.ism}+{t.familya}&background=random"
        }

        return {
            'total_count': User.objects.filter(center=center, role='teacher').count(),
            'best': [fmt(t) for t in teachers[:5]],
            'low': [fmt(t) for t in teachers.order_by('revenue')[:5]],
            'top': [fmt(t) for t in teachers[:3]]
        }

    def get_group_stats(self, center, start, end):
        from education.models import TuitionMonth, PaymentAllocation
        from education.services.tuition import tuition_month_fee_field
        from django.db.models import OuterRef, Subquery, IntegerField
        from django.db.models.functions import Coalesce
        from django.utils import timezone as _tz
        _cur_month = _tz.localdate().replace(day=1)
        _fee_field = tuition_month_fee_field()
        _fee_sub = TuitionMonth.objects.filter(
            enrollment=OuterRef("pk"), month=_cur_month
        ).values("enrollment").annotate(s=Sum(_fee_field)).values("s")
        _paid_sub = PaymentAllocation.objects.filter(
            tuition_month__enrollment=OuterRef("pk"),
            tuition_month__month=_cur_month
        ).values("tuition_month__enrollment").annotate(s=Sum("amount")).values("s")

        groups = Group.objects.filter(center=center, is_archived=False).annotate(
            revenue=Sum('group_payments__summa', filter=Q(group_payments__paid_date__range=(start, end))),
        ).order_by('-revenue')

        from django.db.models import IntegerField
        from django.db.models.functions import Coalesce as _Coalesce
        # Compute per-group debt using TuitionMonth for current month
        enr_debt_qs = (
            Enrollment.objects
            .filter(group__center=center, is_active=True, student__is_archived=False, group__is_archived=False)
            .annotate(
                _f=Coalesce(Subquery(_fee_sub, output_field=IntegerField()), 0),
                _p=Coalesce(Subquery(_paid_sub, output_field=IntegerField()), 0),
            )
            .annotate(_d=F("_f") - F("_p"))
            .filter(_d__gt=0)
            .values("group_id")
            .annotate(group_debt=Sum("_d"))
        )
        debt_by_group = {row["group_id"]: row["group_debt"] for row in enr_debt_qs}

        def fmt(g):
            return {
                'name': g.nom,
                'revenue': int(g.revenue or 0),
                'debt': int(debt_by_group.get(g.pk, 0))
            }

        groups_list = list(groups)
        groups_by_debt = sorted(groups_list, key=lambda g: debt_by_group.get(g.pk, 0), reverse=True)
        most_debt = groups_by_debt[0] if groups_by_debt else None

        return {
            'total_count': len(groups_list),
            'top_5_income': [fmt(g) for g in groups_list[:5]],
            'bottom_5_income': [fmt(g) for g in sorted(groups_list, key=lambda g: g.revenue or 0)[:5]],
            'most_indebted': fmt(most_debt) if most_debt else None,
            'plan_fulfillment': 85
        }

    def get_marketing_stats(self, center, start, end):
        leads = Lead.objects.filter(center=center, is_archived=False, qoshilgan_sana__date__range=(start, end))
        by_source = leads.values('manba__nom').annotate(
            count=Count('id'),
            converted=Count('id', filter=Q(converted_to_student=True) | Q(converted_user__isnull=False))
        )
        
        out = []
        for s in by_source:
            name = s['manba__nom'] or "Noma'lum"
            conv_rate = round((s['converted'] / s['count']) * 100) if s['count'] > 0 else 0
            
            lead_user_ids = leads.filter(manba__nom=s['manba__nom']).values_list('converted_user_id', flat=True)
            revenue = Payment.objects.filter(student_id__in=lead_user_ids, paid_date__range=(start, end)).aggregate(s=Sum('summa'))['s'] or 0
            
            out.append({
                'name': name,
                'count': s['count'],
                'value': s['count'], 
                'conversion': conv_rate,
                'revenue': int(revenue)
            })
        if not out:
            # Fallback for empty data
            return [
                {'name': 'Telegram', 'count': 0, 'value': 0, 'conversion': 0, 'revenue': 0},
                {'name': 'Instagram', 'count': 0, 'value': 0, 'conversion': 0, 'revenue': 0},
                {'name': 'Tavsiya', 'count': 0, 'value': 0, 'conversion': 0, 'revenue': 0}
            ]
        return out

    def get_plans_stats(self, center, start, end):
        total_income = Payment.objects.filter(center=center, paid_date__range=(start, end)).aggregate(s=Sum('summa'))['s'] or 0
        student_count = User.objects.filter(center=center, role='student', is_archived=False).count()
        leads_count = Lead.objects.filter(center=center, is_archived=False, qoshilgan_sana__date__range=(start, end)).count()

        targets = {'income': 50000000, 'students': 300, 'leads': 150}
        
        calc = lambda cur, tar: {'target': tar, 'current': int(cur), 'pct': min(round((cur/tar)*100), 100), 'rem': max(tar-int(cur), 0)}

        return {
            'finance': calc(total_income, targets['income']),
            'students': calc(student_count, targets['students']),
            'marketing': calc(leads_count, targets['leads']),
        }

    def get_chart_data(self, center, period, start, end):
        now = timezone.localtime(timezone.now()).date()
        uz_months = {1: 'Yanvar', 2: 'Fevral', 3: 'Mart', 4: 'Aprel', 5: 'May', 6: 'Iyun', 7: 'Iyul', 8: 'Avgust', 9: 'Sentabr', 10: 'Oktabr', 11: 'Noyabr', 12: 'Dekabr'}
        
        from education.models import TuitionMonth, PaymentAllocation
        from education.services.tuition import tuition_month_fee_field
        from django.db.models.functions import Coalesce
        from django.db import models
        import calendar
        from datetime import date
        
        fee_field = tuition_month_fee_field()
        
        # ✅ [FIX] Force 12 months display for the selected year
        year = start.year
        months_to_query = [(m, year) for m in range(1, 13)]
        
        # Pre-aggregate monthly stats for the entire year
        agg_start = date(year, 1, 1)
        agg_end = date(year, 12, 31)

        labels = []
        income = []
        expenses = []
        debt_series = []
        new_students = []
        income_students = []
        debt_students = []

        income_rows = (
            Payment.objects
            .filter(center=center, paid_date__range=(agg_start, agg_end))
            .annotate(y=ExtractYear("paid_date"), m=ExtractMonth("paid_date"))
            .values("y", "m")
            .annotate(total=Sum("summa"), students=Count("student", distinct=True))
        )
        income_map = {(r["y"], r["m"]): int(r["total"] or 0) for r in income_rows}
        income_students_map = {(r["y"], r["m"]): int(r["students"] or 0) for r in income_rows}

        expense_rows = (
            Expense.objects
            .filter(center=center, sana__date__range=(agg_start, agg_end))
            .annotate(y=ExtractYear("sana"), m=ExtractMonth("sana"))
            .values("y", "m")
            .annotate(total=Sum("summa"))
        )
        expense_map = {(r["y"], r["m"]): int(r["total"] or 0) for r in expense_rows}

        new_students_rows = (
            User.objects
            .filter(
                center=center,
                role="student",
                is_archived=False,
                date_joined__date__range=(agg_start, agg_end),
            )
            .annotate(y=ExtractYear("date_joined"), m=ExtractMonth("date_joined"))
            .values("y", "m")
            .annotate(total=Count("id"))
        )
        new_students_map = {(r["y"], r["m"]): int(r["total"] or 0) for r in new_students_rows}
        
        for m, y in months_to_query:
            labels.append(f"{uz_months[m]} {y}" if y != now.year else uz_months[m])

            inc = income_map.get((y, m), 0)
            exp = expense_map.get((y, m), 0)
            
            from django.db.models import OuterRef, Subquery, IntegerField
            from datetime import date as _date
            
            # ✅ [FIX] Only for that specific month
            month_first = _date(y, m, 1)
            total_fee_sub = TuitionMonth.objects.filter(
                enrollment=OuterRef("pk"), month=month_first
            ).values("enrollment").annotate(s=Sum(fee_field)).values("s")

            total_paid_sub = PaymentAllocation.objects.filter(
                tuition_month__enrollment=OuterRef("pk"),
                tuition_month__month=month_first
            ).values("tuition_month__enrollment").annotate(s=Sum("amount")).values("s")

            center_qs = Enrollment.objects.filter(
                is_active=True, student__is_archived=False,
                center=center, group__is_archived=False
            )
            
            calculated_qs = center_qs.annotate(
                f=Coalesce(Subquery(total_fee_sub, output_field=IntegerField()), 0),
                p=Coalesce(Subquery(total_paid_sub, output_field=IntegerField()), 0)
            ).annotate(d=F("f")-F("p"))
            
            m_debt = calculated_qs.filter(d__gt=0).aggregate(total=Sum("d"))["total"] or 0
            m_debt_st = calculated_qs.filter(d__gt=0).values('student').distinct().count()
            
            inc_st = income_students_map.get((y, m), 0)
            new_st = new_students_map.get((y, m), 0)
            
            income.append(int(inc))
            expenses.append(int(exp))
            debt_series.append(int(m_debt))
            new_students.append(new_st)
            income_students.append(inc_st)
            debt_students.append(m_debt_st)
            
        mkt = self.get_marketing_stats(center, start, end)
        return {
            'labels': labels,
            'income': income,
            'expenses': expenses,
            'debt_series': debt_series,
            'new_students': new_students,
            'income_students': income_students,
            'debt_students': debt_students,
            'marketing': mkt
        }

class StudentChartAPIView(View):
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or getattr(request.user, 'role', None) in ('director', 'manager')):
            return JsonResponse({'error': 'Permission denied'}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        try:
            center = getattr(request, 'center', None) or request.user.center
            if not center:
                return JsonResponse({'error': 'Center not found'}, status=404)

            year_str = request.GET.get('year', '')
            try:
                year = int(year_str)
            except ValueError:
                year = timezone.localtime(timezone.now()).year

            cache_key = f"student_chart:v2:center:{center.id}:year:{year}"
            cached_payload = cache.get(cache_key)
            if cached_payload is not None:
                return JsonResponse(cached_payload)

            uz_months = {1: 'Yanvar', 2: 'Fevral', 3: 'Mart', 4: 'Aprel', 5: 'May', 6: 'Iyun', 
                         7: 'Iyul', 8: 'Avgust', 9: 'Sentabr', 10: 'Oktabr', 11: 'Noyabr', 12: 'Dekabr'}
            
            labels = []
            new_students = []

            monthly_counts = (
                User.objects
                .filter(center=center, role='student', is_archived=False, date_joined__year=year)
                .annotate(month=ExtractMonth('date_joined'))
                .values('month')
                .annotate(total=Count('id'))
            )
            month_map = {row['month']: row['total'] for row in monthly_counts}

            for m in range(1, 13):
                labels.append(uz_months[m])
                new_students.append(int(month_map.get(m, 0)))

            payload = {
                'labels': labels,
                'new_students': new_students
            }
            cache.set(cache_key, payload, timeout=300)
            return JsonResponse(payload)
        except Exception as e:
            import traceback
            logger.error(traceback.format_exc())
            return JsonResponse({'error': str(e)}, status=500)
