"""Sincronizacao dos andamentos com a API publica do DataJud."""
from __future__ import annotations

import hashlib
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.processos.models import Andamento, FonteAndamento, TipoAndamento

from .datajud import DataJudClient, DataJudError, ProcessoDataJud
from .models import SincronizacaoDataJud, StatusSincronizacao

logger = logging.getLogger(__name__)

# Heuristica simples para classificar o movimento do CNJ nos tipos do sistema.
PALAVRAS_POR_TIPO = [
    (TipoAndamento.SENTENCA, ("sentenca", "sentença", "julgamento procedente", "extincao")),
    (TipoAndamento.DECISAO, ("decisao", "decisão", "liminar", "tutela", "deferimento")),
    (TipoAndamento.DESPACHO, ("despacho",)),
    (TipoAndamento.AUDIENCIA, ("audiencia", "audiência")),
    (TipoAndamento.ASSEMBLEIA, ("assembleia", "assembleia geral de credores", "agc")),
    (TipoAndamento.PETICAO, ("peticao", "petição", "juntada de peticao")),
    (TipoAndamento.RELATORIO_AJ, ("relatorio mensal", "relatório mensal", "administrador judicial")),
]


def classificar_movimento(nome: str) -> str:
    texto = (nome or "").lower()
    for tipo, palavras in PALAVRAS_POR_TIPO:
        if any(palavra in texto for palavra in palavras):
            return tipo
    return TipoAndamento.MOVIMENTACAO


def identificador_movimento(movimento: dict) -> str:
    """Identificador estavel do movimento, usado para nao duplicar andamentos."""
    bruto = f"{movimento.get('codigo')}|{movimento.get('data_hora')}|{movimento.get('nome')}"
    return hashlib.sha1(bruto.encode("utf-8")).hexdigest()


def _data_do_movimento(valor: str):
    """Data do movimento como o tribunal informou.

    O DataJud manda o timestamp com sufixo Z, mas a hora e a do tribunal. Nao
    convertemos o fuso de proposito: converter jogaria um ato da meia-noite
    para o dia anterior, e um dia a menos em sistema de prazo e erro grave.
    """
    momento = parse_datetime(valor) if valor else None
    if momento:
        return momento.date()
    return parse_date(valor or "") or timezone.localdate()


def _titulo(movimento: dict) -> str:
    titulo = movimento.get("nome") or "Movimentacao processual"
    complementos = [item for item in movimento.get("complementos") or [] if item]
    if complementos:
        titulo = f"{titulo} ({'; '.join(complementos)})"
    return titulo[:200]


def _completar_dados_do_processo(processo, dados: ProcessoDataJud) -> list[str]:
    """Preenche apenas o que esta vazio: o cadastro manual sempre prevalece."""
    alterados = []
    if not processo.vara and dados.orgao_julgador:
        processo.vara = dados.orgao_julgador[:120]
        alterados.append("vara")
    if not processo.data_distribuicao and dados.data_ajuizamento:
        data = _data_do_movimento(dados.data_ajuizamento)
        if data:
            processo.data_distribuicao = data
            alterados.append("data_distribuicao")
    if alterados:
        processo.save(update_fields=[*alterados, "atualizado_em"])
    return alterados


@transaction.atomic
def sincronizar_processo(processo, client: DataJudClient | None = None, usuario=None) -> SincronizacaoDataJud:
    """Busca o processo no DataJud e cria os andamentos que ainda nao existem."""
    client = client or DataJudClient()
    tribunal = processo.datajud_alias or processo.tribunal

    try:
        dados = client.consultar_processo(tribunal, processo.numero_cnj)
    except DataJudError as erro:
        logger.warning("Falha ao sincronizar processo %s: %s", processo.pk, erro)
        return SincronizacaoDataJud.objects.create(
            processo=processo,
            executado_por=usuario,
            status=StatusSincronizacao.ERRO,
            mensagem=str(erro),
        )

    if dados is None:
        return SincronizacaoDataJud.objects.create(
            processo=processo,
            executado_por=usuario,
            status=StatusSincronizacao.SEM_RESULTADO,
            mensagem="O tribunal nao retornou nenhum processo com esse numero.",
        )

    existentes = set(
        processo.andamentos.exclude(id_externo="").values_list("id_externo", flat=True)
    )
    # Processo com sigilo nunca vai para o portal, mesmo com a opcao ligada.
    visivel = settings.DATAJUD_ANDAMENTOS_VISIVEIS_CLIENTE and dados.nivel_sigilo == 0
    novos = []
    for movimento in dados.movimentos:
        identificador = identificador_movimento(movimento)
        if identificador in existentes:
            continue
        existentes.add(identificador)
        novos.append(
            Andamento(
                processo=processo,
                data=_data_do_movimento(movimento.get("data_hora")),
                tipo=classificar_movimento(movimento.get("nome")),
                titulo=_titulo(movimento),
                descricao="",
                fonte=FonteAndamento.TRIBUNAL,
                visivel_cliente=visivel,
                id_externo=identificador,
                codigo_movimento=movimento.get("codigo") or None,
            )
        )
    if novos:
        Andamento.objects.bulk_create(novos)

    alterados = _completar_dados_do_processo(processo, dados)
    mensagem = f"{len(novos)} andamento(s) novo(s)."
    if alterados:
        mensagem += f" Campos preenchidos a partir do tribunal: {', '.join(alterados)}."
    if not visivel and novos:
        mensagem += " Os andamentos importados ficam restritos a equipe ate serem liberados."
    if dados.nivel_sigilo:
        mensagem += f" Atencao: o tribunal marcou este processo com nivel de sigilo {dados.nivel_sigilo}."

    return SincronizacaoDataJud.objects.create(
        processo=processo,
        executado_por=usuario,
        status=StatusSincronizacao.SUCESSO,
        movimentos_recebidos=len(dados.movimentos),
        andamentos_criados=len(novos),
        atualizado_no_tribunal_em=dados.ultima_atualizacao[:40],
        mensagem=mensagem,
    )
