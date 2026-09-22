from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.empresas.models import UFS, Porte


class Estagio(models.TextChoices):
    NOVO = "NOVO", "Novo lead"
    CONTATO = "CONT", "Contato iniciado"
    DIAGNOSTICO = "DIAG", "Diagnostico"
    PROPOSTA = "PROP", "Proposta enviada"
    NEGOCIACAO = "NEG", "Negociacao"
    GANHO = "GANHO", "Fechado - ganho"
    PERDIDO = "PERD", "Fechado - perdido"

    @classmethod
    def funil(cls) -> list[tuple[str, str]]:
        """Estagios que aparecem como colunas do funil."""
        return [
            (cls.NOVO.value, cls.NOVO.label),
            (cls.CONTATO.value, cls.CONTATO.label),
            (cls.DIAGNOSTICO.value, cls.DIAGNOSTICO.label),
            (cls.PROPOSTA.value, cls.PROPOSTA.label),
            (cls.NEGOCIACAO.value, cls.NEGOCIACAO.label),
        ]


class OrigemLead(models.TextChoices):
    INDICACAO = "IND", "Indicacao"
    SITE = "SITE", "Site / formulario"
    EVENTO = "EVEN", "Evento"
    ATIVA = "ATIV", "Prospeccao ativa"
    PARCEIRO = "PARC", "Escritorio parceiro"
    PUBLICACAO = "PUBL", "Publicacao judicial / DJE"
    OUTRO = "OUT", "Outro"


class SituacaoJuridica(models.TextChoices):
    PRE_CRISE = "PRE", "Dificuldade financeira, sem processo"
    EXTRAJUDICIAL = "EXTRA", "Negociacao extrajudicial"
    RJ_EM_CURSO = "RJ", "Recuperacao judicial em curso"
    RJ_ENCERRADA = "RJENC", "Recuperacao judicial encerrada"
    FALENCIA = "FAL", "Falencia"
    OUTRO = "OUT", "Outro"


class Urgencia(models.TextChoices):
    ALTA = "ALTA", "Urgência alta"
    MEDIA = "MEDIA", "Urgência média"
    BAIXA = "BAIXA", "Urgência baixa"
    NAO_AVALIADA = "NA", "Não avaliada"


class Lead(TimeStampedModel):
    razao_social = models.CharField("razao social", max_length=200)
    nome_fantasia = models.CharField("nome fantasia", max_length=200, blank=True)
    cnpj = models.CharField("CNPJ", max_length=18, blank=True)
    porte = models.CharField("porte", max_length=10, choices=Porte.choices, default=Porte.EPP)
    setor = models.CharField("setor de atuacao", max_length=150, blank=True)
    cidade = models.CharField("cidade", max_length=100, blank=True)
    uf = models.CharField("UF", max_length=2, choices=UFS, blank=True)

    contato_nome = models.CharField("contato", max_length=150, blank=True)
    contato_cargo = models.CharField("cargo do contato", max_length=120, blank=True)
    contato_email = models.EmailField("e-mail", blank=True)
    contato_telefone = models.CharField("telefone", max_length=20, blank=True)

    origem = models.CharField(
        "origem", max_length=4, choices=OrigemLead.choices, default=OrigemLead.ATIVA
    )
    situacao_juridica = models.CharField(
        "situacao juridica",
        max_length=5,
        choices=SituacaoJuridica.choices,
        default=SituacaoJuridica.PRE_CRISE,
    )
    estagio = models.CharField(
        "estagio", max_length=5, choices=Estagio.choices, default=Estagio.NOVO
    )
    urgencia = models.CharField(
        "urgencia", max_length=5, choices=Urgencia.choices, default=Urgencia.NAO_AVALIADA,
        help_text="Vem do diagnostico feito no site, quando houver.",
    )
    valor_estimado = models.DecimalField(
        "valor estimado do contrato", max_digits=12, decimal_places=2, null=True, blank=True
    )
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="responsavel",
        related_name="leads",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    proximo_contato = models.DateField("proximo contato", null=True, blank=True)
    motivo_perda = models.CharField("motivo da perda", max_length=200, blank=True)
    empresa = models.OneToOneField(
        "empresas.Empresa",
        verbose_name="empresa convertida",
        related_name="lead",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    observacoes = models.TextField("observacoes", blank=True)

    class Meta:
        verbose_name = "lead"
        verbose_name_plural = "leads"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return self.nome_fantasia or self.razao_social

    def get_absolute_url(self) -> str:
        return reverse("crm:detalhe", args=[self.pk])

    @property
    def cor_urgencia(self) -> str:
        return {
            Urgencia.ALTA: "vermelho",
            Urgencia.MEDIA: "amarelo",
            Urgencia.BAIXA: "verde",
        }.get(self.urgencia, "cinza")

    @property
    def esta_aberto(self) -> bool:
        return self.estagio not in {Estagio.GANHO, Estagio.PERDIDO}

    @property
    def contato_atrasado(self) -> bool:
        return bool(
            self.proximo_contato
            and self.esta_aberto
            and self.proximo_contato < timezone.localdate()
        )

    def converter_em_empresa(self):
        """Cria a empresa cliente a partir do lead ganho."""
        from apps.empresas.models import Empresa, SituacaoEmpresa

        if self.empresa_id:
            return self.empresa
        empresa = Empresa.objects.create(
            razao_social=self.razao_social,
            nome_fantasia=self.nome_fantasia,
            cnpj=self.cnpj,
            porte=self.porte,
            atividade=self.setor,
            cidade=self.cidade,
            uf=self.uf,
            email=self.contato_email,
            telefone=self.contato_telefone,
            responsavel=self.responsavel,
            situacao=SituacaoEmpresa.CLIENTE,
            inicio_contrato=timezone.localdate(),
        )
        if self.contato_nome:
            empresa.contatos.create(
                nome=self.contato_nome,
                cargo=self.contato_cargo,
                email=self.contato_email,
                telefone=self.contato_telefone,
                principal=True,
            )
        self.empresa = empresa
        self.estagio = Estagio.GANHO
        self.save(update_fields=["empresa", "estagio", "atualizado_em"])
        return empresa


class TipoAtividade(models.TextChoices):
    LIGACAO = "LIG", "Ligacao"
    EMAIL = "MAIL", "E-mail"
    WHATSAPP = "WPP", "WhatsApp"
    REUNIAO = "REUN", "Reuniao"
    VISITA = "VIS", "Visita"
    NOTA = "NOTA", "Anotacao"


class Atividade(TimeStampedModel):
    lead = models.ForeignKey(
        Lead, verbose_name="lead", related_name="atividades", on_delete=models.CASCADE
    )
    tipo = models.CharField(
        "tipo", max_length=4, choices=TipoAtividade.choices, default=TipoAtividade.LIGACAO
    )
    data = models.DateField("data", default=timezone.localdate)
    titulo = models.CharField("titulo", max_length=200)
    descricao = models.TextField("descricao", blank=True)
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="autor",
        related_name="atividades",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "atividade"
        verbose_name_plural = "atividades"
        ordering = ["-data", "-id"]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} - {self.titulo}"
