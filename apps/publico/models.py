import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import TimeStampedModel


class Urgencia(models.TextChoices):
    ALTA = "ALTA", "Urgência alta"
    MEDIA = "MEDIA", "Urgência média"
    BAIXA = "BAIXA", "Urgência baixa"
    PESSOA_FISICA = "PF", "Dívida apenas pessoal"

    @classmethod
    def da_pontuacao(cls, pontos: int) -> str:
        """Regra do diagnostico: 11+ e alta, 7+ e media, abaixo e baixa."""
        if pontos >= 11:
            return cls.ALTA
        if pontos >= 7:
            return cls.MEDIA
        return cls.BAIXA

    @classmethod
    def cor(cls, valor: str) -> str:
        return {
            cls.ALTA: "vermelho",
            cls.MEDIA: "amarelo",
            cls.BAIXA: "verde",
            cls.PESSOA_FISICA: "cinza",
        }.get(valor, "cinza")

    @classmethod
    def minutos_sla(cls, valor: str) -> int | None:
        """Tempo prometido para o primeiro contato humano."""
        return {cls.ALTA: 30, cls.MEDIA: 240, cls.BAIXA: 1440}.get(valor)

    @classmethod
    def prazo_legivel(cls, valor: str) -> str:
        return {cls.ALTA: "30 minutos", cls.MEDIA: "4 horas", cls.BAIXA: "1 dia útil"}.get(valor, "")


RESULTADOS = {
    Urgencia.ALTA: {
        "titulo": "Chegou na hora certa. Existe caminho.",
        "mensagem": "Com credores já em movimento, quem age primeiro negocia melhor. Seu caso tem "
                    "prioridade: uma pessoa do time fala com você em até 30 minutos no horário comercial.",
    },
    Urgencia.MEDIA: {
        "titulo": "Ainda dá para negociar de posição forte.",
        "mensagem": "Sua situação é delicada, mas há tempo — e é exatamente essa janela que "
                    "aproveitamos. Vamos conversar.",
    },
    Urgencia.BAIXA: {
        "titulo": "Ainda tem fôlego e margem para planejar.",
        "mensagem": "É nessa fase que resolver custa menos e rende mais. Um plano simples de "
                    "reestruturação costuma evitar que o problema vire crise.",
    },
}


class Diagnostico(TimeStampedModel):
    """Respostas do diagnostico feito no site, com a urgencia calculada."""

    token = models.UUIDField("identificador publico", default=uuid.uuid4, unique=True, editable=False)
    nome = models.CharField("nome", max_length=150, blank=True)
    empresa = models.CharField("empresa", max_length=200, blank=True)
    telefone = models.CharField("telefone", max_length=20, blank=True)
    email = models.EmailField("e-mail", blank=True)

    contato_em = models.DateTimeField("contato informado em", null=True, blank=True)

    respostas = models.JSONField("respostas", default=list)
    pontuacao = models.PositiveIntegerField("pontuacao", default=0)
    urgencia = models.CharField("urgencia", max_length=5, choices=Urgencia.choices)

    atendido_em = models.DateTimeField("primeiro contato em", null=True, blank=True)
    atendido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="atendido por",
        related_name="diagnosticos",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    lead = models.OneToOneField(
        "crm.Lead",
        verbose_name="lead gerado",
        related_name="diagnostico",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    observacoes = models.TextField("observacoes", blank=True)

    class Meta:
        verbose_name = "diagnostico"
        verbose_name_plural = "diagnosticos"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.empresa or self.nome or 'Diagnostico'} ({self.get_urgencia_display()})"

    def get_absolute_url(self) -> str:
        return reverse("crm:diagnosticos")

    @property
    def tem_contato(self) -> bool:
        return self.contato_em is not None

    @property
    def cor(self) -> str:
        return Urgencia.cor(self.urgencia)

    @property
    def prazo_contato(self):
        """Ate quando o primeiro contato humano deveria acontecer."""
        minutos = Urgencia.minutos_sla(self.urgencia)
        if minutos is None:
            return None
        return self.criado_em + timedelta(minutes=minutos)

    @property
    def minutos_sem_contato(self) -> int:
        fim = self.atendido_em or timezone.now()
        return max(0, int((fim - self.criado_em).total_seconds() // 60))

    @property
    def sla_estourado(self) -> bool:
        minutos = Urgencia.minutos_sla(self.urgencia)
        if minutos is None or self.atendido_em:
            return False
        return self.minutos_sem_contato > minutos

    @property
    def resumo_sla(self) -> str:
        if self.lead_id or self.atendido_em:
            return "contato humano feito"
        if self.sla_estourado:
            return f"prazo estourado — {self.minutos_sem_contato} min sem contato humano"
        return f"{Urgencia.prazo_legivel(self.urgencia)} para o 1º contato · aguardando"

    @property
    def perfil(self) -> str:
        """Resumo curto das respostas, para a lista do painel."""
        por_chave = {item.get("chave"): item.get("resposta") for item in self.respostas or []}
        partes = [por_chave.get("faturamento"), por_chave.get("divida"), por_chave.get("situacao")]
        return " · ".join(parte for parte in partes if parte)
