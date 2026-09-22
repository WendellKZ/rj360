"""Cliente da API publica do DataJud (CNJ).

A API expoe os metadados processuais dos tribunais em indices Elasticsearch,
um por tribunal (``api_publica_tjsp``, ``api_publica_trt3``...). A chave de
acesso e publica, mas nao fica no codigo: leia de DATAJUD_API_KEY no .env.

Documentacao: https://datajud-wiki.cnj.jus.br/api-publica/
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class DataJudError(Exception):
    """Falha ao consultar a API do DataJud."""


class DataJudNaoConfigurado(DataJudError):
    """A chave de acesso nao foi informada no .env."""


class TribunalNaoSuportado(DataJudError):
    """Nao foi possivel deduzir o indice do tribunal."""


UFS = [
    "AC", "AL", "AM", "AP", "BA", "CE", "ES", "GO", "MA", "MG", "MS", "MT",
    "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE",
    "SP", "TO",
]

# Siglas com endpoint na API publica, conforme
# https://datajud-wiki.cnj.jus.br/api-publica/endpoints/
# (o STF nao tem endpoint publico no Datajud).
TRIBUNAIS = (
    {"TST", "TSE", "STJ", "STM"}
    | {f"TRF{numero}" for numero in range(1, 7)}
    | {f"TJ{uf}" for uf in UFS}
    | {"TJDFT"}
    | {f"TRT{numero}" for numero in range(1, 25)}
    | {f"TRE-{uf}" for uf in UFS}
    | {"TRE-DFT"}
    | {"TJMMG", "TJMRS", "TJMSP"}  # justica militar estadual
)


def normalizar_sigla(tribunal: str) -> str:
    """'TJ-SP', 'tjsp ' -> 'TJSP'. Tribunais eleitorais levam hifen."""
    sigla = re.sub(r"[^A-Za-z0-9]", "", (tribunal or "")).upper()
    if sigla.startswith("TRE") and len(sigla) > 3:
        return f"TRE-{sigla[3:]}"
    return sigla


def alias_do_tribunal(tribunal: str) -> str:
    """'TJSP' -> 'api_publica_tjsp'."""
    sigla = normalizar_sigla(tribunal)
    if not sigla:
        raise TribunalNaoSuportado(
            "Informe a sigla do tribunal no processo (ex.: TJSP, TRT15, TRF3)."
        )
    if sigla not in TRIBUNAIS:
        raise TribunalNaoSuportado(
            f"Tribunal sem endpoint na API publica do Datajud: {tribunal!r}. "
            "Use uma das siglas da lista do CNJ (TJSP, TJDFT, TRT15, TRF3, TRE-SP...)."
        )
    return f"api_publica_{sigla.lower()}"


def somente_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


@dataclass
class ProcessoDataJud:
    """Resposta da API ja normalizada."""

    numero_processo: str
    tribunal: str = ""
    grau: str = ""
    classe: str = ""
    orgao_julgador: str = ""
    data_ajuizamento: str = ""
    ultima_atualizacao: str = ""
    nivel_sigilo: int = 0
    assuntos: list[str] = field(default_factory=list)
    movimentos: list[dict[str, Any]] = field(default_factory=list)
    bruto: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def de_hit(cls, hit: dict[str, Any]) -> "ProcessoDataJud":
        fonte = hit.get("_source", hit) or {}
        classe = fonte.get("classe") or {}
        orgao = fonte.get("orgaoJulgador") or {}
        movimentos = []
        for movimento in fonte.get("movimentos") or []:
            movimentos.append(
                {
                    "codigo": movimento.get("codigo"),
                    "nome": (movimento.get("nome") or "").strip(),
                    "data_hora": movimento.get("dataHora") or "",
                    # 'descricao' e um rotulo tecnico do CNJ
                    # ("tipo_de_distribuicao_redistribuicao"); so 'nome' e legivel.
                    "complementos": [
                        (item.get("nome") or "").strip()
                        for item in movimento.get("complementosTabelados") or []
                        if (item.get("nome") or "").strip()
                    ],
                }
            )
        return cls(
            numero_processo=fonte.get("numeroProcesso", ""),
            tribunal=fonte.get("tribunal", ""),
            grau=fonte.get("grau", ""),
            classe=(classe.get("nome") or "").strip(),
            orgao_julgador=(orgao.get("nome") or "").strip(),
            data_ajuizamento=fonte.get("dataAjuizamento") or "",
            ultima_atualizacao=fonte.get("dataHoraUltimaAtualizacao") or "",
            nivel_sigilo=int(fonte.get("nivelSigilo") or 0),
            assuntos=[
                (assunto.get("nome") or "").strip()
                for assunto in fonte.get("assuntos") or []
            ],
            movimentos=movimentos,
            bruto=fonte,
        )


class DataJudClient:
    """Consulta a API publica do DataJud.

    O esquema do header ('APIKey' por padrao) e configuravel para o caso de o
    CNJ mudar a forma de autenticacao sem precisar alterar o codigo.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        esquema: str | None = None,
        timeout: int | None = None,
        sessao: requests.Session | None = None,
    ):
        self.api_key = api_key if api_key is not None else settings.DATAJUD_API_KEY
        self.base_url = (base_url or settings.DATAJUD_BASE_URL).rstrip("/")
        self.esquema = esquema or settings.DATAJUD_AUTH_SCHEME
        self.timeout = timeout or settings.DATAJUD_TIMEOUT
        self.sessao = sessao or requests.Session()

    @property
    def configurado(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        if not self.configurado:
            raise DataJudNaoConfigurado(
                "Defina DATAJUD_API_KEY no .env. A chave publica esta em "
                "https://datajud-wiki.cnj.jus.br/api-publica/acesso/"
            )
        return {
            "Authorization": f"{self.esquema} {self.api_key}".strip(),
            "Content-Type": "application/json",
        }

    def buscar(self, tribunal: str, consulta: dict[str, Any]) -> list[dict[str, Any]]:
        """Executa uma busca no indice do tribunal e devolve os hits."""
        url = f"{self.base_url}/{alias_do_tribunal(tribunal)}/_search"
        try:
            resposta = self.sessao.post(
                url, json=consulta, headers=self._headers(), timeout=self.timeout
            )
        except requests.RequestException as erro:
            raise DataJudError(f"Falha de conexao com o DataJud: {erro}") from erro

        if resposta.status_code in (401, 403):
            raise DataJudNaoConfigurado(
                "O DataJud recusou a chave de acesso (HTTP "
                f"{resposta.status_code}). Confira DATAJUD_API_KEY no .env."
            )
        if resposta.status_code >= 400:
            raise DataJudError(
                f"DataJud respondeu HTTP {resposta.status_code}: {resposta.text[:300]}"
            )
        try:
            dados = resposta.json()
        except ValueError as erro:
            raise DataJudError("Resposta do DataJud nao e um JSON valido.") from erro
        return (dados.get("hits") or {}).get("hits") or []

    def consultar_processo(self, tribunal: str, numero_cnj: str) -> ProcessoDataJud | None:
        """Busca um processo pelo numero unico (com ou sem mascara)."""
        numero = somente_digitos(numero_cnj)
        if len(numero) != 20:
            raise DataJudError("Numero CNJ invalido: sao esperados 20 digitos.")
        hits = self.buscar(
            tribunal,
            {"size": 1, "query": {"match": {"numeroProcesso": numero}}},
        )
        if not hits:
            return None
        return ProcessoDataJud.de_hit(hits[0])
