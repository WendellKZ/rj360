from datetime import date, timedelta

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.core.validators import formatar_numero_cnj, validar_numero_cnj


class FaseProcesso(models.TextChoices):
    PRE_AJUIZAMENTO = "PRE", "Pre-ajuizamento"
    DISTRIBUIDO = "DIST", "Distribuido"
    DEFERIDO = "DEFER", "Processamento deferido (art. 52)"
    PLANO_APRESENTADO = "PLANO", "Plano apresentado (art. 53)"
    EDITAL = "EDITAL", "Edital publicado / habilitacoes"
    OBJECOES = "OBJ", "Prazo de objecoes"
    AGC = "AGC", "Assembleia de credores"
    CONCEDIDA = "CONC", "RJ concedida (art. 58)"
    FISCALIZACAO = "FISC", "Periodo de fiscalizacao (art. 61)"
    ENCERRADA = "ENC", "Encerrada (art. 63)"
    FALENCIA = "FAL", "Convolada em falencia"

    @classmethod
    def cor(cls, valor: str) -> str:
        mapa = {
            cls.PRE_AJUIZAMENTO: "cinza",
            cls.DISTRIBUIDO: "azul",
            cls.DEFERIDO: "azul",
            cls.PLANO_APRESENTADO: "azul",
            cls.EDITAL: "amarelo",
            cls.OBJECOES: "amarelo",
            cls.AGC: "amarelo",
            cls.CONCEDIDA: "verde",
            cls.FISCALIZACAO: "verde",
            cls.ENCERRADA: "cinza",
            cls.FALENCIA: "vermelho",
        }
        return mapa.get(valor, "cinza")


class ProcessoRJ(TimeStampedModel):
    """Processo de recuperacao judicial (Lei 11.101/2005)."""

    empresa = models.ForeignKey(
        "empresas.Empresa", verbose_name="empresa", related_name="processos", on_delete=models.CASCADE
    )
    numero_cnj = models.CharField(
        "numero CNJ", max_length=25, unique=True, validators=[validar_numero_cnj]
    )
    tribunal = models.CharField("tribunal", max_length=50, blank=True)
    comarca = models.CharField("comarca", max_length=120, blank=True)
    vara = models.CharField("vara", max_length=120, blank=True)
    juiz = models.CharField("juiz", max_length=150, blank=True)

    administrador_judicial = models.CharField("administrador judicial", max_length=200, blank=True)
    aj_email = models.EmailField("e-mail do AJ", blank=True)
    aj_telefone = models.CharField("telefone do AJ", max_length=20, blank=True)
    advogado = models.CharField("advogado responsavel", max_length=200, blank=True)

    fase = models.CharField(
        "fase atual", max_length=6, choices=FaseProcesso.choices, default=FaseProcesso.DISTRIBUIDO
    )

    data_distribuicao = models.DateField("distribuicao", null=True, blank=True)
    data_deferimento = models.DateField(
        "deferimento do processamento", null=True, blank=True,
        help_text="Art. 52. Marco inicial do stay period e do prazo do plano.",
    )
    data_edital_52 = models.DateField(
        "publicacao do edital (art. 52, §1)", null=True, blank=True,
        help_text="Abre o prazo de 15 dias para habilitacoes e divergencias.",
    )
    data_plano = models.DateField("apresentacao do plano", null=True, blank=True)
    data_edital_53 = models.DateField(
        "publicacao do aviso do plano (art. 53)", null=True, blank=True,
        help_text="Abre o prazo de 30 dias para objecoes dos credores.",
    )
    data_agc = models.DateField("assembleia geral de credores", null=True, blank=True)
    data_concessao = models.DateField("concessao da RJ (art. 58)", null=True, blank=True)
    encerrado_em = models.DateField("encerramento (art. 63)", null=True, blank=True)

    stay_prorrogado = models.BooleanField(
        "stay period prorrogado", default=False,
        help_text="Art. 6, §4: prorrogacao por igual periodo, uma unica vez.",
    )
    valor_divida = models.DecimalField(
        "valor total sujeito a RJ", max_digits=15, decimal_places=2, null=True, blank=True
    )
    datajud_alias = models.CharField(
        "sigla no DataJud", max_length=20, blank=True,
        help_text="Use apenas se a sigla do tribunal acima nao for a do indice "
                  "do CNJ (ex.: TJSP, TRT15, TRF3).",
    )
    observacoes = models.TextField("observacoes", blank=True)

    class Meta:
        verbose_name = "processo de RJ"
        verbose_name_plural = "processos de RJ"
        ordering = ["-data_distribuicao", "-id"]

    def __str__(self) -> str:
        return f"{self.numero_formatado} - {self.empresa}"

    def get_absolute_url(self) -> str:
        return reverse("processos:detalhe", args=[self.pk])

    @property
    def numero_formatado(self) -> str:
        return formatar_numero_cnj(self.numero_cnj)

    @property
    def cor_fase(self) -> str:
        return FaseProcesso.cor(self.fase)

    @property
    def stay_period_fim(self) -> date | None:
        """180 dias do deferimento, 360 se prorrogado (art. 6, §4)."""
        if not self.data_deferimento:
            return None
        dias = 360 if self.stay_prorrogado else 180
        return self.data_deferimento + timedelta(days=dias)

    @property
    def stay_dias_restantes(self) -> int | None:
        fim = self.stay_period_fim
        if not fim:
            return None
        return (fim - timezone.localdate()).days

    @property
    def fiscalizacao_fim(self) -> date | None:
        """Dois anos da concessao (art. 61)."""
        if not self.data_concessao:
            return None
        return self.data_concessao + timedelta(days=730)

    @property
    def prazos_abertos(self):
        return self.prazos.filter(status=StatusPrazo.PENDENTE).order_by("data_fim")

    @property
    def total_credores(self):
        return self.credores.count()


class TipoAndamento(models.TextChoices):
    MOVIMENTACAO = "MOV", "Movimentacao"
    PETICAO = "PET", "Peticao"
    DECISAO = "DEC", "Decisao"
    DESPACHO = "DESP", "Despacho"
    SENTENCA = "SENT", "Sentenca"
    AUDIENCIA = "AUD", "Audiencia"
    ASSEMBLEIA = "AGC", "Assembleia de credores"
    RELATORIO_AJ = "RAJ", "Relatorio do administrador judicial"
    OUTRO = "OUT", "Outro"


class FonteAndamento(models.TextChoices):
    MANUAL = "MANUAL", "Lancamento manual"
    TRIBUNAL = "TRIBUNAL", "Integracao com o tribunal"
    IMPORTACAO = "IMPORT", "Importacao de arquivo"


class Andamento(TimeStampedModel):
    processo = models.ForeignKey(
        ProcessoRJ, verbose_name="processo", related_name="andamentos", on_delete=models.CASCADE
    )
    data = models.DateField("data", default=timezone.localdate)
    tipo = models.CharField(
        "tipo", max_length=5, choices=TipoAndamento.choices, default=TipoAndamento.MOVIMENTACAO
    )
    titulo = models.CharField("titulo", max_length=200)
    descricao = models.TextField("descricao", blank=True)
    fonte = models.CharField(
        "fonte", max_length=10, choices=FonteAndamento.choices, default=FonteAndamento.MANUAL
    )
    visivel_cliente = models.BooleanField(
        "visivel no portal do cliente", default=True,
        help_text="Desmarque para manter o andamento restrito a equipe interna.",
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="registrado por",
        related_name="andamentos",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    id_externo = models.CharField(
        "identificador na origem", max_length=64, blank=True,
        help_text="Preenchido pela integracao com o tribunal para evitar duplicidade.",
    )
    codigo_movimento = models.PositiveIntegerField(
        "codigo do movimento (CNJ)", null=True, blank=True
    )

    class Meta:
        verbose_name = "andamento"
        verbose_name_plural = "andamentos"
        ordering = ["-data", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["processo", "id_externo"],
                condition=~models.Q(id_externo=""),
                name="andamento_unico_por_origem",
            )
        ]

    def __str__(self) -> str:
        return f"{self.data:%d/%m/%Y} - {self.titulo}"


class StatusPrazo(models.TextChoices):
    PENDENTE = "PEND", "Pendente"
    CUMPRIDO = "CUMP", "Cumprido"
    PRORROGADO = "PROR", "Prorrogado"
    PERDIDO = "PERD", "Perdido"


class TipoPrazo(models.TextChoices):
    LEGAL = "LEGAL", "Prazo legal"
    JUDICIAL = "JUD", "Prazo judicial"
    INTERNO = "INT", "Controle interno"


class Prazo(TimeStampedModel):
    processo = models.ForeignKey(
        ProcessoRJ, verbose_name="processo", related_name="prazos", on_delete=models.CASCADE
    )
    titulo = models.CharField("titulo", max_length=200)
    base_legal = models.CharField(
        "base legal", max_length=120, blank=True, help_text="Ex.: Lei 11.101/2005, art. 53."
    )
    tipo = models.CharField("tipo", max_length=5, choices=TipoPrazo.choices, default=TipoPrazo.LEGAL)
    data_inicio = models.DateField("inicio", null=True, blank=True)
    data_fim = models.DateField("vencimento")
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="responsavel",
        related_name="prazos",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    status = models.CharField(
        "status", max_length=4, choices=StatusPrazo.choices, default=StatusPrazo.PENDENTE
    )
    concluido_em = models.DateField("concluido em", null=True, blank=True)
    observacoes = models.TextField("observacoes", blank=True)

    class Meta:
        verbose_name = "prazo"
        verbose_name_plural = "prazos"
        ordering = ["data_fim"]

    def __str__(self) -> str:
        return f"{self.titulo} ({self.data_fim:%d/%m/%Y})"

    @property
    def dias_restantes(self) -> int:
        return (self.data_fim - timezone.localdate()).days

    @property
    def dias_atraso(self) -> int:
        """Dias corridos desde o vencimento (0 se ainda nao venceu)."""
        return max(0, -self.dias_restantes)

    @property
    def atrasado(self) -> bool:
        return self.status == StatusPrazo.PENDENTE and self.dias_restantes < 0

    @property
    def cor(self) -> str:
        if self.status == StatusPrazo.CUMPRIDO:
            return "verde"
        if self.status == StatusPrazo.PERDIDO or self.atrasado:
            return "vermelho"
        if self.dias_restantes <= settings.PRAZO_ALERTA_DIAS:
            return "amarelo"
        return "azul"


class CategoriaDocumento(models.TextChoices):
    PLANO = "PLANO", "Plano de recuperacao"
    LAUDO = "LAUDO", "Laudo economico-financeiro"
    BALANCO = "BALANCO", "Demonstracoes contabeis"
    EDITAL = "EDITAL", "Edital"
    ATA_AGC = "ATA", "Ata de assembleia"
    PETICAO = "PET", "Peticao"
    DECISAO = "DEC", "Decisao / sentenca"
    RELATORIO = "REL", "Relatorio mensal de atividades"
    CERTIDAO = "CERT", "Certidao"
    CONTRATO = "CONTR", "Contrato"
    OUTRO = "OUT", "Outro"


def caminho_documento(instance, filename: str) -> str:
    return f"processos/{instance.processo_id}/{filename}"


class Documento(TimeStampedModel):
    processo = models.ForeignKey(
        ProcessoRJ, verbose_name="processo", related_name="documentos", on_delete=models.CASCADE
    )
    titulo = models.CharField("titulo", max_length=200)
    categoria = models.CharField(
        "categoria", max_length=8, choices=CategoriaDocumento.choices, default=CategoriaDocumento.OUTRO
    )
    arquivo = models.FileField("arquivo", upload_to=caminho_documento)
    data_referencia = models.DateField("data de referencia", null=True, blank=True)
    visivel_cliente = models.BooleanField("visivel no portal do cliente", default=True)
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="enviado por",
        related_name="documentos",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "documento"
        verbose_name_plural = "documentos"
        ordering = ["-data_referencia", "-criado_em"]

    def __str__(self) -> str:
        return self.titulo


class ClasseCredor(models.TextChoices):
    I = "I", "Classe I - trabalhista"
    II = "II", "Classe II - garantia real"
    III = "III", "Classe III - quirografario"
    IV = "IV", "Classe IV - ME/EPP"


class SituacaoCredito(models.TextChoices):
    ARROLADO = "ARR", "Arrolado pela devedora"
    HABILITADO = "HAB", "Habilitado"
    DIVERGENCIA = "DIV", "Divergencia apresentada"
    IMPUGNADO = "IMP", "Impugnado"
    EXCLUIDO = "EXC", "Excluido"


class Credor(TimeStampedModel):
    processo = models.ForeignKey(
        ProcessoRJ, verbose_name="processo", related_name="credores", on_delete=models.CASCADE
    )
    nome = models.CharField("credor", max_length=200)
    documento = models.CharField("CPF/CNPJ", max_length=18, blank=True)
    classe = models.CharField("classe", max_length=3, choices=ClasseCredor.choices)
    valor_arrolado = models.DecimalField(
        "valor arrolado", max_digits=15, decimal_places=2, default=0
    )
    valor_habilitado = models.DecimalField(
        "valor habilitado", max_digits=15, decimal_places=2, null=True, blank=True
    )
    situacao = models.CharField(
        "situacao", max_length=3, choices=SituacaoCredito.choices, default=SituacaoCredito.ARROLADO
    )
    sujeito_rj = models.BooleanField("sujeito a RJ", default=True)
    observacoes = models.TextField("observacoes", blank=True)

    class Meta:
        verbose_name = "credor"
        verbose_name_plural = "credores"
        ordering = ["classe", "-valor_arrolado"]

    def __str__(self) -> str:
        return f"{self.nome} ({self.get_classe_display()})"


class StatusParcela(models.TextChoices):
    PREVISTA = "PREV", "Prevista"
    PAGA = "PAGA", "Paga"
    ATRASADA = "ATRA", "Em atraso"
    RENEGOCIADA = "RENE", "Renegociada"


class Parcela(TimeStampedModel):
    """Obrigacao prevista no plano aprovado."""

    processo = models.ForeignKey(
        ProcessoRJ, verbose_name="processo", related_name="parcelas", on_delete=models.CASCADE
    )
    classe = models.CharField("classe", max_length=3, choices=ClasseCredor.choices, blank=True)
    descricao = models.CharField("descricao", max_length=200)
    vencimento = models.DateField("vencimento")
    valor_previsto = models.DecimalField("valor previsto", max_digits=15, decimal_places=2)
    valor_pago = models.DecimalField(
        "valor pago", max_digits=15, decimal_places=2, null=True, blank=True
    )
    pago_em = models.DateField("pago em", null=True, blank=True)
    status = models.CharField(
        "status", max_length=4, choices=StatusParcela.choices, default=StatusParcela.PREVISTA
    )

    class Meta:
        verbose_name = "parcela do plano"
        verbose_name_plural = "parcelas do plano"
        ordering = ["vencimento"]

    def __str__(self) -> str:
        return f"{self.descricao} - {self.vencimento:%d/%m/%Y}"
