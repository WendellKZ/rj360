from django.urls import path

from . import views

app_name = "processos"

urlpatterns = [
    path("", views.ProcessoListView.as_view(), name="lista"),
    path("novo/", views.ProcessoCreateView.as_view(), name="novo"),
    path("agenda/", views.AgendaPrazosView.as_view(), name="agenda"),
    path("<int:pk>/", views.ProcessoDetailView.as_view(), name="detalhe"),
    path("<int:pk>/editar/", views.ProcessoUpdateView.as_view(), name="editar"),
    path("<int:pk>/andamentos/novo/", views.AndamentoCreateView.as_view(), name="andamento_novo"),
    path("<int:pk>/prazos/novo/", views.PrazoCreateView.as_view(), name="prazo_novo"),
    path("<int:pk>/prazos/gerar/", views.GerarPrazosView.as_view(), name="prazos_gerar"),
    path("<int:pk>/sincronizar/", views.SincronizarDataJudView.as_view(), name="sincronizar"),
    path("<int:pk>/documentos/novo/", views.DocumentoCreateView.as_view(), name="documento_novo"),
    path("<int:pk>/credores/novo/", views.CredorCreateView.as_view(), name="credor_novo"),
    path("<int:pk>/credores/importar/", views.ImportarCredoresView.as_view(), name="credores_importar"),
    path("credores/modelo.xlsx", views.ModeloCredoresView.as_view(), name="credores_modelo"),
    path(
        "credores/importacoes/<int:pk>/confirmar/",
        views.ConfirmarImportacaoCredoresView.as_view(),
        name="credores_importar_confirmar",
    ),
    path("<int:pk>/parcelas/nova/", views.ParcelaCreateView.as_view(), name="parcela_nova"),
    path("prazos/<int:pk>/concluir/", views.PrazoConcluirView.as_view(), name="prazo_concluir"),
]
