from django.conf import settings


def branding(request):
    return {
        "APP_NOME": "RJ360",
        "APP_DESCRICAO": "Gestao e acompanhamento de recuperacao judicial",
        "DEBUG": settings.DEBUG,
    }
