from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.empresas.models import Empresa
from apps.notificacoes.models import AvisoPrazo
from apps.notificacoes.services import enviar_alertas, montar_resumos
from apps.processos.models import Prazo, ProcessoRJ, StatusPrazo

User = get_user_model()

SUPERVISAO = ["supervisao@exemplo.com.br"]


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    NOTIFICACOES_SUPERVISAO=SUPERVISAO,
    PRAZO_ALERTA_DIAS=15,
    SITE_URL="https://rj360.exemplo.com.br",
)
class AlertaPrazosTest(TestCase):
    def setUp(self):
        self.hoje = timezone.localdate()
        self.ana = User.objects.create_user(
            "ana", email="ana@exemplo.com.br", password="x", first_name="Ana"
        )
        self.bruno = User.objects.create_user(
            "bruno", email="bruno@exemplo.com.br", password="x", first_name="Bruno"
        )
        empresa = Empresa.objects.create(
            razao_social="Empresa Teste Ltda", cnpj="04.252.011/0001-10"
        )
        self.processo = ProcessoRJ.objects.create(
            empresa=empresa, numero_cnj="1002345-12.2025.8.26.0114"
        )

    def _prazo(self, titulo, dias, responsavel=None, status=StatusPrazo.PENDENTE):
        return Prazo.objects.create(
            processo=self.processo,
            titulo=titulo,
            data_fim=self.hoje + timedelta(days=dias),
            responsavel=responsavel,
            status=status,
        )

    def test_agrupa_por_responsavel(self):
        self._prazo("Plano", 5, self.ana)
        self._prazo("Objecoes", -2, self.ana)
        self._prazo("Relatorio", 0, self.bruno)

        enviados = enviar_alertas()

        self.assertEqual(len(enviados), 2)
        self.assertEqual(len(mail.outbox), 2)
        por_email = {resumo.email: resumo for resumo in enviados}
        self.assertEqual(por_email["ana@exemplo.com.br"].total, 2)
        self.assertEqual(len(por_email["ana@exemplo.com.br"].atrasados), 1)
        self.assertEqual(len(por_email["bruno@exemplo.com.br"].vencem_hoje), 1)

    def test_prazo_sem_responsavel_vai_para_supervisao(self):
        self._prazo("Sem dono", 3)
        enviados = enviar_alertas()
        self.assertEqual([r.email for r in enviados], SUPERVISAO)

    def test_responsavel_sem_email_cai_para_supervisao(self):
        sem_email = User.objects.create_user("sem", password="x")
        self._prazo("Orfao", 3, sem_email)
        enviados = enviar_alertas()
        self.assertEqual([r.email for r in enviados], SUPERVISAO)

    def test_ignora_prazo_cumprido_e_fora_da_janela(self):
        self._prazo("Cumprido", 2, self.ana, status=StatusPrazo.CUMPRIDO)
        self._prazo("Distante", 90, self.ana)
        self.assertEqual(montar_resumos(), [])
        self.assertEqual(enviar_alertas(), [])
        self.assertEqual(len(mail.outbox), 0)

    def test_nao_repete_aviso_no_mesmo_dia(self):
        self._prazo("Plano", 5, self.ana)
        enviar_alertas()
        mail.outbox.clear()

        enviar_alertas()
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(AvisoPrazo.objects.count(), 1)

    def test_prazo_novo_no_mesmo_dia_e_avisado(self):
        self._prazo("Plano", 5, self.ana)
        enviar_alertas()
        mail.outbox.clear()

        self._prazo("Peticao urgente", 1, self.ana)
        enviados = enviar_alertas()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(enviados[0].total, 1)
        self.assertEqual(enviados[0].prazos[0].titulo, "Peticao urgente")

    def test_avisa_de_novo_no_dia_seguinte(self):
        self._prazo("Plano", 5, self.ana)
        enviar_alertas()
        mail.outbox.clear()

        enviar_alertas(hoje=self.hoje + timedelta(days=1))
        self.assertEqual(len(mail.outbox), 1)

    def test_conteudo_do_email(self):
        self._prazo("Apresentar o plano", 3, self.ana)
        enviar_alertas()

        mensagem = mail.outbox[0]
        self.assertIn("Prazos", mensagem.subject)
        self.assertIn("Apresentar o plano", mensagem.body)
        self.assertIn("Empresa Teste Ltda", mensagem.body)
        self.assertIn("https://rj360.exemplo.com.br/processos/", mensagem.body)
        corpo_html = mensagem.alternatives[0][0]
        self.assertIn("Apresentar o plano", corpo_html)
        self.assertEqual(mensagem.to, ["ana@exemplo.com.br"])

    def test_simulacao_nao_envia_nem_registra(self):
        self._prazo("Plano", 5, self.ana)
        enviados = enviar_alertas(simular=True)
        self.assertEqual(len(enviados), 1)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(AvisoPrazo.objects.count(), 0)

    def test_redireciona_para_endereco_de_teste(self):
        self._prazo("Plano", 5, self.ana)
        enviar_alertas(para="teste@exemplo.com.br")
        self.assertEqual(mail.outbox[0].to, ["teste@exemplo.com.br"])
        # o registro guarda o destinatario real, nao o redirecionado
        self.assertEqual(AvisoPrazo.objects.get().destinatario, "ana@exemplo.com.br")

    def test_janela_personalizada(self):
        self._prazo("Distante", 40, self.ana)
        self.assertEqual(enviar_alertas(), [])
        self.assertEqual(len(enviar_alertas(dias=60)), 1)

    def test_comando_simular(self):
        self._prazo("Plano", 5, self.ana)
        saida = StringIO()
        call_command("alertar_prazos", "--simular", stdout=saida)
        texto = saida.getvalue()
        self.assertIn("ana@exemplo.com.br", texto)
        self.assertIn("Modo simulacao", texto)
        self.assertEqual(len(mail.outbox), 0)

    def test_comando_sem_prazos(self):
        saida = StringIO()
        call_command("alertar_prazos", stdout=saida)
        self.assertIn("Nenhum prazo a comunicar", saida.getvalue())
