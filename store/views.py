from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Product, PurchaseRequest
from .services import approve_purchase
from .forms import ProductForm
from chaqmoq.models import Ledger

@login_required
def products(request):
    items = Product.objects.all().order_by('-yaratilgan')
    return render(request, 'store/products.html', {'items': items})

@login_required
def product_detail(request, pk):
    item = get_object_or_404(Product, pk=pk)
    has_pending = False
    if request.user.role == 'student':
        has_pending = PurchaseRequest.objects.filter(
            student=request.user, product=item, status=PurchaseRequest.PENDING
        ).exists()
    return render(request, 'store/product_detail.html', {'item': item, 'has_pending': has_pending})

@login_required
def create_request(request, pk):
    item = get_object_or_404(Product, pk=pk)
    if request.user.role != 'student':
        messages.error(request, 'Faqat o‘quvchi so‘rov yaratishi mumkin.')
        return redirect('store:products')
    exists = PurchaseRequest.objects.filter(
        student=request.user, product=item, status=PurchaseRequest.PENDING
    ).exists()
    if exists:
        messages.info(request, 'Oldin yuborilgan so‘rov mavjud.')
        return redirect('store:product_detail', pk=pk)
    PurchaseRequest.objects.create(student=request.user, product=item, qty=1)
    messages.success(request, 'Xarid so‘rovi yuborildi.')
    return redirect('store:product_detail', pk=pk)


@login_required
def request_list(request):
    if request.user.role not in ('manager','director'):
        messages.error(request, 'Ruxsat yo‘q')
        return redirect('core:home')
    items = PurchaseRequest.objects.order_by('-sana')
    return render(request, 'store/requests.html', {'items': items})

@login_required
def request_approve(request, pk):
    if request.user.role not in ('manager','director'):
        messages.error(request, 'Ruxsat yo‘q')
        return redirect('store:requests')
    pr = get_object_or_404(PurchaseRequest, pk=pk)
    ok, msg = approve_purchase(pr, request.user)
    (messages.success if ok else messages.error)(request, msg)
    return redirect('store:requests')


@login_required
def product_create(request):
    if request.user.role not in ('manager','director') and not request.user.is_superuser:
        messages.error(request,'Ruxsat yo‘q'); return redirect('core:stat_products')
    form = ProductForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save(); messages.success(request,'Mahsulot qo‘shildi'); return redirect('core:stat_products')
    return render(request, 'accounts/add_teacher.html', {'form': form})

@login_required
def product_edit(request, pk):
    if request.user.role not in ('manager','director') and not request.user.is_superuser:
        messages.error(request,'Ruxsat yo‘q'); return redirect('core:stat_products')
    obj = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save(); messages.success(request,'Saqlandi'); return redirect('core:stat_products')
    return render(request, 'accounts/add_teacher.html', {'form': form})

@login_required
def product_delete(request, pk):
    if request.user.role not in ('director',) and not request.user.is_superuser:
        messages.error(request,'Ruxsat yo‘q'); return redirect('core:stat_products')
    obj = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        obj.delete(); messages.success(request,'O‘chirildi'); return redirect('core:stat_products')
    return render(request, 'accounts/logout_confirm.html', {})


@login_required
def request_reject(request, pk):
    if request.user.role not in ('manager','director'):
        messages.error(request, 'Ruxsat yo‘q')
        return redirect('store:requests')
    pr = get_object_or_404(PurchaseRequest, pk=pk)
    from .services import reject_purchase
    ok, msg = reject_purchase(pr, request.user)
    (messages.success if ok else messages.error)(request, msg)
    return redirect('core:stat_requests')



def _student_has_enough(user, price: int) -> bool:
    if getattr(user, 'role', None) != 'student':
        return True
    bal = Ledger.student_balansi(user.id)
    return bal >= price

@login_required
def request_product(request, pk):
    """Mahsulotga so‘rov (savatcha) yuborish. Studentda bal yetmasa – rad etamiz."""
    product = get_object_or_404(Product, pk=pk)

    if not _student_has_enough(request.user, product.narxi):
        messages.error(request, "Chaqmoqingiz yetarli emas.")
        return redirect('store:products')

    # so‘rovni yaratish — sizdagi mavjud mantiq
    PurchaseRequest.objects.create(
        student=request.user,
        product=product,
        status=PurchaseRequest.PENDING
    )
    messages.success(request, "So‘rov yuborildi. Manager tasdiqlashi kutiladi.")
    return redirect('store:requests')