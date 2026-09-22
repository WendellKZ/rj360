from django.urls import path

from .views import PortalHomeView, PortalProcessoView

app_name = "portal"

urlpatterns = [
    path("", PortalHomeView.as_view(), name="home"),
    path("processo/<int:pk>/", PortalProcessoView.as_view(), name="processo"),
]
