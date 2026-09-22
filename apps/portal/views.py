from django.http import Http404
from django.views.generic import DetailView, TemplateView

from apps.accounts.mixins import ClienteMixin
from apps.processos.models import ProcessoRJ, StatusPrazo


class PortalHomeView(ClienteMixin, TemplateView):
    """Visao do cliente: o proprio processo, em linguagem simples."""

    template_name = "portal/home.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        empresa = self.request.user.empresa
        processo = (
            ProcessoRJ.objects.filter(empresa=empresa)
            .order_by("encerrado_em", "-data_distribuicao")
            .first()
        )
        contexto["empresa"] = empresa
        contexto["processo"] = processo
        if processo:
            contexto["andamentos"] = processo.andamentos.filter(visivel_cliente=True)[:15]
            contexto["documentos"] = processo.documentos.filter(visivel_cliente=True)[:10]
            contexto["prazos"] = processo.prazos.filter(status=StatusPrazo.PENDENTE).order_by("data_fim")[:10]
            contexto["parcelas"] = processo.parcelas.all()[:10]
        return contexto


class PortalProcessoView(ClienteMixin, DetailView):
    model = ProcessoRJ
    template_name = "portal/processo.html"
    context_object_name = "processo"

    def get_object(self, queryset=None):
        processo = super().get_object(queryset)
        if processo.empresa_id != self.request.user.empresa_id:
            raise Http404("Processo nao encontrado.")
        return processo

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["andamentos"] = self.object.andamentos.filter(visivel_cliente=True)
        contexto["documentos"] = self.object.documentos.filter(visivel_cliente=True)
        return contexto
