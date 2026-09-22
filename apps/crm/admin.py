from django.contrib import admin

from .models import Atividade, Lead


class AtividadeInline(admin.TabularInline):
    model = Atividade
    extra = 0
    fields = ("data", "tipo", "titulo", "autor")


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        "razao_social", "cidade", "uf", "situacao_juridica", "estagio",
        "valor_estimado", "responsavel", "proximo_contato",
    )
    list_filter = ("estagio", "situacao_juridica", "origem", "uf", "porte")
    search_fields = ("razao_social", "nome_fantasia", "cnpj", "contato_nome")
    autocomplete_fields = ("responsavel", "empresa")
    inlines = [AtividadeInline]


@admin.register(Atividade)
class AtividadeAdmin(admin.ModelAdmin):
    list_display = ("data", "lead", "tipo", "titulo", "autor")
    list_filter = ("tipo",)
    search_fields = ("titulo", "descricao", "lead__razao_social")
    autocomplete_fields = ("lead", "autor")
    date_hierarchy = "data"
