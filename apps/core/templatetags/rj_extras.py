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
    cores = {
        "verde": "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
        "amarelo": "bg-amber-50 text-amber-800 ring-amber-600/20",
        "vermelho": "bg-rose-50 text-rose-700 ring-rose-600/20",
        "azul": "bg-sky-50 text-sky-700 ring-sky-600/20",
        "cinza": "bg-slate-100 text-slate-700 ring-slate-500/20",
    }
    return cores.get(chave, cores["cinza"])
