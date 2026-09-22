import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook

from apps.empresas.models import Empresa
from apps.processos.importacao import (
    PlanilhaInvalida,
    aplicar_importacao,
    converter_classe,
    converter_valor,
    ler_planilha,
    planilha_modelo,
)
from apps.processos.models import ClasseCredor, Credor, ImportacaoCredores, ProcessoRJ, SituacaoCredito, StatusImportacao

User = get_user_model()

CABECALHO = ["Credor", "CPF/CNPJ", "Classe", "Valor", "Situacao", "Sujeito a RJ", "Observacoes"]


def xlsx(linhas, cabecalho=None):
    livro = Workbook()
    aba = livro.active
    aba.append(cabecalho or CABECALHO)
    for linha in linhas:
        aba.append(linha)
    fluxo = io.BytesIO()
    livro.save(fluxo)
    fluxo.seek(0)
    return fluxo


def csv_arquivo(texto):
    return io.BytesIO(texto.encode("utf-8"))


class ConversoesTest(TestCase):
    def test_valores_em_formato_brasileiro(self):
        self.assertEqual(converter_valor("1.234,56"), Decimal("1234.56"))
        self.assertEqual(converter_valor("R$ 1.234,56"), Decimal("1234.56"))
        self.assertEqual(converter_valor("1234,56"), Decimal("1234.56"))
        self.assertEqual(converter_valor("1234.56"), Decimal("1234.56"))
        self.assertEqual(converter_valor("1,234.56"), Decimal("1234.56"))
        self.assertEqual(converter_valor(1234.5), Decimal("1234.50"))
        self.assertEqual(converter_valor(""), Decimal("0"))

    def test_valor_invalido(self):
        with self.assertRaises(ValueError):
            converter_valor("abc")

    def test_classes_por_numero_romano_arabe_e_nome(self):
        self.assertEqual(converter_classe("I"), ClasseCredor.I)
        self.assertEqual(converter_classe("1"), ClasseCredor.I)
        self.assertEqual(converter_classe("Trabalhista"), ClasseCredor.I)
        self.assertEqual(converter_classe("Classe II"), ClasseCredor.II)
        self.assertEqual(converter_classe("garantia real"), ClasseCredor.II)
        self.assertEqual(converter_classe("Quirografário"), ClasseCredor.III)
        self.assertEqual(converter_classe("ME/EPP"), ClasseCredor.IV)

    def test_classe_desconhecida(self):
        with self.assertRaises(ValueError):
            converter_classe("classe V")


class LeituraTest(TestCase):
    def test_le_xlsx_completo(self):
        arquivo = xlsx([
            ["Banco Exemplo S.A.", "60.746.948/0001-12", "II", "1.850.000,00", "Habilitado", "Sim", "garantia"],
            ["Fornecedora Alfa", "", "III", "1230000", "", "", ""],
        ])
        resultado = ler_planilha(arquivo, "credores.xlsx")

        self.assertEqual(len(resultado.validas), 2)
        primeiro = resultado.validas[0]
        self.assertEqual(primeiro.nome, "Banco Exemplo S.A.")
        self.assertEqual(primeiro.classe, ClasseCredor.II)
        self.assertEqual(primeiro.valor_arrolado, Decimal("1850000.00"))
        self.assertEqual(primeiro.situacao, SituacaoCredito.HABILITADO)
        self.assertEqual(resultado.total_valor, Decimal("3080000.00"))
        # sem situacao informada, entra como arrolado
        self.assertEqual(resultado.validas[1].situacao, SituacaoCredito.ARROLADO)

    def test_cabecalho_com_acento_e_ordem_diferente(self):
        arquivo = xlsx(
            [["1.850.000,00", "Banco Exemplo", "II"]],
            cabecalho=["Valor do crédito", "Razão Social", "Classe"],
        )
        resultado = ler_planilha(arquivo, "credores.xlsx")
        self.assertEqual(len(resultado.validas), 1)
        self.assertEqual(resultado.validas[0].nome, "Banco Exemplo")

    def test_colunas_a_mais_sao_ignoradas(self):
        arquivo = xlsx(
            [["Banco", "II", "1000", "coisa"]],
            cabecalho=["Credor", "Classe", "Valor", "Coluna estranha"],
        )
        resultado = ler_planilha(arquivo, "credores.xlsx")
        self.assertEqual(resultado.colunas_ignoradas, ["Coluna estranha"])
        self.assertEqual(len(resultado.validas), 1)

    def test_le_csv_com_ponto_e_virgula(self):
        arquivo = csv_arquivo(
            "Credor;CPF/CNPJ;Classe;Valor\n"
            "Banco Exemplo;60.746.948/0001-12;II;1.850.000,00\n"
        )
        resultado = ler_planilha(arquivo, "credores.csv")
        self.assertEqual(len(resultado.validas), 1)
        self.assertEqual(resultado.validas[0].valor_arrolado, Decimal("1850000.00"))

    def test_relata_erro_por_linha_sem_derrubar_o_resto(self):
        arquivo = xlsx([
            ["Credor bom", "", "III", "1000", "", "", ""],
            ["", "", "III", "1000", "", "", ""],
            ["Credor com classe errada", "", "classe X", "1000", "", "", ""],
            ["Credor com valor errado", "", "III", "mil reais", "", "", ""],
        ])
        resultado = ler_planilha(arquivo, "credores.xlsx")
        self.assertEqual(len(resultado.validas), 1)
        self.assertEqual(len(resultado.invalidas), 3)
        self.assertEqual(resultado.invalidas[0].linha, 3)
        self.assertIn("sem nome", resultado.invalidas[0].erros[0])

    def test_formata_documento(self):
        arquivo = xlsx([["Banco", "60746948000112", "II", "10", "", "", ""]])
        resultado = ler_planilha(arquivo, "credores.xlsx")
        self.assertEqual(resultado.validas[0].documento, "60.746.948/0001-12")

    def test_sujeito_a_rj_negativo(self):
        arquivo = xlsx([["Fisco", "", "III", "10", "", "Nao", ""]])
        resultado = ler_planilha(arquivo, "credores.xlsx")
        self.assertFalse(resultado.validas[0].sujeito_rj)

    def test_falta_coluna_obrigatoria(self):
        arquivo = xlsx([["Banco", "1000"]], cabecalho=["Credor", "Valor"])
        with self.assertRaises(PlanilhaInvalida) as contexto:
            ler_planilha(arquivo, "credores.xlsx")
        self.assertIn("Classe", str(contexto.exception))

    def test_formato_nao_suportado(self):
        with self.assertRaises(PlanilhaInvalida):
            ler_planilha(io.BytesIO(b"conteudo"), "credores.pdf")

    def test_planilha_so_com_cabecalho(self):
        with self.assertRaises(PlanilhaInvalida):
            ler_planilha(xlsx([]), "credores.xlsx")

    def test_modelo_pode_ser_lido_pelo_proprio_leitor(self):
        resultado = ler_planilha(io.BytesIO(planilha_modelo()), "modelo.xlsx")
        self.assertEqual(len(resultado.validas), 4)
        self.assertEqual(len(resultado.invalidas), 0)


class GravacaoTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("interno", password="x")
        empresa = Empresa.objects.create(razao_social="Empresa Teste Ltda", cnpj="04.252.011/0001-10")
        self.processo = ProcessoRJ.objects.create(
            empresa=empresa, numero_cnj="1002345-12.2025.8.26.0114"
        )
        self.importacao = ImportacaoCredores.objects.create(
            processo=self.processo, arquivo="importacoes/x.xlsx", enviado_por=self.user
        )

    def _resultado(self, linhas):
        return ler_planilha(xlsx(linhas), "credores.xlsx")

    def test_cria_credores(self):
        resultado = self._resultado([
            ["Banco Exemplo", "60.746.948/0001-12", "II", "1000", "", "", ""],
            ["Fornecedora Alfa", "", "III", "500", "", "", ""],
        ])
        numeros = aplicar_importacao(self.importacao, resultado)
        self.assertEqual(numeros["criados"], 2)
        self.assertEqual(Credor.objects.count(), 2)
        self.importacao.refresh_from_db()
        self.assertEqual(self.importacao.status, StatusImportacao.CONCLUIDA)

    def test_atualiza_credor_existente_pelo_documento(self):
        Credor.objects.create(
            processo=self.processo, nome="Banco Exemplo SA",
            documento="60.746.948/0001-12", classe=ClasseCredor.III, valor_arrolado=1,
        )
        resultado = self._resultado([["Banco Exemplo", "60746948000112", "II", "1000", "Habilitado", "", ""]])
        numeros = aplicar_importacao(self.importacao, resultado, politica="atualizar")

        self.assertEqual(numeros["atualizados"], 1)
        self.assertEqual(Credor.objects.count(), 1)
        credor = Credor.objects.get()
        self.assertEqual(credor.classe, ClasseCredor.II)
        self.assertEqual(credor.valor_arrolado, Decimal("1000.00"))
        self.assertEqual(credor.situacao, SituacaoCredito.HABILITADO)

    def test_politica_ignorar_mantem_o_que_existe(self):
        Credor.objects.create(
            processo=self.processo, nome="Banco Exemplo",
            documento="60.746.948/0001-12", classe=ClasseCredor.III, valor_arrolado=1,
        )
        resultado = self._resultado([
            ["Banco Exemplo", "60746948000112", "II", "1000", "", "", ""],
            ["Novo Credor", "", "III", "500", "", "", ""],
        ])
        numeros = aplicar_importacao(self.importacao, resultado, politica="ignorar")
        self.assertEqual(numeros["ignorados"], 1)
        self.assertEqual(numeros["criados"], 1)
        self.assertEqual(Credor.objects.get(nome="Banco Exemplo").valor_arrolado, Decimal("1.00"))

    def test_duplicidade_por_nome_quando_nao_ha_documento(self):
        Credor.objects.create(
            processo=self.processo, nome="Fornecedora Alfa", classe=ClasseCredor.III, valor_arrolado=1
        )
        resultado = self._resultado([["fornecedora alfa", "", "III", "900", "", "", ""]])
        numeros = aplicar_importacao(self.importacao, resultado, politica="atualizar")
        self.assertEqual(numeros["atualizados"], 1)
        self.assertEqual(Credor.objects.count(), 1)

    def test_politica_duplicar_cria_de_novo(self):
        Credor.objects.create(
            processo=self.processo, nome="Fornecedora Alfa", classe=ClasseCredor.III, valor_arrolado=1
        )
        resultado = self._resultado([["Fornecedora Alfa", "", "III", "900", "", "", ""]])
        aplicar_importacao(self.importacao, resultado, politica="duplicar")
        self.assertEqual(Credor.objects.count(), 2)


class FluxoTelaTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("interno", password="x")
        empresa = Empresa.objects.create(razao_social="Empresa Teste Ltda", cnpj="04.252.011/0001-10")
        self.processo = ProcessoRJ.objects.create(
            empresa=empresa, numero_cnj="1002345-12.2025.8.26.0114"
        )
        self.client.force_login(self.user)

    def _upload(self, linhas=None):
        conteudo = xlsx(linhas or [["Banco Exemplo", "60.746.948/0001-12", "II", "1.000,00", "", "", ""]]).read()
        return SimpleUploadedFile(
            "credores.xlsx", conteudo,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_previa_nao_grava_nada(self):
        url = reverse("processos:credores_importar", args=[self.processo.pk])
        resposta = self.client.post(url, {"arquivo": self._upload(), "politica": "atualizar"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Banco Exemplo")
        self.assertEqual(Credor.objects.count(), 0)
        self.assertEqual(ImportacaoCredores.objects.count(), 1)

    def test_confirmacao_grava(self):
        url = reverse("processos:credores_importar", args=[self.processo.pk])
        self.client.post(url, {"arquivo": self._upload(), "politica": "atualizar"})
        importacao = ImportacaoCredores.objects.get()

        resposta = self.client.post(
            reverse("processos:credores_importar_confirmar", args=[importacao.pk]),
            {"politica": "atualizar"},
        )
        self.assertRedirects(resposta, self.processo.get_absolute_url())
        self.assertEqual(Credor.objects.count(), 1)
        self.assertEqual(Credor.objects.get().valor_arrolado, Decimal("1000.00"))

    def test_arquivo_invalido_mostra_erro(self):
        url = reverse("processos:credores_importar", args=[self.processo.pk])
        arquivo = SimpleUploadedFile("credores.xlsx", b"nao e uma planilha")
        resposta = self.client.post(url, {"arquivo": arquivo, "politica": "atualizar"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "planilha")
        self.assertEqual(ImportacaoCredores.objects.count(), 0)

    def test_extensao_recusada(self):
        url = reverse("processos:credores_importar", args=[self.processo.pk])
        arquivo = SimpleUploadedFile("credores.pdf", b"%PDF-1.4")
        resposta = self.client.post(url, {"arquivo": arquivo, "politica": "atualizar"})
        self.assertContains(resposta, ".xlsx")

    def test_download_do_modelo(self):
        resposta = self.client.get(reverse("processos:credores_modelo"))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("spreadsheetml", resposta["Content-Type"])
        self.assertIn("modelo-credores", resposta["Content-Disposition"])
