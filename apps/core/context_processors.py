from django.conf import settings
from django.utils import timezone


def branding(request):
    """Nome do sistema e contadores que a barra lateral mostra."""
    contexto = {
        "APP_NOME": "RJ360",
        "APP_DESCRICAO": "Gestao e acompanhamento de recuperacao judicial",
        "DEBUG": settings.DEBUG,
    }
    usuario = getattr(request, "user", None)
    if usuario is not None and usuario.is_authenticated and getattr(usuario, "is_interno", False):
        from apps.crm.models import Estagio, Lead
        from apps.processos.models import Prazo, StatusPrazo
        from apps.publico.models import Diagnostico

        hoje = timezone.localdate()
        contexto["prazos_atrasados"] = Prazo.objects.filter(
            status=StatusPrazo.PENDENTE, data_fim__lt=hoje
        ).count()
        contexto["leads_atrasados_total"] = (
            Lead.objects.exclude(estagio__in=[Estagio.GANHO, Estagio.PERDIDO])
            .filter(proximo_contato__lt=hoje)
            .count()
        )
    return contexto
