from django.db.models import F, Sum, Count, Q
from django.contrib.auth import get_user_model
from django.utils import timezone
from education.models import Group, Enrollment, TeacherExpectedIncomeSnapshot

User = get_user_model()

def calculate_expected_income(teacher, year=None, month=None, center=None, course_id=None):
    """
    Seniorshunoslik uslubida sof biznes logika.
    Har bir aktiv guruhdagi aktiv o'quvchilardan
    o'qituvchiga tushishi kerak bo'lgan sof ulush.
    """
    now = timezone.now()
    req_year = int(year) if year else now.year
    req_month = int(month) if month else now.month
    
    # 0. Agar so'ralgan oy - o'tib ketgan eski oy bo'lsa va snapshot bor bo'lsa (faqat kurs obyekti bo'lmaganda filterlanyapti deb faraz qilamiz)
    if not course_id:
        snapshot = TeacherExpectedIncomeSnapshot.objects.filter(
            teacher=teacher, year=req_year, month=req_month, center=center
        ).first()
        
        # O'tgan oy (yoki joriy oy bo'lmasa qat'iy) va snapshot topilsa saqlanganni qaytaramiz!
        if snapshot and (req_year < now.year or (req_year == now.year and req_month < now.month)):
            return {
                "teacher_id": teacher.id,
                "teacher_name": teacher.ism or teacher.email,
                "active_students": snapshot.active_students,
                "income_per_student": snapshot.income_per_student,
                "expected_income": snapshot.expected_income,
                "breakdown": [] # Breakdown o'tgan oylar uchun optional qilib qo'yamiz yoki alohida model kerak
            }

    # 1. Faqat aktiv guruhlarni olish (is_archived=False)
    groups = Group.objects.filter(oqituvchi=teacher, is_archived=False)
    
    if center:
        groups = groups.filter(center=center)
        
    if course_id:
        groups = groups.filter(category_obj_id=course_id)
        
    total_expected_income = 0
    total_active_students = 0
    breakdown = []
    
    for group in groups:
        # Har bir guruh uchun faqat aktiv o'quvchilarni olish
        active_enrollments = Enrollment.objects.filter(
            group=group, 
            is_active=True
        )
        
        student_count = active_enrollments.count()
        if student_count == 0:
            continue
            
        # O'qituvchi ulushini hisoblash 
        # (ChaqmoqApp da foiz va narx asosan Enrollment ga yoki Group ga bog'langan bo'ladi)
        # Guruhning o'zidan olamiz (Agar foizli bo'lsa)
        monthly_fee = group.kurs_narxi or 0
        teacher_percent = group.oqituvchi_foiz or 0
        
        income_per_student = (monthly_fee * teacher_percent) / 100
        
        group_expected_income = student_count * income_per_student
        
        total_expected_income += group_expected_income
        total_active_students += student_count
        
        breakdown.append({
            "group_name": group.nom,
            "students": student_count,
            "per_student_income": income_per_student,
            "group_total": group_expected_income
        })

    
    income_per_student = total_expected_income / total_active_students if total_active_students > 0 else 0
    
    # Snapshot saqlash yoxud yangilash logikasi faqat joriy yoki yangi oylarni tekshirayotganda va global ko'rganda (kurs filterisiz)
    if not course_id and (req_year == now.year and req_month == now.month):
        TeacherExpectedIncomeSnapshot.objects.update_or_create(
            teacher=teacher,
            year=req_year,
            month=req_month,
            center=center,
            defaults={
                'active_students': total_active_students,
                'expected_income': total_expected_income,
                'income_per_student': income_per_student
            }
        )

    return {
        "teacher_id": teacher.id,
        "teacher_name": teacher.ism or teacher.email,
        "active_students": total_active_students,
        "income_per_student": income_per_student,
        "expected_income": total_expected_income,
        "breakdown": breakdown
    }
