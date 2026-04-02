from django.http import HttpResponseForbidden
from django_tenants.utils import get_tenant


class CenterStatusMiddleware:
    """
    Tenant deactivate bo‘lsa, hamma joyni bloklaydi (admin ham).
    Faqat public schema’da ishlamaydi.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant = get_tenant(request)

        # public schema bo‘lsa o'tkazib yuboramiz
        if getattr(tenant, "schema_name", None) in (None, "public"):
            return self.get_response(request)

        # tenant o‘chirilgan bo‘lsa blok
        if hasattr(tenant, "is_active") and not tenant.is_active:
            return HttpResponseForbidden("Bu o‘quv markaz vaqtincha bloklangan.")

        return self.get_response(request)
