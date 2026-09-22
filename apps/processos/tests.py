from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.validators import formatar_cnpj, validar_cnpj, validar_numero_cnj
from apps.empresas.models import Empresa
from apps.processos.models import FaseProcesso, Prazo, ProcessoRJ, StatusPrazo
from apps.processos.services import gerar_prazos_legais

User = get_user_model()


class ValidadoresTest(TestCase):
    def test_cnpj_valido(self):
        validar_cnpj("04.252.011/0001-10")

    def test_cnpj_invalido(self):
        with self.assertRaises(ValidationError):
            validar_cnpj("11.111.111/1111-11")

    def test_formatacao_cnpj(self):
        self.assertEqual(formatar_cnpj("04252011000110"), "04.252.011/0001-10")

    def test_numero_cnj_precisa_de_20_digitos(self):
        validar_numero_cnj("1002345-12.2025.8.26.0114")
        with self.assertRaises(ValidationError):
            validar_numero_cnj("123456")


class PrazosLegaisTest(TestCase):
    def setUp(self):
        self.hoje = timezone.localdate()
        self.empresa = Empresa.objects.create(
            razao_social="Empresa Teste Ltda", cnpj="04.252.011/0001-10"
        )
        self.processo = ProcessoRJ.objects.create(
            empresa=self.empresa,
            numero_cnj="1002345-12.2025.8.26.0114",
            data_deferimento=self.hoje,
            fase=FaseProcesso.DEFERIDO,
        )

    def test_gera_prazo_do_plano_em_60_dias(self):
        gerar_prazos_legais(self.processo)
        prazo = Prazo.objects.get(processo=self.processo, titulo__icontains="plano")
        self.assertEqual(prazo.data_fim, self.hoje + timedelta(days=60))
        self.assertEqual(prazo.status, StatusPrazo.PENDENTE)

    def test_nao_duplica_prazos(self):
        gerar_prazos_legais(self.processo)
        total = Prazo.objects.count()
        gerar_prazos_legais(self.processo)
        self.assertEqual(Prazo.objects.count(), total)

    def test_stay_period_180_dias_e_360_quando_prorrogado(self):
        self.assertEqual(self.processo.stay_period_fim, self.hoje + timedelta(days=180))
        self.processo.stay_prorrogado = True
        self.assertEqual(self.processo.stay_period_fim, self.hoje + timedelta(days=360))

    def test_prazo_atrasado(self):
        prazo = Prazo.objects.create(
            processo=self.processo, titulo="Peticao", data_fim=self.hoje - timedelta(days=1)
        )
        self.assertTrue(prazo.atrasado)
        self.assertEqual(prazo.cor, "vermelho")


class PaginasInternasTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("interno", password="senha123")
        self.empresa = Empresa.objects.create(
            razao_social="Empresa Teste Ltda", cnpj="04.252.011/0001-10"
        )
        self.processo = ProcessoRJ.objects.create(
            empresa=self.empresa,
            numero_cnj="1002345-12.2025.8.26.0114",
            data_deferimento=timezone.localdate(),
        )
        gerar_prazos_legais(self.processo, responsavel=self.user)
        self.processo.credores.create(
            nome="Banco Exemplo", classe="II", valor_arrolado=1000
        )
        self.client.force_login(self.user)

    def test_paginas_respondem(self):
        urls = [
            reverse("core:dashboard"),
            reverse("empresas:lista"),
            reverse("empresas:detalhe", args=[self.empresa.pk]),
            reverse("processos:lista"),
            reverse("processos:detalhe", args=[self.processo.pk]),
            reverse("processos:agenda"),
            reverse("crm:funil"),
            reverse("crm:lista"),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_marcar_prazo_como_cumprido(self):
        prazo = Prazo.objects.create(
            processo=self.processo, titulo="Peticao", data_fim=timezone.localdate()
        )
        self.client.post(reverse("processos:prazo_concluir", args=[prazo.pk]))
        prazo.refresh_from_db()
        self.assertEqual(prazo.status, StatusPrazo.CUMPRIDO)
        self.assertIsNotNone(prazo.concluido_em)
