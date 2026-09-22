"""Envia por e-mail o resumo de prazos a vencer.

Exemplos:
    python manage.py alertar_prazos
    python manage.py alertar_prazos --dias 30
    python manage.py alertar_prazos --simular
    python manage.py alertar_prazos --para voce@empresa.com.br
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.notificacoes.services import enviar_alertas


class Command(BaseCommand):
    help = "Envia o resumo de prazos pendentes para os responsaveis."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias", type=int, default=None,
            help=f"Janela de antecedencia (padrao: {settings.PRAZO_ALERTA_DIAS}).",
        )
        parser.add_argument(
            "--simular", action="store_true",
            help="Mostra o que seria enviado, sem enviar e sem registrar.",
        )
        parser.add_argument(
            "--para", type=str, default=None,
            help="Redireciona todos os e-mails para um endereco (teste de SMTP).",
        )

    def handle(self, *args, **options):
        resumos = enviar_alertas(
            dias=options["dias"], simular=options["simular"], para=options["para"]
        )
        if not resumos:
            self.stdout.write(self.style.SUCCESS("Nenhum prazo a comunicar hoje."))
            return

        verbo = "Seria enviado" if options["simular"] else "Enviado"
        for resumo in resumos:
            self.stdout.write(
                f"{verbo} para {resumo.email}: {resumo.total} prazo(s) "
                f"({len(resumo.atrasados)} atrasado(s), "
                f"{len(resumo.vencem_hoje)} hoje, {len(resumo.proximos)} a vencer)"
            )
            if options["simular"]:
                for prazo in resumo.prazos:
                    self.stdout.write(
                        f"    - {prazo.data_fim:%d/%m/%Y} {prazo.titulo} "
                        f"({prazo.processo.empresa})"
                    )
        total = sum(resumo.total for resumo in resumos)
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"{len(resumos)} e-mail(s), {total} prazo(s)."
                + (" Modo simulacao: nada foi enviado." if options["simular"] else "")
            )
        )
