from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    allowed_roles: list[str] = []

    def test_func(self):
        u = self.request.user
        return u.is_authenticated and (u.role in self.allowed_roles or u.is_superuser)
