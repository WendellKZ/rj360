from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import TipoUsuario
from apps.empresas.models import Empresa
from apps.processos.models import Credor, EstagioNegociacao, ProcessoRJ
from apps.relacionamento.models import (
    DocumentoSolicitado,
    Mensagem,
    Reuniao,
    StatusDocumento,
    StatusReuniao,
)

User = get_user_model()


class BasePortal(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(razao_social="Empresa A Ltda", cnpj="04.252.011/0001-10")
        self.outra = Empresa.objects.create(razao_social="Empresa B Ltda", cnpj="19.131.243/0001-97")
        self.processo = ProcessoRJ.objects.create(
            empresa=self.empresa, numero_cnj="1002345-12.2025.8.26.0114"
        )
        self.processo_outro = ProcessoRJ.objects.create(
            empresa=self.outra, numero_cnj="2002345-12.2025.8.26.0114"
        )
        self.cliente = User.objects.create_user(
            "cliente", password="x", tipo=TipoUsuario.CLIENTE, empresa=self.empresa
        )
        self.interno = User.objects.create_user("ana", password="x", first_name="Ana")


class DocumentosTest(BasePortal):
    def setUp(self):
        super().setUp()
        self.pedido = DocumentoSolicitado.objects.create(
            processo=self.processo, titulo="DAS dos últimos 3 meses",
            motivo="necessário para o parcelamento", prazo=timezone.localdate() + timedelta(days=3),
        )

    def test_cliente_ve_o_pedido_e_envia(self):
        self.client.force_login(self.cliente)
        resposta = self.client.get(reverse("portal:documentos"))
        self.assertContains(resposta, "DAS dos últimos 3 meses")

        arquivo = SimpleUploadedFile("das.pdf", b"%PDF-1.4 conteudo")
        self.client.post(reverse("portal:documento_enviar", args=[self.pedido.pk]), {"arquivo": arquivo})

        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, StatusDocumento.RECEBIDO)
        self.assertIsNotNone(self.pedido.enviado_em)
        self.assertTrue(self.pedido.arquivo)

    def test_cliente_nao_envia_para_processo_de_outra_empresa(self):
        pedido_alheio = DocumentoSolicitado.objects.create(
            processo=self.processo_outro, titulo="Balanço"
        )
        self.client.force_login(self.cliente)
        resposta = self.client.post(
            reverse("portal:documento_enviar", args=[pedido_alheio.pk]),
            {"arquivo": SimpleUploadedFile("x.pdf", b"x")},
        )
        self.assertEqual(resposta.status_code, 404)
        pedido_alheio.refresh_from_db()
        self.assertFalse(pedido_alheio.arquivo)

    def test_pendente_atrasado(self):
        self.pedido.prazo = timezone.localdate() - timedelta(days=1)
        self.assertTrue(self.pedido.atrasado)
        self.pedido.status = StatusDocumento.VALIDADO
        self.assertFalse(self.pedido.atrasado)

    def test_equipe_solicita_e_confere(self):
        self.client.force_login(self.interno)
        self.client.post(
            reverse("relacionamento:documento_solicitar", args=[self.processo.pk]),
            {"titulo": "Contrato social", "motivo": "conferência", "prazo": ""},
        )
        novo = DocumentoSolicitado.objects.get(titulo="Contrato social")
        self.assertEqual(novo.solicitado_por, self.interno)

        self.client.post(
            reverse("relacionamento:documento_conferir", args=[self.pedido.pk]),
            {"status": StatusDocumento.VALIDADO, "observacao_equipe": ""},
        )
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, StatusDocumento.VALIDADO)


class ConversaTest(BasePortal):
    def test_cliente_escreve_e_equipe_responde(self):
        self.client.force_login(self.cliente)
        self.client.post(reverse("portal:conversa"), {"texto": "Consigo enviar o DAS na quinta?"})
        mensagem = Mensagem.objects.get()
        self.assertEqual(mensagem.autor, self.cliente)
        self.assertFalse(mensagem.da_equipe)

        self.client.force_login(self.interno)
        self.client.post(
            reverse("relacionamento:responder", args=[self.processo.pk]), {"texto": "Pode ser!"}
        )
        resposta = Mensagem.objects.latest("id")
        self.assertTrue(resposta.da_equipe)
        self.assertEqual(Mensagem.objects.count(), 2)

    def test_mensagem_da_equipe_fica_lida_quando_o_cliente_abre(self):
        Mensagem.objects.create(processo=self.processo, autor=self.interno, texto="Oi")
        self.client.force_login(self.cliente)
        self.client.get(reverse("portal:conversa"))
        self.assertIsNotNone(Mensagem.objects.get().lida_em)

    def test_cliente_so_ve_a_propria_conversa(self):
        Mensagem.objects.create(processo=self.processo_outro, autor=self.interno, texto="Segredo")
        self.client.force_login(self.cliente)
        resposta = self.client.get(reverse("portal:conversa"))
        self.assertNotContains(resposta, "Segredo")


class ReunioesTest(BasePortal):
    def test_separa_proximas_de_anteriores(self):
        futura = Reuniao.objects.create(
            processo=self.processo, titulo="Alinhamento do plano",
            quando=timezone.now() + timedelta(days=3),
        )
        passada = Reuniao.objects.create(
            processo=self.processo, titulo="Kickoff", status=StatusReuniao.REALIZADA,
            quando=timezone.now() - timedelta(days=10), ata="Definimos a ordem dos credores.",
        )
        self.client.force_login(self.cliente)
        resposta = self.client.get(reverse("portal:reunioes"))
        self.assertEqual(list(resposta.context["proximas"]), [futura])
        self.assertEqual(list(resposta.context["anteriores"]), [passada])
        self.assertContains(resposta, "Definimos a ordem dos credores")

    def test_reuniao_interna_nao_aparece_no_portal(self):
        Reuniao.objects.create(
            processo=self.processo, titulo="Estratégia interna", visivel_cliente=False,
            quando=timezone.now() + timedelta(days=1),
        )
        self.client.force_login(self.cliente)
        self.assertNotContains(self.client.get(reverse("portal:reunioes")), "Estratégia interna")


class CredoresPortalTest(BasePortal):
    def setUp(self):
        super().setUp()
        self.credor = Credor.objects.create(
            processo=self.processo, nome="Banco Alpha", classe="II",
            valor_arrolado=480000, valor_negociado=346000,
            estagio_negociacao=EstagioNegociacao.ACORDO,
        )

    def test_mostra_economia_e_progresso(self):
        self.assertEqual(self.credor.economia, 134000)
        self.assertEqual(self.credor.progresso, 100)

        self.client.force_login(self.cliente)
        resposta = self.client.get(reverse("portal:credores"))
        self.assertContains(resposta, "Banco Alpha")
        self.assertEqual(resposta.context["economia_total"], 134000)
        self.assertEqual(resposta.context["com_acordo"], 1)

    def test_credor_restrito_nao_aparece(self):
        Credor.objects.create(
            processo=self.processo, nome="Credor sensível", classe="III",
            valor_arrolado=1000, visivel_cliente=False,
        )
        self.client.force_login(self.cliente)
        self.assertNotContains(self.client.get(reverse("portal:credores")), "Credor sensível")

    def test_equipe_registra_passo_da_negociacao(self):
        self.client.force_login(self.interno)
        self.client.post(
            reverse("relacionamento:credor_evento", args=[self.credor.pk]),
            {"descricao": "Proposta aceita pelo banco", "estagio_negociacao": "ACOR",
             "valor_negociado": "300.000,00"},
        )
        self.credor.refresh_from_db()
        self.assertEqual(self.credor.eventos.count(), 1)
        self.assertEqual(str(self.credor.valor_negociado), "300000.00")

    def test_evento_interno_nao_vai_para_o_portal(self):
        self.credor.eventos.create(descricao="Negociar por fora", visivel_cliente=False)
        self.credor.eventos.create(descricao="Proposta enviada")
        self.client.force_login(self.cliente)
        resposta = self.client.get(reverse("portal:credores"))
        self.assertContains(resposta, "Proposta enviada")
        self.assertNotContains(resposta, "Negociar por fora")


class PainelRelacionamentoTest(BasePortal):
    def test_pagina_interna_responde(self):
        self.client.force_login(self.interno)
        resposta = self.client.get(reverse("relacionamento:painel", args=[self.processo.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Relacionamento com o cliente")

    def test_cliente_nao_acessa_a_pagina_interna(self):
        self.client.force_login(self.cliente)
        resposta = self.client.get(reverse("relacionamento:painel", args=[self.processo.pk]))
        self.assertEqual(resposta.status_code, 403)


class NotificacoesPortalTest(BasePortal):
    def test_lista_pendencias_do_cliente(self):
        from apps.relacionamento.models import DocumentoSolicitado

        DocumentoSolicitado.objects.create(
            processo=self.processo, titulo="DAS", prazo=timezone.localdate() - timedelta(days=1)
        )
        Mensagem.objects.create(processo=self.processo, autor=self.interno, texto="Oi")
        Reuniao.objects.create(
            processo=self.processo, titulo="Alinhamento", quando=timezone.now() + timedelta(days=2)
        )

        self.client.force_login(self.cliente)
        resposta = self.client.get(reverse("portal:credores"))
        avisos = resposta.context["notificacoes"]
        textos = [aviso["texto"] for aviso in avisos]

        self.assertIn("Documento pendente: DAS", textos)
        self.assertTrue(any("mensagem" in texto for texto in textos))
        self.assertTrue(any("Alinhamento" in texto for texto in textos))
        self.assertTrue(avisos[0]["alerta"])  # o documento atrasado vem primeiro e sinalizado

    def test_sem_pendencias_nao_gera_aviso(self):
        self.client.force_login(self.cliente)
        resposta = self.client.get(reverse("portal:credores"))
        self.assertEqual(resposta.context["notificacoes"], [])

    def test_avisos_nao_vazam_de_outra_empresa(self):
        from apps.relacionamento.models import DocumentoSolicitado

        DocumentoSolicitado.objects.create(processo=self.processo_outro, titulo="Documento alheio")
        self.client.force_login(self.cliente)
        resposta = self.client.get(reverse("portal:credores"))
        self.assertEqual(resposta.context["notificacoes"], [])
