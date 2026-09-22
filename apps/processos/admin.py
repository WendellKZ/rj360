from django.contrib import admin

from .models import Andamento, Credor, Documento, Parcela, Prazo, ProcessoRJ


class AndamentoInline(admin.TabularInline):
    model = Andamento
    extra = 0
    fields = ("data", "tipo", "titulo", "visivel_cliente")


class PrazoInline(admin.TabularInline):
    model = Prazo
    extra = 0
    fields = ("titulo", "base_legal", "data_inicio", "data_fim", "status", "responsavel")


@admin.register(ProcessoRJ)
class ProcessoRJAdmin(admin.ModelAdmin):
    list_display = ("numero_cnj", "empresa", "fase", "comarca", "data_deferimento", "data_concessao")
    list_filter = ("fase", "tribunal", "stay_prorrogado")
    search_fields = ("numero_cnj", "empresa__razao_social", "empresa__cnpj")
    autocomplete_fields = ("empresa",)
    date_hierarchy = "data_distribuicao"
    inlines = [PrazoInline, AndamentoInline]
    fieldsets = (
        (None, {"fields": ("empresa", "numero_cnj", "fase", "valor_divida")}),
        ("Juizo", {"fields": ("tribunal", "comarca", "vara", "juiz", "advogado")}),
        ("Administrador judicial", {"fields": ("administrador_judicial", "aj_email", "aj_telefone")}),
        (
            "Marcos processuais",
            {
                "fields": (
                    "data_distribuicao",
                    "data_deferimento",
                    "data_edital_52",
                    "data_plano",
                    "data_edital_53",
                    "data_agc",
                    "data_concessao",
                    "encerrado_em",
                    "stay_prorrogado",
                )
            },
        ),
        ("Outros", {"fields": ("observacoes",)}),
    )


@admin.register(Andamento)
class AndamentoAdmin(admin.ModelAdmin):
    list_display = ("data", "processo", "tipo", "titulo", "fonte", "visivel_cliente")
    list_filter = ("tipo", "fonte", "visivel_cliente")
    search_fields = ("titulo", "descricao", "processo__numero_cnj")
    autocomplete_fields = ("processo",)
    date_hierarchy = "data"


@admin.register(Prazo)
class PrazoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "processo", "data_fim", "status", "responsavel")
    list_filter = ("status", "tipo")
    search_fields = ("titulo", "processo__numero_cnj")
    autocomplete_fields = ("processo", "responsavel")
    date_hierarchy = "data_fim"


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "processo", "categoria", "data_referencia", "visivel_cliente")
    list_filter = ("categoria", "visivel_cliente")
    search_fields = ("titulo", "processo__numero_cnj")
    autocomplete_fields = ("processo",)


@admin.register(Credor)
class CredorAdmin(admin.ModelAdmin):
    list_display = ("nome", "processo", "classe", "valor_arrolado", "valor_habilitado", "situacao")
    list_filter = ("classe", "situacao", "sujeito_rj")
    search_fields = ("nome", "documento", "processo__numero_cnj")
    autocomplete_fields = ("processo",)


@admin.register(Parcela)
class ParcelaAdmin(admin.ModelAdmin):
    list_display = ("descricao", "processo", "classe", "vencimento", "valor_previsto", "status")
    list_filter = ("status", "classe")
    search_fields = ("descricao", "processo__numero_cnj")
    autocomplete_fields = ("processo",)
    date_hierarchy = "vencimento"
