from django.urls import path

from .views import EmpresaCreateView, EmpresaDetailView, EmpresaListView, EmpresaUpdateView

app_name = "empresas"

urlpatterns = [
    path("", EmpresaListView.as_view(), name="lista"),
    path("nova/", EmpresaCreateView.as_view(), name="nova"),
    path("<int:pk>/", EmpresaDetailView.as_view(), name="detalhe"),
    path("<int:pk>/editar/", EmpresaUpdateView.as_view(), name="editar"),
]
