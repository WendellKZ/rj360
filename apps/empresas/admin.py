from django.contrib import admin

from .models import Contato, Empresa


class ContatoInline(admin.TabularInline):
    model = Contato
    extra = 1


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("razao_social", "cnpj", "porte", "situacao", "cidade", "uf", "responsavel")
    list_filter = ("situacao", "porte", "uf")
    search_fields = ("razao_social", "nome_fantasia", "cnpj")
    inlines = [ContatoInline]
    autocomplete_fields = ("responsavel",)


@admin.register(Contato)
class ContatoAdmin(admin.ModelAdmin):
    list_display = ("nome", "empresa", "cargo", "email", "telefone", "principal")
    list_filter = ("principal",)
    search_fields = ("nome", "email", "empresa__razao_social")
    autocomplete_fields = ("empresa",)
