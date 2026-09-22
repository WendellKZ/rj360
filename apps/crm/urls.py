from django.urls import path

from . import views

app_name = "crm"

urlpatterns = [
    path("", views.FunilView.as_view(), name="funil"),
    path("leads/", views.LeadListView.as_view(), name="lista"),
    path("leads/novo/", views.LeadCreateView.as_view(), name="novo"),
    path("leads/<int:pk>/", views.LeadDetailView.as_view(), name="detalhe"),
    path("leads/<int:pk>/editar/", views.LeadUpdateView.as_view(), name="editar"),
    path("leads/<int:pk>/atividades/nova/", views.AtividadeCreateView.as_view(), name="atividade_nova"),
    path("leads/<int:pk>/mover/", views.MoverEstagioView.as_view(), name="mover"),
    path("leads/<int:pk>/converter/", views.ConverterLeadView.as_view(), name="converter"),
]
