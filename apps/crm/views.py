from django.contrib import messages
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView, View

from apps.accounts.mixins import EquipeInternaMixin

from .forms import AtividadeForm, LeadForm
from .models import Estagio, Lead


class FunilView(EquipeInternaMixin, TemplateView):
    template_name = "crm/funil.html"

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

    def form_valid(self, form):
        messages.success(self.request, "Lead cadastrado.")
        return super().form_valid(form)


class LeadUpdateView(EquipeInternaMixin, UpdateView):
    model = Lead
    form_class = LeadForm
    template_name = "crm/form.html"

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
