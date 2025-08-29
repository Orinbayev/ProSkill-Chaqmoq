from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Product, PurchaseRequest
from .services import approve_purchase

@login_required
def products(request):
    items = Product.objects.all().order_by('-yaratilgan')
    return render(request, 'store/products.html', {'items': items})

@login_required
def product_detail(request, pk):
    item = get_object_or_404(Product, pk=pk)
    return render(request, 'store/product_detail.html', {'item': item})

@login_required
def create_request(request, pk):
    item = get_object_or_404(Product, pk=pk)
    if request.user.role != 'student':
        messages.error(request, 'Faqat o‘quvchi so‘rov yaratishi mumkin.')
        return redirect('store:products')
    PurchaseRequest.objects.create(student=request.user, product=item, qty=1)
    messages.success(request, 'Xarid so‘rovi yuborildi. Manager tasdiqlashi kutiladi.')
    return redirect('store:products')

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
