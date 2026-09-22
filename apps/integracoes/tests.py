from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.empresas.models import Empresa
from apps.integracoes.datajud import (
    DataJudClient,
    DataJudError,
    DataJudNaoConfigurado,
    ProcessoDataJud,
    TribunalNaoSuportado,
    alias_do_tribunal,
)
from apps.integracoes.models import SincronizacaoDataJud, StatusSincronizacao
from apps.integracoes.services import classificar_movimento, sincronizar_processo
from apps.processos.models import Andamento, FonteAndamento, ProcessoRJ, TipoAndamento

User = get_user_model()


def resposta_datajud(
    movimentos,
    orgao="1a Vara de Falencias",
    ajuizamento="2025-03-10T00:00:00.000Z",
    nivel_sigilo=0,
):
    """Resposta no formato documentado pelo CNJ (wiki do Datajud, Ex. 1)."""
    return {
        "hits": {
            "total": {"value": 1, "relation": "eq"},
            "hits": [
                {
                    "_index": "api_publica_tjsp",
                    "_id": "TJSP_129_G1_114_10023451220258260114",
                    "_source": {
                        "numeroProcesso": "10023451220258260114",
                        "tribunal": "TJSP",
                        "grau": "G1",
                        "nivelSigilo": nivel_sigilo,
                        "sistema": {"codigo": 1, "nome": "Pje"},
                        "formato": {"codigo": 1, "nome": "Eletronico"},
                        "dataHoraUltimaAtualizacao": "2025-04-02T19:10:08.483Z",
                        "classe": {"codigo": 129, "nome": "Recuperacao Judicial"},
                        "orgaoJulgador": {"codigoMunicipioIBGE": 6291, "codigo": 1, "nome": orgao},
                        "dataAjuizamento": ajuizamento,
                        "assuntos": [{"codigo": 1, "nome": "Recuperacao judicial"}],
                        "movimentos": movimentos,
                    },
                }
            ],
        }
    }


class RespostaFalsa:
    def __init__(self, dados, status_code=200):
        self._dados = dados
        self.status_code = status_code
        self.text = str(dados)

    def json(self):
        return self._dados


class SessaoFalsa:
    def __init__(self, resposta):
        self.resposta = resposta
        self.chamadas = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.chamadas.append({"url": url, "json": json, "headers": headers})
        return self.resposta


class AliasTest(TestCase):
    def test_siglas_comuns(self):
        self.assertEqual(alias_do_tribunal("TJSP"), "api_publica_tjsp")
        self.assertEqual(alias_do_tribunal("tj-sp"), "api_publica_tjsp")
        self.assertEqual(alias_do_tribunal("TRT15"), "api_publica_trt15")
        self.assertEqual(alias_do_tribunal("TRF3"), "api_publica_trf3")
        self.assertEqual(alias_do_tribunal("TRESP"), "api_publica_tre-sp")

    def test_siglas_fora_do_padrao_de_duas_letras(self):
        self.assertEqual(alias_do_tribunal("TJDFT"), "api_publica_tjdft")
        self.assertEqual(alias_do_tribunal("TJMSP"), "api_publica_tjmsp")
        self.assertEqual(alias_do_tribunal("TRT24"), "api_publica_trt24")
        self.assertEqual(alias_do_tribunal("STJ"), "api_publica_stj")

    def test_sigla_invalida(self):
        with self.assertRaises(TribunalNaoSuportado):
            alias_do_tribunal("Vara de Campinas")
        with self.assertRaises(TribunalNaoSuportado):
            alias_do_tribunal("")
        with self.assertRaises(TribunalNaoSuportado):
            alias_do_tribunal("TJXX")
        with self.assertRaises(TribunalNaoSuportado):
            # o STF nao tem endpoint na API publica
            alias_do_tribunal("STF")


class ClienteTest(TestCase):
    def test_consulta_monta_url_e_header(self):
        sessao = SessaoFalsa(RespostaFalsa(resposta_datajud([])))
        client = DataJudClient(api_key="chave-teste", sessao=sessao)
        dados = client.consultar_processo("TJSP", "1002345-12.2025.8.26.0114")

        chamada = sessao.chamadas[0]
        self.assertTrue(chamada["url"].endswith("/api_publica_tjsp/_search"))
        self.assertEqual(chamada["headers"]["Authorization"], "APIKey chave-teste")
        self.assertEqual(chamada["json"]["query"]["match"]["numeroProcesso"], "10023451220258260114")
        self.assertIsInstance(dados, ProcessoDataJud)
        self.assertEqual(dados.classe, "Recuperacao Judicial")

    def test_sem_resultado_devolve_none(self):
        client = DataJudClient(api_key="x", sessao=SessaoFalsa(RespostaFalsa({"hits": {"hits": []}})))
        self.assertIsNone(client.consultar_processo("TJSP", "1002345-12.2025.8.26.0114"))

    def test_chave_recusada(self):
        client = DataJudClient(api_key="x", sessao=SessaoFalsa(RespostaFalsa({}, status_code=401)))
        with self.assertRaises(DataJudNaoConfigurado):
            client.consultar_processo("TJSP", "1002345-12.2025.8.26.0114")

    def test_sem_chave_configurada(self):
        client = DataJudClient(api_key="", sessao=SessaoFalsa(RespostaFalsa({})))
        with self.assertRaises(DataJudNaoConfigurado):
            client.consultar_processo("TJSP", "1002345-12.2025.8.26.0114")

    def test_numero_invalido(self):
        client = DataJudClient(api_key="x", sessao=SessaoFalsa(RespostaFalsa({})))
        with self.assertRaises(DataJudError):
            client.consultar_processo("TJSP", "123")


class ClienteFalso:
    """Substitui o DataJudClient nos testes de sincronizacao."""

    def __init__(self, dados=None, erro=None):
        self.dados = dados
        self.erro = erro

    def consultar_processo(self, tribunal, numero):
        if self.erro:
            raise self.erro
        return self.dados


class SincronizacaoTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            razao_social="Empresa Teste Ltda", cnpj="04.252.011/0001-10"
        )
        self.processo = ProcessoRJ.objects.create(
            empresa=self.empresa,
            numero_cnj="1002345-12.2025.8.26.0114",
            tribunal="TJSP",
        )
        self.movimentos = [
            {"codigo": 26, "nome": "Distribuicao", "dataHora": "2025-03-10T09:00:00.000Z"},
            {
                "codigo": 193,
                "nome": "Decisao",
                "dataHora": "2025-03-20T15:30:00.000Z",
                "complementosTabelados": [{"nome": "Deferido o processamento"}],
            },
        ]

    def _dados(self, movimentos=None, **kwargs):
        bruto = resposta_datajud(movimentos if movimentos is not None else self.movimentos, **kwargs)
        return ProcessoDataJud.de_hit(bruto["hits"]["hits"][0])

    def test_importa_movimentos_como_andamentos(self):
        registro = sincronizar_processo(self.processo, client=ClienteFalso(self._dados()))
        self.assertEqual(registro.status, StatusSincronizacao.SUCESSO)
        self.assertEqual(registro.andamentos_criados, 2)
        self.assertEqual(Andamento.objects.count(), 2)
        andamento = Andamento.objects.get(codigo_movimento=193)
        self.assertEqual(andamento.fonte, FonteAndamento.TRIBUNAL)
        self.assertEqual(andamento.tipo, TipoAndamento.DECISAO)
        self.assertIn("Deferido o processamento", andamento.titulo)
        self.assertFalse(andamento.visivel_cliente)

    def test_nao_duplica_ao_sincronizar_de_novo(self):
        sincronizar_processo(self.processo, client=ClienteFalso(self._dados()))
        registro = sincronizar_processo(self.processo, client=ClienteFalso(self._dados()))
        self.assertEqual(registro.andamentos_criados, 0)
        self.assertEqual(Andamento.objects.count(), 2)

    def test_importa_apenas_o_movimento_novo(self):
        sincronizar_processo(self.processo, client=ClienteFalso(self._dados()))
        novos = self.movimentos + [
            {"codigo": 60, "nome": "Peticao juntada", "dataHora": "2025-04-01T10:00:00.000Z"}
        ]
        registro = sincronizar_processo(self.processo, client=ClienteFalso(self._dados(novos)))
        self.assertEqual(registro.andamentos_criados, 1)
        self.assertEqual(Andamento.objects.count(), 3)

    def test_preenche_apenas_campos_vazios(self):
        self.processo.vara = "Vara informada pela equipe"
        self.processo.save()
        sincronizar_processo(self.processo, client=ClienteFalso(self._dados()))
        self.processo.refresh_from_db()
        self.assertEqual(self.processo.vara, "Vara informada pela equipe")
        self.assertEqual(str(self.processo.data_distribuicao), "2025-03-10")

    def test_data_do_movimento_nao_desloca_para_o_dia_anterior(self):
        movimentos = [{"codigo": 26, "nome": "Distribuicao", "dataHora": "2025-03-10T00:00:00.000Z"}]
        sincronizar_processo(self.processo, client=ClienteFalso(self._dados(movimentos)))
        self.assertEqual(str(Andamento.objects.get().data), "2025-03-10")

    def test_processo_nao_encontrado(self):
        registro = sincronizar_processo(self.processo, client=ClienteFalso(None))
        self.assertEqual(registro.status, StatusSincronizacao.SEM_RESULTADO)
        self.assertEqual(Andamento.objects.count(), 0)

    def test_erro_da_api_registra_log_sem_quebrar(self):
        with self.assertLogs("apps.integracoes.services", level="WARNING"):
            registro = sincronizar_processo(
                self.processo, client=ClienteFalso(erro=DataJudError("timeout"))
            )
        self.assertEqual(registro.status, StatusSincronizacao.ERRO)
        self.assertIn("timeout", registro.mensagem)
        self.assertEqual(Andamento.objects.count(), 0)

    @override_settings(DATAJUD_ANDAMENTOS_VISIVEIS_CLIENTE=True)
    def test_visibilidade_configuravel(self):
        sincronizar_processo(self.processo, client=ClienteFalso(self._dados()))
        self.assertTrue(Andamento.objects.first().visivel_cliente)

    @override_settings(DATAJUD_ANDAMENTOS_VISIVEIS_CLIENTE=True)
    def test_processo_sigiloso_nunca_vai_para_o_portal(self):
        dados = self._dados(nivel_sigilo=1)
        registro = sincronizar_processo(self.processo, client=ClienteFalso(dados))
        self.assertFalse(Andamento.objects.filter(visivel_cliente=True).exists())
        self.assertIn("sigilo", registro.mensagem)

    def test_guarda_a_ultima_atualizacao_do_tribunal(self):
        registro = sincronizar_processo(self.processo, client=ClienteFalso(self._dados()))
        self.assertEqual(registro.atualizado_no_tribunal_em, "2025-04-02T19:10:08.483Z")

    def test_complemento_tecnico_nao_entra_no_titulo(self):
        movimentos = [
            {
                "codigo": 26,
                "nome": "Distribuicao",
                "dataHora": "2025-03-10T09:00:00.000Z",
                "complementosTabelados": [
                    {"codigo": 2, "valor": 1, "nome": "competencia exclusiva",
                     "descricao": "tipo_de_distribuicao_redistribuicao"}
                ],
            }
        ]
        sincronizar_processo(self.processo, client=ClienteFalso(self._dados(movimentos)))
        titulo = Andamento.objects.get().titulo
        self.assertIn("competencia exclusiva", titulo)
        self.assertNotIn("tipo_de_distribuicao", titulo)

    def test_classificacao_dos_movimentos(self):
        self.assertEqual(classificar_movimento("Sentenca publicada"), TipoAndamento.SENTENCA)
        self.assertEqual(classificar_movimento("Audiencia designada"), TipoAndamento.AUDIENCIA)
        self.assertEqual(classificar_movimento("Ato ordinatorio"), TipoAndamento.MOVIMENTACAO)


class BotaoSincronizarTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("interno", password="senha123")
        empresa = Empresa.objects.create(razao_social="Empresa Teste Ltda", cnpj="04.252.011/0001-10")
        self.processo = ProcessoRJ.objects.create(
            empresa=empresa, numero_cnj="1002345-12.2025.8.26.0114", tribunal="TJSP"
        )
        self.client.force_login(self.user)

    def test_post_dispara_sincronizacao(self):
        with patch("apps.processos.views.sincronizar_processo") as falso:
            falso.return_value = SincronizacaoDataJud(
                processo=self.processo, status=StatusSincronizacao.SUCESSO, mensagem="2 andamentos"
            )
            resposta = self.client.post(reverse("processos:sincronizar", args=[self.processo.pk]))
        self.assertRedirects(resposta, self.processo.get_absolute_url())
        falso.assert_called_once()
