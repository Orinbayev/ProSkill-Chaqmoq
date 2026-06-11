from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.apps import apps
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from django.utils import timezone

def _get_center(request):
    return getattr(request, "center", None) or getattr(getattr(request, "user", None), "center", None)

def can_access_trash(user, center):
    if user.is_superuser or user.role == 'director':
        return True
    if user.role == 'manager':
        # Manager can access only if center allows and specifically this manager is enabled
        return center.manager_can_access_trash and user.can_access_trash
    return False

@login_required
def deleted_items_list(request):
    center = _get_center(request)
    if not can_access_trash(request.user, center):
        messages.error(request, "Sizda bu bo'limga kirish huquqi yo'q.")
        return redirect('core:home')

    type_filter = request.GET.get('type', 'all')
    search_query = request.GET.get('q', '').strip()
    
    # Mapping of types to models and display labels
    MODELS = {
        'teachers': {'model': 'accounts.User', 'label': 'O‘qituvchilar', 'role': 'teacher'},
        'managers': {'model': 'accounts.User', 'label': 'Managerlar', 'role': 'manager'},
        'students': {'model': 'accounts.User', 'label': 'O‘quvchilar', 'role': 'student'},
        'parents': {'model': 'accounts.User', 'label': 'Ota-onalar', 'role': 'parent'},
        'groups': {'model': 'education.Group', 'label': 'Guruhlar'},
        'courses': {'model': 'education.Category', 'label': 'Kurslar'},
        'payments': {'model': 'education.Payment', 'label': 'To‘lovlar'},
        'products': {'model': 'store.Product', 'label': 'Mahsulotlar'},
    }

    deleted_items = []

    for key, info in MODELS.items():
        if type_filter != 'all' and type_filter != key:
            continue
            
        try:
            model_class = apps.get_model(info['model'])
        except LookupError:
            continue

        # Use all_objects to access dead items
        qs = model_class.all_objects.filter(is_deleted=True)
        
        # Center filtering
        if hasattr(model_class, 'center'):
            qs = qs.filter(center=center)
        elif key in ['teachers', 'managers', 'students', 'parents']:
            qs = qs.filter(center=center)
            
        # Role filtering for User model
        if 'role' in info:
            qs = qs.filter(role=info['role'])
            
        # Search filtering
        if search_query:
            if key in ['teachers', 'managers', 'students', 'parents']:
                qs = qs.filter(Q(ism__icontains=search_query) | Q(familya__icontains=search_query) | Q(email__icontains=search_query))
            elif key == 'groups':
                qs = qs.filter(nom__icontains=search_query)
            elif key == 'courses':
                qs = qs.filter(name__icontains=search_query)
            elif key == 'products':
                qs = qs.filter(nom__icontains=search_query)

        qs = qs.select_related('deleted_by')

        for item in qs:
            name = ""
            if hasattr(item, 'full_name'):
                name = item.full_name()
            elif hasattr(item, 'nom'):
                name = item.nom
            elif hasattr(item, 'name'):
                name = item.name
            elif hasattr(item, 'get_full_name'):
                name = item.get_full_name()
            else:
                name = str(item)

            deleted_items.append({
                'id': item.id,
                'name': name,
                'type': info['label'],
                'type_key': key,
                'deleted_by': item.deleted_by,
                'deleted_at': item.deleted_at,
                'obj': item,
            })

    # Sort by deleted_at desc
    deleted_items.sort(key=lambda x: x['deleted_at'] or timezone.now(), reverse=True)

    # If Director or Superuser, also fetch managers for the permission modal
    managers = []
    if request.user.role == 'director' or request.user.is_superuser:
        from django.contrib.auth import get_user_model
        managers = get_user_model().objects.filter(center=center, role='manager')

    context = {
        'deleted_items': deleted_items,
        'type_filter': type_filter,
        'search_query': search_query,
        'MODELS_INFO': MODELS,
        'center': center,
        'managers': managers,
        'title': "O'chirilganlar"
    }
    return render(request, 'core/deleted_items.html', context)

@login_required
def restore_item(request, model_key, pk):
    if request.method not in ('GET', 'POST'):
        return redirect('core:deleted_items')

    center = _get_center(request)
    if not can_access_trash(request.user, center):
        raise PermissionDenied

    MODELS = {
        'teachers': 'accounts.User',
        'managers': 'accounts.User',
        'students': 'accounts.User',
        'parents': 'accounts.User',
        'groups': 'education.Group',
        'courses': 'education.Category',
        'payments': 'education.Payment',
        'products': 'store.Product',
    }

    if model_key not in MODELS:
        messages.error(request, "Noma'lum tur.")
        return redirect('core:deleted_items')

    model_class = apps.get_model(MODELS[model_key])
    item = get_object_or_404(model_class.all_objects, pk=pk, is_deleted=True)
    
    # Security check: center
    if hasattr(item, 'center') and item.center != center:
        raise PermissionDenied

    item.restore(restored_by=request.user)
    messages.success(request, f"Ma'lumot muvaffaqiyatli tiklandi ✅")
    return redirect('core:deleted_items')

@login_required
def hard_delete_item(request, model_key, pk):
    center = _get_center(request)
    if not can_access_trash(request.user, center):
        raise PermissionDenied

    if request.method != "POST":
        return redirect('core:deleted_items')

    MODELS = {
        'teachers': 'accounts.User',
        'managers': 'accounts.User',
        'students': 'accounts.User',
        'parents': 'accounts.User',
        'groups': 'education.Group',
        'courses': 'education.Category',
        'payments': 'education.Payment',
        'products': 'store.Product',
    }

    if model_key not in MODELS:
        messages.error(request, "Noma'lum tur.")
        return redirect('core:deleted_items')

    model_class = apps.get_model(MODELS[model_key])
    item = get_object_or_404(model_class.all_objects, pk=pk, is_deleted=True)
    
    # Security check: center
    if hasattr(item, 'center') and item.center != center:
        raise PermissionDenied

    item.hard_delete()
    messages.success(request, "Ma'lumot butunlay o'chirildi.")
    return redirect('core:deleted_items')

@login_required
def toggle_manager_user_trash_access(request, user_id):
    if not (request.user.role == 'director' or request.user.is_superuser):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({"ok": False, "error": "Permission denied"}, status=403)
        raise PermissionDenied
    
    from django.contrib.auth import get_user_model
    manager = get_object_or_404(get_user_model(), id=user_id, role='manager')
    
    # Security check: same center
    center = _get_center(request)
    if manager.center != center:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({"ok": False, "error": "Center mismatch"}, status=403)
        raise PermissionDenied
        
    manager.can_access_trash = not manager.can_access_trash
    manager.save()
    
    status_text = "berildi" if manager.can_access_trash else "olib tashlandi"
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            "ok": True, 
            "status": manager.can_access_trash,
            "message": f"{manager.get_full_name()} uchun ruxsat {status_text}."
        })
    
    messages.success(request, f"{manager.get_full_name()} uchun ruxsat {status_text}.")
    return redirect('core:deleted_items')
