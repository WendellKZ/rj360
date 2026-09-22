"""Entrada do portal por codigo de uso unico."""
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.shortcuts import redirect, render
from django.views.generic import View

from .codigos import MAX_TENTATIVAS, VALIDADE_MINUTOS, CodigoAcesso, criar_e_enviar
from .models import TipoUsuario

User = get_user_model()

SESSAO_USUARIO = "codigo_usuario_id"

# Mensagem unica: nao dizemos se o contato existe ou nao.
AVISO_ENVIO = (
    "Se esse contato estiver cadastrado, o codigo chega em instantes. "
    f"Ele vale por {VALIDADE_MINUTOS} minutos."
)


def _somente_digitos(valor: str) -> str:
    return "".join(c for c in valor if c.isdigit())


class PedirCodigoView(View):
    """Passo 1: o cliente informa o contato cadastrado."""

    template_name = "accounts/codigo_pedir.html"

    def get(self, request):
        return render(request, self.template_name, {})

    def post(self, request):
        contato = (request.POST.get("contato") or "").strip()
        if not contato:
            return render(request, self.template_name, {"erro": "Informe seu e-mail ou celular."})

        usuario = self._encontrar(contato)
        if usuario:
            registro = criar_e_enviar(usuario)
            if registro is None:
                return render(request, self.template_name, {
                    "erro": "Muitos pedidos seguidos. Aguarde alguns minutos e tente de novo.",
                })
            request.session[SESSAO_USUARIO] = usuario.pk

        messages.info(request, AVISO_ENVIO)
        return redirect("accounts:codigo_confirmar")

    def _encontrar(self, contato):
        """Procura o cliente pelo e-mail ou pelo telefone, sem revelar o resultado."""
        base = User.objects.filter(tipo=TipoUsuario.CLIENTE, is_active=True)
        if "@" in contato:
            return base.filter(email__iexact=contato).first()
        digitos = _somente_digitos(contato)
        if len(digitos) < 10:
            return None
        for usuario in base.exclude(telefone=""):
            if _somente_digitos(usuario.telefone).endswith(digitos[-10:]):
                return usuario
        return None


class ConfirmarCodigoView(View):
    """Passo 2: o cliente digita o codigo recebido."""

    template_name = "accounts/codigo_confirmar.html"

    def get(self, request):
        if not request.session.get(SESSAO_USUARIO):
            return render(request, self.template_name, {"sem_pedido": True})
        return render(request, self.template_name, {})

    def post(self, request):
        digitado = _somente_digitos(request.POST.get("codigo") or "")
        usuario_id = request.session.get(SESSAO_USUARIO)

        if len(digitado) != 6:
            return render(request, self.template_name, {"erro": "Digite os 6 digitos do codigo."})
        if not usuario_id:
            return render(request, self.template_name, {"sem_pedido": True})

        registro = (
            CodigoAcesso.objects.filter(usuario_id=usuario_id, usado_em__isnull=True)
            .order_by("-criado_em").first()
        )
        if registro is None or registro.expirado:
            return render(request, self.template_name, {
                "erro": "Esse codigo expirou. Peca um novo.", "expirado": True,
            })
        if registro.tentativas >= MAX_TENTATIVAS:
            return render(request, self.template_name, {
                "erro": "Tentativas demais para esse codigo. Peca um novo.", "expirado": True,
            })

        if not registro.confere(digitado):
            restantes = max(0, MAX_TENTATIVAS - registro.tentativas)
            return render(request, self.template_name, {
                "erro": f"Codigo invalido. Voce ainda tem {restantes} tentativa(s).",
                "expirado": restantes == 0,
            })

        request.session.pop(SESSAO_USUARIO, None)
        login(request, registro.usuario, backend="django.contrib.auth.backends.ModelBackend")
        return redirect("portal:home")
