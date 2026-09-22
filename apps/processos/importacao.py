"""Leitura de planilhas com o quadro de credores.

Aceita .xlsx e .csv, com cabecalhos em portugues (com ou sem acento) e valores
no formato brasileiro. Nada e gravado aqui: o resultado e conferido na tela
antes de virar registro.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from .models import ClasseCredor, SituacaoCredito

# Nome da coluna no sistema -> apelidos aceitos na planilha
COLUNAS = {
    "nome": ["nome", "credor", "razao social", "nome razao social", "nome do credor", "razao"],
    "documento": ["documento", "cpf cnpj", "cnpj", "cpf", "cpf ou cnpj", "doc"],
    "classe": ["classe", "classe do credito", "classe credor"],
    "valor_arrolado": [
        "valor", "valor arrolado", "credito", "valor do credito",
        "valor arrolado pela devedora", "montante",
    ],
    "valor_habilitado": ["valor habilitado", "habilitado"],
    "situacao": ["situacao", "status"],
    "sujeito_rj": ["sujeito a rj", "sujeito", "sujeito rj", "concursal"],
    "observacoes": ["observacoes", "obs", "observacao", "notas"],
}

CLASSES = {
    "i": ClasseCredor.I, "1": ClasseCredor.I, "classe i": ClasseCredor.I,
    "trabalhista": ClasseCredor.I, "trabalhistas": ClasseCredor.I, "acidente de trabalho": ClasseCredor.I,
    "ii": ClasseCredor.II, "2": ClasseCredor.II, "classe ii": ClasseCredor.II,
    "garantia real": ClasseCredor.II, "com garantia real": ClasseCredor.II,
    "iii": ClasseCredor.III, "3": ClasseCredor.III, "classe iii": ClasseCredor.III,
    "quirografario": ClasseCredor.III, "quirografarios": ClasseCredor.III,
    "iv": ClasseCredor.IV, "4": ClasseCredor.IV, "classe iv": ClasseCredor.IV,
    "me epp": ClasseCredor.IV, "me": ClasseCredor.IV, "epp": ClasseCredor.IV,
    "microempresa": ClasseCredor.IV, "empresa de pequeno porte": ClasseCredor.IV,
}

SITUACOES = {
    "arrolado": SituacaoCredito.ARROLADO, "arrolada": SituacaoCredito.ARROLADO,
    "habilitado": SituacaoCredito.HABILITADO, "habilitada": SituacaoCredito.HABILITADO,
    "divergencia": SituacaoCredito.DIVERGENCIA, "divergente": SituacaoCredito.DIVERGENCIA,
    "impugnado": SituacaoCredito.IMPUGNADO, "impugnacao": SituacaoCredito.IMPUGNADO,
    "excluido": SituacaoCredito.EXCLUIDO, "excluida": SituacaoCredito.EXCLUIDO,
}

NEGATIVOS = {"nao", "n", "false", "0", "no"}


def normalizar(texto) -> str:
    """'Razão Social ' -> 'razao social'."""
    if texto is None:
        return ""
    texto = str(texto).strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return texto.strip()


def converter_valor(bruto) -> Decimal:
    """Aceita 1234.56, '1.234,56', 'R$ 1.234,56', '1234,56' e '1,234.56'."""
    if bruto is None or str(bruto).strip() == "":
        return Decimal("0")
    if isinstance(bruto, (int, float, Decimal)):
        return Decimal(str(bruto)).quantize(Decimal("0.01"))
    texto = re.sub(r"[^\d,.\-]", "", str(bruto).strip())
    # "mil reais" viraria 0,00 em silencio: num quadro de credores isso e pior
    # do que recusar a linha.
    if not re.search(r"\d", texto):
        raise ValueError(f"valor invalido: {bruto!r}")
    if "," in texto and "." in texto:
        # o separador decimal e o que aparece por ultimo
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        return Decimal(texto).quantize(Decimal("0.01"))
    except InvalidOperation as erro:
        raise ValueError(f"valor invalido: {bruto!r}") from erro


def converter_classe(bruto) -> str:
    chave = normalizar(bruto)
    if chave in CLASSES:
        return CLASSES[chave]
    for apelido, classe in CLASSES.items():
        if chave.startswith(apelido + " ") or chave == apelido:
            return classe
    raise ValueError(
        f"classe nao reconhecida: {bruto!r} (use I, II, III, IV ou o nome da classe)"
    )


def converter_situacao(bruto) -> str:
    chave = normalizar(bruto)
    if not chave:
        return SituacaoCredito.ARROLADO
    for apelido, situacao in SITUACOES.items():
        if chave.startswith(apelido):
            return situacao
    raise ValueError(f"situacao nao reconhecida: {bruto!r}")


def formatar_documento(bruto) -> str:
    digitos = re.sub(r"\D", "", str(bruto or ""))
    if len(digitos) == 11:
        return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"
    if len(digitos) == 14:
        return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"
    return str(bruto or "").strip()[:18]


@dataclass
class LinhaCredor:
    linha: int
    nome: str = ""
    documento: str = ""
    classe: str = ""
    valor_arrolado: Decimal = Decimal("0")
    valor_habilitado: Decimal | None = None
    situacao: str = SituacaoCredito.ARROLADO
    sujeito_rj: bool = True
    observacoes: str = ""
    erros: list[str] = field(default_factory=list)

    @property
    def valida(self) -> bool:
        return not self.erros


@dataclass
class ResultadoLeitura:
    linhas: list[LinhaCredor] = field(default_factory=list)
    colunas_encontradas: dict[str, int] = field(default_factory=dict)
    colunas_ignoradas: list[str] = field(default_factory=list)

    @property
    def validas(self) -> list[LinhaCredor]:
        return [linha for linha in self.linhas if linha.valida]

    @property
    def invalidas(self) -> list[LinhaCredor]:
        return [linha for linha in self.linhas if not linha.valida]

    @property
    def total_valor(self) -> Decimal:
        return sum((linha.valor_arrolado for linha in self.validas), Decimal("0"))


class PlanilhaInvalida(Exception):
    """A planilha nao pode ser lida (formato ou cabecalho)."""


def _linhas_do_arquivo(arquivo, nome_arquivo: str) -> list[list]:
    nome = (nome_arquivo or "").lower()
    conteudo = arquivo.read()
    if isinstance(conteudo, str):
        conteudo = conteudo.encode("utf-8")

    if nome.endswith(".csv") or nome.endswith(".txt"):
        for codificacao in ("utf-8-sig", "latin-1"):
            try:
                texto = conteudo.decode(codificacao)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise PlanilhaInvalida("Nao foi possivel ler o arquivo de texto.")
        amostra = texto[:2048]
        try:
            dialeto = csv.Sniffer().sniff(amostra, delimiters=";,\t")
        except csv.Error:
            dialeto = csv.excel
            dialeto.delimiter = ";" if amostra.count(";") > amostra.count(",") else ","
        return [linha for linha in csv.reader(io.StringIO(texto), dialeto)]

    if nome.endswith((".xlsx", ".xlsm")):
        try:
            from openpyxl import load_workbook
        except ImportError as erro:  # pragma: no cover
            raise PlanilhaInvalida(
                "Suporte a XLSX indisponivel: instale o openpyxl."
            ) from erro
        try:
            planilha = load_workbook(io.BytesIO(conteudo), data_only=True, read_only=True)
        except Exception as erro:
            raise PlanilhaInvalida(f"Nao foi possivel abrir a planilha: {erro}") from erro
        aba = planilha[planilha.sheetnames[0]]
        return [list(linha) for linha in aba.iter_rows(values_only=True)]

    raise PlanilhaInvalida("Formato nao suportado. Envie um arquivo .xlsx ou .csv.")


def _mapear_cabecalho(cabecalho: list) -> tuple[dict[str, int], list[str]]:
    encontradas: dict[str, int] = {}
    ignoradas: list[str] = []
    for indice, celula in enumerate(cabecalho):
        chave = normalizar(celula)
        if not chave:
            continue
        for campo, apelidos in COLUNAS.items():
            if chave in apelidos and campo not in encontradas:
                encontradas[campo] = indice
                break
        else:
            ignoradas.append(str(celula).strip())
    return encontradas, ignoradas


def ler_planilha(arquivo, nome_arquivo: str = "") -> ResultadoLeitura:
    """Le o arquivo e devolve as linhas ja validadas, sem gravar nada."""
    linhas_brutas = _linhas_do_arquivo(arquivo, nome_arquivo or getattr(arquivo, "name", ""))
    linhas_brutas = [linha for linha in linhas_brutas if any(
        celula is not None and str(celula).strip() != "" for celula in linha
    )]
    if not linhas_brutas:
        raise PlanilhaInvalida("A planilha esta vazia.")

    colunas, ignoradas = _mapear_cabecalho(linhas_brutas[0])
    faltando = [campo for campo in ("nome", "classe", "valor_arrolado") if campo not in colunas]
    if faltando:
        nomes = {"nome": "Credor", "classe": "Classe", "valor_arrolado": "Valor"}
        raise PlanilhaInvalida(
            "A primeira linha deve ser o cabecalho. Faltam as colunas: "
            + ", ".join(nomes[campo] for campo in faltando)
            + ". Baixe a planilha modelo para conferir o formato."
        )

    resultado = ResultadoLeitura(colunas_encontradas=colunas, colunas_ignoradas=ignoradas)

    def celula(linha, campo):
        indice = colunas.get(campo)
        if indice is None or indice >= len(linha):
            return None
        return linha[indice]

    for numero, bruta in enumerate(linhas_brutas[1:], start=2):
        item = LinhaCredor(linha=numero)
        item.nome = str(celula(bruta, "nome") or "").strip()[:200]
        if not item.nome:
            item.erros.append("credor sem nome")

        item.documento = formatar_documento(celula(bruta, "documento"))

        try:
            item.classe = converter_classe(celula(bruta, "classe"))
        except ValueError as erro:
            item.erros.append(str(erro))

        try:
            item.valor_arrolado = converter_valor(celula(bruta, "valor_arrolado"))
            if item.valor_arrolado < 0:
                item.erros.append("valor negativo")
        except ValueError as erro:
            item.erros.append(str(erro))

        bruto_habilitado = celula(bruta, "valor_habilitado")
        if bruto_habilitado not in (None, ""):
            try:
                item.valor_habilitado = converter_valor(bruto_habilitado)
            except ValueError as erro:
                item.erros.append(f"valor habilitado: {erro}")

        try:
            item.situacao = converter_situacao(celula(bruta, "situacao"))
        except ValueError as erro:
            item.erros.append(str(erro))

        sujeito = celula(bruta, "sujeito_rj")
        if sujeito not in (None, ""):
            item.sujeito_rj = normalizar(sujeito) not in NEGATIVOS

        item.observacoes = str(celula(bruta, "observacoes") or "").strip()
        resultado.linhas.append(item)

    if not resultado.linhas:
        raise PlanilhaInvalida("A planilha tem cabecalho, mas nenhuma linha de credor.")
    return resultado


# ---------------------------------------------------------------------------
# Gravacao


def _chave_duplicidade(nome: str, documento: str) -> str:
    digitos = re.sub(r"\D", "", documento or "")
    return f"doc:{digitos}" if digitos else f"nome:{normalizar(nome)}"


def aplicar_importacao(importacao, resultado: ResultadoLeitura, politica: str = "atualizar") -> dict:
    """Grava as linhas validas no quadro de credores do processo.

    politica define o que fazer com credor ja cadastrado (mesmo CPF/CNPJ ou,
    na falta dele, mesmo nome): 'atualizar', 'ignorar' ou 'duplicar'.
    """
    from django.db import transaction

    from .models import Credor, StatusImportacao

    processo = importacao.processo
    existentes = {}
    for credor in processo.credores.all():
        existentes.setdefault(_chave_duplicidade(credor.nome, credor.documento), credor)

    criar: list = []
    atualizar: list = []
    ignorados = 0

    for linha in resultado.validas:
        chave = _chave_duplicidade(linha.nome, linha.documento)
        atual = existentes.get(chave)
        if atual and politica == "ignorar":
            ignorados += 1
            continue
        if atual and politica == "atualizar":
            atual.classe = linha.classe
            atual.valor_arrolado = linha.valor_arrolado
            if linha.valor_habilitado is not None:
                atual.valor_habilitado = linha.valor_habilitado
            atual.situacao = linha.situacao
            atual.sujeito_rj = linha.sujeito_rj
            if linha.observacoes:
                atual.observacoes = linha.observacoes
            if linha.documento and not atual.documento:
                atual.documento = linha.documento
            atualizar.append(atual)
            continue
        novo = Credor(
            processo=processo,
            nome=linha.nome,
            documento=linha.documento,
            classe=linha.classe,
            valor_arrolado=linha.valor_arrolado,
            valor_habilitado=linha.valor_habilitado,
            situacao=linha.situacao,
            sujeito_rj=linha.sujeito_rj,
            observacoes=linha.observacoes,
        )
        criar.append(novo)
        existentes.setdefault(chave, novo)

    with transaction.atomic():
        if criar:
            Credor.objects.bulk_create(criar)
        if atualizar:
            Credor.objects.bulk_update(
                atualizar,
                ["classe", "valor_arrolado", "valor_habilitado", "situacao",
                 "sujeito_rj", "observacoes", "documento", "atualizado_em"],
            )
        importacao.status = StatusImportacao.CONCLUIDA
        importacao.linhas_lidas = len(resultado.linhas)
        importacao.linhas_validas = len(resultado.validas)
        importacao.criados = len(criar)
        importacao.atualizados = len(atualizar)
        importacao.ignorados = ignorados + len(resultado.invalidas)
        importacao.mensagem = (
            f"{len(criar)} credor(es) criado(s), {len(atualizar)} atualizado(s), "
            f"{ignorados} ja cadastrado(s) ignorado(s), "
            f"{len(resultado.invalidas)} linha(s) com erro descartada(s)."
        )
        importacao.save()

    return {
        "criados": len(criar),
        "atualizados": len(atualizar),
        "ignorados": ignorados,
        "com_erro": len(resultado.invalidas),
    }


def planilha_modelo() -> bytes:
    """Gera o XLSX modelo, com uma linha de exemplo por classe."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    cabecalho = [
        "Credor", "CPF/CNPJ", "Classe", "Valor", "Valor habilitado",
        "Situacao", "Sujeito a RJ", "Observacoes",
    ]
    exemplos = [
        ["Sindicato dos Metalurgicos", "12.345.678/0001-90", "I", "320000,00", "", "Arrolado", "Sim", ""],
        ["Banco Exemplo S.A.", "60.746.948/0001-12", "II", "1850000,00", "1850000,00", "Habilitado", "Sim", "Garantia: imovel matricula 123"],
        ["Fornecedora Alfa Ltda", "11.222.333/0001-44", "III", "1230000,00", "", "Divergencia", "Sim", ""],
        ["Transportes Beta ME", "22.333.444/0001-55", "IV", "145000,00", "", "Arrolado", "Sim", ""],
    ]

    livro = Workbook()
    aba = livro.active
    aba.title = "Credores"
    aba.append(cabecalho)
    for linha in exemplos:
        aba.append(linha)

    fundo = PatternFill("solid", fgColor="0F172A")
    for indice, _ in enumerate(cabecalho, start=1):
        celula = aba.cell(row=1, column=indice)
        celula.font = Font(bold=True, color="FFFFFF")
        celula.fill = fundo
        celula.alignment = Alignment(vertical="center")
        aba.column_dimensions[get_column_letter(indice)].width = 26
    aba.freeze_panes = "A2"

    ajuda = livro.create_sheet("Instrucoes")
    for linha in [
        ["Como preencher"],
        [""],
        ["Credor", "obrigatorio - nome ou razao social"],
        ["CPF/CNPJ", "opcional - usado para identificar credor ja cadastrado"],
        ["Classe", "obrigatorio - I, II, III, IV ou o nome (trabalhista, garantia real, quirografario, ME/EPP)"],
        ["Valor", "obrigatorio - valor arrolado. Aceita 1.234,56 ou 1234.56"],
        ["Valor habilitado", "opcional - valor apos a verificacao do AJ"],
        ["Situacao", "opcional - arrolado, habilitado, divergencia, impugnado, excluido. Vazio = arrolado"],
        ["Sujeito a RJ", "opcional - sim/nao. Vazio = sim"],
        ["Observacoes", "opcional - texto livre"],
        [""],
        ["A ordem das colunas nao importa; o sistema le pelo cabecalho."],
        ["Colunas a mais sao ignoradas."],
    ]:
        ajuda.append(linha)
    ajuda.column_dimensions["A"].width = 20
    ajuda.column_dimensions["B"].width = 90
    ajuda["A1"].font = Font(bold=True, size=13)

    fluxo = io.BytesIO()
    livro.save(fluxo)
    return fluxo.getvalue()
