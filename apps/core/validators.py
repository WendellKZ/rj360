"""Validadores de documentos brasileiros."""
import re

from django.core.exceptions import ValidationError


def somente_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def validar_cnpj(valor: str) -> None:
    cnpj = somente_digitos(valor)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        raise ValidationError("CNPJ invalido.")

    def digito(base: str, pesos: list[int]) -> str:
        soma = sum(int(d) * p for d, p in zip(base, pesos))
        resto = soma % 11
        return "0" if resto < 2 else str(11 - resto)

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    if digito(cnpj[:12], pesos1) != cnpj[12] or digito(cnpj[:13], pesos2) != cnpj[13]:
        raise ValidationError("CNPJ invalido.")


def validar_numero_cnj(valor: str) -> None:
    """Formato NNNNNNN-DD.AAAA.J.TR.OOOO (20 digitos)."""
    numero = somente_digitos(valor)
    if len(numero) != 20:
        raise ValidationError(
            "Numero CNJ invalido: deve ter 20 digitos "
            "(NNNNNNN-DD.AAAA.J.TR.OOOO)."
        )


def formatar_cnpj(valor: str) -> str:
    cnpj = somente_digitos(valor)
    if len(cnpj) != 14:
        return valor or ""
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"


def formatar_numero_cnj(valor: str) -> str:
    numero = somente_digitos(valor)
    if len(numero) != 20:
        return valor or ""
    return (
        f"{numero[:7]}-{numero[7:9]}.{numero[9:13]}."
        f"{numero[13]}.{numero[14:16]}.{numero[16:]}"
    )
