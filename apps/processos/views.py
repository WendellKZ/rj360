from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from apps.accounts.mixins import EquipeInternaMixin

from apps.integracoes.models import StatusSincronizacao
from apps.integracoes.services import sincronizar_processo

from .forms import (
    AndamentoForm,
    CredorForm,
    DocumentoForm,
    ImportacaoCredoresForm,
    ParcelaForm,
    PrazoForm,
    ProcessoForm,
)
from .importacao import PlanilhaInvalida, aplicar_importacao, ler_planilha, planilha_modelo
from .models import FaseProcesso, ImportacaoCredores, Prazo, ProcessoRJ, StatusPrazo
from .services import gerar_prazos_legais, resumo_credores


class ProcessoListView(EquipeInternaMixin, ListView):
    model = ProcessoRJ
    template_name = "processos/lista.html"
    extra_context = {"secao": "processos"}
    context_object_name = "processos"
    paginate_by = 25

    def get_queryset(self):
        qs = ProcessoRJ.objects.select_related("empresa")
        busca = self.request.GET.get("q", "").strip()
        fase = self.request.GET.get("fase", "").strip()
        if busca:
            qs = qs.filter(
                Q(numero_cnj__icontains=busca)
                | Q(empresa__razao_social__icontains=busca)
                | Q(empresa__nome_fantasia__icontains=busca)
            )
        if fase:
            qs = qs.filter(fase=fase)
        if self.request.GET.get("ativos") == "1":
            qs = qs.filter(encerrado_em__isnull=True)
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.request.GET.get("q", "")
        contexto["fase_atual"] = self.request.GET.get("fase", "")
        contexto["fases"] = FaseProcesso.choices
        return contexto


class ProcessoDetailView(EquipeInternaMixin, DetailView):
    model = ProcessoRJ
    template_name = "processos/detalhe.html"
    extra_context = {"secao": "processos"}
    context_object_name = "processo"

    def get_queryset(self):
        return ProcessoRJ.objects.select_related("empresa")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        processo = self.object
        contexto["andamentos"] = processo.andamentos.select_related("registrado_por")[:50]
        contexto["prazos"] = processo.prazos.select_related("responsavel")
        contexto["documentos"] = processo.documentos.all()
        contexto["credores"] = processo.credores.all()
        contexto["parcelas"] = processo.parcelas.all()
        contexto["resumo_credores"] = resumo_credores(processo)
        contexto["form_andamento"] = kwargs.get("form_andamento") or AndamentoForm()
        contexto["form_prazo"] = kwargs.get("form_prazo") or PrazoForm()
        contexto["form_documento"] = kwargs.get("form_documento") or DocumentoForm()
        contexto["form_credor"] = kwargs.get("form_credor") or CredorForm()
        contexto["form_parcela"] = kwargs.get("form_parcela") or ParcelaForm()
        contexto["ultima_sincronizacao"] = processo.sincronizacoes.first()
        return contexto


class ProcessoCreateView(EquipeInternaMixin, CreateView):
    model = ProcessoRJ
    form_class = ProcessoForm
    template_name = "processos/form.html"
    extra_context = {"secao": "processos"}

    def form_valid(self, form):
        resposta = super().form_valid(form)
        criados = gerar_prazos_legais(self.object, responsavel=self.request.user)
        if criados:
            messages.info(self.request, f"{len(criados)} prazo(s) legal(is) gerado(s) automaticamente.")
        messages.success(self.request, "Processo cadastrado.")
        return resposta


class ProcessoUpdateView(EquipeInternaMixin, UpdateView):
    model = ProcessoRJ
    form_class = ProcessoForm
    template_name = "processos/form.html"
    extra_context = {"secao": "processos"}

    def form_valid(self, form):
        resposta = super().form_valid(form)
        gerar_prazos_legais(self.object, responsavel=self.request.user)
        messages.success(self.request, "Processo atualizado.")
        return resposta


class _ProcessoSubCreate(EquipeInternaMixin, View):
    """Base para cadastros feitos dentro da pagina do processo."""

    form_class = None
    campo_contexto = ""
    mensagem = "Registro adicionado."

    def post(self, request, pk):
        processo = get_object_or_404(ProcessoRJ, pk=pk)
        form = self.form_class(request.POST, request.FILES or None)
        if form.is_valid():
            objeto = form.save(commit=False)
            objeto.processo = processo
            self.antes_de_salvar(objeto, request)
            objeto.save()
            messages.success(request, self.mensagem)
        else:
            messages.error(request, "Nao foi possivel salvar. Confira os campos destacados.")
        return redirect(processo.get_absolute_url())

    def antes_de_salvar(self, objeto, request):
        return None


class AndamentoCreateView(_ProcessoSubCreate):
    form_class = AndamentoForm
    mensagem = "Andamento registrado."

    def antes_de_salvar(self, objeto, request):
        objeto.registrado_por = request.user


class PrazoCreateView(_ProcessoSubCreate):
    form_class = PrazoForm
    mensagem = "Prazo cadastrado."


class DocumentoCreateView(_ProcessoSubCreate):
    form_class = DocumentoForm
    mensagem = "Documento anexado."

    def antes_de_salvar(self, objeto, request):
        objeto.enviado_por = request.user


class CredorCreateView(_ProcessoSubCreate):
    form_class = CredorForm
    mensagem = "Credor cadastrado."


class ParcelaCreateView(_ProcessoSubCreate):
    form_class = ParcelaForm
    mensagem = "Parcela cadastrada."


class GerarPrazosView(EquipeInternaMixin, View):
    def post(self, request, pk):
        processo = get_object_or_404(ProcessoRJ, pk=pk)
        criados = gerar_prazos_legais(processo, responsavel=request.user)
        if criados:
            messages.success(request, f"{len(criados)} prazo(s) legal(is) criado(s).")
        else:
            messages.info(request, "Nenhum prazo novo: os marcos ja estao cadastrados.")
        return redirect(processo.get_absolute_url())


class PrazoConcluirView(EquipeInternaMixin, View):
    def post(self, request, pk):
        prazo = get_object_or_404(Prazo, pk=pk)
        prazo.status = StatusPrazo.CUMPRIDO
        prazo.concluido_em = timezone.localdate()
        prazo.save(update_fields=["status", "concluido_em", "atualizado_em"])
        if request.headers.get("HX-Request"):
            return render(request, "processos/partials/linha_prazo.html", {"prazo": prazo})
        messages.success(request, "Prazo marcado como cumprido.")
        return redirect(prazo.processo.get_absolute_url())


class AgendaPrazosView(EquipeInternaMixin, ListView):
    template_name = "processos/agenda.html"
    extra_context = {"secao": "prazos"}
    context_object_name = "prazos"
    paginate_by = 50

    def get_queryset(self):
        qs = Prazo.objects.select_related("processo", "processo__empresa", "responsavel")
        status = self.request.GET.get("status", StatusPrazo.PENDENTE)
        if status:
            qs = qs.filter(status=status)
        if self.request.GET.get("meus") == "1":
            qs = qs.filter(responsavel=self.request.user)
        return qs.order_by("data_fim")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        hoje = timezone.localdate()
        contexto["hoje"] = hoje
        contexto["limite_alerta"] = hoje + timedelta(days=settings.PRAZO_ALERTA_DIAS)
        contexto["status_atual"] = self.request.GET.get("status", StatusPrazo.PENDENTE)
        contexto["status_opcoes"] = StatusPrazo.choices
        return contexto


class SincronizarDataJudView(EquipeInternaMixin, View):
    """Importa as movimentacoes do processo a partir da API publica do CNJ."""

    def post(self, request, pk):
        processo = get_object_or_404(ProcessoRJ, pk=pk)
        registro = sincronizar_processo(processo, usuario=request.user)
        if registro.status == StatusSincronizacao.SUCESSO:
            messages.success(request, f"Sincronizado com o tribunal: {registro.mensagem}")
        elif registro.status == StatusSincronizacao.SEM_RESULTADO:
            messages.warning(request, registro.mensagem)
        else:
            messages.error(request, f"Nao foi possivel sincronizar: {registro.mensagem}")
        return redirect(processo.get_absolute_url())


class ImportarCredoresView(EquipeInternaMixin, View):
    """Passo 1: recebe a planilha e mostra a previa para conferencia."""

    template_name = "processos/importar_credores.html"

    def get(self, request, pk):
        processo = get_object_or_404(ProcessoRJ, pk=pk)
        return render(
            request,
            self.template_name,
            {"processo": processo, "form": ImportacaoCredoresForm(), "secao": "processos"},
        )

    def post(self, request, pk):
        processo = get_object_or_404(ProcessoRJ, pk=pk)
        form = ImportacaoCredoresForm(request.POST, request.FILES)
        contexto = {"processo": processo, "form": form, "secao": "processos"}
        if not form.is_valid():
            return render(request, self.template_name, contexto)

        arquivo = form.cleaned_data["arquivo"]
        try:
            resultado = ler_planilha(arquivo, arquivo.name)
        except PlanilhaInvalida as erro:
            form.add_error("arquivo", str(erro))
            return render(request, self.template_name, contexto)

        arquivo.seek(0)
        importacao = ImportacaoCredores.objects.create(
            processo=processo,
            arquivo=arquivo,
            enviado_por=request.user,
            linhas_lidas=len(resultado.linhas),
            linhas_validas=len(resultado.validas),
        )
        contexto.update(
            {
                "resultado": resultado,
                "importacao": importacao,
                "politica": form.cleaned_data["politica"],
            }
        )
        return render(request, self.template_name, contexto)


class ConfirmarImportacaoCredoresView(EquipeInternaMixin, View):
    """Passo 2: relê o arquivo salvo e grava o que foi conferido."""

    def post(self, request, pk):
        importacao = get_object_or_404(ImportacaoCredores, pk=pk)
        politica = request.POST.get("politica", "atualizar")
        if politica not in {"atualizar", "ignorar", "duplicar"}:
            politica = "atualizar"
        try:
            with importacao.arquivo.open("rb") as arquivo:
                resultado = ler_planilha(arquivo, importacao.arquivo.name)
        except PlanilhaInvalida as erro:
            messages.error(request, f"Nao foi possivel reler a planilha: {erro}")
            return redirect(importacao.processo.get_absolute_url())

        numeros = aplicar_importacao(importacao, resultado, politica)
        messages.success(
            request,
            f"Quadro de credores atualizado: {numeros['criados']} criado(s), "
            f"{numeros['atualizados']} atualizado(s), {numeros['ignorados']} ignorado(s)"
            + (f", {numeros['com_erro']} linha(s) com erro descartada(s)." if numeros["com_erro"] else "."),
        )
        return redirect(importacao.processo.get_absolute_url())


class ModeloCredoresView(EquipeInternaMixin, View):
    """Baixa a planilha modelo preenchida com exemplos."""

    def get(self, request):
        resposta = HttpResponse(
            planilha_modelo(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        resposta["Content-Disposition"] = 'attachment; filename="modelo-credores-rj360.xlsx"'
        return resposta
