
# ⚙️ Lead Sozlamalari (Manba, Yo'nalish, Status)
@login_required
@require_feature("leads")
def lead_settings(request):
    center = require_center(request)
    if request.user.role not in ('manager', 'director') and not request.user.is_superuser:
        messages.error(request, 'Ruxsat yo‘q.')
        return redirect('store:lead_list')

    manbalar = Manba.objects.filter(center=center)
    yonalishlar = Yonalish.objects.filter(center=center)
    statuses = LeadStatus.objects.filter(center=center)

    return render(request, 'store/lead_settings.html', {
        'manbalar': manbalar,
        'yonalishlar': yonalishlar,
        'statuses': statuses
    })


@require_POST
@login_required
def lead_config_add(request):
    center = require_center(request)
    if request.user.role not in ('manager', 'director') and not request.user.is_superuser:
        return redirect('store:lead_settings')

    conf_type = request.POST.get('type')  # 'manba' | 'yonalish' | 'status'
    nom = request.POST.get('nom', '').strip()

    if not nom:
        messages.error(request, "Nom kiritilmadi!")
        return redirect('store:lead_settings')

    try:
        if conf_type == 'manba':
            Manba.objects.create(center=center, nom=nom)
            messages.success(request, f"Manba qo'shildi: {nom}")
        elif conf_type == 'yonalish':
            Yonalish.objects.create(center=center, nom=nom)
            messages.success(request, f"Yo'nalish qo'shildi: {nom}")
        elif conf_type == 'status':
            LeadStatus.objects.create(center=center, nom=nom)
            messages.success(request, f"Status qo'shildi: {nom}")
    except Exception as e:
        messages.error(request, f"Xatolik: {str(e)}")

    return redirect('store:lead_settings')


@login_required
def lead_config_delete(request, type_code, pk):
    center = require_center(request)
    if request.user.role not in ('manager', 'director') and not request.user.is_superuser:
        messages.error(request, "Ruxsat yo'q")
        return redirect('store:lead_settings')

    model_map = {
        'manba': Manba,
        'yonalish': Yonalish,
        'status': LeadStatus
    }
    
    ModelClass = model_map.get(type_code)
    if ModelClass:
        obj = get_object_or_404(ModelClass, pk=pk, center=center)
        if request.method == 'POST':
            obj.delete()
            messages.success(request, "O'chirildi!")
    
    return redirect('store:lead_settings')
