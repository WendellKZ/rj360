from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import TipoUsuario
from apps.empresas.models import Empresa
from apps.processos.models import Andamento, ProcessoRJ

User = get_user_model()


class AcessoPortalTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            razao_social="Empresa A Ltda", cnpj="04.252.011/0001-10"
        )
        self.outra = Empresa.objects.create(
            razao_social="Empresa B Ltda", cnpj="19.131.243/0001-97"
        )
        self.cliente = User.objects.create_user(
            "cliente", password="senha123", tipo=TipoUsuario.CLIENTE, empresa=self.empresa
        )
        self.processo_outro = ProcessoRJ.objects.create(
            empresa=self.outra, numero_cnj="2002345-12.2025.8.26.0114"
        )

    def test_cliente_e_redirecionado_para_o_portal(self):
        self.client.force_login(self.cliente)
        resposta = self.client.get(reverse("core:home"))
        self.assertRedirects(resposta, reverse("portal:home"))

    def test_cliente_nao_acessa_painel_interno(self):
        self.client.force_login(self.cliente)
        self.assertEqual(self.client.get(reverse("core:dashboard")).status_code, 403)

    def test_cliente_nao_acessa_processo_de_outra_empresa(self):
        self.client.force_login(self.cliente)
        url = reverse("portal:processo", args=[self.processo_outro.pk])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_portal_esconde_andamento_interno(self):
        processo = ProcessoRJ.objects.create(
            empresa=self.empresa, numero_cnj="3002345-12.2025.8.26.0114"
        )
        Andamento.objects.create(
            processo=processo, titulo="Publico", visivel_cliente=True
        )
        Andamento.objects.create(
            processo=processo, titulo="Estrategia interna", visivel_cliente=False
        )
        self.client.force_login(self.cliente)
        resposta = self.client.get(reverse("portal:home"))
        self.assertContains(resposta, "Publico")
        self.assertNotContains(resposta, "Estrategia interna")

    def test_visitante_vai_para_login(self):
        resposta = self.client.get(reverse("core:dashboard"))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("accounts:login"), resposta.url)


class LoginPorCodigoTest(TestCase):
    def setUp(self):
        from apps.empresas.models import Empresa

        self.empresa = Empresa.objects.create(
            razao_social="Empresa A Ltda", cnpj="04.252.011/0001-10"
        )
        self.cliente = User.objects.create_user(
            "carlos", password="x", email="carlos@empresa.com.br", telefone="(19) 98888-7777",
            tipo=TipoUsuario.CLIENTE, empresa=self.empresa,
        )
        self.interno = User.objects.create_user("ana", password="x", email="ana@rj360.com.br")

    def _pedir(self, contato="carlos@empresa.com.br"):
        return self.client.post(reverse("accounts:codigo_pedir"), {"contato": contato})

    def _codigo_enviado(self):
        from django.core import mail

        assunto = mail.outbox[-1].subject
        return "".join(c for c in assunto if c.isdigit())

    def test_fluxo_completo_por_email(self):
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            self._pedir()
            codigo = self._codigo_enviado()
            self.assertEqual(len(codigo), 6)

            resposta = self.client.post(reverse("accounts:codigo_confirmar"), {"codigo": codigo})
        self.assertRedirects(resposta, reverse("portal:home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.cliente.pk)

    def test_funciona_com_o_celular(self):
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            self._pedir("19988887777")
            codigo = self._codigo_enviado()
            self.client.post(reverse("accounts:codigo_confirmar"), {"codigo": codigo})
        self.assertIn("_auth_user_id", self.client.session)

    def test_codigo_nunca_fica_em_claro_no_banco(self):
        from apps.accounts.codigos import CodigoAcesso

        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            self._pedir()
            codigo = self._codigo_enviado()
        registro = CodigoAcesso.objects.get()
        self.assertNotIn(codigo, registro.codigo_hash)
        self.assertTrue(registro.codigo_hash.startswith("pbkdf2"))

    def test_codigo_errado_gasta_tentativa_e_bloqueia(self):
        from apps.accounts.codigos import MAX_TENTATIVAS, CodigoAcesso

        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            self._pedir()
            for _ in range(MAX_TENTATIVAS):
                self.client.post(reverse("accounts:codigo_confirmar"), {"codigo": "000000"})
            resposta = self.client.post(reverse("accounts:codigo_confirmar"), {"codigo": "000000"})

        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(resposta, "Peca um novo")
        self.assertEqual(CodigoAcesso.objects.get().tentativas, MAX_TENTATIVAS)

    def test_codigo_expirado_nao_entra(self):
        from datetime import timedelta

        from django.utils import timezone

        from apps.accounts.codigos import CodigoAcesso

        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            self._pedir()
            codigo = self._codigo_enviado()
            CodigoAcesso.objects.update(expira_em=timezone.now() - timedelta(minutes=1))
            resposta = self.client.post(reverse("accounts:codigo_confirmar"), {"codigo": codigo})

        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(resposta, "expirou")

    def test_codigo_so_serve_uma_vez(self):
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            self._pedir()
            codigo = self._codigo_enviado()
            self.client.post(reverse("accounts:codigo_confirmar"), {"codigo": codigo})
            self.client.post(reverse("accounts:logout"))
            resposta = self.client.post(reverse("accounts:codigo_confirmar"), {"codigo": codigo})

        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(resposta, "Peça o código")

    def test_pedido_novo_invalida_o_anterior(self):
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            self._pedir()
            primeiro = self._codigo_enviado()
            self._pedir()
            resposta = self.client.post(reverse("accounts:codigo_confirmar"), {"codigo": primeiro})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_excesso_de_pedidos_e_barrado(self):
        from apps.accounts.codigos import MAX_PEDIDOS_POR_JANELA

        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            for _ in range(MAX_PEDIDOS_POR_JANELA):
                self._pedir()
            resposta = self._pedir()
        self.assertContains(resposta, "Muitos pedidos")

    def test_contato_desconhecido_nao_revela_nada(self):
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            from django.core import mail

            resposta = self._pedir("ninguem@exemplo.com")
            self.assertEqual(len(mail.outbox), 0)
        self.assertRedirects(resposta, reverse("accounts:codigo_confirmar"))

    def test_equipe_interna_nao_entra_por_codigo(self):
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            from django.core import mail

            self._pedir("ana@rj360.com.br")
            self.assertEqual(len(mail.outbox), 0)

    def test_confirmar_sem_pedir_nao_quebra(self):
        resposta = self.client.get(reverse("accounts:codigo_confirmar"))
        self.assertContains(resposta, "Peça o código")
