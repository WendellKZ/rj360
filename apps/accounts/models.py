from django.contrib.auth.models import AbstractUser
from django.db import models


class TipoUsuario(models.TextChoices):
    INTERNO = "INTERNO", "Equipe interna"
    CLIENTE = "CLIENTE", "Cliente (portal)"


class User(AbstractUser):
    """Usuario do sistema.

    Equipe interna enxerga todas as empresas. Usuario do tipo cliente so
    enxerga a empresa a que esta vinculado, pelo portal.
    """

    tipo = models.CharField(
        "tipo de acesso",
        max_length=10,
        choices=TipoUsuario.choices,
        default=TipoUsuario.INTERNO,
    )
    empresa = models.ForeignKey(
        "empresas.Empresa",
        verbose_name="empresa vinculada",
        related_name="usuarios",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Obrigatorio para usuarios do tipo cliente.",
    )
    cargo = models.CharField("cargo", max_length=120, blank=True)
    telefone = models.CharField("telefone", max_length=20, blank=True)

    class Meta(AbstractUser.Meta):
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def __str__(self) -> str:
        return self.get_full_name() or self.username

    @property
    def is_interno(self) -> bool:
        return self.tipo == TipoUsuario.INTERNO

    @property
    def is_cliente(self) -> bool:
        return self.tipo == TipoUsuario.CLIENTE

    def clean(self):
        from django.core.exceptions import ValidationError

        super().clean()
        if self.tipo == TipoUsuario.CLIENTE and self.empresa_id is None:
            raise ValidationError(
                {"empresa": "Usuario do tipo cliente precisa estar vinculado a uma empresa."}
            )


# O login por codigo vive em codigos.py; aqui so reexportamos o model para o
# Django registra-lo no app accounts.
from .codigos import CodigoAcesso  # noqa: E402,F401
