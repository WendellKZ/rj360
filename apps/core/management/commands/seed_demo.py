"""Popula o banco com dados ficticios para demonstracao e testes manuais."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import TipoUsuario
from apps.crm.models import Estagio, Lead, OrigemLead, SituacaoJuridica, TipoAtividade
from apps.empresas.models import Empresa, Porte, SituacaoEmpresa
from apps.processos.models import (
    Andamento,
    ClasseCredor,
    Credor,
    FaseProcesso,
    ProcessoRJ,
    TipoAndamento,
)
from apps.processos.services import gerar_prazos_legais

User = get_user_model()


class Command(BaseCommand):
    help = "Cria dados de demonstracao (usuarios, empresa, processo e leads)."

    def add_arguments(self, parser):
        parser.add_argument("--senha", default="rj360demo", help="Senha dos usuarios criados.")

    def handle(self, *args, **options):
        senha = options["senha"]
        hoje = timezone.localdate()

        analista, criado = User.objects.get_or_create(
            username="analista",
            defaults={
                "first_name": "Ana",
                "last_name": "Consultora",
                "email": "analista@exemplo.com.br",
                "tipo": TipoUsuario.INTERNO,
                "is_staff": True,
            },
        )
        if criado:
            analista.set_password(senha)
            analista.save()

        empresa, _ = Empresa.objects.get_or_create(
            cnpj="04.252.011/0001-10",
            defaults={
                "razao_social": "Metalurgica Exemplo Industria e Comercio Ltda",
                "nome_fantasia": "Metalurgica Exemplo",
                "porte": Porte.EPP,
                "atividade": "Fabricacao de estruturas metalicas",
                "situacao": SituacaoEmpresa.CLIENTE,
                "cidade": "Campinas",
                "uf": "SP",
                "telefone": "(19) 3333-0000",
                "email": "contato@exemplo.com.br",
                "responsavel": analista,
                "inicio_contrato": hoje - timedelta(days=200),
            },
        )

        cliente, criado = User.objects.get_or_create(
            username="cliente",
            defaults={
                "first_name": "Carlos",
                "last_name": "Diretor",
                "email": "diretor@exemplo.com.br",
                "tipo": TipoUsuario.CLIENTE,
                "empresa": empresa,
            },
        )
        if criado:
            cliente.set_password(senha)
            cliente.save()

        processo, _ = ProcessoRJ.objects.get_or_create(
            numero_cnj="1002345-12.2025.8.26.0114",
            defaults={
                "empresa": empresa,
                "tribunal": "TJSP",
                "comarca": "Campinas",
                "vara": "2a Vara de Falencias e Recuperacoes Judiciais",
                "juiz": "Dr. Exemplo de Souza",
                "administrador_judicial": "Exemplo Administracao Judicial Ltda",
                "aj_email": "aj@exemplo.com.br",
                "advogado": "Escritorio Exemplo Advogados",
                "fase": FaseProcesso.EDITAL,
                "data_distribuicao": hoje - timedelta(days=150),
                "data_deferimento": hoje - timedelta(days=140),
                "data_edital_52": hoje - timedelta(days=120),
                "data_plano": hoje - timedelta(days=80),
                "data_edital_53": hoje - timedelta(days=70),
                "valor_divida": Decimal("4850000.00"),
            },
        )
        gerar_prazos_legais(processo, responsavel=analista)

        if not processo.andamentos.exists():
            Andamento.objects.bulk_create(
                [
                    Andamento(
                        processo=processo,
                        data=hoje - timedelta(days=140),
                        tipo=TipoAndamento.DECISAO,
                        titulo="Deferido o processamento da recuperacao judicial",
                        descricao="Nomeado administrador judicial e determinada a publicacao do edital.",
                        registrado_por=analista,
                    ),
                    Andamento(
                        processo=processo,
                        data=hoje - timedelta(days=80),
                        tipo=TipoAndamento.PETICAO,
                        titulo="Plano de recuperacao judicial apresentado",
                        descricao="Plano protocolado dentro do prazo do art. 53.",
                        registrado_por=analista,
                    ),
                    Andamento(
                        processo=processo,
                        data=hoje - timedelta(days=20),
                        tipo=TipoAndamento.RELATORIO_AJ,
                        titulo="Relatorio mensal de atividades juntado",
                        registrado_por=analista,
                    ),
                ]
            )

        if not processo.credores.exists():
            Credor.objects.bulk_create(
                [
                    Credor(processo=processo, nome="Sindicato dos Metalurgicos", classe=ClasseCredor.I,
                           valor_arrolado=Decimal("320000.00")),
                    Credor(processo=processo, nome="Banco Exemplo S.A.", classe=ClasseCredor.II,
                           valor_arrolado=Decimal("1850000.00")),
                    Credor(processo=processo, nome="Fornecedora Alfa Ltda", classe=ClasseCredor.III,
                           valor_arrolado=Decimal("1230000.00")),
                    Credor(processo=processo, nome="Transportes Beta ME", classe=ClasseCredor.IV,
                           valor_arrolado=Decimal("145000.00")),
                ]
            )

        leads = [
            ("Padaria Central Ltda", Estagio.NOVO, SituacaoJuridica.PRE_CRISE, "Piracicaba"),
            ("Confeccoes Horizonte ME", Estagio.CONTATO, SituacaoJuridica.EXTRAJUDICIAL, "Americana"),
            ("Transportadora Rota Sul", Estagio.DIAGNOSTICO, SituacaoJuridica.RJ_EM_CURSO, "Sorocaba"),
            ("Supermercado Bom Preco", Estagio.PROPOSTA, SituacaoJuridica.PRE_CRISE, "Limeira"),
        ]
        for nome, estagio, situacao, cidade in leads:
            lead, criado = Lead.objects.get_or_create(
                razao_social=nome,
                defaults={
                    "estagio": estagio,
                    "situacao_juridica": situacao,
                    "cidade": cidade,
                    "uf": "SP",
                    "origem": OrigemLead.ATIVA,
                    "responsavel": analista,
                    "valor_estimado": Decimal("18000.00"),
                    "proximo_contato": hoje + timedelta(days=3),
                    "contato_nome": "Responsavel financeiro",
                },
            )
            if criado:
                lead.atividades.create(
                    tipo=TipoAtividade.LIGACAO,
                    titulo="Primeiro contato realizado",
                    descricao="Apresentacao do servico de acompanhamento de RJ.",
                    autor=analista,
                )

        self.stdout.write(self.style.SUCCESS("Dados de demonstracao criados."))
        self.stdout.write(f"  usuario interno: analista / {senha}")
        self.stdout.write(f"  usuario cliente: cliente / {senha}")
