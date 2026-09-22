from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class EquipeInternaMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restringe a view a usuarios da equipe interna."""

    def test_func(self) -> bool:
        return bool(self.request.user.is_authenticated and self.request.user.is_interno)


class ClienteMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restringe a view a usuarios do portal do cliente."""

    def test_func(self) -> bool:
        user = self.request.user
        return bool(user.is_authenticated and user.is_cliente and user.empresa_id)
