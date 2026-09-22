"""Site publico: apresentacao, jornada e diagnostico gratuito."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import TemplateView, View

from .conteudo import ETAPAS_JORNADA, PERGUNTAS_QUIZ, TOTAL_PERGUNTAS
from .forms import ContatoDiagnosticoForm
from .models import RESULTADOS, Diagnostico, Urgencia

SESSAO = "diagnostico_respostas"


class JornadaView(TemplateView):
    template_name = "publico/jornada.html"
    extra_context = {"etapas": ETAPAS_JORNADA}


class QuizView(View):
    """Uma pergunta por vez, guardada na sessao. Funciona sem JavaScript."""

    template_name = "publico/quiz.html"

    def get(self, request):
        if request.GET.get("reiniciar"):
            request.session.pop(SESSAO, None)
        respostas = request.session.get(SESSAO, [])
        indice = len(respostas)
        if indice >= TOTAL_PERGUNTAS:
            request.session.pop(SESSAO, None)
            indice, respostas = 0, []
        return self._mostrar(request, indice)

    def post(self, request):
        respostas = request.session.get(SESSAO, [])
        indice = len(respostas)
        if indice >= TOTAL_PERGUNTAS:
            return redirect("publico:quiz")

        pergunta = PERGUNTAS_QUIZ[indice]
        try:
            escolha = int(request.POST.get("opcao", ""))
            rotulo, valor = pergunta["opcoes"][escolha]
        except (ValueError, IndexError):
            return self._mostrar(request, indice, erro="Escolha uma das opcoes para continuar.")

        if valor == "pf":
            request.session.pop(SESSAO, None)
            return render(request, "publico/quiz_pessoa_fisica.html")

        respostas.append({"chave": pergunta["chave"], "pergunta": pergunta["texto"],
                          "resposta": rotulo, "pontos": valor})
        request.session[SESSAO] = respostas

        if len(respostas) < TOTAL_PERGUNTAS:
            return redirect("publico:quiz")

        pontuacao = sum(item["pontos"] for item in respostas)
        diagnostico = Diagnostico.objects.create(
            respostas=respostas,
            pontuacao=pontuacao,
            urgencia=Urgencia.da_pontuacao(pontuacao),
        )
        request.session.pop(SESSAO, None)
        return redirect("publico:resultado", token=diagnostico.token)

    def _mostrar(self, request, indice, erro=""):
        pergunta = PERGUNTAS_QUIZ[indice]
        return render(
            request,
            self.template_name,
            {
                "pergunta": pergunta,
                "opcoes": list(enumerate(pergunta["opcoes"])),
                "numero": indice + 1,
                "total": TOTAL_PERGUNTAS,
                "percentual": round(indice / TOTAL_PERGUNTAS * 100),
                "pode_voltar": indice > 0,
                "erro": erro,
            },
        )


class VoltarPerguntaView(View):
    def post(self, request):
        respostas = request.session.get(SESSAO, [])
        if respostas:
            request.session[SESSAO] = respostas[:-1]
        return redirect("publico:quiz")


class ResultadoView(View):
    template_name = "publico/resultado.html"

    def get(self, request, token):
        diagnostico = get_object_or_404(Diagnostico, token=token)
        return render(request, self.template_name, self._contexto(diagnostico, ContatoDiagnosticoForm()))

    def post(self, request, token):
        diagnostico = get_object_or_404(Diagnostico, token=token)
        form = ContatoDiagnosticoForm(request.POST, instance=diagnostico)
        if form.is_valid():
            diagnostico = form.save(commit=False)
            diagnostico.contato_em = timezone.now()
            diagnostico.save()
            messages.success(
                request,
                "Recebemos seus dados. Em breve alguem do time entra em contato — "
                f"o combinado e retornar em ate {Urgencia.prazo_legivel(diagnostico.urgencia)}.",
            )
            return redirect("publico:resultado", token=diagnostico.token)
        return render(request, self.template_name, self._contexto(diagnostico, form))

    def _contexto(self, diagnostico, form):
        texto = RESULTADOS.get(diagnostico.urgencia, {})
        return {
            "diagnostico": diagnostico,
            "form": form,
            "titulo_resultado": texto.get("titulo", ""),
            "mensagem_resultado": texto.get("mensagem", ""),
            "prazo": Urgencia.prazo_legivel(diagnostico.urgencia),
            # vem do banco: um POST invalido nao pode fazer a tela dizer que recebeu
            "ja_enviou": diagnostico.tem_contato,
        }
