from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import CodigoAcesso, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "first_name", "last_name", "email", "tipo", "empresa", "is_staff")
    list_filter = ("tipo", "is_staff", "is_superuser", "is_active")
    autocomplete_fields = ("empresa",)
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Perfil RJ360", {"fields": ("tipo", "empresa", "cargo", "telefone")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Perfil RJ360", {"fields": ("tipo", "empresa", "cargo", "telefone")}),
    )


@admin.register(CodigoAcesso)
class CodigoAcessoAdmin(admin.ModelAdmin):
    """So para auditoria: o codigo em si nunca fica legivel."""

    list_display = ("criado_em", "usuario", "canal", "expira_em", "tentativas", "usado_em")
    list_filter = ("canal",)
    search_fields = ("usuario__username", "usuario__email")
    readonly_fields = ("usuario", "codigo_hash", "expira_em", "tentativas", "usado_em", "canal")

    def has_add_permission(self, request):
        return False
