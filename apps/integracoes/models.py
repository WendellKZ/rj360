from django.conf import settings
from django.db import models


class StatusSincronizacao(models.TextChoices):
    SUCESSO = "OK", "Concluida"
    SEM_RESULTADO = "VAZIO", "Processo nao encontrado no tribunal"
    ERRO = "ERRO", "Erro"


class SincronizacaoDataJud(models.Model):
    """Historico das consultas feitas a API publica do DataJud."""

    processo = models.ForeignKey(
        "processos.ProcessoRJ",
        verbose_name="processo",
        related_name="sincronizacoes",
        on_delete=models.CASCADE,
    )
    executado_em = models.DateTimeField("executado em", auto_now_add=True)
    executado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="executado por",
        related_name="sincronizacoes",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    status = models.CharField("status", max_length=5, choices=StatusSincronizacao.choices)
    movimentos_recebidos = models.PositiveIntegerField("movimentos recebidos", default=0)
    andamentos_criados = models.PositiveIntegerField("andamentos criados", default=0)
    atualizado_no_tribunal_em = models.CharField(
        "ultima atualizacao no tribunal", max_length=40, blank=True,
        help_text="Campo dataHoraUltimaAtualizacao devolvido pelo Datajud.",
    )
    mensagem = models.TextField("mensagem", blank=True)

    class Meta:
        verbose_name = "sincronizacao com o DataJud"
        verbose_name_plural = "sincronizacoes com o DataJud"
        ordering = ["-executado_em"]

    def __str__(self) -> str:
        return f"{self.processo_id} - {self.get_status_display()} ({self.executado_em:%d/%m/%Y %H:%M})"

    @property
    def deu_certo(self) -> bool:
        return self.status == StatusSincronizacao.SUCESSO
