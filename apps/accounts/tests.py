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
