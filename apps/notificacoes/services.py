"""Resumo de prazos a vencer enviado por e-mail aos responsaveis."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.utils import timezone

from apps.processos.models import Prazo, StatusPrazo

from .models import AvisoPrazo

logger = logging.getLogger(__name__)


@dataclass
class ResumoPrazos:
    """O que sera enviado para um destinatario."""

    email: str
    nome: str = ""
    atrasados: list[Prazo] = field(default_factory=list)
    vencem_hoje: list[Prazo] = field(default_factory=list)
    proximos: list[Prazo] = field(default_factory=list)

    @property
    def prazos(self) -> list[Prazo]:
        return [*self.atrasados, *self.vencem_hoje, *self.proximos]

    @property
    def total(self) -> int:
        return len(self.prazos)

    @property
    def assunto(self) -> str:
        partes = []
        if self.atrasados:
            partes.append(f"{len(self.atrasados)} atrasado(s)")
        if self.vencem_hoje:
            partes.append(f"{len(self.vencem_hoje)} vence(m) hoje")
        if self.proximos:
            partes.append(f"{len(self.proximos)} a vencer")
        detalhe = ", ".join(partes)
        return f"[RJ360] Prazos: {detalhe}"


def prazos_em_alerta(dias: int | None = None, hoje: date | None = None):
    """Prazos pendentes ja vencidos ou que vencem nos proximos `dias`."""
    hoje = hoje or timezone.localdate()
    dias = settings.PRAZO_ALERTA_DIAS if dias is None else dias
    return (
        Prazo.objects.filter(status=StatusPrazo.PENDENTE, data_fim__lte=hoje + timedelta(days=dias))
        .select_related("processo", "processo__empresa", "responsavel")
        .order_by("data_fim", "id")
    )


def _destinatarios_do_prazo(prazo: Prazo) -> list[tuple[str, str]]:
    """(email, nome) de quem deve receber o aviso desse prazo."""
    responsavel = prazo.responsavel
    if responsavel and responsavel.email:
        nome = responsavel.get_full_name() or responsavel.username
        return [(responsavel.email, nome)]
    # Sem responsavel definido (ou sem e-mail cadastrado): a supervisao assume.
    return [(email, "Supervisao") for email in settings.NOTIFICACOES_SUPERVISAO]


def montar_resumos(dias: int | None = None, hoje: date | None = None) -> list[ResumoPrazos]:
    """Agrupa os prazos em alerta por destinatario."""
    hoje = hoje or timezone.localdate()
    resumos: dict[str, ResumoPrazos] = {}
    for prazo in prazos_em_alerta(dias, hoje):
        for email, nome in _destinatarios_do_prazo(prazo):
            resumo = resumos.setdefault(email, ResumoPrazos(email=email, nome=nome))
            if prazo.data_fim < hoje:
                resumo.atrasados.append(prazo)
            elif prazo.data_fim == hoje:
                resumo.vencem_hoje.append(prazo)
            else:
                resumo.proximos.append(prazo)
    return [resumo for resumo in resumos.values() if resumo.total]


def _remover_ja_avisados(resumo: ResumoPrazos, hoje: date) -> ResumoPrazos:
    """Tira do resumo o que ja foi avisado para esse destinatario hoje."""
    avisados = set(
        AvisoPrazo.objects.filter(
            destinatario=resumo.email,
            data=hoje,
            prazo_id__in=[prazo.pk for prazo in resumo.prazos],
        ).values_list("prazo_id", flat=True)
    )
    if not avisados:
        return resumo
    return ResumoPrazos(
        email=resumo.email,
        nome=resumo.nome,
        atrasados=[p for p in resumo.atrasados if p.pk not in avisados],
        vencem_hoje=[p for p in resumo.vencem_hoje if p.pk not in avisados],
        proximos=[p for p in resumo.proximos if p.pk not in avisados],
    )


def _mensagem(resumo: ResumoPrazos, hoje: date, conexao=None) -> EmailMultiAlternatives:
    contexto = {
        "resumo": resumo,
        "hoje": hoje,
        "site_url": settings.SITE_URL.rstrip("/"),
        "app_nome": "RJ360",
    }
    texto = render_to_string("notificacoes/alerta_prazos.txt", contexto)
    html = render_to_string("notificacoes/alerta_prazos.html", contexto)
    mensagem = EmailMultiAlternatives(
        subject=resumo.assunto,
        body=texto,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[resumo.email],
        connection=conexao,
    )
    mensagem.attach_alternative(html, "text/html")
    return mensagem


def enviar_alertas(
    dias: int | None = None,
    simular: bool = False,
    para: str | None = None,
    hoje: date | None = None,
) -> list[ResumoPrazos]:
    """Envia um resumo por destinatario e devolve o que foi (ou seria) enviado.

    `simular` monta tudo sem enviar e sem registrar. `para` redireciona todos os
    e-mails para um endereco, util no primeiro teste de configuracao do SMTP.
    """
    hoje = hoje or timezone.localdate()
    enviados: list[ResumoPrazos] = []
    conexao = None if simular else get_connection()

    for resumo in montar_resumos(dias, hoje):
        pendente = resumo if simular else _remover_ja_avisados(resumo, hoje)
        if not pendente.total:
            continue
        if para:
            pendente = ResumoPrazos(
                email=para,
                nome=f"{pendente.nome} (redirecionado de {pendente.email})",
                atrasados=pendente.atrasados,
                vencem_hoje=pendente.vencem_hoje,
                proximos=pendente.proximos,
            )
        if simular:
            enviados.append(pendente)
            continue
        try:
            _mensagem(pendente, hoje, conexao).send(fail_silently=False)
        except Exception as erro:  # o envio de um nao pode derrubar os outros
            logger.error("Falha ao enviar alerta para %s: %s", pendente.email, erro)
            continue
        AvisoPrazo.objects.bulk_create(
            [
                AvisoPrazo(prazo=prazo, destinatario=resumo.email, data=hoje)
                for prazo in pendente.prazos
            ],
            ignore_conflicts=True,
        )
        enviados.append(pendente)
    return enviados
