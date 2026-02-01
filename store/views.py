from .models import Product, PurchaseRequest, Comment
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Product, ProductImage, PurchaseRequest
from .services import approve_purchase, reject_purchase
from .forms import ProductForm
from chaqmoq.models import Ledger
from .services import convert_lead_to_student  # tepaga import qiling
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.shortcuts import get_object_or_404
from core.tenant import require_center, ensure_obj_center
from .models import Lead
from billing.decorators import require_feature
from django.utils import timezone


def lead_detail(request, pk):
    center = require_center(request)
    lead = get_object_or_404(Lead, pk=pk)
    ensure_obj_center(request, lead.center_id)
    return render(request, "store/lead_detail.html", {"lead": lead})

# ✅ Mahsulotlar ro‘yxati
@login_required
def products(request):
    """Mahsulotlar ro‘yxati va tanlab o‘chirish funksiyasi"""
    from django.db.models import Q
    from core.tenant import get_request_center
    center = get_request_center(request)
    
    items = Product.objects.filter(Q(center=center) | Q(center__isnull=True)).order_by('-yaratilgan')

    # 🔹 Faqat manager, director yoki superuser qo‘sha / o‘chira oladi
    can_add = request.user.role in ('manager', 'director') or request.user.is_superuser

    # 🔹 Tanlangan mahsulotlarni o‘chirish (POST orqali)
    if request.method == "POST":
        selected_ids = request.POST.getlist("selected_products")
        if selected_ids:
            # ✅ Xavfsizlik: faqat shu center mahsulotlarini o'chirish
            Product.objects.filter(id__in=selected_ids, center=center).delete()
            messages.success(request, f"{len(selected_ids)} ta mahsulot o‘chirildi ✅")
            return redirect('store:products')
        else:
            messages.warning(request, "Hech qanday mahsulot tanlanmadi ❗")

    return render(request, 'store/product_list.html', {'items': items, 'can_add': can_add})



# ✅ Mahsulot tafsiloti
from django.contrib.auth import get_user_model
User = get_user_model()

@login_required
def product_detail(request, pk):
    center = require_center(request)
    item = get_object_or_404(Product, pk=pk, center=center)
    user = request.user
    request_status = None

    if user.role == 'student':
        last_request = PurchaseRequest.objects.filter(
            student=user,
            product=item
        ).order_by('-sana').first()
        if last_request:
            request_status = last_request.status

    from chaqmoq.models import Ledger
    user_chaqmoq = Ledger.student_balansi(user.id)

    sotib_olganlar_soni = PurchaseRequest.objects.filter(
        product=item,
        status=PurchaseRequest.APPROVED
    ).count()

    comments = Comment.objects.filter(product=item, parent=None).prefetch_related('replies', 'user')
    yetarli = user_chaqmoq >= item.narx_chaqmoq

    return render(request, 'store/product_detail.html', {
        'item': item,
        'request_status': request_status,
        'comments': comments,
        'user_chaqmoq': user_chaqmoq,
        'yetarli': yetarli,
        'sotib_olganlar_soni': sotib_olganlar_soni,
    })



@login_required
def add_comment(request, pk):
    if request.method == 'POST':
        item = get_object_or_404(Product, pk=pk)
        text = request.POST.get('text', '').strip()
        if text:
            Comment.objects.create(product=item, user=request.user, text=text)
        return redirect('store:product_detail', pk=pk)
    return redirect('store:product_detail', pk=pk)



@login_required
def reply_comment(request, cid):
    parent = get_object_or_404(Comment, pk=cid)
    if request.method == 'POST':
        text = request.POST.get('text', '').strip()
        if text:
            Comment.objects.create(
                product=parent.product,
                user=request.user,
                text=text,
                parent=parent
            )
    return redirect('store:product_detail', pk=parent.product.id)

from django.db import transaction


# ✅ Mahsulotga so‘rov yuborish (student uchun)
# ✅ Mahsulotga so‘rov yuborish (student uchun)
@login_required
def create_request(request, pk):
    """O‘quvchi mahsulot uchun so‘rov yuboradi"""
    product = get_object_or_404(Product, pk=pk)
    user = request.user  # Foydalanuvchini olamiz

    # ✅ 1. Faqat studentlarga ruxsat
    if user.role != 'student':
        messages.error(request, "Faqat o‘quvchilar sotib olishlari mumkin.")
        return redirect('store:product_detail', pk=pk)

    # ✅ 2. Agar so‘rov allaqachon yuborilgan bo‘lsa
    # ❌ faqat "pending" emas, balki "tasdiqlangan"ni ham qayta sotib olishga ruxsat beramiz
    if PurchaseRequest.objects.filter(
        student=user, product=product, status=PurchaseRequest.PENDING
    ).exists():
        messages.warning(request, "Siz bu mahsulot uchun so‘rov yuborgansiz. Tasdiqlanishini kuting.")
        return redirect('store:product_detail', pk=pk)


    # ✅ 3. Ledger orqali foydalanuvchining real chaqmoq balansini olish
    user_chaqmoq = Ledger.student_balansi(user.id)

    if user_chaqmoq < product.narx_chaqmoq:
        messages.error(
            request,
            f"Sizda yetarli chaqmoq mavjud emas. ({user_chaqmoq} / {product.narx_chaqmoq})"
        )
        return redirect('store:product_detail', pk=pk)

    # ✅ 4. So‘rovni yaratish
    with transaction.atomic():
        PurchaseRequest.objects.create(
            student=user,
            product=product,
            qty=1,
            status=PurchaseRequest.PENDING
        )

    messages.success(
        request,
        f"So‘rovingiz yuborildi! Sizning joriy balansingiz: {user_chaqmoq - product.narx_chaqmoq} Chaqmoq."
    )
    return redirect('store:product_detail', pk=pk)


# ✅ Manager/Direktor uchun so‘rovlar ro‘yxati
@login_required
def request_list(request):
    center = require_center(request)
    if request.user.role not in ('manager', 'director'):
        messages.error(request, 'Ruxsat yo‘q.')
        return redirect('core:home')
    items = PurchaseRequest.objects.filter(center=center).order_by('-sana')
    return render(request, 'store/requests.html', {'items': items})


# ✅ So‘rovni tasdiqlash
@login_required
def request_approve(request, pk):
    if request.user.role not in ('manager', 'director'):
        messages.error(request, 'Ruxsat yo‘q.')
        return redirect(request.META.get('HTTP_REFERER', 'store:requests'))

    center = require_center(request)
    pr = get_object_or_404(PurchaseRequest, pk=pk, center=center)
    ok, msg = approve_purchase(pr, request.user)
    (messages.success if ok else messages.error)(request, msg)

    return redirect(request.META.get('HTTP_REFERER', 'store:requests'))


@login_required
def request_reject(request, pk):
    if request.user.role not in ('manager', 'director'):
        messages.error(request, 'Ruxsat yo‘q.')
        return redirect(request.META.get('HTTP_REFERER', 'store:requests'))

    pr = get_object_or_404(PurchaseRequest, pk=pk)
    ok, msg = reject_purchase(pr, request.user)
    (messages.success if ok else messages.error)(request, msg)

    return redirect(request.META.get('HTTP_REFERER', 'store:requests'))


# ✅ Mahsulot qo‘shish
@login_required
def product_create(request):
    if request.user.role not in ('manager', 'director') and not request.user.is_superuser:
        messages.error(request, 'Ruxsat yo‘q.')
        return redirect('store:products')

    from .forms import ProductForm, ProductImageForm

    form = ProductForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        center = require_center(request)
        product = form.save(commit=False)
        product.center = center
        product.save()
        # Rasmlar yuklash
        files = request.FILES.getlist('rasmlar')
        for file in files:
            ProductImage.objects.create(product=product, rasm=file)
        messages.success(request, 'Mahsulot va rasmlar muvaffaqiyatli qo‘shildi!')
        return redirect('store:products')

    return render(request, 'store/product_form.html', {'form': form, 'title': "Mahsulot qo‘shish"})


def product_list(request):
    center = require_center(request)
    products = Product.objects.filter(center=center)

    # 🔹 Tanlanganlarni o‘chirish
    if request.method == "POST":
        ids = request.POST.getlist('selected_products')
        if ids:
            Product.objects.filter(id__in=ids, center=center).delete()
            messages.success(request, "Tanlangan mahsulotlar muvaffaqiyatli o‘chirildi ✅")
            return redirect('store:products')

    return render(request, 'store/product_list.html', {'products': products})


# ✅ Mahsulotni tahrirlash
@login_required
def product_edit(request, pk):
    if request.user.role not in ('manager', 'director') and not request.user.is_superuser:
        messages.error(request, 'Ruxsat yo‘q.')
        return redirect('store:products')

    center = require_center(request)
    obj = get_object_or_404(Product, pk=pk, center=center)
    form = ProductForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        product = form.save()
        
        # ✅ FIX: Rasmlarni tahrirlash paytida ham yuklash
        files = request.FILES.getlist('rasmlar')
        for file in files:
            ProductImage.objects.create(product=product, rasm=file)
            
        messages.success(request, 'Mahsulot saqlandi!')
        return redirect('store:products')

    return render(request, 'store/product_form.html', {'form': form, 'title': 'Mahsulotni tahrirlash'})


# ✅ Mahsulotni o‘chirish
@login_required
def product_delete(request, pk):
    if request.user.role not in ('director',) and not request.user.is_superuser:
        messages.error(request, 'Ruxsat yo‘q.')
        return redirect('store:products')

    center = require_center(request)
    obj = get_object_or_404(Product, pk=pk, center=center)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Mahsulot o‘chirildi!')
        return redirect('store:products')

    return render(request, 'accounts/logout_confirm.html', {})


# 🔒 Talabaning balansini tekshirish
def _student_has_enough(user, price: int) -> bool:
    if getattr(user, 'role', None) != 'student':
        return True
    bal = Ledger.student_balansi(user.id)
    return bal >= price

from .models import Lead
from .forms import LeadForm
from .models import Lead, LeadStatus

from django.db.models import Count, Q

@login_required
@require_feature("leads")
def lead_list(request):
    center = require_center(request)

    status_id = (request.GET.get('status') or "").strip()
    q = (request.GET.get('q') or "").strip()

    # ✅ Tenant isolation: faqat shu center leadlari
    if request.user.is_superuser:
        leads = Lead.objects.all()
    else:
        leads = Lead.objects.filter(center=center)

    if request.user.is_superuser:
         # Superuser uchun: faqat mavjud leadlarda ishlatilgan statuslarni chiqaramiz
         used_ids = leads.values_list('status', flat=True).distinct()
         statuses_qs = LeadStatus.objects.filter(id__in=used_ids)
    else:
         statuses_qs = LeadStatus.objects.filter(center=center)

    statuses = (
        statuses_qs
        .annotate(
            leads_count=Count('lead', distinct=True),
            converted_count=Count('lead', filter=Q(lead__converted_user__isnull=False), distinct=True),
        )
        .order_by('id')
    )

    if status_id:
        leads = leads.filter(status_id=status_id)

    if q:
        leads = leads.filter(
            Q(ism__icontains=q) |
            Q(familya__icontains=q) |
            Q(telefon1__icontains=q) |
            Q(telefon2__icontains=q)
        )

    leads = leads.order_by('-qoshilgan_sana')

    context = {
        'leads': leads,
        'statuses': statuses,
        'selected_status': status_id,
        'q': q,
        'total_count': Lead.objects.filter(center=center).count(),
        'total_converted': Lead.objects.filter(center=center, converted_user__isnull=False).count(),
        'leads_count_filtered': leads.count(),
        'converted_count_filtered': leads.filter(converted_user__isnull=False).count(),
    }
    return render(request, 'store/lead_list.html', context)


@login_required
@require_feature("leads")
def lead_create(request):
    center = require_center(request)
    if request.method == 'POST':
        form = LeadForm(request.POST, center=center)
        if form.is_valid():
            lead = form.save(commit=False)
            lead.center = center
            
            # Auto-calculate age
            if lead.birth_date:
                lead.yosh = timezone.now().year - lead.birth_date.year
            else:
                lead.yosh = 0
                
            lead.save()
            messages.success(request, "✅ Yangi o‘quvchi (lead) qo‘shildi!")
            return redirect('store:lead_list')
    else:
        form = LeadForm(center=center)
    return render(request, 'store/lead_create.html', {'form': form})


# ✏️ Leadni tahrirlash

@login_required
@require_feature("leads")
def lead_edit(request, pk):
    center = require_center(request)
    if request.user.is_superuser:
        lead = get_object_or_404(Lead, pk=pk)
    else:
        lead = get_object_or_404(Lead, pk=pk, center=center)

    if request.method == 'POST':
        form = LeadForm(request.POST, instance=lead, center=center)
        if form.is_valid():
            lead = form.save(commit=False)
            
            # Auto-calculate age
            if lead.birth_date:
                lead.yosh = timezone.now().year - lead.birth_date.year
            elif not lead.yosh:
                lead.yosh = 0
                
            lead.save()

            # ✅ STATUS "Tasdiqlandi" bo'lsa avtomatik studentga o'tkazamiz
            if lead.status and (lead.status.nom or "").strip().lower() == "tasdiqlandi":
                user, password, created = convert_lead_to_student(lead, request.user)

                if created:
                    messages.success(
                        request,
                        f"✅ Lead o‘quvchiga o‘tkazildi! Login: {user.email} | Parol: {password}"
                    )
                else:
                    messages.info(
                        request,
                        f"ℹ️ Lead oldindan mavjud o‘quvchiga bog‘landi: {user.email}"
                    )
            else:
                messages.success(request, "✏️ Ma’lumot tahrirlandi!")

            return redirect('store:lead_list')
    else:
        form = LeadForm(instance=lead, center=center)

    return render(request, 'store/lead_edit.html', {'form': form, 'lead': lead})


# 🗑️ Leadni o‘chirish
@login_required
@require_feature("leads")
def lead_delete(request, pk):
    center = require_center(request)
    if request.user.is_superuser:
        lead = get_object_or_404(Lead, pk=pk)
    else:
        lead = get_object_or_404(Lead, pk=pk, center=center)

    if request.method == 'POST':
        lead.delete()
        messages.warning(request, "🗑️ Lead o‘chirildi!")
        return redirect('store:lead_list')
    return render(request, 'store/lead_delete.html', {'lead': lead})




@login_required
@require_feature("leads")
def lead_detail(request, pk):
    center = require_center(request)
    if request.user.is_superuser:
        lead = get_object_or_404(Lead, pk=pk)
    else:
        lead = get_object_or_404(Lead, pk=pk, center=center)
    return render(request, "store/lead_detail.html", {"lead": lead})



@require_POST
@login_required
def lead_convert(request, pk):
    lead = get_object_or_404(Lead, pk=pk)

    # ruxsat
    if not (request.user.is_superuser or request.user.role in ('manager', 'director')):
        messages.error(request, "Ruxsat yo‘q.")
        return redirect('store:lead_list')

    # statusni "Tasdiqlandi" ga qo'yamiz
    tasdiq = LeadStatus.objects.filter(nom="Tasdiqlandi").first()
    if tasdiq:
        lead.status = tasdiq
        lead.save(update_fields=["status"])

    user, password, created = convert_lead_to_student(lead, request.user)

    if created:
        messages.success(request, f"✅ O‘tkazildi! Login: {user.email} | Parol: {password}")
    else:
        messages.info(request, f"ℹ️ Lead mavjud o‘quvchiga bog‘landi: {user.email}")

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or reverse("store:lead_list")
    return redirect(next_url)
