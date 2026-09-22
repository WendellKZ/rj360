from django.db import models
from django.utils import timezone


class AvisoPrazo(models.Model):
    """Registro de que um prazo ja foi avisado a um destinatario num dia.

    Serve para o comando poder rodar varias vezes ao dia sem repetir e-mail,
    e para auditar o que foi comunicado a quem.
    """

    prazo = models.ForeignKey(
        "processos.Prazo", verbose_name="prazo", related_name="avisos", on_delete=models.CASCADE
    )
    destinatario = models.EmailField("destinatario")
    data = models.DateField("data do aviso", default=timezone.localdate)
    enviado_em = models.DateTimeField("enviado em", auto_now_add=True)

    class Meta:
        verbose_name = "aviso de prazo"
        verbose_name_plural = "avisos de prazo"
        ordering = ["-enviado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["prazo", "destinatario", "data"], name="aviso_unico_por_dia"
            )
        ]

    def __str__(self) -> str:
        return f"{self.destinatario} - {self.prazo_id} ({self.data:%d/%m/%Y})"
