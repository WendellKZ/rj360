"""O que a empresa em recuperacao ve e faz no portal: documentos pedidos,
reunioes marcadas e a conversa com a equipe."""
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


def caminho_documento_cliente(instance, filename: str) -> str:
    return f"solicitacoes/{instance.processo_id}/{filename}"


class StatusDocumento(models.TextChoices):
    SOLICITADO = "SOL", "Solicitado"
    RECEBIDO = "REC", "Recebido, em conferência"
    VALIDADO = "VAL", "Validado"
    RECUSADO = "RECU", "Precisa reenviar"

    @classmethod
    def cor(cls, valor: str) -> str:
        return {
            cls.SOLICITADO: "amarelo",
            cls.RECEBIDO: "azul",
            cls.VALIDADO: "verde",
            cls.RECUSADO: "vermelho",
        }.get(valor, "cinza")


class DocumentoSolicitado(TimeStampedModel):
    """Documento que a equipe pediu e o cliente envia pelo portal."""

    processo = models.ForeignKey(
        "processos.ProcessoRJ", verbose_name="processo",
        related_name="solicitacoes", on_delete=models.CASCADE,
    )
    titulo = models.CharField("documento", max_length=200)
    motivo = models.CharField(
        "para que serve", max_length=250, blank=True,
        help_text="Explique em uma linha por que ele e necessario.",
    )
    prazo = models.DateField("prazo", null=True, blank=True)
    status = models.CharField(
        "status", max_length=4, choices=StatusDocumento.choices, default=StatusDocumento.SOLICITADO
    )
    arquivo = models.FileField("arquivo enviado", upload_to=caminho_documento_cliente, blank=True)
    enviado_em = models.DateTimeField("enviado em", null=True, blank=True)
    observacao_equipe = models.CharField("observacao da equipe", max_length=250, blank=True)
    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="solicitado por",
        related_name="documentos_solicitados", on_delete=models.SET_NULL, null=True, blank=True,
    )

    class Meta:
        verbose_name = "documento solicitado"
        verbose_name_plural = "documentos solicitados"
        ordering = ["status", "prazo", "-criado_em"]

    def __str__(self) -> str:
        return self.titulo

    @property
    def cor(self) -> str:
        return StatusDocumento.cor(self.status)

    @property
    def pendente(self) -> bool:
        return self.status in {StatusDocumento.SOLICITADO, StatusDocumento.RECUSADO}

    @property
    def atrasado(self) -> bool:
        return bool(self.pendente and self.prazo and self.prazo < timezone.localdate())


class StatusReuniao(models.TextChoices):
    AGENDADA = "AGEN", "Agendada"
    REALIZADA = "REAL", "Realizada"
    CANCELADA = "CANC", "Cancelada"


class Reuniao(TimeStampedModel):
    """Encontro entre a equipe e a empresa, com pauta antes e ata depois."""

    processo = models.ForeignKey(
        "processos.ProcessoRJ", verbose_name="processo",
        related_name="reunioes", on_delete=models.CASCADE,
    )
    titulo = models.CharField("assunto", max_length=200)
    quando = models.DateTimeField("data e hora")
    duracao_minutos = models.PositiveIntegerField("duracao (min)", default=60)
    local = models.CharField(
        "local ou link", max_length=250, blank=True,
        help_text="Endereco, sala ou o link da chamada.",
    )
    participantes = models.CharField("participantes", max_length=250, blank=True)
    pauta = models.TextField("pauta", blank=True)
    ata = models.TextField("resumo do que foi decidido", blank=True)
    status = models.CharField(
        "status", max_length=4, choices=StatusReuniao.choices, default=StatusReuniao.AGENDADA
    )
    visivel_cliente = models.BooleanField("visivel no portal", default=True)

    class Meta:
        verbose_name = "reunião"
        verbose_name_plural = "reuniões"
        ordering = ["-quando"]

    def __str__(self) -> str:
        return f"{self.titulo} ({self.quando:%d/%m/%Y %H:%M})"

    @property
    def futura(self) -> bool:
        return self.status == StatusReuniao.AGENDADA and self.quando >= timezone.now()

    @property
    def cor(self) -> str:
        if self.status == StatusReuniao.CANCELADA:
            return "cinza"
        if self.status == StatusReuniao.REALIZADA:
            return "verde"
        return "amarelo" if self.futura else "vermelho"


class Mensagem(TimeStampedModel):
    """Conversa entre a empresa e a equipe, dentro do processo."""

    processo = models.ForeignKey(
        "processos.ProcessoRJ", verbose_name="processo",
        related_name="mensagens", on_delete=models.CASCADE,
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="autor",
        related_name="mensagens", on_delete=models.SET_NULL, null=True,
    )
    texto = models.TextField("mensagem")
    lida_em = models.DateTimeField("lida em", null=True, blank=True)

    class Meta:
        verbose_name = "mensagem"
        verbose_name_plural = "mensagens"
        ordering = ["criado_em"]

    def __str__(self) -> str:
        return f"{self.autor}: {self.texto[:40]}"

    @property
    def da_equipe(self) -> bool:
        return bool(self.autor and self.autor.is_interno)
