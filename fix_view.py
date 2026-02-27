import re

with open('education/views.py', 'r') as f:
    text = f.read()

# Replace the teacher check in teacher_income_dashboard
old_check = """
    if request.user.role != 'teacher':
        messages.error(request, "Bu bo'lim faqat o'qituvchilar uchun.")
        return redirect('core:home')
"""
new_check = """    if request.user.role not in ['teacher', 'admin', 'superadmin']:
        messages.error(request, "Bu bo'lim ushbu rol uchun emas.")
        return redirect('core:home')
        
    is_admin = request.user.role in ['admin', 'superadmin']
"""

text = text.replace(old_check.strip(), new_check.strip())

# We need to wrap the whole chart logic in if not is_admin: ... ? No, if admin, we can just skip or let it be empty since they have no groups.
# But teacher = request.user, so groups = Group.objects.filter(oqituvchi=teacher) will be empty for admin. 

with open('education/views.py', 'w') as f:
    f.write(text)
