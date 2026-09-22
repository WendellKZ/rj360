from django import template

from apps.core.validators import formatar_cnpj, formatar_numero_cnj

register = template.Library()


@register.filter(name="cnpj")
def cnpj(valor):
    return formatar_cnpj(valor)


@register.filter(name="cnj")
def cnj(valor):
    return formatar_numero_cnj(valor)


@register.filter(name="moeda")
def moeda(valor):
    if valor in (None, ""):
        return "-"
    texto = f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


@register.filter(name="badge_cor")
def badge_cor(chave):
    """Classe da etiqueta a partir da familia de cor (verde, amarelo...)."""
    familias = {"verde", "amarelo", "vermelho", "azul", "cinza"}
    return f"etiqueta--{chave}" if chave in familias else "etiqueta--cinza"
