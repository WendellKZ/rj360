from datetime import timedelta

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import TemplateView, View

from apps.accounts.mixins import EquipeInternaMixin
from apps.crm.models import Estagio, Lead
from apps.empresas.models import Empresa, SituacaoEmpresa
from apps.processos.models import FaseProcesso, Prazo, ProcessoRJ, StatusPrazo


class HomeView(LoginRequiredMixin, View):
    """Direciona equipe interna para o painel e cliente para o portal."""

    def get(self, request, *args, **kwargs):
        if request.user.is_cliente:
            return redirect("portal:home")
        return redirect("core:dashboard")


class DashboardView(EquipeInternaMixin, TemplateView):
    template_name = "core/dashboard.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        hoje = timezone.localdate()
        limite = hoje + timedelta(days=settings.PRAZO_ALERTA_DIAS)

        processos_ativos = ProcessoRJ.objects.filter(encerrado_em__isnull=True)

        contexto["total_clientes"] = Empresa.objects.filter(
            situacao=SituacaoEmpresa.CLIENTE
        ).count()
        contexto["total_processos"] = processos_ativos.count()

        contexto["prazos_criticos"] = (
            Prazo.objects.filter(status=StatusPrazo.PENDENTE, data_fim__lte=limite)
            .select_related("processo", "processo__empresa", "responsavel")
            .order_by("data_fim")[:10]
        )
        contexto["total_prazos_atrasados"] = Prazo.objects.filter(
            status=StatusPrazo.PENDENTE, data_fim__lt=hoje
        ).count()

        fases = {
            linha["fase"]: linha["total"]
            for linha in processos_ativos.values("fase").annotate(total=Count("id"))
        }
        contexto["por_fase"] = [
            {"fase": valor, "rotulo": rotulo, "total": fases.get(valor, 0), "cor": FaseProcesso.cor(valor)}
            for valor, rotulo in FaseProcesso.choices
            if fases.get(valor, 0)
        ]

        contexto["proximas_agc"] = (
            processos_ativos.filter(data_agc__gte=hoje)
            .select_related("empresa")
            .order_by("data_agc")[:5]
        )

        leads_abertos = Lead.objects.exclude(estagio__in=[Estagio.GANHO, Estagio.PERDIDO])
        contexto["total_leads"] = leads_abertos.count()
        contexto["pipeline_valor"] = leads_abertos.aggregate(t=Sum("valor_estimado"))["t"] or 0
        contexto["leads_atrasados"] = (
            leads_abertos.filter(proximo_contato__lt=hoje)
            .select_related("responsavel")
            .order_by("proximo_contato")[:5]
        )
        contexto["leads_por_estagio"] = [
            {
                "rotulo": rotulo,
                "total": leads_abertos.filter(estagio=valor).count(),
            }
            for valor, rotulo in Estagio.funil()
        ]

        contexto["processos_stay"] = sorted(
            [
                processo
                for processo in processos_ativos.select_related("empresa").filter(
                    data_deferimento__isnull=False, data_concessao__isnull=True
                )
                if processo.stay_dias_restantes is not None
                and processo.stay_dias_restantes <= 60
            ],
            key=lambda p: p.stay_dias_restantes,
        )[:5]

        contexto["empresas_sem_processo"] = Empresa.objects.filter(
            situacao=SituacaoEmpresa.CLIENTE
        ).annotate(qtd=Count("processos", filter=Q(processos__encerrado_em__isnull=True))).filter(qtd=0)[:5]
        return contexto
