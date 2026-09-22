from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.crm.models import Estagio, Lead, Urgencia as UrgenciaLead
from apps.publico.conteudo import PERGUNTAS_QUIZ, TOTAL_PERGUNTAS
from apps.publico.models import Diagnostico, Urgencia

User = get_user_model()


def indice_da_opcao(pergunta_idx, rotulo):
    opcoes = PERGUNTAS_QUIZ[pergunta_idx]["opcoes"]
    for indice, (texto, _) in enumerate(opcoes):
        if texto == rotulo:
            return indice
    raise AssertionError(f"opcao {rotulo!r} nao existe na pergunta {pergunta_idx}")


class PaginasPublicasTest(TestCase):
    def test_visitante_ve_o_site_na_raiz(self):
        resposta = self.client.get("/", follow=True)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Sua empresa tem saída")

    def test_jornada_lista_as_seis_etapas(self):
        resposta = self.client.get(reverse("publico:jornada"))
        self.assertContains(resposta, "D+0")
        self.assertContains(resposta, "D+180")
        self.assertContains(resposta, "Novo fôlego")

    def test_equipe_interna_continua_indo_para_o_painel(self):
        User.objects.create_user("interno", password="x")
        self.client.login(username="interno", password="x")
        self.assertRedirects(self.client.get("/"), reverse("core:dashboard"))


class QuizTest(TestCase):
    def responder(self, rotulos):
        """Responde o quiz em sequencia e devolve a ultima resposta HTTP."""
        resposta = self.client.get(reverse("publico:quiz"), {"reiniciar": 1})
        for indice, rotulo in enumerate(rotulos):
            resposta = self.client.post(
                reverse("publico:quiz"), {"opcao": indice_da_opcao(indice, rotulo)}, follow=True
            )
        return resposta

    def test_caso_grave_vira_urgencia_alta(self):
        self.responder([
            "Mista (empresa + aval pessoal)",   # 1
            "Acima de R$ 500 mil",              # 3
            "Acima de R$ 3 milhões",            # 4
            "Bancos",                           # 2
            "Execução judicial",                # 3
            "Sim",                              # 2
            "Sim, sem sucesso",                 # 2  -> 17
        ])
        diagnostico = Diagnostico.objects.get()
        self.assertEqual(diagnostico.pontuacao, 17)
        self.assertEqual(diagnostico.urgencia, Urgencia.ALTA)

    def test_caso_intermediario_vira_urgencia_media(self):
        self.responder([
            "Sim, só CNPJ",                     # 0
            "R$ 100 mil a R$ 300 mil",          # 2
            "R$ 300 mil a R$ 1 milhão",         # 2
            "Fornecedores",                     # 1
            "Protesto / Serasa",                # 2
            "Não",                              # 0
            "Ainda não",                        # 0  -> 7
        ])
        diagnostico = Diagnostico.objects.get()
        self.assertEqual(diagnostico.pontuacao, 7)
        self.assertEqual(diagnostico.urgencia, Urgencia.MEDIA)

    def test_caso_leve_vira_urgencia_baixa(self):
        self.responder([
            "Sim, só CNPJ",                     # 0
            "Até R$ 100 mil",                   # 1
            "Até R$ 300 mil",                   # 1
            "Fornecedores",                     # 1
            "Apertando, mas controlando",       # 1
            "Não",                              # 0
            "Ainda não",                        # 0  -> 4
        ])
        self.assertEqual(Diagnostico.objects.get().urgencia, Urgencia.BAIXA)

    def test_divida_so_pessoal_encerra_sem_registro(self):
        self.client.get(reverse("publico:quiz"), {"reiniciar": 1})
        resposta = self.client.post(reverse("publico:quiz"), {"opcao": indice_da_opcao(0, "Não, só pessoal (PF)")})
        self.assertContains(resposta, "dívidas de empresas")
        self.assertEqual(Diagnostico.objects.count(), 0)

    def test_voltar_apaga_a_ultima_resposta(self):
        self.client.get(reverse("publico:quiz"), {"reiniciar": 1})
        self.client.post(reverse("publico:quiz"), {"opcao": 0})
        self.client.post(reverse("publico:quiz"), {"opcao": 0})
        self.client.post(reverse("publico:quiz_voltar"))
        resposta = self.client.get(reverse("publico:quiz"))
        self.assertContains(resposta, "Pergunta 2 de 7")

    def test_opcao_invalida_nao_avanca(self):
        self.client.get(reverse("publico:quiz"), {"reiniciar": 1})
        resposta = self.client.post(reverse("publico:quiz"), {"opcao": "99"})
        self.assertContains(resposta, "Escolha uma das opcoes")

    def test_resultado_mostra_prazo_e_aceita_contato(self):
        self.responder(["Sim, só CNPJ", "Até R$ 100 mil", "Até R$ 300 mil", "Fornecedores",
                        "Apertando, mas controlando", "Não", "Ainda não"])
        diagnostico = Diagnostico.objects.get()
        url = reverse("publico:resultado", args=[diagnostico.token])
        self.assertContains(self.client.get(url), "1 dia útil")

        self.client.post(url, {"nome": "Wendell", "empresa": "Padaria Central",
                               "telefone": "(19) 99999-0000", "email": ""}, follow=True)
        diagnostico.refresh_from_db()
        self.assertEqual(diagnostico.empresa, "Padaria Central")

    def test_contato_exige_telefone_ou_email(self):
        self.responder(["Sim, só CNPJ", "Até R$ 100 mil", "Até R$ 300 mil", "Fornecedores",
                        "Apertando, mas controlando", "Não", "Ainda não"])
        diagnostico = Diagnostico.objects.get()
        resposta = self.client.post(
            reverse("publico:resultado", args=[diagnostico.token]),
            {"nome": "Wendell", "empresa": "Padaria", "telefone": "", "email": ""},
        )
        self.assertContains(resposta, "ao menos um telefone")

    def test_quantidade_de_perguntas(self):
        self.assertEqual(TOTAL_PERGUNTAS, 7)


class SlaTest(TestCase):
    def test_prazo_por_urgencia(self):
        self.assertEqual(Urgencia.prazo_legivel(Urgencia.ALTA), "30 minutos")
        self.assertEqual(Urgencia.prazo_legivel(Urgencia.MEDIA), "4 horas")
        self.assertEqual(Urgencia.prazo_legivel(Urgencia.BAIXA), "1 dia útil")

    def test_sla_estoura_quando_passa_do_prazo(self):
        from datetime import timedelta

        from django.utils import timezone

        diagnostico = Diagnostico.objects.create(urgencia=Urgencia.ALTA, pontuacao=12)
        Diagnostico.objects.filter(pk=diagnostico.pk).update(
            criado_em=timezone.now() - timedelta(hours=2)
        )
        diagnostico.refresh_from_db()
        self.assertTrue(diagnostico.sla_estourado)
        self.assertIn("estourado", diagnostico.resumo_sla)

    def test_sla_nao_estoura_depois_do_contato(self):
        from datetime import timedelta

        from django.utils import timezone

        diagnostico = Diagnostico.objects.create(
            urgencia=Urgencia.ALTA, pontuacao=12, atendido_em=timezone.now()
        )
        Diagnostico.objects.filter(pk=diagnostico.pk).update(
            criado_em=timezone.now() - timedelta(hours=2)
        )
        diagnostico.refresh_from_db()
        self.assertFalse(diagnostico.sla_estourado)


class ConversaoEmLeadTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("interno", password="x")
        self.client.force_login(self.user)
        self.diagnostico = Diagnostico.objects.create(
            nome="Maria", empresa="Padaria Central Ltda", telefone="(19) 99999-0000",
            pontuacao=12, urgencia=Urgencia.ALTA,
            respostas=[{"chave": "situacao", "pergunta": "Qual a situação atual?",
                        "resposta": "Execução judicial", "pontos": 3}],
        )

    def test_cria_lead_com_urgencia_e_historico(self):
        self.client.post(reverse("crm:diagnostico_lead", args=[self.diagnostico.pk]))

        lead = Lead.objects.get()
        self.assertEqual(lead.razao_social, "Padaria Central Ltda")
        self.assertEqual(lead.urgencia, UrgenciaLead.ALTA)
        self.assertEqual(lead.estagio, Estagio.NOVO)
        self.assertEqual(lead.responsavel, self.user)
        self.assertEqual(lead.atividades.count(), 1)

        self.diagnostico.refresh_from_db()
        self.assertEqual(self.diagnostico.lead_id, lead.pk)
        self.assertIsNotNone(self.diagnostico.atendido_em)

    def test_nao_cria_lead_duas_vezes(self):
        self.client.post(reverse("crm:diagnostico_lead", args=[self.diagnostico.pk]))
        self.client.post(reverse("crm:diagnostico_lead", args=[self.diagnostico.pk]))
        self.assertEqual(Lead.objects.count(), 1)

    def test_marcar_contato_sem_criar_lead(self):
        self.client.post(reverse("crm:diagnostico_contato", args=[self.diagnostico.pk]))
        self.diagnostico.refresh_from_db()
        self.assertIsNotNone(self.diagnostico.atendido_em)
        self.assertEqual(Lead.objects.count(), 0)

    def test_tela_lista_os_abertos(self):
        resposta = self.client.get(reverse("crm:diagnosticos"))
        self.assertContains(resposta, "Padaria Central")
        self.assertContains(resposta, "Urgência alta")

    def test_visitante_nao_acessa_a_tela(self):
        self.client.logout()
        resposta = self.client.get(reverse("crm:diagnosticos"))
        self.assertEqual(resposta.status_code, 302)
