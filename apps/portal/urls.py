from django.urls import path

from . import views

app_name = "portal"

urlpatterns = [
    path("", views.PortalHomeView.as_view(), name="home"),
    path("credores/", views.PortalCredoresView.as_view(), name="credores"),
    path("documentos/", views.PortalDocumentosView.as_view(), name="documentos"),
    path("documentos/<int:pk>/enviar/", views.EnviarDocumentoView.as_view(), name="documento_enviar"),
    path("reunioes/", views.PortalReunioesView.as_view(), name="reunioes"),
    path("conversa/", views.PortalConversaView.as_view(), name="conversa"),
    path("processo/<int:pk>/", views.PortalProcessoView.as_view(), name="processo"),
]
