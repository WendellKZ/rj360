from django.contrib import admin

from .models import Diagnostico


@admin.register(Diagnostico)
class DiagnosticoAdmin(admin.ModelAdmin):
    list_display = ("criado_em", "empresa", "nome", "urgencia", "pontuacao", "lead", "atendido_em")
    list_filter = ("urgencia",)
    search_fields = ("empresa", "nome", "email", "telefone")
    readonly_fields = ("respostas", "pontuacao", "urgencia", "criado_em")
    autocomplete_fields = ("lead", "atendido_por")
