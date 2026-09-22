"""Lado interno do relacionamento: pedir documento, marcar reuniao, responder."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import View

from apps.accounts.mixins import EquipeInternaMixin
from apps.processos.models import Credor, ProcessoRJ

from .forms import (
    ConferenciaDocumentoForm,
    MensagemForm,
    ReuniaoForm,
    SolicitacaoDocumentoForm,
)
from .models import DocumentoSolicitado, StatusDocumento


class RelacionamentoView(EquipeInternaMixin, View):
    """Tudo que a equipe troca com a empresa, num lugar so."""

    template_name = "processos/relacionamento.html"

    def get(self, request, pk, **extra):
        processo = get_object_or_404(
            ProcessoRJ.objects.select_related("empresa"), pk=pk
        )
        contexto = {
            "processo": processo,
            "secao": "processos",
            "solicitacoes": processo.solicitacoes.all(),
            "reunioes": processo.reunioes.all(),
            "mensagens": processo.mensagens.select_related("autor"),
            "credores": processo.credores.prefetch_related("eventos").order_by("-valor_arrolado"),
            "form_solicitacao": extra.get("form_solicitacao") or SolicitacaoDocumentoForm(),
            "form_reuniao": extra.get("form_reuniao") or ReuniaoForm(),
            "form_mensagem": extra.get("form_mensagem") or MensagemForm(),
            "nao_lidas": processo.mensagens.filter(lida_em__isnull=True).exclude(
                autor__tipo="INTERNO"
            ).count(),
        }
        processo.mensagens.filter(lida_em__isnull=True).exclude(autor__tipo="INTERNO").update(
            lida_em=timezone.now()
        )
        return render(request, self.template_name, contexto)


class SolicitarDocumentoView(EquipeInternaMixin, View):
    def post(self, request, pk):
        processo = get_object_or_404(ProcessoRJ, pk=pk)
        form = SolicitacaoDocumentoForm(request.POST)
        if form.is_valid():
            solicitacao = form.save(commit=False)
            solicitacao.processo = processo
            solicitacao.solicitado_por = request.user
            solicitacao.save()
            messages.success(request, "Documento solicitado. Ele aparece no portal do cliente.")
        else:
            messages.error(request, "Confira os campos da solicitacao.")
        return redirect("relacionamento:painel", pk=processo.pk)


class ConferirDocumentoView(EquipeInternaMixin, View):
    """Marca o documento recebido como validado ou pede reenvio."""

    def post(self, request, pk):
        solicitacao = get_object_or_404(DocumentoSolicitado, pk=pk)
        form = ConferenciaDocumentoForm(request.POST, instance=solicitacao)
        if form.is_valid():
            form.save()
            messages.success(request, "Conferencia registrada.")
        else:
            messages.error(request, "Nao foi possivel registrar a conferencia.")
        return redirect("relacionamento:painel", pk=solicitacao.processo_id)


class ReuniaoCreateView(EquipeInternaMixin, View):
    def post(self, request, pk):
        processo = get_object_or_404(ProcessoRJ, pk=pk)
        form = ReuniaoForm(request.POST)
        if form.is_valid():
            reuniao = form.save(commit=False)
            reuniao.processo = processo
            reuniao.save()
            messages.success(request, "Reuniao registrada.")
        else:
            messages.error(request, "Confira os dados da reuniao.")
        return redirect("relacionamento:painel", pk=processo.pk)


class ResponderView(EquipeInternaMixin, View):
    def post(self, request, pk):
        processo = get_object_or_404(ProcessoRJ, pk=pk)
        form = MensagemForm(request.POST)
        if form.is_valid():
            mensagem = form.save(commit=False)
            mensagem.processo = processo
            mensagem.autor = request.user
            mensagem.save()
        else:
            messages.error(request, "Escreva a mensagem antes de enviar.")
        return redirect("relacionamento:painel", pk=processo.pk)


class EventoNegociacaoView(EquipeInternaMixin, View):
    """Registra um passo da negociacao com um credor e atualiza o estagio."""

    def post(self, request, pk):
        credor = get_object_or_404(Credor, pk=pk)
        descricao = (request.POST.get("descricao") or "").strip()
        estagio = request.POST.get("estagio_negociacao") or credor.estagio_negociacao
        valor = (request.POST.get("valor_negociado") or "").strip()

        if descricao:
            credor.eventos.create(descricao=descricao[:250], registrado_por=request.user)
        campos = []
        if estagio != credor.estagio_negociacao:
            credor.estagio_negociacao = estagio
            campos.append("estagio_negociacao")
        if valor:
            from apps.processos.importacao import converter_valor

            try:
                credor.valor_negociado = converter_valor(valor)
                campos.append("valor_negociado")
            except ValueError:
                messages.error(request, f"Valor invalido: {valor}")
        if campos:
            credor.save(update_fields=[*campos, "atualizado_em"])
        if descricao or campos:
            messages.success(request, "Negociacao atualizada.")
        return redirect("relacionamento:painel", pk=credor.processo_id)
