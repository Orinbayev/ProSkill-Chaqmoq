from .models import Product, PurchaseRequest, Comment
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Product, ProductImage, PurchaseRequest
from .services import approve_purchase, reject_purchase
from .forms import ProductForm
from chaqmoq.models import Ledger


# ✅ Mahsulotlar ro‘yxati
@login_required
def products(request):
    """Mahsulotlar ro‘yxati va tanlab o‘chirish funksiyasi"""
    items = Product.objects.all().order_by('-yaratilgan')

    # 🔹 Faqat manager, director yoki superuser qo‘sha / o‘chira oladi
    can_add = request.user.role in ('manager', 'director') or request.user.is_superuser

    # 🔹 Tanlangan mahsulotlarni o‘chirish (POST orqali)
    if request.method == "POST":
        selected_ids = request.POST.getlist("selected_products")
        if selected_ids:
            Product.objects.filter(id__in=selected_ids).delete()
            messages.success(request, f"{len(selected_ids)} ta mahsulot o‘chirildi ✅")
            return redirect('store:products')
        else:
            messages.warning(request, "Hech qanday mahsulot tanlanmadi ❗")

    return render(request, 'store/products.html', {
        'items': items,
        'can_add': can_add,
    })



# ✅ Mahsulot tafsiloti
from django.contrib.auth import get_user_model
User = get_user_model()

@login_required
def product_detail(request, pk):
    item = get_object_or_404(Product, pk=pk)
    has_pending = False

    # Foydalanuvchini bazadan yangilab olish
    user = User.objects.get(id=request.user.id)

    # Agar foydalanuvchi o‘quvchi bo‘lsa, so‘rovni tekshir
    if user.role == 'student':
        has_pending = PurchaseRequest.objects.filter(
            student=user,
            product=item,
            status=PurchaseRequest.PENDING
        ).exists()

    # Foydalanuvchi chaqmog'ini bazadan olish
    user_chaqmoq = user.chaqmoq

    # Sotib olishlar soni
    item.sotib_olganlar = PurchaseRequest.objects.filter(
        product=item,
        status=PurchaseRequest.APPROVED
    ).count()

    comments = Comment.objects.filter(product=item, parent=None).prefetch_related('replies', 'user')

    # Yetarlilik holati
    yetarli = user_chaqmoq >= item.narx_chaqmoq

    return render(request, 'store/product_detail.html', {
        'item': item,
        'has_pending': has_pending,
        'comments': comments,
        'user_chaqmoq': user_chaqmoq,
        'yetarli': yetarli,
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
@login_required
def create_request(request, pk):
    """O‘quvchi mahsulot uchun so‘rov yuboradi"""
    product = get_object_or_404(Product, pk=pk)
    user = User.objects.get(id=request.user.id)

    if user.role != 'student':
        messages.error(request, "Faqat o‘quvchilar sotib olishlari mumkin.")
        return redirect('store:product_detail', pk=pk)

    # Agar mavjud bo‘lmasa
    if product.qoldiq <= 0:
        messages.error(request, "Mahsulot omborda qolmagan.")
        return redirect('store:product_detail', pk=pk)

    # Agar so‘rov oldin yuborilgan bo‘lsa
    if PurchaseRequest.objects.filter(student=user, product=product, status=PurchaseRequest.PENDING).exists():
        messages.warning(request, "Siz bu mahsulot uchun so‘rov yuborgansiz.")
        return redirect('store:product_detail', pk=pk)

    # ✅ Chaqmoqni hozircha yechmaymiz — manager tasdiqlaganda yechiladi
    with transaction.atomic():
        PurchaseRequest.objects.create(
            student=user,
            product=product,
            qty=1,
            status=PurchaseRequest.PENDING
        )

    messages.success(request, f"So‘rovingiz yuborildi! Manager tasdiqlaganidan keyin chaqmoq yechiladi.")
    return redirect('store:product_detail', pk=pk)


# ✅ Manager/Direktor uchun so‘rovlar ro‘yxati
@login_required
def request_list(request):
    if request.user.role not in ('manager', 'director'):
        messages.error(request, 'Ruxsat yo‘q.')
        return redirect('core:home')
    items = PurchaseRequest.objects.order_by('-sana')
    return render(request, 'store/requests.html', {'items': items})


# ✅ So‘rovni tasdiqlash
@login_required
def request_approve(request, pk):
    if request.user.role not in ('manager', 'director'):
        messages.error(request, 'Ruxsat yo‘q.')
        return redirect('store:requests')

    pr = get_object_or_404(PurchaseRequest, pk=pk)
    ok, msg = approve_purchase(pr, request.user)
    (messages.success if ok else messages.error)(request, msg)
    return redirect('store:requests')


# ✅ So‘rovni rad etish
@login_required
def request_reject(request, pk):
    if request.user.role not in ('manager', 'director'):
        messages.error(request, 'Ruxsat yo‘q.')
        return redirect('store:requests')

    pr = get_object_or_404(PurchaseRequest, pk=pk)
    ok, msg = reject_purchase(pr, request.user)
    (messages.success if ok else messages.error)(request, msg)
    return redirect('store:requests')


# ✅ Mahsulot qo‘shish
@login_required
def product_create(request):
    if request.user.role not in ('manager', 'director') and not request.user.is_superuser:
        messages.error(request, 'Ruxsat yo‘q.')
        return redirect('store:products')

    from .forms import ProductForm, ProductImageForm

    form = ProductForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        product = form.save()
        # Rasmlar yuklash
        files = request.FILES.getlist('rasmlar')
        for file in files:
            ProductImage.objects.create(product=product, rasm=file)
        messages.success(request, 'Mahsulot va rasmlar muvaffaqiyatli qo‘shildi!')
        return redirect('store:products')

    return render(request, 'store/product_form.html', {'form': form, 'title': "Mahsulot qo‘shish"})


def product_list(request):
    products = Product.objects.all()

    # 🔹 Tanlanganlarni o‘chirish
    if request.method == "POST":
        ids = request.POST.getlist('selected_products')
        if ids:
            Product.objects.filter(id__in=ids).delete()
            messages.success(request, "Tanlangan mahsulotlar muvaffaqiyatli o‘chirildi ✅")
            return redirect('store:products')

    return render(request, 'store/product_list.html', {'products': products})


# ✅ Mahsulotni tahrirlash
@login_required
def product_edit(request, pk):
    if request.user.role not in ('manager', 'director') and not request.user.is_superuser:
        messages.error(request, 'Ruxsat yo‘q.')
        return redirect('store:products')

    obj = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Mahsulot saqlandi!')
        return redirect('store:products')

    return render(request, 'store/product_form.html', {'form': form, 'title': 'Mahsulotni tahrirlash'})


# ✅ Mahsulotni o‘chirish
@login_required
def product_delete(request, pk):
    if request.user.role not in ('director',) and not request.user.is_superuser:
        messages.error(request, 'Ruxsat yo‘q.')
        return redirect('store:products')

    obj = get_object_or_404(Product, pk=pk)
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

@login_required
def lead_list(request):
    # 🔹 status bo‘yicha filter
    status_id = request.GET.get('status')
    statuses = LeadStatus.objects.all()

    if status_id:
        leads = Lead.objects.filter(status_id=status_id).order_by('-qoshilgan_sana')
    else:
        leads = Lead.objects.all().order_by('-qoshilgan_sana')

    context = {
        'leads': leads,
        'statuses': statuses,
        'selected_status': status_id,
    }
    return render(request, 'store/lead_list.html', context)


@login_required
def lead_create(request):
    if request.method == 'POST':
        form = LeadForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Yangi o‘quvchi (lead) qo‘shildi!")
            return redirect('store:lead_list')
    else:
        form = LeadForm()
    return render(request, 'store/lead_create.html', {'form': form})


# ✏️ Leadni tahrirlash
@login_required
def lead_edit(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    if request.method == 'POST':
        form = LeadForm(request.POST, instance=lead)
        if form.is_valid():
            form.save()
            messages.success(request, "✏️ Ma’lumot tahrirlandi!")
            return redirect('store:lead_list')
    else:
        form = LeadForm(instance=lead)
    return render(request, 'store/lead_edit.html', {'form': form, 'lead': lead})


# 🗑️ Leadni o‘chirish
@login_required
def lead_delete(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    if request.method == 'POST':
        lead.delete()
        messages.warning(request, "🗑️ Lead o‘chirildi!")
        return redirect('store:lead_list')
    return render(request, 'store/lead_delete.html', {'lead': lead})
