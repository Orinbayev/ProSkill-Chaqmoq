from django.utils import timezone
from education.models import (
    Group, Enrollment, Attendance, StudentGroupHistory, 
    FinancialMonth, MonthlyFinanceSnapshot, TeacherSalarySnapshot
)
from django.db.models import Q, Sum
from datetime import date
import json

class HistoricalFinanceService:
    @staticmethod
    def get_student_membership_period(student, group, year, month):
        """Returns the start and end dates of a student's membership in a group for a specific month."""
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1)
        else:
            month_end = date(year, month + 1, 1)
        
        histories = StudentGroupHistory.objects.filter(
            student=student, 
            group=group,
            start_date__lt=month_end
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=month_start)
        )
        
        # In case of multiple memberships in one month (though rare), we might need to handle it.
        # For simplicity, we'll return the periods that overlap with the requested month.
        membership_periods = []
        for h in histories:
            actual_start = max(h.start_date, month_start)
            actual_end = min(h.end_date, month_end) if h.end_date else month_end
            membership_periods.append({
                'start': actual_start,
                'end': actual_end,
                'kurs_narxi': h.kurs_narxi,
                'oqituvchi_foiz': h.oqituvchi_foiz
            })
        return membership_periods

    @staticmethod
    def calculate_teacher_salary(teacher, year, month, center=None):
        """Calculates teacher salary for a specific month, using snapshots if the month is closed."""
        fin_month = FinancialMonth.objects.filter(center=center, year=year, month=month).first()
        
        if fin_month and fin_month.is_closed:
            snapshot = TeacherSalarySnapshot.objects.filter(teacher=teacher, financial_month=fin_month).first()
            if snapshot:
                details_data = snapshot.details
                daily_breakdown = [0] * 31
                actual_details = details_data
                
                if isinstance(details_data, dict):
                    actual_details = details_data.get('breakdown', [])
                    daily_breakdown = details_data.get('daily_breakdown', [0] * 31)
                
                return {
                    'salary': snapshot.salary,
                    'attendance_count': snapshot.attendance_count,
                    'details': actual_details,
                    'daily_breakdown': daily_breakdown,
                    'is_locked': True
                }

        # Dynamic calculation
        total_salary = 0
        total_attendance = 0
        details = []
        daily_breakdown = [0] * 31 # Support up to 31 days

        # Find all groups where the teacher is lead OR has taken attendance
        lead_group_ids = list(Group.objects.filter(oqituvchi=teacher).values_list('id', flat=True))
        att_group_ids = list(Attendance.objects.filter(
            teacher=teacher, 
            date__year=year, 
            date__month=month
        ).values_list('group_id', flat=True).distinct())
        
        all_group_ids = set(lead_group_ids) | set(att_group_ids)
        groups = Group.objects.filter(id__in=all_group_ids)
        if center:
            groups = groups.filter(center=center)

        # Pre-fetch all relevant memberships for this month for all groups involved
        membership_qs = StudentGroupHistory.objects.filter(
            group_id__in=all_group_ids,
            start_date__lt=date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=date(year, month, 1))
        ).select_related('group')
        
        # Build an easy lookup map: (group_id, student_id, date) -> membership info
        # Since membership can overlap, we'll check date ranges in memory
        membership_map = {} # group_id -> list of memberships
        for m in membership_qs:
            if m.group_id not in membership_map:
                membership_map[m.group_id] = []
            membership_map[m.group_id].append(m)

        for group in groups:
            # Determine which attendances this teacher gets paid for in this group
            group_atts_qs = Attendance.objects.filter(
                group=group,
                date__year=year,
                date__month=month
            ).filter(Q(present=True) | Q(forced=True))
            
            if group.oqituvchi != teacher:
                # Substitute teacher gets paid only for lessons they actually taught
                group_atts_qs = group_atts_qs.filter(teacher=teacher)
            
            group_salary = 0
            group_attendance = group_atts_qs.count()
            
            if group_attendance == 0 and group.oqituvchi != teacher:
                continue

            # Optimize further: get all atts for this group in memory
            group_atts = list(group_atts_qs)
            
            for att in group_atts:
                # Find corresponding historical membership in memory 
                # (usually just 1 m per student, but we check date range)
                possible_memberships = membership_map.get(group.id, [])
                h = None
                for m in possible_memberships:
                    if m.student_id == att.student_id and m.start_date <= att.date and (not m.end_date or m.end_date >= att.date):
                        h = m
                        break
                
                if h:
                    oy_dars_soni = h.group.oy_dars_soni or 12
                    share = (h.kurs_narxi * h.oqituvchi_foiz / 100) / oy_dars_soni
                    group_salary += float(share)
                    daily_breakdown[att.date.day - 1] += float(share)
                else:
                    # Fallback to group current rates if history record is missing
                    oy_dars_soni = group.oy_dars_soni or 12
                    share = (group.kurs_narxi * group.oqituvchi_foiz / 100) / oy_dars_soni
                    group_salary += float(share)
                    daily_breakdown[att.date.day - 1] += float(share)

            if round(group_salary) > 0 or group_attendance > 0:
                total_salary += round(group_salary)
                total_attendance += group_attendance
                details.append({
                    'group_id': group.id,
                    'group_name': group.nom,
                    'salary': round(group_salary),
                    'attendance': group_attendance,
                    'is_lead': group.oqituvchi == teacher
                })

        return {
            'salary': total_salary,
            'attendance_count': total_attendance,
            'details': details,
            'daily_breakdown': daily_breakdown,
            'is_locked': False
        }
    
    @staticmethod
    def get_yearly_teacher_salary(teacher, year, center=None):
        """Ultra-fast yearly stats using bulk queries for all 12 months in one go."""
        results = [0] * 12
        today = date.today()
        
        # 1. Fetch locked months from snapshots
        snaps = TeacherSalarySnapshot.objects.filter(
            teacher=teacher, financial_month__year=year, financial_month__is_closed=True
        ).select_related('financial_month')
        
        locked_months = set()
        for s in snaps:
            m = s.financial_month.month
            results[m-1] = float(s.salary)
            locked_months.add(m)
            
        # 2. Identify open months that need dynamic calculation
        unlocked_months = [m for m in range(1, 13) if m not in locked_months and (year < today.year or (year == today.year and m <= today.month))]
        
        if not unlocked_months:
            return results

        # 3. Bulk fetch data for all unlocked months at once
        start_bound = date(year, min(unlocked_months), 1)
        end_bound = date(year + 1, 1, 1) if max(unlocked_months) == 12 else date(year, max(unlocked_months) + 1, 1)
        
        # All relevant attendances for the year (open months)
        all_atts = Attendance.objects.filter(
            Q(teacher=teacher) | Q(group__oqituvchi=teacher),
            date__gte=start_bound,
            date__lt=end_bound
        ).filter(Q(present=True) | Q(forced=True)).select_related('group')
        
        # All relevant histories
        all_histories = StudentGroupHistory.objects.filter(
            Q(group__oqituvchi=teacher) | Q(group__in=all_atts.values_list('group_id', flat=True)),
            start_date__lt=end_bound
        ).filter(Q(end_date__isnull=True) | Q(end_date__gte=start_bound)).select_related('group')
        
        # Organize histories by group
        hist_map = {}
        for h in all_histories:
            if h.group_id not in hist_map: hist_map[h.group_id] = []
            hist_map[h.group_id].append(h)
            
        # Group attendances by month
        monthly_atts = {} # month -> list of atts
        for a in all_atts:
            m = a.date.month
            if m not in monthly_atts: monthly_atts[m] = []
            monthly_atts[m].append(a)
            
        # 4. Process each month in memory
        for m in unlocked_months:
            month_salary = 0
            month_atts = monthly_atts.get(m, [])
            
            for att in month_atts:
                # Basic rule: Pay lead teacher always, pay substitute only if it's them
                is_lead = (att.group.oqituvchi_id == teacher.id)
                if not is_lead and att.teacher_id != teacher.id:
                    continue
                
                # Find history record
                h = None
                for candidate in hist_map.get(att.group_id, []):
                    if candidate.student_id == att.student_id and candidate.start_date <= att.date and (not candidate.end_date or candidate.end_date >= att.date):
                        h = candidate
                        break
                
                if h:
                    share = (h.kurs_narxi * h.oqituvchi_foiz / 100) / (h.group.oy_dars_soni or 12)
                    month_salary += float(share)
                else:
                    share = (att.group.kurs_narxi * att.group.oqituvchi_foiz / 100) / (att.group.oy_dars_soni or 12)
                    month_salary += float(share)
            
            results[m-1] = round(month_salary)
            
        return results

    @staticmethod
    def get_yearly_teacher_stats(teacher, year, center=None):
        """Returns complex stats [{salary, center_profit, turnover, lessons}] per month."""
        results = [{'salary': 0, 'center_profit': 0, 'turnover': 0, 'lessons': 0} for _ in range(12)]
        today = date.today()
        
        # 1. Fetch locked months from snapshots
        snaps = TeacherSalarySnapshot.objects.filter(
            teacher=teacher, financial_month__year=year, financial_month__is_closed=True
        ).select_related('financial_month')
        
        locked_months = set()
        for s in snaps:
            m = s.financial_month.month
            # Center profit and turnover aren't in snapshot natively, we can approximate or return 0
            # A full system would have them in the snapshot. For now, we estimate center profit.
            results[m-1] = {
                'salary': float(s.salary),
                'center_profit': 0, # Since we didn't store it
                'turnover': 0,
                'lessons': s.attendance_count
            }
            locked_months.add(m)
            
        unlocked_months = [m for m in range(1, 13) if m not in locked_months and (year < today.year or (year == today.year and m <= today.month))]
        
        if not unlocked_months:
            return results

        start_bound = date(year, min(unlocked_months), 1)
        end_bound = date(year + 1, 1, 1) if max(unlocked_months) == 12 else date(year, max(unlocked_months) + 1, 1)
        
        all_atts = Attendance.objects.filter(
            Q(teacher=teacher) | Q(group__oqituvchi=teacher),
            date__gte=start_bound,
            date__lt=end_bound
        ).filter(Q(present=True) | Q(forced=True)).select_related('group')
        
        if center:
            all_atts = all_atts.filter(group__center=center)
            
        all_histories = StudentGroupHistory.objects.filter(
            Q(group__oqituvchi=teacher) | Q(group__in=all_atts.values_list('group_id', flat=True)),
            start_date__lt=end_bound
        ).filter(Q(end_date__isnull=True) | Q(end_date__gte=start_bound)).select_related('group')
        
        hist_map = {}
        for h in all_histories:
            if h.group_id not in hist_map: hist_map[h.group_id] = []
            hist_map[h.group_id].append(h)
            
        monthly_atts = {}
        for a in all_atts:
            m = a.date.month
            if m not in monthly_atts: monthly_atts[m] = []
            monthly_atts[m].append(a)
            
        for m in unlocked_months:
            m_salary = 0
            m_center_profit = 0
            m_turnover = 0
            month_atts = monthly_atts.get(m, [])
            m_lessons = len(month_atts)
            
            for att in month_atts:
                is_lead = (att.group.oqituvchi_id == teacher.id)
                if not is_lead and att.teacher_id != teacher.id:
                    continue
                
                h = None
                for candidate in hist_map.get(att.group_id, []):
                    if candidate.student_id == att.student_id and candidate.start_date <= att.date and (not candidate.end_date or candidate.end_date >= att.date):
                        h = candidate
                        break
                
                if h:
                    oy_dars_soni = h.group.oy_dars_soni or 12
                    share = (h.kurs_narxi * h.oqituvchi_foiz / 100) / oy_dars_soni
                    cp = (h.kurs_narxi * (100 - h.oqituvchi_foiz) / 100) / oy_dars_soni
                    turn = h.kurs_narxi / oy_dars_soni
                else:
                    oy_dars_soni = att.group.oy_dars_soni or 12
                    share = (att.group.kurs_narxi * att.group.oqituvchi_foiz / 100) / oy_dars_soni
                    cp = (att.group.kurs_narxi * (100 - att.group.oqituvchi_foiz) / 100) / oy_dars_soni
                    turn = att.group.kurs_narxi / oy_dars_soni
                    
                m_salary += float(share)
                # O'qituvchining asosiy guruhidagina markaz foydasini yozamiz
                if is_lead:
                    m_center_profit += float(cp)
                    m_turnover += float(turn)
            
            results[m-1] = {
                'salary': round(m_salary),
                'center_profit': round(m_center_profit),
                'turnover': round(m_turnover),
                'lessons': m_lessons
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
            return fin_month # Already closed

        fin_month.is_closed = True
        fin_month.closed_at = timezone.now()
        fin_month.closed_by = user
        fin_month.save()

        # Create snapshots for all teachers in this center
        teachers = Group.objects.filter(center=center).values_list('oqituvchi', flat=True).distinct()
        for teacher_id in teachers:
            if not teacher_id: continue
            from django.contrib.auth import get_user_model
            User = get_user_model()
            teacher = User.objects.get(id=teacher_id)
            # Create/Update snapshot
            salary_data = HistoricalFinanceService.calculate_teacher_salary(teacher, year, month, center)
            # Store daily_breakdown inside details for snapshot storage
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
            
        # Center snapshot
        # (Simplified: just sum of teacher salaries and income)
        # In a real system you'd sum up all payments and expenses
        MonthlyFinanceSnapshot.objects.create(
            financial_month=fin_month,
            # Placeholder values - would need more complex logic to get real totals
            total_income=0, 
            total_expense=0,
            center_profit=0,
            student_count=0
        )
        
        return fin_month
