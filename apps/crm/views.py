from django.contrib import messages
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView, View

from apps.publico.models import Diagnostico, Urgencia as UrgenciaDiagnostico

from apps.accounts.mixins import EquipeInternaMixin

from .forms import AtividadeForm, LeadForm
from .models import Estagio, Lead, OrigemLead, SituacaoJuridica, Urgencia


class FunilView(EquipeInternaMixin, TemplateView):
    template_name = "crm/funil.html"
    extra_context = {"secao": "funil"}

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        base = Lead.objects.select_related("responsavel")
        if self.request.GET.get("meus") == "1":
            base = base.filter(responsavel=self.request.user)
        colunas = []
        for valor, rotulo in Estagio.funil():
            leads = base.filter(estagio=valor)
            colunas.append(
                {
                    "valor": valor,
                    "rotulo": rotulo,
                    "leads": leads,
                    "total": leads.count(),
                    "valor_total": leads.aggregate(t=Sum("valor_estimado"))["t"] or 0,
                }
            )
        contexto["colunas"] = colunas
        contexto["estagios"] = Estagio.choices
        contexto["ganhos"] = base.filter(estagio=Estagio.GANHO).count()
        contexto["perdidos"] = base.filter(estagio=Estagio.PERDIDO).count()
        return contexto


class LeadListView(EquipeInternaMixin, ListView):
    model = Lead
    template_name = "crm/lista.html"
    extra_context = {"secao": "leads"}
    context_object_name = "leads"
    paginate_by = 25

    def get_queryset(self):
        qs = Lead.objects.select_related("responsavel", "empresa")
        busca = self.request.GET.get("q", "").strip()
        estagio = self.request.GET.get("estagio", "").strip()
        if busca:
            qs = qs.filter(
                Q(razao_social__icontains=busca)
                | Q(nome_fantasia__icontains=busca)
                | Q(cnpj__icontains=busca)
                | Q(contato_nome__icontains=busca)
            )
        if estagio:
            qs = qs.filter(estagio=estagio)
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.request.GET.get("q", "")
        contexto["estagio_atual"] = self.request.GET.get("estagio", "")
        contexto["estagios"] = Estagio.choices
        return contexto


class LeadDetailView(EquipeInternaMixin, DetailView):
    model = Lead
    template_name = "crm/detalhe.html"
    extra_context = {"secao": "leads"}
    context_object_name = "lead"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["atividades"] = self.object.atividades.select_related("autor")
        contexto["form_atividade"] = AtividadeForm()
        contexto["estagios"] = Estagio.choices
        return contexto


class LeadCreateView(EquipeInternaMixin, CreateView):
    model = Lead
    form_class = LeadForm
    template_name = "crm/form.html"
    extra_context = {"secao": "leads"}

    def form_valid(self, form):
        messages.success(self.request, "Lead cadastrado.")
        return super().form_valid(form)


class LeadUpdateView(EquipeInternaMixin, UpdateView):
    model = Lead
    form_class = LeadForm
    template_name = "crm/form.html"
    extra_context = {"secao": "leads"}

    def form_valid(self, form):
        messages.success(self.request, "Lead atualizado.")
        return super().form_valid(form)


class AtividadeCreateView(EquipeInternaMixin, View):
    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk)
        form = AtividadeForm(request.POST)
        if form.is_valid():
            atividade = form.save(commit=False)
            atividade.lead = lead
            atividade.autor = request.user
            atividade.save()
            messages.success(request, "Atividade registrada.")
        else:
            messages.error(request, "Confira os campos da atividade.")
        return redirect(lead.get_absolute_url())


class MoverEstagioView(EquipeInternaMixin, View):
    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk)
        novo = request.POST.get("estagio")
        if novo in dict(Estagio.choices):
            lead.estagio = novo
            lead.save(update_fields=["estagio", "atualizado_em"])
            messages.success(request, f"Lead movido para {lead.get_estagio_display()}.")
        else:
            messages.error(request, "Estagio invalido.")
        destino = request.POST.get("next") or lead.get_absolute_url()
        return redirect(destino)


class ConverterLeadView(EquipeInternaMixin, View):
    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk)
        if lead.empresa_id:
            messages.info(request, "Este lead ja foi convertido.")
            return redirect(lead.empresa.get_absolute_url())
        empresa = lead.converter_em_empresa()
        messages.success(request, "Lead convertido em empresa cliente.")
        return redirect(empresa.get_absolute_url())


# ---------------------------------------------------------------- diagnosticos

URGENCIA_DO_DIAGNOSTICO = {
    UrgenciaDiagnostico.ALTA: Urgencia.ALTA,
    UrgenciaDiagnostico.MEDIA: Urgencia.MEDIA,
    UrgenciaDiagnostico.BAIXA: Urgencia.BAIXA,
}

SITUACAO_PELA_RESPOSTA = {
    "Execução judicial": SituacaoJuridica.RJ_EM_CURSO,
    "Protesto / Serasa": SituacaoJuridica.PRE_CRISE,
    "Fornecedor cortando prazo": SituacaoJuridica.PRE_CRISE,
    "Apertando, mas controlando": SituacaoJuridica.PRE_CRISE,
}


class DiagnosticosView(EquipeInternaMixin, ListView):
    """Diagnosticos recebidos pelo site, na ordem de quem espera ha mais tempo."""

    template_name = "crm/diagnosticos.html"
    context_object_name = "diagnosticos"
    paginate_by = 30
    extra_context = {"secao": "diagnosticos"}

    def get_queryset(self):
        qs = Diagnostico.objects.select_related("lead", "atendido_por")
        filtro = self.request.GET.get("filtro", "abertos")
        if filtro == "abertos":
            qs = qs.filter(lead__isnull=True, atendido_em__isnull=True)
        elif filtro in {"ALTA", "MEDIA", "BAIXA", "PF"}:
            qs = qs.filter(urgencia=filtro)
        return qs.order_by("-criado_em")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["filtro"] = self.request.GET.get("filtro", "abertos")
        abertos = Diagnostico.objects.filter(lead__isnull=True, atendido_em__isnull=True)
        contexto["total_abertos"] = abertos.count()
        contexto["total_estourados"] = sum(1 for d in abertos if d.sla_estourado)
        return contexto


class CriarLeadDoDiagnosticoView(EquipeInternaMixin, View):
    """Transforma o diagnostico em lead no topo do funil."""

    def post(self, request, pk):
        diagnostico = get_object_or_404(Diagnostico, pk=pk)
        if diagnostico.lead_id:
            messages.info(request, "Este diagnostico ja virou lead.")
            return redirect(diagnostico.lead.get_absolute_url())

        respostas = {item.get("chave"): item.get("resposta") for item in diagnostico.respostas or []}
        lead = Lead.objects.create(
            razao_social=diagnostico.empresa or diagnostico.nome or f"Diagnóstico #{diagnostico.pk}",
            contato_nome=diagnostico.nome,
            contato_email=diagnostico.email,
            contato_telefone=diagnostico.telefone,
            origem=OrigemLead.SITE,
            situacao_juridica=SITUACAO_PELA_RESPOSTA.get(
                respostas.get("situacao"), SituacaoJuridica.PRE_CRISE
            ),
            estagio=Estagio.NOVO,
            urgencia=URGENCIA_DO_DIAGNOSTICO.get(diagnostico.urgencia, Urgencia.NAO_AVALIADA),
            responsavel=request.user,
            proximo_contato=timezone.localdate(),
            observacoes="\n".join(
                f"{item.get('pergunta')} {item.get('resposta')}" for item in diagnostico.respostas or []
            ),
        )
        diagnostico.lead = lead
        diagnostico.atendido_em = timezone.now()
        diagnostico.atendido_por = request.user
        diagnostico.save(update_fields=["lead", "atendido_em", "atendido_por", "atualizado_em"])

        lead.atividades.create(
            titulo="Diagnóstico recebido pelo site",
            descricao=f"Pontuação {diagnostico.pontuacao} · {diagnostico.get_urgencia_display()}",
            autor=request.user,
        )
        messages.success(request, "Lead criado no funil, em “Novo lead”.")
        return redirect(lead.get_absolute_url())


class MarcarContatoDiagnosticoView(EquipeInternaMixin, View):
    """Registra que alguem ja falou com a pessoa, sem criar lead."""

    def post(self, request, pk):
        diagnostico = get_object_or_404(Diagnostico, pk=pk)
        diagnostico.atendido_em = timezone.now()
        diagnostico.atendido_por = request.user
        diagnostico.save(update_fields=["atendido_em", "atendido_por", "atualizado_em"])
        messages.success(request, "Contato registrado.")
        return redirect("crm:diagnosticos")
