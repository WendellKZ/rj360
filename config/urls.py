from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("", include("apps.publico.urls")),
    path("conta/", include("apps.accounts.urls")),
    path("empresas/", include("apps.empresas.urls")),
    path("processos/", include("apps.processos.urls")),
    path("prospeccao/", include("apps.crm.urls")),
    path("portal/", include("apps.portal.urls")),
    path("relacionamento/", include("apps.relacionamento.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
