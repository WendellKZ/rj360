from django.urls import path

from . import views

app_name = "relacionamento"

urlpatterns = [
    path("processos/<int:pk>/", views.RelacionamentoView.as_view(), name="painel"),
    path("processos/<int:pk>/documentos/", views.SolicitarDocumentoView.as_view(), name="documento_solicitar"),
    path("documentos/<int:pk>/conferir/", views.ConferirDocumentoView.as_view(), name="documento_conferir"),
    path("processos/<int:pk>/reunioes/", views.ReuniaoCreateView.as_view(), name="reuniao_nova"),
    path("processos/<int:pk>/responder/", views.ResponderView.as_view(), name="responder"),
    path("credores/<int:pk>/evento/", views.EventoNegociacaoView.as_view(), name="credor_evento"),
]
