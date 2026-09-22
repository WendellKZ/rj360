"""Login por codigo de uso unico para o cliente.

O codigo nunca e guardado em claro: fica o hash, como uma senha. O envio passa
por um canal configuravel — hoje e-mail, amanha WhatsApp — sem mudar o fluxo.
"""
from __future__ import annotations

import logging
import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db import models
from django.template.loader import render_to_string
from django.utils import timezone

from apps.core.models import TimeStampedModel

logger = logging.getLogger(__name__)

TAMANHO = 6
VALIDADE_MINUTOS = 10
MAX_TENTATIVAS = 5
MAX_PEDIDOS_POR_JANELA = 3
JANELA_PEDIDOS_MINUTOS = 15


def gerar_codigo() -> str:
    """Seis digitos sorteados de forma criptografica."""
    return f"{secrets.randbelow(10 ** TAMANHO):0{TAMANHO}d}"


class CodigoAcesso(TimeStampedModel):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="usuario",
        related_name="codigos_acesso", on_delete=models.CASCADE,
    )
    codigo_hash = models.CharField("codigo (hash)", max_length=128)
    expira_em = models.DateTimeField("expira em")
    tentativas = models.PositiveSmallIntegerField("tentativas", default=0)
    usado_em = models.DateTimeField("usado em", null=True, blank=True)
    canal = models.CharField("canal de envio", max_length=20, default="email")

    class Meta:
        verbose_name = "codigo de acesso"
        verbose_name_plural = "codigos de acesso"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.usuario} ({self.criado_em:%d/%m %H:%M})"

    @property
    def expirado(self) -> bool:
        return timezone.now() > self.expira_em

    @property
    def valido(self) -> bool:
        return not self.usado_em and not self.expirado and self.tentativas < MAX_TENTATIVAS

    def confere(self, digitado: str) -> bool:
        """Compara o codigo digitado e consome uma tentativa."""
        if not self.valido:
            return False
        self.tentativas += 1
        acertou = check_password(digitado.strip(), self.codigo_hash)
        if acertou:
            self.usado_em = timezone.now()
        self.save(update_fields=["tentativas", "usado_em", "atualizado_em"])
        return acertou


def pode_pedir(usuario) -> bool:
    """Evita que alguem peça codigo em serie para um mesmo usuario."""
    desde = timezone.now() - timezone.timedelta(minutes=JANELA_PEDIDOS_MINUTOS)
    recentes = CodigoAcesso.objects.filter(usuario=usuario, criado_em__gte=desde).count()
    return recentes < MAX_PEDIDOS_POR_JANELA


def criar_e_enviar(usuario) -> CodigoAcesso | None:
    """Gera o codigo, guarda o hash e manda pelo canal configurado."""
    if not pode_pedir(usuario):
        logger.warning("Pedidos de codigo em excesso para o usuario %s", usuario.pk)
        return None

    # um codigo novo invalida os anteriores
    CodigoAcesso.objects.filter(usuario=usuario, usado_em__isnull=True).update(
        expira_em=timezone.now()
    )

    codigo = gerar_codigo()
    registro = CodigoAcesso.objects.create(
        usuario=usuario,
        codigo_hash=make_password(codigo),
        expira_em=timezone.now() + timezone.timedelta(minutes=VALIDADE_MINUTOS),
        canal=settings.CANAL_CODIGO_ACESSO,
    )
    _enviar(usuario, codigo)
    return registro


def _enviar(usuario, codigo: str) -> None:
    canal = settings.CANAL_CODIGO_ACESSO
    if canal == "email" and usuario.email:
        contexto = {"codigo": codigo, "minutos": VALIDADE_MINUTOS, "usuario": usuario}
        send_mail(
            subject=f"Seu codigo de acesso: {codigo}",
            message=render_to_string("accounts/email_codigo.txt", contexto),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[usuario.email],
            fail_silently=False,
        )
        return
    # Nenhum canal configurado: registra para o time conseguir ajudar o cliente.
    logger.info("Codigo de acesso gerado para %s (canal %s indisponivel)", usuario.pk, canal)
