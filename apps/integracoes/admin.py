from django.contrib import admin

from .models import SincronizacaoDataJud


@admin.register(SincronizacaoDataJud)
class SincronizacaoDataJudAdmin(admin.ModelAdmin):
    list_display = (
        "executado_em", "processo", "status", "movimentos_recebidos",
        "andamentos_criados", "executado_por",
    )
    list_filter = ("status",)
    search_fields = ("processo__numero_cnj", "mensagem")
    autocomplete_fields = ("processo",)
    readonly_fields = (
        "processo", "executado_em", "executado_por", "status",
        "movimentos_recebidos", "andamentos_criados", "atualizado_no_tribunal_em", "mensagem",
    )

    def has_add_permission(self, request):
        return False
