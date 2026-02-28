import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings") 
django.setup()

from accounts.forms import CenterAdminForm
from accounts.models import Center

c = Center.objects.first()
if getattr(c, 'features', None) is None or c.features == {}:
    c.features = {"dashboard": True, "students": True}

f = CenterAdminForm(instance=c)
print(f['features'].as_hidden())
