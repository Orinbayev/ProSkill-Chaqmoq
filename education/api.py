from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.db.models import Sum
from datetime import date
from .services.expected_income_service import calculate_expected_income
from accounts.models import Center

User = get_user_model()

def teacher_expected_income_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Unauthorized"}, status=401)
        
    user = request.user
    if user.role not in ['director', 'manager', 'teacher'] and not user.is_superuser:
        return JsonResponse({"error": "Permission denied"}, status=403)
        
    year = int(request.GET.get('year', date.today().year))
    month = int(request.GET.get('month', date.today().month))
    teacher_id = request.GET.get('teacher_id')
    course_id = request.GET.get('course_id')
    
    center = user.center if user.role in ['director', 'manager'] and hasattr(user, 'center') else None
    
    teachers = User.objects.filter(role='teacher')
    
    if user.role == 'teacher' and not user.is_superuser:
        teachers = teachers.filter(id=user.id)
    else:
        if center:
            teachers = teachers.filter(center=center)
        if teacher_id:
            teachers = teachers.filter(id=teacher_id)
        
    results = []
    for t in teachers:
        # Pass course_id if filtering by course is requested
        res = calculate_expected_income(
            teacher=t, 
            year=year, 
            month=month, 
            center=center,
            course_id=course_id
        )
        if res['active_students'] > 0:
            results.append(res)
        
    return JsonResponse(results, safe=False)
    

