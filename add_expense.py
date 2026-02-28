import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings") # Adjust if different
django.setup()

from store.models import Expense
from accounts.models import Center
from datetime import datetime, date

c = Center.objects.first()
if c:
    # Check if there is already an expense for Fevral 2026?
    # Create one if not!
    Expense.objects.create(
        center=c,
        izoh="Markaz xarajatlari (Test)",
        summa=3000000,
        sana=datetime.now()
    )
    print("Added 3M expense for today.")
else:
    print("Center not found.")
