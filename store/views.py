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
@login_required
def product_detail(request, pk):
    item = get_object_or_404(Product, pk=pk)
    has_pending = False
    if request.user.role == 'student':
        has_pending = PurchaseRequest.objects.filter(
            student=request.user, product=item, status=PurchaseRequest.PENDING
        ).exists()
    return render(request, 'store/product_detail.html', {'item': item, 'has_pending': has_pending})


# ✅ Mahsulotga so‘rov yuborish (student uchun)
@login_required
def create_request(request, pk):
    item = get_object_or_404(Product, pk=pk)
    if request.user.role != 'student':
        messages.error(request, 'Faqat o‘quvchi so‘rov yuborishi mumkin.')
        return redirect('store:products')

    exists = PurchaseRequest.objects.filter(
        student=request.user, product=item, status=PurchaseRequest.PENDING
    ).exists()
    if exists:
        messages.info(request, 'Oldin yuborilgan so‘rov mavjud.')
        return redirect('store:product_detail', pk=pk)

    if not _student_has_enough(request.user, item.narx_chaqmoq):
        messages.error(request, "Chaqmoqingiz yetarli emas.")
        return redirect('store:products')

    PurchaseRequest.objects.create(student=request.user, product=item, qty=1)
    messages.success(request, 'Xarid so‘rovi yuborildi.')
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
