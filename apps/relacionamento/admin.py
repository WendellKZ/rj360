from django.contrib import admin

from .models import DocumentoSolicitado, Mensagem, Reuniao


@admin.register(DocumentoSolicitado)
class DocumentoSolicitadoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "processo", "status", "prazo", "enviado_em")
    list_filter = ("status",)
    search_fields = ("titulo", "processo__numero_cnj")
    autocomplete_fields = ("processo",)


@admin.register(Reuniao)
class ReuniaoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "processo", "quando", "status", "visivel_cliente")
    list_filter = ("status", "visivel_cliente")
    search_fields = ("titulo", "processo__numero_cnj")
    autocomplete_fields = ("processo",)
    date_hierarchy = "quando"


@admin.register(Mensagem)
class MensagemAdmin(admin.ModelAdmin):
    list_display = ("criado_em", "processo", "autor", "texto")
    search_fields = ("texto", "processo__numero_cnj")
    autocomplete_fields = ("processo", "autor")
