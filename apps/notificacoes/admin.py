from django.contrib import admin

from .models import AvisoPrazo


@admin.register(AvisoPrazo)
class AvisoPrazoAdmin(admin.ModelAdmin):
    list_display = ("enviado_em", "destinatario", "prazo", "data")
    list_filter = ("data",)
    search_fields = ("destinatario", "prazo__titulo", "prazo__processo__numero_cnj")
    autocomplete_fields = ("prazo",)
    readonly_fields = ("prazo", "destinatario", "data", "enviado_em")

    def has_add_permission(self, request):
        return False
