from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from django.contrib.auth import get_user_model
from .models import Ledger

User = get_user_model()

@login_required
def reyting(request):
    q = (Ledger.objects
         .values('student__id','student__ism','student__familya')
         .annotate(jami=Sum('ball'))
         .order_by('-jami'))
    return render(request, 'chaqmoq/reyting.html', {'rows': q})
