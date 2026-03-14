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

        groups = Group.objects.filter(oqituvchi=teacher, is_archived=False)
        if center:
            groups = groups.filter(center=center)
        
        # Barcha enrollmentlarni olamiz (faol, nofaol, hatto soft-deleted ham)
        from django.db.models import Prefetch
        from datetime import date as date_cls
        import calendar
        groups = list(groups.prefetch_related(
            Prefetch(
                'enrollments',
                queryset=Enrollment.all_objects.filter().select_related('student'),
                to_attr='all_enrollments'
            )
        ))
            
        group_ids = [g.id for g in groups]
        
        # O'sha oy uchun sana oralig'ini aniqlaymiz
        month_start = date_cls(year, month, 1)
        month_end_day = calendar.monthrange(year, month)[1]
        month_end = date_cls(year, month, month_end_day)
        
        atts = Attendance.objects.filter(
            group_id__in=group_ids,
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
        
        # enr_lookup[group_id][student_id] = enrollment
        enr_lookup = {}
        for g in groups:
            enr_lookup[g.id] = {}
            for enr in g.all_enrollments:
                enr_lookup[g.id][enr.student_id] = enr
        
        # O'quvchining guruhda bo'lish tarixini olamiz
        # history_lookup[group_id][student_id] = [(start_date, end_date), ...]
        histories = StudentGroupHistory.objects.filter(
            group_id__in=group_ids
        ).values('group_id', 'student_id', 'start_date', 'end_date')
        
        history_lookup = {}
        for h in histories:
            gid = h['group_id']
            sid = h['student_id']
            if gid not in history_lookup:
                history_lookup[gid] = {}
            if sid not in history_lookup[gid]:
                history_lookup[gid][sid] = []
            history_lookup[gid][sid].append((h['start_date'], h['end_date']))
        
        def student_was_in_group(gid, sid, m_start, m_end):
            """O'quvchi o'sha oyda guruhda bo'lganligini tekshiradi."""
            for start, end in history_lookup.get(gid, {}).get(sid, []):
                # Tarix o'sha oydagi biror kunga to'g'ri kelishi kerak
                period_end = end if end else date_cls.today()
                if start <= m_end and period_end >= m_start:
                    return True
            return False
        
        total_salary = 0
        total_turnover = 0
        total_center_profit = 0
        total_lessons = 0
        details_map = {}
        daily_breakdown = [0] * 31
        
        for g in groups:
            oy_dars_soni = g.oy_dars_soni or 12
            if oy_dars_soni <= 0: oy_dars_soni = 12
            
            group_atts = att_lookup.get(g.id, {})
            
            for sid, days in group_atts.items():
                if not days:
                    continue
                
                # Enrollment ma'lumotlarini topamiz
                enr = enr_lookup.get(g.id, {}).get(sid)
                
                # Agar enrollment topilmasa — o'quvchi bu guruhga
                # rasman yozilmagan, uni hisoblamaymiz
                if enr is None:
                    continue
                
                # O'quvchi o'sha oyda guruhda bo'lganligini tekshiramiz
                # Bu "Mart qo'shilgan → Fevralda ko'rinmasin" muammosini hal qiladi
                group_has_history = bool(history_lookup.get(g.id, {}).get(sid))
                if group_has_history:
                    # Tarix bor — shu orqali tekshiramiz
                    if not student_was_in_group(g.id, sid, month_start, month_end):
                        continue
                else:
                    # Tarix yo'q — enrollment created_at dan foydalanamiz
                    enr_created = None
                    if hasattr(enr, 'created_at') and enr.created_at:
                        enr_created = enr.created_at.date() if hasattr(enr.created_at, 'date') else enr.created_at
                    if enr_created and enr_created > month_end:
                        continue
                
                foiz = getattr(teacher, 'oqituvchi_foizi', 0) or enr.oqituvchi_foiz or 0
                k = enr.kurs_narhi or 0
                
                c = len(days)
                
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
                    
                    try:
                        student_name = enr.student.get_full_name() or enr.student.email
                    except Exception:
                        student_name = 'Noma\'lum'
                    
                    details_map[gid]['enrollments'].append({
                        'student_id': sid,
                        'student_name': student_name,
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
                    
        groups = Group.objects.filter(oqituvchi=teacher, is_archived=False)
        if center:
            groups = groups.filter(center=center)
        
        # Barcha enrollmentlarni olamiz (faol, nofaol, hatto soft-deleted ham)
        from django.db.models import Prefetch
        groups = list(groups.prefetch_related(
            Prefetch(
                'enrollments',
                queryset=Enrollment.all_objects.filter().select_related('student'),
                to_attr='all_enrollments'
            )
        ))

        group_ids = [g.id for g in groups]
            
        att_counts = Attendance.objects.filter(
            group_id__in=group_ids,
            date__year=year
        ).filter(Q(present=True) | Q(forced=True)).values(
            'group_id', 'student_id', 'date__month'
        ).annotate(count=Count('id'))
        
        # att_lookup[group_id][student_id][month] = count
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
        
        # enr_lookup[group_id][student_id] = enrollment
        enr_lookup = {}
        for g in groups:
            enr_lookup[g.id] = {}
            for enr in g.all_enrollments:
                enr_lookup[g.id][enr.student_id] = enr
            
        for g in groups:
            oy_dars_soni = g.oy_dars_soni or 12
            if oy_dars_soni <= 0: oy_dars_soni = 12
            
            # Enrollment emas, DAVOMAT asosida aylanamiz
            for sid, month_counts in att_lookup.get(g.id, {}).items():
                if not month_counts:
                    continue
                
                # Enrollment ma'lumotlarini topamiz (narh va foiz uchun)
                enr = enr_lookup.get(g.id, {}).get(sid)
                if enr is None:
                    foiz = getattr(teacher, 'oqituvchi_foizi', 0) or g.oqituvchi_foiz or 0
                    k = g.kurs_narxi or 0
                else:
                    foiz = getattr(teacher, 'oqituvchi_foizi', 0) or enr.oqituvchi_foiz or 0
                    k = enr.kurs_narhi or 0

                if k > 0 and foiz > 0:
                    amount_per_lesson = round((k / oy_dars_soni) * (foiz / 100))
                    center_per_lesson = round((k / oy_dars_soni) * ((100 - foiz) / 100))
                    turnover_per_lesson = round(k / oy_dars_soni)
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
    def _calculate_salary_dynamic(teacher, year, month, center=None):
        """
        Snapshot tekshiruvisiz, to'g'ridan-to'g'ri davomat asosida hisoblaydi.
        close_month() ichida ishlatiladi — is_closed toggle qilish shart emas.
        Guruhdan chiqarilgan o'quvchilar uchun ham davomat hisoblanadi.
        """
        from education.models import Attendance, Group
        from django.db.models import Count, Q, Prefetch

        groups = Group.objects.filter(oqituvchi=teacher, is_archived=False)
        if center:
            groups = groups.filter(center=center)

        groups = groups.prefetch_related(
            Prefetch(
                'enrollments',
                queryset=Enrollment.objects.filter(is_deleted=False).select_related('student'),
                to_attr='all_enrollments'
            )
        )

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
            if oy_dars_soni <= 0:
                oy_dars_soni = 12

            for enr in g.all_enrollments:
                sid = enr.student_id
                days = att_lookup.get(g.id, {}).get(sid, [])

                if not days:
                    continue

                c = len(days)
                foiz = getattr(teacher, 'oqituvchi_foizi', 0) or enr.oqituvchi_foiz
                k = enr.kurs_narhi or 0

                if k > 0 and foiz > 0:
                    amount = round((k / oy_dars_soni) * (foiz / 100))
                    center_amount = round((k / oy_dars_soni) * ((100 - foiz) / 100))
                    turnover_amount = round(k / oy_dars_soni)
                else:
                    amount = center_amount = turnover_amount = 0

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
                        idx = day - 1
                        if 0 <= idx < 31:
                            daily_breakdown[idx] += amount

        return {
            'salary': round(total_salary),
            'center_profit': round(total_center_profit),
            'turnover': round(total_turnover),
            'attendance_count': total_lessons,
            'details': list(details_map.values()),
            'daily_breakdown': daily_breakdown,
        }

    @staticmethod
    def close_month(center, year, month, user):
        """Locks a financial month and creates snapshots."""
        from education.models import FinancialMonth, TeacherSalarySnapshot
        from django.contrib.auth import get_user_model

        fin_month, created = FinancialMonth.objects.get_or_create(
            center=center, year=year, month=month,
            defaults={'is_closed': False}
        )
        if not created and fin_month.is_closed:
            return fin_month

        # Avval barcha o'qituvchilar uchun joriy oylik hisoblovi saqlaymiz
        User = get_user_model()
        teachers = User.objects.filter(role="teacher", is_archived=False)
        if center:
            teachers = teachers.filter(center=center)

        snapshots = []
        for teacher in teachers:
            # Snapshot check bypass qilinadi — to'g'ridan-to'g'ri davomat hisoblanadi
            salary_data = HistoricalFinanceService._calculate_salary_dynamic(
                teacher, year, month, center
            )
            full_details = {
                'breakdown': salary_data['details'],
                'daily_breakdown': salary_data['daily_breakdown']
            }
            snapshots.append((teacher, salary_data, full_details))

        # Hamma hisob-kitob bitgandan keyin oyni yopamiz
        fin_month.is_closed = True
        fin_month.closed_at = timezone.now()
        fin_month.closed_by = user
        fin_month.save()

        # Snapshotlarni saqlaymiz
        for teacher, salary_data, full_details in snapshots:
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

