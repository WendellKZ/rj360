from django.db import models


class TimeStampedModel(models.Model):
    """Base com marcacao de criacao e atualizacao."""

    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        abstract = True
