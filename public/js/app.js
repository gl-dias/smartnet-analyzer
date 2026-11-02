// Estado da aplicação e chamadas à API. O front guarda o grafo e o envia a cada requisição.

const CHAVE_ARMAZENAMENTO = "smartnet-estado";

const estado = {
  grafo: { direcionado: false, ponderado: true, vertices: [], arestas: [] },
  listaAdjacencia: [],
  estatisticas: { vertices: 0, arestas: 0, densidade: 0 },
  avisos: [],
  contadores: { grafos: 0, algoritmos: 0 },
  ultimoResultado: null,
};

const $ = (seletor) => document.querySelector(seletor);
const $$ = (seletor) => [...document.querySelectorAll(seletor)];
const visual = new GrafoVisual($("#mapa"));

// Utilitários de interface

// Cria elementos sempre com textContent: nomes de vértices nunca são interpretados como HTML.
function el(tag, propriedades = {}, ...filhos) {
  const elemento = document.createElement(tag);
  Object.entries(propriedades).forEach(([chave, valor]) => {
    if (chave.startsWith("on")) elemento.addEventListener(chave.slice(2), valor);
    else if (chave === "classe") elemento.className = valor;
    else if (chave === "texto") elemento.textContent = valor;
    else elemento.setAttribute(chave, valor);
  });
  elemento.append(...filhos.filter((filho) => filho !== null && filho !== undefined));
  return elemento;
}

function avisar(mensagem, tipo = "") {
  const aviso = el("div", { classe: `flutuante ${tipo}`, texto: mensagem });
  const pilha = $("#avisos-flutuantes");
  pilha.append(aviso);
  while (pilha.children.length > 3) pilha.firstChild.remove();
  setTimeout(() => aviso.remove(), tipo === "erro" ? 7000 : 4000);
}

function confirmar(titulo, texto, rotulo) {
  const modal = $("#modal");
  $("#modal-titulo").textContent = titulo;
  $("#modal-texto").textContent = texto;
  $("#modal-confirmar").textContent = rotulo;
  modal.returnValue = "nao";
  modal.showModal();
  return new Promise((resolver) => {
    modal.addEventListener("close", () => resolver(modal.returnValue === "sim"), { once: true });
  });
}

async function chamarApi(caminho, corpo) {
  let resposta;
  try {
    resposta = await fetch(caminho, corpo === undefined ? {} : {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corpo),
    });
  } catch {
    throw new Error("Não foi possível falar com o servidor. Verifique a conexão.");
  }
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(dados.erro || "O servidor não conseguiu processar o pedido.");
  return dados;
}

function nomeLimpo(nome) {
  if (typeof nome === "number") return String(nome);
  return typeof nome === "string" ? nome.trim().replace(/\s+/g, " ") : nome;
}

function lerPeso(texto) {
  const limpo = String(texto).trim().replace(",", ".");
  return limpo === "" ? NaN : Number(limpo);
}

function simboloVia(grafo) {
  return grafo.direcionado ? "→" : "↔";
}

// Estado do grafo

function normalizarGrafo(grafo) {
  const limparAresta = (aresta) => (aresta && typeof aresta === "object"
    ? { ...aresta, origem: nomeLimpo(aresta.origem), destino: nomeLimpo(aresta.destino) }
    : aresta);
  return {
    direcionado: grafo.direcionado ?? false,
    ponderado: grafo.ponderado ?? true,
    vertices: Array.isArray(grafo.vertices) ? grafo.vertices.map(nomeLimpo) : grafo.vertices ?? [],
    arestas: Array.isArray(grafo.arestas) ? grafo.arestas.map(limparAresta) : grafo.arestas ?? [],
  };
}

// Só troca o estado depois que o backend aceita o grafo candidato.
// As arestas ficam como o usuário as inseriu (sentido e peso) para sobreviver às chaves do topo.
async function aplicarGrafo(candidato, { novo = false } = {}) {
  const normalizado = normalizarGrafo(candidato);
  try {
    const resposta = await chamarApi("/api/estrutura", normalizado);
    const estavaVazio = estado.grafo.vertices.length === 0;
    estado.grafo = { ...normalizado, vertices: resposta.vertices };
    estado.listaAdjacencia = resposta.lista_adjacencia;
    estado.estatisticas = resposta.estatisticas;
    estado.avisos = resposta.avisos;
    if (resposta.vertices.length && (novo || estavaVazio)) estado.contadores.grafos += 1;
    renderizar();
    salvarEstado();
    return true;
  } catch (erro) {
    avisar(erro.message, "erro");
    renderizar();
    return false;
  }
}

function copiaGrafo() {
  return {
    ...estado.grafo,
    vertices: [...estado.grafo.vertices],
    arestas: estado.grafo.arestas.map((aresta) => ({ ...aresta })),
  };
}

function salvarEstado() {
  try {
    sessionStorage.setItem(CHAVE_ARMAZENAMENTO, JSON.stringify({
      grafo: estado.grafo,
      contadores: estado.contadores,
    }));
  } catch { /* O armazenamento é só uma conveniência para recarregar a página. */ }
}

function restaurarEstado() {
  try {
    return JSON.parse(sessionStorage.getItem(CHAVE_ARMAZENAMENTO));
  } catch {
    return null;
  }
}

// Renderização

function renderizar() {
  limparResultado();
  visual.atualizar(estado.grafo, estado.grafo.vertices);
  $("#chave-direcionado").checked = estado.grafo.direcionado;
  $("#chave-ponderado").checked = estado.grafo.ponderado;
  $$(".so-ponderado").forEach((elemento) => { elemento.hidden = !estado.grafo.ponderado; });
  $("#via-peso").required = estado.grafo.ponderado;
  renderizarEstatisticas();
  renderizarEstrutura();
  renderizarManual();
  renderizarSeletores();
}

function renderizarEstatisticas() {
  const { vertices, arestas, densidade } = estado.estatisticas;
  $("#estatisticas").textContent = vertices
    ? `V = ${vertices}   |   E = ${arestas}   |   Densidade = ${densidade}   |   ${estado.grafo.direcionado ? "Direcionado" : "Não direcionado"}, ${estado.grafo.ponderado ? "ponderado" : "sem peso"}`
    : "Nenhum grafo carregado. Comece pela aba Importar/Exemplos ou pela aba Manual.";
}

function renderizarEstrutura() {
  $("#avisos-grafo").replaceChildren(...estado.avisos.map((texto) => el("div", { classe: "aviso", texto })));
  const cartoes = estado.listaAdjacencia.map(({ vertice, vizinhos }) => {
    const itens = [];
    vizinhos.forEach((item, i) => {
      if (i) itens.push(", ");
      itens.push(estado.grafo.ponderado ? `(${item.vizinho}, ${item.peso})` : `(${item.vizinho})`);
    });
    const cartao = el(
      "div",
      { classe: "cartao" },
      el("strong", { texto: vertice }),
      el("span", { classe: "seta", texto: " -> " }),
      el("span", { classe: "colchete", texto: "[ " }),
      itens.join(""),
      el("span", { classe: "colchete", texto: " ]" }),
    );
    cartao.dataset.vertice = vertice;
    cartao.dataset.vizinhos = JSON.stringify(vizinhos.map((item) => item.vizinho));
    return cartao;
  });
  $("#estrutura").replaceChildren(...cartoes);
}

function destacarCartao(cartao) {
  $$(".cartao").forEach((outro) => outro.classList.remove("ativo", "vizinho"));
  if (!cartao) {
    visual.removerSelecao();
    return;
  }
  cartao.classList.add("ativo");
  const vizinhos = new Set(JSON.parse(cartao.dataset.vizinhos));
  $$(".cartao").forEach((outro) => {
    if (vizinhos.has(outro.dataset.vertice) && outro !== cartao) outro.classList.add("vizinho");
  });
  visual.destacarVertice(cartao.dataset.vertice);
}

function renderizarManual() {
  const { vertices, arestas, ponderado } = estado.grafo;
  $("#lista-vertices").replaceChildren(...vertices.map((v) => el("option", { value: v })));
  $("#lista-bairros").replaceChildren(...(vertices.length
    ? vertices.map((v) => el(
      "span",
      { classe: "etiqueta" },
      v,
      el("button", {
        type: "button",
        title: `Remover ${v} e suas vias`,
        "aria-label": `Remover ${v} e suas vias`,
        texto: "×",
        onclick: () => removerBairro(v),
      }),
    ))
    : [el("span", { classe: "nota", texto: "Nenhum bairro cadastrado." })]));

  const simbolo = simboloVia(estado.grafo);
  $("#tabela-vias").replaceChildren(...(arestas.length
    ? arestas.map((aresta, indice) => el(
      "tr",
      {},
      el("td", { classe: "quebra", texto: `${aresta.origem} ${simbolo} ${aresta.destino}` }),
      ponderado
        ? el("td", {}, el("input", {
          value: aresta.peso ?? 1,
          inputmode: "decimal",
          "aria-label": `Peso de ${aresta.origem} ${simbolo} ${aresta.destino}`,
          onchange: (evento) => alterarPesoVia(indice, evento.target.value),
        }))
        : null,
      el("td", {}, el("button", {
        type: "button",
        classe: "botao mini",
        title: "Remover via",
        "aria-label": `Remover via ${aresta.origem} ${simbolo} ${aresta.destino}`,
        texto: "×",
        onclick: () => removerVia(indice),
      })),
    ))
    : [el("tr", {}, el("td", { colspan: "3", classe: "nota", texto: "Nenhuma via cadastrada." }))]));
}

function renderizarSeletores() {
  const { vertices } = estado.grafo;
  const seletorOrigem = $("#seletor-origem");
  const seletorDestino = $("#seletor-destino");
  const origemAtual = seletorOrigem.value;
  const destinoAtual = seletorDestino.value;
  seletorOrigem.replaceChildren(...vertices.map((v) => el("option", { value: v, texto: v })));
  seletorDestino.replaceChildren(
    el("option", { value: "", texto: "Nenhum" }),
    ...vertices.map((v) => el("option", { value: v, texto: v })),
  );
  // O enunciado usa O como origem, então ele é o padrão quando existe.
  if (vertices.includes(origemAtual)) seletorOrigem.value = origemAtual;
  else if (vertices.includes("O")) seletorOrigem.value = "O";
  if (vertices.includes(destinoAtual)) seletorDestino.value = destinoAtual;
}

// Alterações pelo formulário manual

async function adicionarVia(evento) {
  evento.preventDefault();
  const origem = nomeLimpo($("#via-origem").value);
  const destino = nomeLimpo($("#via-destino").value);
  const candidato = copiaGrafo();
  const aresta = { origem, destino };
  if (estado.grafo.ponderado) {
    aresta.peso = lerPeso($("#via-peso").value);
    if (!Number.isFinite(aresta.peso)) {
      avisar("O peso precisa ser um número.", "erro");
      return;
    }
  }
  candidato.arestas.push(aresta);
  if (await aplicarGrafo(candidato)) {
    evento.target.reset();
    $("#via-origem").focus();
  }
}

async function adicionarBairro(evento) {
  evento.preventDefault();
  const candidato = copiaGrafo();
  candidato.vertices.push(nomeLimpo($("#bairro-nome").value));
  if (await aplicarGrafo(candidato)) evento.target.reset();
}

function removerBairro(vertice) {
  const candidato = copiaGrafo();
  candidato.vertices = candidato.vertices.filter((v) => v !== vertice);
  candidato.arestas = candidato.arestas.filter((a) => a.origem !== vertice && a.destino !== vertice);
  aplicarGrafo(candidato);
}

function removerVia(indice) {
  const candidato = copiaGrafo();
  candidato.arestas.splice(indice, 1);
  aplicarGrafo(candidato);
}

function alterarPesoVia(indice, texto) {
  const peso = lerPeso(texto);
  if (!Number.isFinite(peso)) {
    avisar("O peso precisa ser um número.", "erro");
    renderizarManual();
    return;
  }
  const candidato = copiaGrafo();
  candidato.arestas[indice].peso = peso;
  aplicarGrafo(candidato);
}

// Chaves do topo

function alternarDirecionado(direcionado) {
  const candidato = copiaGrafo();
  candidato.direcionado = direcionado;
  if (direcionado) {
    if (candidato.arestas.length) avisar("Cada via passou a valer só no sentido em que foi cadastrada.", "alerta");
  } else {
    // A -> B e B -> A viram a mesma via sem direção: fica a primeira cadastrada.
    const vistas = new Set();
    candidato.arestas = candidato.arestas.filter((aresta) => {
      const par = JSON.stringify([aresta.origem, aresta.destino].sort());
      if (vistas.has(par)) return false;
      vistas.add(par);
      return true;
    });
    const unidas = estado.grafo.arestas.length - candidato.arestas.length;
    if (unidas) avisar(`${unidas} via(s) em sentido oposto foram unidas (ficou o peso da primeira cadastrada).`, "alerta");
  }
  aplicarGrafo(candidato);
}

function alternarPonderado(ponderado) {
  const candidato = copiaGrafo();
  candidato.ponderado = ponderado;
  // Vias criadas sem peso recebem 1. Pesos já informados voltam intactos ao religar a chave.
  if (ponderado) candidato.arestas.forEach((aresta) => { aresta.peso ??= 1; });
  aplicarGrafo(candidato);
}

// Entrada por texto

function interpretarTexto(texto) {
  const arestas = [];
  const linhas = texto.split("\n");
  for (let i = 0; i < linhas.length; i += 1) {
    const partes = linhas[i].trim().split(/\s+/).filter(Boolean);
    if (partes.length === 0) continue;
    if (partes.length > 3 || partes.length < 2) {
      throw new Error(`Linha ${i + 1}: use o formato "origem destino peso", com nomes sem espaço.`);
    }
    const [origem, destino, pesoTexto] = partes;
    const aresta = { origem, destino };
    if (estado.grafo.ponderado) {
      if (pesoTexto === undefined) throw new Error(`Linha ${i + 1}: falta o peso (a chave Ponderado está ligada).`);
      aresta.peso = lerPeso(pesoTexto);
      if (!Number.isFinite(aresta.peso)) throw new Error(`Linha ${i + 1}: o peso "${pesoTexto}" não é um número.`);
    }
    arestas.push(aresta);
  }
  if (!arestas.length) throw new Error("Escreva ao menos uma via.");
  return arestas;
}

async function aplicarTexto(substituir) {
  let arestas;
  try {
    arestas = interpretarTexto($("#texto-arestas").value);
  } catch (erro) {
    avisar(erro.message, "erro");
    return;
  }
  const candidato = copiaGrafo();
  if (substituir) candidato.vertices = [];
  candidato.arestas = substituir ? arestas : [...candidato.arestas, ...arestas];
  if (await aplicarGrafo(candidato, { novo: substituir })) {
    avisar(`${arestas.length} via(s) aplicada(s).`);
  }
}

// Importação, exportação e exemplos

async function carregarExemplo(nome) {
  try {
    const exemplo = await chamarApi(`/api/exemplos/${nome}`);
    if (await aplicarGrafo(exemplo, { novo: true })) avisar(`${exemplo.nome} carregado.`);
  } catch (erro) {
    avisar(erro.message, "erro");
  }
}

function exportarJson() {
  const conteudo = JSON.stringify(estado.grafo, null, 2);
  const url = URL.createObjectURL(new Blob([conteudo], { type: "application/json" }));
  const link = el("a", { href: url, download: "smartnet-grafo.json" });
  link.click();
  URL.revokeObjectURL(url);
}

async function importarJson(evento) {
  const [arquivo] = evento.target.files;
  evento.target.value = "";
  if (!arquivo) return;
  let dados;
  try {
    dados = JSON.parse(await arquivo.text());
  } catch {
    avisar("O arquivo não contém um JSON válido.", "erro");
    return;
  }
  if (!dados || typeof dados !== "object" || Array.isArray(dados)) {
    avisar("O JSON deve ser um objeto com vertices e arestas.", "erro");
    return;
  }
  if (await aplicarGrafo(dados, { novo: true })) avisar("Grafo importado.");
}

// Resultados dos algoritmos

function limparResultado() {
  estado.ultimoResultado = null;
  $("#resultados").replaceChildren();
  $$(".botao-algoritmo").forEach((botao) => botao.classList.remove("ativo"));
}

function exibir(valor) {
  return valor === null || valor === undefined ? "-" : String(valor);
}

function tabela(colunas, linhas) {
  return el(
    "div",
    { classe: "tabela-rolagem" },
    el(
      "table",
      {},
      el("thead", {}, el("tr", {}, ...colunas.map((coluna) => el("th", { texto: coluna })))),
      el("tbody", {}, ...linhas.map((linha) => el(
        "tr",
        {},
        ...linha.map((celula) => (celula instanceof Node ? el("td", {}, celula) : el("td", { texto: exibir(celula) }))),
      ))),
    ),
  );
}

function sequencia(itens) {
  const elementos = [];
  itens.forEach((item, i) => {
    if (i) elementos.push(el("i", { texto: "→" }));
    elementos.push(el("b", { texto: item }));
  });
  return el("div", { classe: "sequencia" }, ...elementos);
}

function juntar(itens, vazio = "Nenhum") {
  return itens.length ? itens.join(", ") : vazio;
}

function dados(pares) {
  return el("dl", { classe: "dados" }, ...pares.flatMap(([rotulo, valor]) => [
    el("dt", { texto: rotulo }),
    el("dd", { texto: valor }),
  ]));
}

function secao(titulo, ...conteudo) {
  return el("div", {}, el("h3", { texto: titulo }), ...conteudo);
}

function resultadoDfs(r) {
  const c = r.conectividade;
  const conectividade = [["Classificação", c.classificacao]];
  conectividade.push(["Componentes", c.componentes.map((grupo) => `{${grupo.join(", ")}}`).join("  ")]);
  if (estado.grafo.direcionado) {
    conectividade.push(["Componentes fortes", c.componentes_fortes.map((grupo) => `{${grupo.join(", ")}}`).join("  ")]);
  }
  conectividade.push(["Não alcançáveis", juntar(r.nao_alcancaveis)]);
  conectividade.push([
    estado.grafo.direcionado ? "Becos sem saída (sem saídas)" : "Becos sem saída (grau 1)",
    juntar(r.becos_sem_saida),
  ]);
  return [
    secao("Ordem de visita", sequencia(r.ordem_visita)),
    secao("Árvore DFS", el("pre", { classe: "arvore", texto: r.arvore_texto })),
    secao("Conectividade", dados(conectividade)),
    secao(
      "Predecessores e tempos",
      tabela(
        ["Vértice", "Predecessor", "Descoberta", "Finalização"],
        r.tabela.map((l) => [l.vertice, l.predecessor, l.descoberta, l.finalizacao]),
      ),
    ),
  ];
}

function resultadoBfs(r) {
  const partes = [
    secao("Fila final de execução", sequencia(r.ordem_visita)),
    secao(
      "Fila passo a passo",
      tabela(
        ["Passo", "Removido", "Enfileirados", "Fila atual"],
        r.passos.map((p) => [p.passo, p.removido, juntar(p.enfileirados, "-"), `[ ${p.fila.join(", ")} ]`]),
      ),
    ),
    secao(
      "Nível de cada vértice (saltos)",
      tabela(
        ["Vértice", "Nível", "Predecessor"],
        r.tabela.map((l) => [l.vertice, l.nivel === null ? "∞" : l.nivel, l.predecessor]),
      ),
    ),
  ];
  if (r.caminho_destino) {
    const rota = r.caminho_destino;
    partes.splice(1, 0, secao(
      `Menos saltos até ${rota.destino}`,
      rota.alcancavel
        ? el("div", {}, sequencia(rota.caminho), el("p", { classe: "nota", texto: `${rota.saltos} salto(s)` }))
        : el("p", { texto: `${rota.destino} não é alcançável a partir de ${r.origem}.` }),
    ));
  }
  return partes;
}

function resultadoDijkstra(r) {
  const partes = [
    secao(
      `Distâncias a partir de ${r.origem}`,
      tabela(
        ["Vértice", "Distância", "Predecessor", "Caminho"],
        r.tabela.map((l) => [l.vertice, l.distancia, l.predecessor, l.caminho.length ? l.caminho.join(" → ") : "-"]),
      ),
    ),
    el(
      "details",
      {},
      el("summary", { texto: "Relaxações passo a passo" }),
      tabela(
        ["Passo", "Extraído", "Dist.", "Vizinho", "Peso", "Antes", "Candidata", "Atualizou"],
        r.passos.flatMap((p) => (p.relaxacoes.length
          ? p.relaxacoes.map((x) => [p.passo, p.vertice, p.distancia, x.vizinho, x.peso, x.distancia_anterior, x.distancia_candidata, x.atualizou ? "Sim" : "Não"])
          : [[p.passo, p.vertice, p.distancia, "-", "-", "-", "-", "-"]])),
      ),
    ),
  ];
  if (r.caminho_destino) {
    const rota = r.caminho_destino;
    partes.unshift(secao(
      `Rota até ${rota.destino}`,
      rota.alcancavel
        ? el("div", {}, sequencia(rota.caminho), el("p", { classe: "nota", texto: `Custo total: ${rota.custo}` }))
        : el("p", { texto: `${rota.destino} não é alcançável a partir de ${r.origem} (distância ∞).` }),
    ));
  }
  return partes;
}

function resultadoKruskal(r) {
  const simbolo = simboloVia(estado.grafo);
  return [
    secao(r.floresta ? "Custo total da floresta" : "Custo total da árvore", el("div", { classe: "custo", texto: String(r.custo_total) })),
    secao(
      `Arestas selecionadas (${r.arestas_selecionadas.length})`,
      tabela(["Aresta", "Peso"], r.arestas_selecionadas.map((a) => [`${a.origem} - ${a.destino}`, a.peso])),
    ),
    secao(
      "Passo a passo",
      tabela(
        ["Passo", "Aresta", "Peso", "Decisão", "Motivo"],
        r.passos.map((p) => [
          p.passo,
          `${p.origem} ${simbolo} ${p.destino}`,
          p.peso,
          el("span", { classe: p.aceita ? "aceita" : "rejeitada", texto: p.aceita ? "Aceita" : "Rejeitada" }),
          p.motivo,
        ]),
      ),
    ),
  ];
}

const NOMES_ALGORITMOS = { dfs: "DFS", bfs: "BFS", dijkstra: "Dijkstra", kruskal: "Kruskal" };
const RENDERIZADORES = { dfs: resultadoDfs, bfs: resultadoBfs, dijkstra: resultadoDijkstra, kruskal: resultadoKruskal };

function renderizarResultado(r) {
  const cabecalho = el(
    "div",
    { classe: "resultado-cabecalho" },
    el("h3", { texto: NOMES_ALGORITMOS[r.algoritmo] }),
    el("span", { classe: "selo complexidade", title: "Complexidade de tempo", texto: `Tempo ${r.complexidade.tempo}` }),
    el("span", { classe: "selo complexidade", title: "Complexidade de espaço", texto: `Espaço ${r.complexidade.espaco}` }),
    el("span", { classe: "selo", title: "Tempo medido nesta execução", texto: `${r.tempo_ms} ms` }),
    el("button", { type: "button", classe: "botao", texto: "Repetir animação", onclick: () => visual.animar(r) }),
  );
  $("#resultados").replaceChildren(
    cabecalho,
    el("p", { classe: "nota", texto: r.complexidade.explicacao }),
    ...r.avisos.map((texto) => el("div", { classe: "aviso", texto })),
    ...RENDERIZADORES[r.algoritmo](r),
  );
}

async function executarAlgoritmo(algoritmo) {
  const botoes = $$(".botao-algoritmo");
  botoes.forEach((botao) => { botao.disabled = true; });
  try {
    const resultado = await chamarApi(`/api/algoritmos/${algoritmo}`, {
      grafo: estado.grafo,
      origem: $("#seletor-origem").value || null,
      destino: $("#seletor-destino").value || null,
    });
    estado.ultimoResultado = resultado;
    estado.contadores.algoritmos += 1;
    salvarEstado();
    botoes.forEach((botao) => botao.classList.toggle("ativo", botao.dataset.algoritmo === algoritmo));
    renderizarResultado(resultado);
    visual.animar(resultado);
  } catch (erro) {
    botoes.forEach((botao) => botao.classList.remove("ativo"));
    visual.limparDestaque();
    $("#resultados").replaceChildren(el("div", { classe: "aviso erro", texto: erro.message }));
  } finally {
    botoes.forEach((botao) => { botao.disabled = false; });
  }
}

// Apagar e finalizar

async function apagarGrafo() {
  const ok = await confirmar("Apagar grafo", "Todos os bairros e vias do grafo atual serão removidos.", "Apagar");
  if (!ok) return;
  aplicarGrafo({ ...estado.grafo, vertices: [], arestas: [] });
}

async function finalizarAplicacao() {
  const ok = await confirmar(
    "Finalizar aplicação",
    "A sessão será encerrada e o grafo atual será descartado. Deseja continuar?",
    "Finalizar",
  );
  if (!ok) return;
  try {
    await chamarApi("/api/sessao/finalizar", {});
  } catch (erro) {
    avisar(erro.message, "alerta");
  }
  $("#resumo-grafos").textContent = estado.contadores.grafos;
  $("#resumo-algoritmos").textContent = estado.contadores.algoritmos;
  visual.cancelarAnimacao();
  try {
    sessionStorage.removeItem(CHAVE_ARMAZENAMENTO);
  } catch { /* Nada a limpar se o armazenamento estiver bloqueado. */ }
  $("#aplicacao").hidden = true;
  $("#encerramento").hidden = false;
}

// Inicialização

function ativarAba(nome) {
  $$(".aba").forEach((aba) => aba.setAttribute("aria-selected", String(aba.dataset.aba === nome)));
  $$(".aba-conteudo").forEach((conteudo) => { conteudo.hidden = conteudo.dataset.conteudo !== nome; });
}

function ligarEventos() {
  $$(".aba").forEach((aba) => aba.addEventListener("click", () => ativarAba(aba.dataset.aba)));
  $("#form-via").addEventListener("submit", adicionarVia);
  $("#form-bairro").addEventListener("submit", adicionarBairro);
  $("#chave-direcionado").addEventListener("change", (e) => alternarDirecionado(e.target.checked));
  $("#chave-ponderado").addEventListener("change", (e) => alternarPonderado(e.target.checked));
  $("#texto-substituir").addEventListener("click", () => aplicarTexto(true));
  $("#texto-adicionar").addEventListener("click", () => aplicarTexto(false));
  $$("[data-exemplo]").forEach((botao) => botao.addEventListener("click", () => carregarExemplo(botao.dataset.exemplo)));
  $("#botao-exportar").addEventListener("click", exportarJson);
  $("#arquivo-importar").addEventListener("change", importarJson);
  $$("[data-algoritmo]").forEach((botao) => botao.addEventListener("click", () => executarAlgoritmo(botao.dataset.algoritmo)));
  $("#botao-apagar").addEventListener("click", apagarGrafo);
  $("#botao-finalizar").addEventListener("click", finalizarAplicacao);
  $("#estrutura").addEventListener("mouseover", (e) => destacarCartao(e.target.closest(".cartao")));
  $("#estrutura").addEventListener("mouseleave", () => destacarCartao(null));
}

ligarEventos();
const salvo = restaurarEstado();
if (salvo && salvo.grafo) {
  estado.contadores = salvo.contadores;
  aplicarGrafo(salvo.grafo);
} else {
  renderizar();
}
