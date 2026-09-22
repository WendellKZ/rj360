from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.crm.models import Estagio, Lead
from apps.empresas.models import Empresa, SituacaoEmpresa

User = get_user_model()


class ConversaoLeadTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("interno", password="senha123")
        self.lead = Lead.objects.create(
            razao_social="Padaria Central Ltda",
            cnpj="19.131.243/0001-97",
            cidade="Campinas",
            uf="SP",
            contato_nome="Maria",
            contato_email="maria@exemplo.com.br",
            responsavel=self.user,
        )

    def test_converter_cria_empresa_cliente_e_contato(self):
        empresa = self.lead.converter_em_empresa()
        self.assertIsInstance(empresa, Empresa)
        self.assertEqual(empresa.situacao, SituacaoEmpresa.CLIENTE)
        self.assertEqual(empresa.contatos.count(), 1)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.estagio, Estagio.GANHO)
        self.assertEqual(self.lead.empresa_id, empresa.pk)

    def test_converter_e_idempotente(self):
        primeira = self.lead.converter_em_empresa()
        segunda = self.lead.converter_em_empresa()
        self.assertEqual(primeira.pk, segunda.pk)
        self.assertEqual(Empresa.objects.count(), 1)

    def test_mover_estagio_pela_view(self):
        self.client.force_login(self.user)
        url = reverse("crm:mover", args=[self.lead.pk])
        self.client.post(url, {"estagio": Estagio.NEGOCIACAO})
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.estagio, Estagio.NEGOCIACAO)
