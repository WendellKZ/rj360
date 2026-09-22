/* Simulacao da jornada: percorre as seis etapas em sequencia.
   Sem JavaScript a pagina continua legivel — tudo aparece de uma vez. */
(function () {
  "use strict";
  var raiz = document.querySelector("[data-jornada]");
  if (!raiz) return;

  var etapas = Array.prototype.slice.call(raiz.querySelectorAll(".etapa-jornada"));
  var botao = document.querySelector("[data-jornada-botao]");
  var resumo = document.querySelector("[data-jornada-resumo]");
  var barra = document.querySelector("[data-jornada-barra]");
  var luz = document.querySelector("[data-jornada-luz]");
  if (!etapas.length || !botao) return;

  var reduzido = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var intervalo = reduzido ? 400 : 2200;
  var atual = 0, rodando = false, pausado = false, temporizador = null;

  function pintar() {
    etapas.forEach(function (etapa, indice) {
      etapa.classList.toggle("apagada", rodando && indice >= atual);
      etapa.classList.toggle("acesa", indice < atual);
    });
    var pct = Math.round((Math.min(atual, etapas.length) / etapas.length) * 100);
    if (barra) barra.style.width = pct + "%";
    if (resumo) {
      resumo.textContent = atual === 0
        ? "Seis etapas · D+0 até D+180"
        : "Etapa " + Math.min(atual, etapas.length) + " de " + etapas.length + " · " +
          etapas[Math.min(atual, etapas.length) - 1].getAttribute("data-titulo");
    }
    if (luz) luz.classList.toggle("acesa", atual >= etapas.length);
  }

  function rotulo() {
    if (atual >= etapas.length && !rodando) return "Rever a simulação";
    if (pausado) return "Continuar simulação";
    if (rodando) return "Pausar";
    return "Simular minha jornada";
  }

  function passo() {
    clearTimeout(temporizador);
    temporizador = setTimeout(function () {
      if (!rodando || pausado) return;
      atual += 1;
      pintar();
      if (atual >= etapas.length) {
        rodando = false;
        botao.textContent = rotulo();
        return;
      }
      passo();
    }, intervalo);
  }

  botao.addEventListener("click", function () {
    if (rodando && !pausado) {
      pausado = true;
      rodando = false;
      clearTimeout(temporizador);
    } else if (pausado) {
      pausado = false;
      rodando = true;
      passo();
    } else {
      atual = 0;
      pausado = false;
      rodando = true;
      pintar();
      passo();
    }
    botao.textContent = rotulo();
  });

  botao.hidden = false;
  pintar();
})();
