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
        """
        O'qituvchi oyligini TeacherIncome jadvalidan hisoblab beradi.
        """
        income_qs = TeacherIncome.objects.filter(
            teacher=teacher,
            attendance__date__year=year,
            attendance__date__month=month
        )
        if center:
            income_qs = income_qs.filter(center=center)
            
        aggregated = income_qs.aggregate(
            salary=Sum('amount'),
            lessons=Count('id')
        )
        
        # Details (breakdown by group)
        details_qs = income_qs.values('group__id', 'group__nom').annotate(
            group_salary=Sum('amount'),
            group_attendance=Count('id')
        )
        
        details = []
        for d in details_qs:
            details.append({
                'group_id': d['group__id'],
                'group_name': d['group__nom'],
                'salary': d['group_salary'] or 0,
                'attendance': d['group_attendance'] or 0,
                'is_lead': True # Simplified
            })
            
        # Daily breakdown
        daily_qs = income_qs.values('attendance__date__day').annotate(day_salary=Sum('amount'))
        daily_breakdown = [0] * 31
        for d in daily_qs:
            day_idx = d['attendance__date__day'] - 1
            if 0 <= day_idx < 31:
                daily_breakdown[day_idx] = float(d['day_salary'] or 0)

        return {
            'salary': aggregated['salary'] or 0,
            'attendance_count': aggregated['lessons'] or 0,
            'details': details,
            'daily_breakdown': daily_breakdown,
            'is_locked': False
        }

    @staticmethod
    def get_yearly_teacher_salary(teacher, year, center=None):
        """
        O'qituvchining yillik oyliklarini list ko'rinishida qaytaradi (grafik uchun).
        """
        stats = HistoricalFinanceService.get_yearly_teacher_stats(teacher, year, center)
        return [s['salary'] for s in stats]
    @staticmethod
    def get_yearly_teacher_stats(teacher, year, center=None):
        """
        O'qituvchi va markaz statistikasini TeacherIncome jadvalidan oladi.
        Bu yagona to'g'ri manba hisoblanadi.
        """
        results = [{'salary': 0, 'center_profit': 0, 'turnover': 0, 'lessons': 0} for _ in range(12)]
        
        income_qs = TeacherIncome.objects.filter(
            teacher=teacher,
            attendance__date__year=year
        )
        if center:
            income_qs = income_qs.filter(center=center)
            
        aggregated = (
            income_qs
            .values('attendance__date__month')
            .annotate(
                total_salary=Sum('amount'),
                total_center=Sum('center_amount'),
                total_turnover=Sum('total_amount'),
                lesson_count=Count('id')
            )
        )
        
        for data in aggregated:
            m = data['attendance__date__month']
            if 1 <= m <= 12:
                results[m-1] = {
                    'salary': data['total_salary'] or 0,
                    'center_profit': data['total_center'] or 0,
                    'turnover': data['total_turnover'] or 0,
                    'lessons': data['lesson_count'] or 0
                }
            
        return results

    @staticmethod
    def close_month(center, year, month, user):
        """Locks a financial month and creates snapshots."""
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

        teachers_ids = TeacherIncome.objects.filter(center=center, attendance__date__year=year, attendance__date__month=month).values_list('teacher_id', flat=True).distinct()
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        for t_id in teachers_ids:
            teacher = User.objects.get(id=t_id)
            salary_data = HistoricalFinanceService.calculate_teacher_salary(teacher, year, month, center)
            full_details = {
                'breakdown': salary_data['details'],
                'daily_breakdown': salary_data['daily_breakdown']
            }
            TeacherSalarySnapshot.objects.update_or_create(
                teacher=teacher, financial_month=fin_month,
                defaults={
                    'salary': salary_data['salary'],
                    'attendance_count': salary_data['attendance_count'],
                    'details': full_details
                }
            )
        return fin_month
