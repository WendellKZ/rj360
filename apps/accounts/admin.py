from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


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
