"""Portal do cliente: a empresa acompanha o proprio processo."""
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import DetailView, TemplateView, View

from apps.accounts.mixins import ClienteMixin
from apps.processos.models import Credor, ProcessoRJ, StatusPrazo
from apps.relacionamento.forms import EnvioDocumentoForm, MensagemForm
from apps.relacionamento.models import DocumentoSolicitado, Mensagem, Reuniao, StatusDocumento


def montar_trilha(processo) -> list[dict]:
    """As seis etapas da RJ como o cliente as acompanha."""
    etapas = [
        ("Pedido protocolado", processo.data_distribuicao),
        ("Processamento deferido", processo.data_deferimento),
        ("Credores habilitados", processo.data_edital_52),
        ("Plano apresentado", processo.data_plano),
        ("Assembleia de credores", processo.data_agc),
        ("Recuperacao concedida", processo.data_concessao),
    ]
    trilha = []
    for indice, (nome, data) in enumerate(etapas, start=1):
        trilha.append({"numero": indice, "nome": nome, "data": data, "concluida": bool(data)})
    concluidas = [etapa for etapa in trilha if etapa["concluida"]]
    atual = len(concluidas) + 1 if len(concluidas) < len(trilha) else len(trilha)
    for etapa in trilha:
        etapa["atual"] = etapa["numero"] == atual and not etapa["concluida"]
    return trilha


class BasePortalView(ClienteMixin, TemplateView):
    """Base das telas do portal: sempre o processo da propria empresa."""

    secao = ""

    @property
    def processo(self):
        if not hasattr(self, "_processo"):
            self._processo = (
                ProcessoRJ.objects.filter(empresa=self.request.user.empresa)
                .order_by("encerrado_em", "-data_distribuicao")
                .first()
            )
        return self._processo

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["empresa"] = self.request.user.empresa
        contexto["processo"] = self.processo
        contexto["secao"] = self.secao
        if self.processo:
            contexto["documentos_pendentes"] = self.processo.solicitacoes.filter(
                status__in=[StatusDocumento.SOLICITADO, StatusDocumento.RECUSADO]
            ).count()
        return contexto


class PortalHomeView(BasePortalView):
    template_name = "portal/home.html"
    secao = "inicio"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        processo = self.processo
        if not processo:
            return contexto
        prazos = list(processo.prazos.filter(status=StatusPrazo.PENDENTE).order_by("data_fim")[:10])
        contexto["andamentos"] = processo.andamentos.filter(visivel_cliente=True)[:15]
        contexto["documentos"] = processo.documentos.filter(visivel_cliente=True)[:10]
        contexto["prazos"] = prazos
        contexto["parcelas"] = processo.parcelas.all()[:10]
        contexto["trilha"] = montar_trilha(processo)
        contexto["etapa_atual"] = next(
            (etapa["numero"] for etapa in contexto["trilha"] if etapa["atual"]),
            len(contexto["trilha"]),
        )
        pendente = processo.solicitacoes.filter(
            status__in=[StatusDocumento.SOLICITADO, StatusDocumento.RECUSADO]
        ).order_by("prazo").first()
        contexto["documento_pendente"] = pendente
        contexto["proximo_prazo"] = prazos[0] if prazos else None
        contexto["proxima_reuniao"] = (
            processo.reunioes.filter(visivel_cliente=True, quando__gte=timezone.now())
            .order_by("quando").first()
        )
        return contexto


class PortalCredoresView(BasePortalView):
    template_name = "portal/credores.html"
    secao = "credores"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        if self.processo:
            credores = list(
                self.processo.credores.filter(visivel_cliente=True)
                .prefetch_related("eventos")
                .order_by("-valor_arrolado")
            )
            contexto["credores"] = credores
            contexto["total_original"] = sum(c.valor_arrolado for c in credores)
            economia = sum((c.economia or 0) for c in credores)
            contexto["economia_total"] = economia
            contexto["com_acordo"] = sum(1 for c in credores if c.progresso == 100)
        return contexto


class PortalDocumentosView(BasePortalView):
    template_name = "portal/documentos.html"
    secao = "documentos"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        if self.processo:
            solicitacoes = list(self.processo.solicitacoes.all())
            contexto["pendentes"] = [s for s in solicitacoes if s.pendente]
            contexto["entregues"] = [s for s in solicitacoes if not s.pendente]
            contexto["form"] = kwargs.get("form") or EnvioDocumentoForm()
        return contexto


class EnviarDocumentoView(ClienteMixin, View):
    """O cliente anexa o arquivo pedido pela equipe."""

    def post(self, request, pk):
        solicitacao = get_object_or_404(DocumentoSolicitado, pk=pk)
        if solicitacao.processo.empresa_id != request.user.empresa_id:
            raise Http404("Documento nao encontrado.")

        form = EnvioDocumentoForm(request.POST, request.FILES, instance=solicitacao)
        if form.is_valid():
            solicitacao = form.save(commit=False)
            solicitacao.status = StatusDocumento.RECEBIDO
            solicitacao.enviado_em = timezone.now()
            solicitacao.save()
            messages.success(request, f"“{solicitacao.titulo}” enviado. A equipe confere e te avisa.")
        else:
            messages.error(request, "Nao foi possivel enviar o arquivo. Tente novamente.")
        return redirect("portal:documentos")


class PortalReunioesView(BasePortalView):
    template_name = "portal/reunioes.html"
    secao = "reunioes"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        if self.processo:
            reunioes = list(self.processo.reunioes.filter(visivel_cliente=True))
            contexto["proximas"] = [r for r in reunioes if r.futura]
            contexto["anteriores"] = [r for r in reunioes if not r.futura]
        return contexto


class PortalConversaView(BasePortalView):
    template_name = "portal/conversa.html"
    secao = "conversa"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        if self.processo:
            contexto["mensagens"] = self.processo.mensagens.select_related("autor")
            contexto["form"] = kwargs.get("form") or MensagemForm()
            # marca como lidas as mensagens que a equipe mandou
            self.processo.mensagens.filter(
                lida_em__isnull=True, autor__tipo="INTERNO"
            ).update(lida_em=timezone.now())
        return contexto

    def post(self, request, *args, **kwargs):
        if not self.processo:
            return redirect("portal:conversa")
        form = MensagemForm(request.POST)
        if form.is_valid():
            mensagem = form.save(commit=False)
            mensagem.processo = self.processo
            mensagem.autor = request.user
            mensagem.save()
            return redirect("portal:conversa")
        return self.render_to_response(self.get_context_data(form=form))


class PortalProcessoView(ClienteMixin, DetailView):
    model = ProcessoRJ
    template_name = "portal/processo.html"
    context_object_name = "processo"
    extra_context = {"secao": "inicio"}

    def get_object(self, queryset=None):
        processo = super().get_object(queryset)
        if processo.empresa_id != self.request.user.empresa_id:
            raise Http404("Processo nao encontrado.")
        return processo

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["andamentos"] = self.object.andamentos.filter(visivel_cliente=True)
        contexto["documentos"] = self.object.documentos.filter(visivel_cliente=True)
        contexto["documentos_pendentes"] = self.object.solicitacoes.filter(
            status__in=[StatusDocumento.SOLICITADO, StatusDocumento.RECUSADO]
        ).count()
        return contexto
