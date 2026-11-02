// Linguagem natural: envia o texto ao backend e conduz a tela de revisão antes de aplicar.

const NL_MAXIMO_CARACTERES = 2000;

const revisao = { operacoes: [], marcadas: [], grafo: null, visual: null };

function atualizarContador() {
  $("#nl-contador").textContent = `${$("#nl-texto").value.length} / ${NL_MAXIMO_CARACTERES}`;
}

function mostrarRetorno(mensagem, classe) {
  const area = $("#nl-retorno");
  area.className = classe;
  area.textContent = mensagem;
  area.hidden = !mensagem;
}

// Envia o texto digitado ou transcrito. A voz usa esta mesma função, mudando só o canal.
async function enviarLinguagemNatural(texto, canal, botao) {
  if (!texto.trim()) {
    mostrarRetorno("Escreva o que deseja fazer no mapa.", "aviso erro");
    return;
  }
  const rotulo = botao.textContent;
  botao.disabled = true;
  botao.textContent = "Interpretando...";
  mostrarRetorno("", "");
  try {
    const resposta = await chamarApi("/api/interpretar", { texto, canal, grafo: estado.grafo });
    if (resposta.tipo === "pergunta") {
      mostrarRetorno(`${resposta.pergunta} Complete o texto acima e envie de novo.`, "aviso");
    } else {
      abrirRevisao(resposta);
    }
  } catch (erro) {
    mostrarRetorno(erro.message, "aviso erro");
  } finally {
    botao.disabled = false;
    botao.textContent = rotulo;
  }
}

function abrirRevisao(resposta) {
  revisao.operacoes = resposta.operacoes;
  // O que o backend recusou começa desmarcado, mas continua visível com o motivo.
  revisao.marcadas = resposta.operacoes.map((op) => !op.erro);
  $("#revisao").showModal();
  if (revisao.visual && revisao.visual.rede) revisao.visual.rede.destroy();
  $("#revisao-mapa").replaceChildren();
  revisao.visual = new GrafoVisual($("#revisao-mapa"));
  aplicarPrevia(resposta, resposta.operacoes.map((_, i) => i));
}

// `posicoes` diz a qual item da lista cada operação da resposta corresponde.
// As operações que não foram enviadas mantêm a última anotação recebida.
function aplicarPrevia(resposta, posicoes) {
  revisao.grafo = resposta.grafo;
  posicoes.forEach((posicao, i) => { revisao.operacoes[posicao] = resposta.operacoes[i]; });
  renderizarRevisao(resposta.estrutura);
}

function renderizarRevisao(estrutura) {
  const itens = revisao.operacoes.map((op, i) => {
    const marcada = revisao.marcadas[i];
    return el(
      "li",
      { classe: "revisao-item" },
      el(
        "label",
        {},
        el("input", {
          type: "checkbox",
          ...(marcada ? { checked: "" } : {}),
          onchange: (evento) => alternarOperacao(i, evento.target.checked),
        }),
        el("span", { texto: op.descricao }),
      ),
      op.erro ? el("div", { classe: "revisao-erro", texto: op.erro }) : null,
      op.aviso && marcada ? el("div", { classe: "revisao-aviso", texto: op.aviso }) : null,
    );
  });
  $("#revisao-lista").replaceChildren(...itens);

  const { vertices, arestas, densidade } = estrutura.estatisticas;
  $("#revisao-estatisticas").textContent = `Resultado: V = ${vertices}   |   E = ${arestas}   |   Densidade = ${densidade}`;
  revisao.visual.atualizar(revisao.grafo, estrutura.vertices);

  const invalida = revisao.operacoes.some((op, i) => revisao.marcadas[i] && op.erro);
  const nenhuma = !revisao.marcadas.some(Boolean);
  $("#revisao-confirmar").disabled = invalida || nenhuma;
  $("#revisao-nota").textContent = invalida
    ? "Desmarque as operações com erro para confirmar."
    : "";
}

async function alternarOperacao(indice, marcada) {
  revisao.marcadas[indice] = marcada;
  const posicoes = revisao.operacoes.flatMap((_, i) => (revisao.marcadas[i] ? [i] : []));
  try {
    const resposta = await chamarApi("/api/operacoes/previa", {
      grafo: estado.grafo,
      operacoes: posicoes.map((i) => camposOperacao(revisao.operacoes[i])),
    });
    aplicarPrevia(resposta, posicoes);
  } catch (erro) {
    avisar(erro.message, "erro");
  }
}

function camposOperacao(op) {
  const { descricao, erro, aviso, ...campos } = op;
  return campos;
}

async function confirmarRevisao() {
  const selecionadas = revisao.operacoes.filter((_, i) => revisao.marcadas[i]);
  const trocaGrafo = selecionadas.some((op) => op.tipo === "limpar_grafo");
  $("#revisao").close();
  if (!await aplicarGrafo(revisao.grafo, { novo: trocaGrafo })) return;

  const avisos = selecionadas.map((op) => op.aviso).filter(Boolean);
  avisos.forEach((texto) => avisar(texto, "alerta", 12000));
  avisar(`${selecionadas.length} operação(ões) aplicada(s).`);
  $("#nl-texto").value = "";
  atualizarContador();
  mostrarRetorno("", "");

  // Algoritmos rodam depois das alterações, já sobre o grafo final.
  for (const op of selecionadas.filter((item) => item.tipo === "executar_algoritmo")) {
    if (op.origem) $("#seletor-origem").value = op.origem;
    $("#seletor-destino").value = op.destino || "";
    await executarAlgoritmo(op.algoritmo);
  }
}

$("#nl-texto").addEventListener("input", atualizarContador);
$("#nl-enviar").addEventListener("click", (evento) => {
  enviarLinguagemNatural($("#nl-texto").value, "texto", evento.currentTarget);
});
$("#nl-texto").addEventListener("keydown", (evento) => {
  if (evento.key === "Enter" && (evento.ctrlKey || evento.metaKey)) $("#nl-enviar").click();
});
$("#revisao-cancelar").addEventListener("click", () => $("#revisao").close());
$("#revisao-confirmar").addEventListener("click", confirmarRevisao);
atualizarContador();
