// Comando de voz com a Web Speech API. A transcrição fica editável e segue o mesmo caminho do texto.

const voz = {
  reconhecimento: null,
  gravando: false,
  mensagemErro: "",
};

const MENSAGENS_ERRO_VOZ = {
  "not-allowed": "O navegador bloqueou o microfone. Libere o acesso nas permissões do site e tente de novo.",
  "service-not-allowed": "O navegador bloqueou o reconhecimento de voz. Libere o acesso nas permissões do site.",
  "no-speech": "Não ouvi nada. Clique no microfone e fale de novo.",
  "audio-capture": "Nenhum microfone foi encontrado neste computador.",
  network: "O reconhecimento de voz precisa de internet e não conseguiu conectar. Use a aba Texto ou Manual.",
  "language-not-supported": "Este navegador não reconhece português. Use o Chrome.",
};

function atualizarEstadoVoz(texto) {
  const botao = $("#voz-microfone");
  botao.classList.toggle("gravando", voz.gravando);
  botao.setAttribute("aria-pressed", String(voz.gravando));
  botao.setAttribute("aria-label", voz.gravando ? "Parar gravação" : "Iniciar gravação");
  $("#voz-rotulo").textContent = voz.gravando ? "Parar" : "Falar";
  $("#voz-estado").textContent = texto;
}

// Só o trecho definitivo vai para a caixa, para não sobrescrever correções do usuário.
function acrescentarTranscricao(trecho) {
  const caixa = $("#voz-texto");
  const atual = caixa.value.trimEnd();
  caixa.value = atual ? `${atual} ${trecho.trim()}` : trecho.trim();
  caixa.dispatchEvent(new Event("input"));
}

function aoReceberFala(evento) {
  let parcial = "";
  for (let i = evento.resultIndex; i < evento.results.length; i += 1) {
    const resultado = evento.results[i];
    if (resultado.isFinal) acrescentarTranscricao(resultado[0].transcript);
    else parcial += resultado[0].transcript;
  }
  $("#voz-parcial").textContent = parcial;
}

function pararGravacao() {
  if (voz.gravando) voz.reconhecimento.stop();
}

function alternarGravacao() {
  if (voz.gravando) {
    pararGravacao();
    return;
  }
  voz.mensagemErro = "";
  try {
    voz.reconhecimento.start();
    voz.gravando = true;
    atualizarEstadoVoz("Gravando. Fale e clique em Parar quando terminar.");
  } catch {
    atualizarEstadoVoz("O microfone ainda está encerrando. Tente de novo em instantes.");
  }
}

function iniciarVoz() {
  const Reconhecimento = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Reconhecimento) {
    $("#voz-microfone").disabled = true;
    $("#voz-sem-suporte").hidden = false;
    return;
  }
  voz.reconhecimento = new Reconhecimento();
  voz.reconhecimento.lang = "pt-BR";
  voz.reconhecimento.continuous = true;
  voz.reconhecimento.interimResults = true;
  voz.reconhecimento.onresult = aoReceberFala;
  voz.reconhecimento.onerror = (evento) => {
    voz.mensagemErro = MENSAGENS_ERRO_VOZ[evento.error] || "";
  };
  // O navegador também encerra sozinho depois de um tempo de silêncio.
  voz.reconhecimento.onend = () => {
    voz.gravando = false;
    $("#voz-parcial").textContent = "";
    atualizarEstadoVoz(voz.mensagemErro || "Gravação encerrada. Revise o texto antes de enviar.");
  };
  $("#voz-microfone").addEventListener("click", alternarGravacao);
  atualizarEstadoVoz("Clique no microfone para começar.");
}

$("#voz-enviar").addEventListener("click", (evento) => {
  pararGravacao();
  enviarLinguagemNatural($("#voz-texto"), "voz", evento.currentTarget);
});
iniciarVoz();
