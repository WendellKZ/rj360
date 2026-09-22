from django.contrib import messages
from django.db.models import Count, Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.accounts.mixins import EquipeInternaMixin

from .forms import ContatoForm, EmpresaForm
from .models import Empresa


class EmpresaListView(EquipeInternaMixin, ListView):
    model = Empresa
    template_name = "empresas/lista.html"
    context_object_name = "empresas"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            Empresa.objects.select_related("responsavel")
            .annotate(processos_ativos=Count("processos", filter=Q(processos__encerrado_em__isnull=True)))
            .order_by("razao_social")
        )
        busca = self.request.GET.get("q", "").strip()
        situacao = self.request.GET.get("situacao", "").strip()
        if busca:
            qs = qs.filter(
                Q(razao_social__icontains=busca)
                | Q(nome_fantasia__icontains=busca)
                | Q(cnpj__icontains=busca)
            )
        if situacao:
            qs = qs.filter(situacao=situacao)
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.request.GET.get("q", "")
        contexto["situacao"] = self.request.GET.get("situacao", "")
        return contexto


class EmpresaDetailView(EquipeInternaMixin, DetailView):
    model = Empresa
    template_name = "empresas/detalhe.html"
    context_object_name = "empresa"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["processos"] = self.object.processos.order_by("-data_distribuicao")
        contexto["contatos"] = self.object.contatos.all()
        contexto["form_contato"] = ContatoForm()
        return contexto

    def post(self, request, *args, **kwargs):
        """Cadastro rapido de contato pela propria pagina da empresa."""
        self.object = self.get_object()
        form = ContatoForm(request.POST)
        if form.is_valid():
            contato = form.save(commit=False)
            contato.empresa = self.object
            contato.save()
            messages.success(request, "Contato adicionado.")
        else:
            messages.error(request, "Verifique os dados do contato.")
        contexto = self.get_context_data(object=self.object)
        contexto["form_contato"] = form
        return self.render_to_response(contexto)


class EmpresaCreateView(EquipeInternaMixin, CreateView):
    model = Empresa
    form_class = EmpresaForm
    template_name = "empresas/form.html"

    def form_valid(self, form):
        messages.success(self.request, "Empresa cadastrada.")
        return super().form_valid(form)


class EmpresaUpdateView(EquipeInternaMixin, UpdateView):
    model = Empresa
    form_class = EmpresaForm
    template_name = "empresas/form.html"

    def form_valid(self, form):
        messages.success(self.request, "Empresa atualizada.")
        return super().form_valid(form)
