"""Regras de negocio dos processos de RJ."""
from dataclasses import dataclass
from datetime import date, timedelta

from .models import Prazo, ProcessoRJ, StatusPrazo, TipoPrazo


@dataclass(frozen=True)
class MarcoLegal:
    chave: str
    titulo: str
    base_legal: str
    campo_inicio: str
    dias: int
    descricao: str


# Marcos da Lei 11.101/2005 que geram prazo a partir de uma data do processo.
MARCOS_LEGAIS: list[MarcoLegal] = [
    MarcoLegal(
        chave="plano",
        titulo="Apresentar o plano de recuperacao judicial",
        base_legal="Lei 11.101/2005, art. 53",
        campo_inicio="data_deferimento",
        dias=60,
        descricao="60 dias da publicacao da decisao que deferiu o processamento.",
    ),
    MarcoLegal(
        chave="habilitacoes",
        titulo="Habilitacoes e divergencias de credito ao AJ",
        base_legal="Lei 11.101/2005, art. 7, §1",
        campo_inicio="data_edital_52",
        dias=15,
        descricao="15 dias da publicacao do edital do art. 52, §1.",
    ),
    MarcoLegal(
        chave="objecoes",
        titulo="Prazo para objecoes ao plano",
        base_legal="Lei 11.101/2005, art. 55",
        campo_inicio="data_edital_53",
        dias=30,
        descricao="30 dias da publicacao do aviso de recebimento do plano.",
    ),
    MarcoLegal(
        chave="stay",
        titulo="Fim do periodo de suspensao (stay period)",
        base_legal="Lei 11.101/2005, art. 6, §4",
        campo_inicio="data_deferimento",
        dias=180,
        descricao="180 dias do deferimento, prorrogaveis por igual periodo uma unica vez.",
    ),
    MarcoLegal(
        chave="fiscalizacao",
        titulo="Fim do periodo de fiscalizacao judicial",
        base_legal="Lei 11.101/2005, art. 61",
        campo_inicio="data_concessao",
        dias=730,
        descricao="Dois anos contados da concessao da recuperacao judicial.",
    ),
]


def gerar_prazos_legais(processo: ProcessoRJ, responsavel=None) -> list[Prazo]:
    """Cria os prazos legais que ainda nao existem para o processo.

    Nao sobrescreve prazos ja cadastrados: o controle manual sempre prevalece.
    """
    criados: list[Prazo] = []
    for marco in MARCOS_LEGAIS:
        inicio: date | None = getattr(processo, marco.campo_inicio, None)
        if not inicio:
            continue
        dias = marco.dias
        if marco.chave == "stay" and processo.stay_prorrogado:
            dias = 360
        prazo, criado = Prazo.objects.get_or_create(
            processo=processo,
            titulo=marco.titulo,
            defaults={
                "base_legal": marco.base_legal,
                "tipo": TipoPrazo.LEGAL,
                "data_inicio": inicio,
                "data_fim": inicio + timedelta(days=dias),
                "responsavel": responsavel,
                "status": StatusPrazo.PENDENTE,
                "observacoes": marco.descricao,
            },
        )
        if criado:
            criados.append(prazo)
    return criados


def resumo_credores(processo: ProcessoRJ) -> list[dict]:
    """Totaliza os creditos por classe."""
    from django.db.models import Count, Sum

    from .models import ClasseCredor

    agregado = {
        linha["classe"]: linha
        for linha in processo.credores.values("classe").annotate(
            quantidade=Count("id"),
            total_arrolado=Sum("valor_arrolado"),
            total_habilitado=Sum("valor_habilitado"),
        )
    }
    resultado = []
    for valor, rotulo in ClasseCredor.choices:
        linha = agregado.get(valor, {})
        resultado.append(
            {
                "classe": valor,
                "rotulo": rotulo,
                "quantidade": linha.get("quantidade", 0),
                "total_arrolado": linha.get("total_arrolado") or 0,
                "total_habilitado": linha.get("total_habilitado") or 0,
            }
        )
    return resultado
