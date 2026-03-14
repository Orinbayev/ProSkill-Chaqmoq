from django.utils import timezone
from education.models import (
    Group, Enrollment, Attendance, StudentGroupHistory, 
    FinancialMonth, MonthlyFinanceSnapshot, TeacherSalarySnapshot, TeacherIncome
)
from django.db.models import Q, Sum, Count
from datetime import date
import json

class HistoricalFinanceService:
    @staticmethod
    def calculate_teacher_salary(teacher, year, month, center=None):
        from education.models import Attendance, Group, FinancialMonth, TeacherSalarySnapshot
        from django.db.models import Count, Q
        
        # Snapshot tekshiruvi (Oyni yopilgan bo'lsa qotib qolgan ma'lumot)
        fin_month = FinancialMonth.objects.filter(year=year, month=month, is_closed=True)
        if center:
            fin_month = fin_month.filter(center=center)
        fin_month = fin_month.first()
        
        if fin_month:
            snap = TeacherSalarySnapshot.objects.filter(teacher=teacher, financial_month=fin_month).first()
            if snap:
                details_val = snap.details or {}
                breakdown = details_val.get('breakdown', []) if isinstance(details_val, dict) else (details_val if isinstance(details_val, list) else [])
                daily_breakdown = details_val.get('daily_breakdown', [0]*31) if isinstance(details_val, dict) else [0]*31
                
                return {
                    'salary': snap.salary,
                    'attendance_count': snap.attendance_count,
                    'details': breakdown,
                    'daily_breakdown': daily_breakdown,
                    'is_locked': True
                }
            else:
                return {
                    'salary': 0, 'attendance_count': 0, 'details': [], 'daily_breakdown': [0]*31, 'is_locked': True
                }

        groups = Group.objects.filter(oqituvchi=teacher, is_archived=False).prefetch_related('enrollments__student')
        if center:
            groups = groups.filter(center=center)
            
        atts = Attendance.objects.filter(
            group__in=groups,
            date__year=year,
            date__month=month
        ).filter(Q(present=True) | Q(forced=True)).values(
            'group_id', 'student_id', 'date__day'
        )
        
        att_lookup = {}
        for a in atts:
            gid = a['group_id']
            sid = a['student_id']
            day = a['date__day']
            if gid not in att_lookup:
                att_lookup[gid] = {}
            if sid not in att_lookup[gid]:
                att_lookup[gid][sid] = []
            att_lookup[gid][sid].append(day)
            
        total_salary = 0
        total_turnover = 0
        total_center_profit = 0
        total_lessons = 0
        details_map = {}
        daily_breakdown = [0] * 31
        
        for g in groups:
            oy_dars_soni = g.oy_dars_soni or 12
            if oy_dars_soni <= 0: oy_dars_soni = 12
            
            for enr in g.enrollments.all():
                sid = enr.student_id
                days = att_lookup.get(g.id, {}).get(sid, [])
                
                if not days and not enr.is_active:
                    continue
                
                c = len(days)
                
                foiz = getattr(teacher, 'oqituvchi_foizi', 0)
                if not foiz:
                    foiz = enr.oqituvchi_foiz
                    
                k = enr.kurs_narhi or 0
                if k > 0 and foiz > 0:
                    amount = round((k / oy_dars_soni) * (foiz / 100))
                    center_amount = round((k / oy_dars_soni) * ((100 - foiz) / 100))
                    turnover_amount = round(k / oy_dars_soni)
                else:
                    amount = 0
                    center_amount = 0
                    turnover_amount = 0
                    
                if c > 0:
                    total_salary += amount * c
                    total_turnover += turnover_amount * c
                    total_center_profit += center_amount * c
                    total_lessons += c
                    
                    gid = g.id
                    if gid not in details_map:
                        details_map[gid] = {
                            'group_id': gid,
                            'group_name': g.nom,
                            'salary': 0,
                            'center_profit': 0,
                            'turnover': 0,
                            'attendance': 0,
                            'is_lead': True,
                            'fi': g.oqituvchi_foiz,
                            'enrollments': []
                        }
                    details_map[gid]['salary'] += amount * c
                    details_map[gid]['center_profit'] += center_amount * c
                    details_map[gid]['turnover'] += turnover_amount * c
                    details_map[gid]['attendance'] += c
                    details_map[gid]['enrollments'].append({
                        'student_id': sid,
                        'student_name': enr.student.get_full_name() or enr.student.email,
                        'kurs_narhi': k,
                        'foiz': foiz,
                        'attended': c,
                        'daromad': amount * c,
                        'markaz_foyda': center_amount * c
                    })
                    
                    for day in days:
                        day_idx = day - 1
                        if 0 <= day_idx < 31:
                            daily_breakdown[day_idx] += amount
                            
        details = list(details_map.values())
        return {
            'salary': round(total_salary),
            'center_profit': round(total_center_profit),
            'turnover': round(total_turnover),
            'attendance_count': total_lessons,
            'details': details,
            'daily_breakdown': daily_breakdown,
            'is_locked': False
        }

    @staticmethod
    def get_yearly_teacher_salary(teacher, year, center=None):
        stats = HistoricalFinanceService.get_yearly_teacher_stats(teacher, year, center)
        return [s['salary'] for s in stats]

    @staticmethod
    def get_yearly_teacher_stats(teacher, year, center=None):
        results = [{'salary': 0, 'center_profit': 0, 'turnover': 0, 'lessons': 0} for _ in range(12)]
        
        from education.models import Attendance, Group, FinancialMonth, TeacherSalarySnapshot
        from django.db.models import Count, Q
        
        # Snapshotlarni tekshiramiz (yopilgan oylar)
        fin_months = FinancialMonth.objects.filter(year=year, is_closed=True)
        if center:
            fin_months = fin_months.filter(center=center)
            
        closed_months_ids = fin_months.values_list('id', flat=True)
        closed_months_map = {fm.month: fm for fm in fin_months}
        
        if closed_months_ids:
            snaps = TeacherSalarySnapshot.objects.filter(
                teacher=teacher, 
                financial_month__in=closed_months_ids
            ).select_related('financial_month')
            
            for snap in snaps:
                m = snap.financial_month.month
                if 1 <= m <= 12:
                    details = []
                    if isinstance(snap.details, dict):
                        details = snap.details.get('breakdown', [])
                    elif isinstance(snap.details, list):
                        details = snap.details
                        
                    snap_turnover = sum(d.get('turnover', 0) for d in details if isinstance(d, dict))
                    snap_center_profit = sum(d.get('center_profit', 0) for d in details if isinstance(d, dict))
                    
                    results[m-1]['salary'] = snap.salary
                    results[m-1]['lessons'] = snap.attendance_count
                    results[m-1]['turnover'] = snap_turnover
                    results[m-1]['center_profit'] = snap_center_profit
                    
        groups = Group.objects.filter(oqituvchi=teacher, is_archived=False).prefetch_related('enrollments__student')
        if center:
            groups = groups.filter(center=center)
            
        att_counts = Attendance.objects.filter(
            group__in=groups,
            date__year=year
        ).filter(Q(present=True) | Q(forced=True)).values(
            'group_id', 'student_id', 'date__month'
        ).annotate(count=Count('id'))
        
        att_lookup = {}
        for ac in att_counts:
            gid = ac['group_id']
            sid = ac['student_id']
            m = ac['date__month']
            if gid not in att_lookup:
                att_lookup[gid] = {}
            if sid not in att_lookup[gid]:
                att_lookup[gid][sid] = {}
            att_lookup[gid][sid][m] = ac['count']
            
        for g in groups:
            oy_dars_soni = g.oy_dars_soni or 12
            if oy_dars_soni <= 0: oy_dars_soni = 12
            
            for enr in g.enrollments.all():
                sid = enr.student_id
                month_counts = att_lookup.get(g.id, {}).get(sid, {})
                
                if not month_counts and not enr.is_active:
                    continue
                    
                foiz = getattr(teacher, 'oqituvchi_foizi', 0)
                if not foiz:
                    foiz = enr.oqituvchi_foiz
                    
                k = enr.kurs_narhi or 0
                if k > 0 and foiz > 0:
                    amount_per_lesson = round((k / oy_dars_soni) * (foiz / 100))
                    center_per_lesson = round((k / oy_dars_soni) * ((100 - foiz) / 100))
                    turnover_per_lesson = round((k / oy_dars_soni))
                else:
                    amount_per_lesson = 0
                    center_per_lesson = 0
                    turnover_per_lesson = 0
                
                for m, count in month_counts.items():
                    if 1 <= m <= 12 and m not in closed_months_map:
                        results[m-1]['salary'] += amount_per_lesson * count
                        results[m-1]['center_profit'] += center_per_lesson * count
                        results[m-1]['turnover'] += turnover_per_lesson * count
                        results[m-1]['lessons'] += count
                        
        return results

    @staticmethod
    def close_month(center, year, month, user):
        """Locks a financial month and creates snapshots."""
        from education.models import FinancialMonth, TeacherSalarySnapshot
        from django.contrib.auth import get_user_model
        
        fin_month, created = FinancialMonth.objects.get_or_create(
            center=center, year=year, month=month,
            defaults={'is_closed': True, 'closed_at': timezone.now(), 'closed_by': user}
        )
        if not created and fin_month.is_closed:
            return fin_month
            
        fin_month.is_closed = True
        fin_month.closed_at = timezone.now()
        fin_month.closed_by = user
        fin_month.save()

        User = get_user_model()
        teachers = User.objects.filter(role="teacher", is_archived=False)
        if center:
            teachers = teachers.filter(center=center)
        
        for teacher in teachers:
            # We must calculate dynamically since fin_month is NOW True, but calculate_teacher_salary 
            # might return the CURRENT snapshot if we don't bypass. 
            # We'll temporarily set it False to calculate, or just bypass snapshot check here
            # Bypass logic by not passing center/running directly:
            # wait, calculate_teacher_salary checks fin_month directly. 
            fin_month.is_closed = False
            fin_month.save()
            
            salary_data = HistoricalFinanceService.calculate_teacher_salary(teacher, year, month, center)
            full_details = {
                'breakdown': salary_data['details'],
                'daily_breakdown': salary_data['daily_breakdown']
            }
            fin_month.is_closed = True
            fin_month.save()
            
            TeacherSalarySnapshot.objects.update_or_create(
                teacher=teacher, financial_month=fin_month,
                defaults={
                    'salary': salary_data['salary'],
                    'attendance_count': salary_data['attendance_count'],
                    'details': full_details
                }
            )
        return fin_month

    @staticmethod
    def open_month(center, year, month, user):
        """Unlocks a financial month and deletes its snapshots."""
        from education.models import FinancialMonth, TeacherSalarySnapshot
        fin_month = FinancialMonth.objects.filter(center=center, year=year, month=month).first()
        if fin_month:
            TeacherSalarySnapshot.objects.filter(financial_month=fin_month).delete()
            fin_month.is_closed = False
            fin_month.save()
        return fin_month
