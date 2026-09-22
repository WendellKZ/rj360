"""Sincroniza os andamentos dos processos com a API publica do DataJud.

Exemplos:
    python manage.py sync_datajud                 # todos os processos em curso
    python manage.py sync_datajud --processo 12
    python manage.py sync_datajud --numero 1002345-12.2025.8.26.0114
    python manage.py sync_datajud --todos         # inclui processos encerrados
"""
import time

from django.core.management.base import BaseCommand, CommandError

from apps.integracoes.datajud import DataJudClient, DataJudNaoConfigurado
from apps.integracoes.models import StatusSincronizacao
from apps.integracoes.services import sincronizar_processo
from apps.processos.models import ProcessoRJ


class Command(BaseCommand):
    help = "Importa as movimentacoes dos processos a partir da API publica do DataJud."

    def add_arguments(self, parser):
        parser.add_argument("--processo", type=int, help="ID de um processo especifico.")
        parser.add_argument("--numero", type=str, help="Numero CNJ de um processo especifico.")
        parser.add_argument(
            "--todos", action="store_true", help="Inclui tambem os processos encerrados."
        )
        parser.add_argument(
            "--intervalo", type=float, default=1.0,
            help="Pausa em segundos entre as consultas (padrao: 1).",
        )

    def handle(self, *args, **options):
        client = DataJudClient()
        if not client.configurado:
            raise CommandError(
                "DATAJUD_API_KEY nao configurada. Defina a chave no .env "
                "(https://datajud-wiki.cnj.jus.br/api-publica/acesso/)."
            )

        processos = ProcessoRJ.objects.select_related("empresa")
        if options["processo"]:
            processos = processos.filter(pk=options["processo"])
        elif options["numero"]:
            processos = processos.filter(numero_cnj=options["numero"])
        elif not options["todos"]:
            processos = processos.filter(encerrado_em__isnull=True)

        total = processos.count()
        if not total:
            self.stdout.write(self.style.WARNING("Nenhum processo para sincronizar."))
            return

        self.stdout.write(f"Sincronizando {total} processo(s)...")
        resumo = {"ok": 0, "vazio": 0, "erro": 0, "novos": 0}

        for indice, processo in enumerate(processos, start=1):
            try:
                registro = sincronizar_processo(processo, client=client)
            except DataJudNaoConfigurado as erro:
                raise CommandError(str(erro)) from erro

            if registro.status == StatusSincronizacao.SUCESSO:
                resumo["ok"] += 1
                resumo["novos"] += registro.andamentos_criados
                estilo = self.style.SUCCESS
            elif registro.status == StatusSincronizacao.SEM_RESULTADO:
                resumo["vazio"] += 1
                estilo = self.style.WARNING
            else:
                resumo["erro"] += 1
                estilo = self.style.ERROR

            self.stdout.write(
                estilo(f"[{indice}/{total}] {processo.numero_formatado} - {registro.mensagem}")
            )
            if indice < total and options["intervalo"]:
                time.sleep(options["intervalo"])

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Concluido: {resumo['ok']} sincronizado(s), {resumo['novos']} andamento(s) novo(s), "
                f"{resumo['vazio']} sem resultado, {resumo['erro']} com erro."
            )
        )
