// Folha de prova: as respostas dos algoritmos no formato de resolução à mão.

const SVG_NS = "http://www.w3.org/2000/svg";
const TIPOS_ARESTA = { retorno: "Retorno", avanco: "Avanço", cruzamento: "Cruzamento" };
let proximoMarcador = 0;

function svg(tag, atributos = {}, texto) {
  const elemento = document.createElementNS(SVG_NS, tag);
  Object.entries(atributos).forEach(([chave, valor]) => elemento.setAttribute(chave, valor));
  if (texto !== undefined) elemento.textContent = texto;
  return elemento;
}

// DFS

// Folhas em colunas consecutivas; cada pai fica centrado sobre os filhos.
// A ordem de visita é pré-ordem, então ao contrário ela trata os filhos antes do pai.
function posicoesDaArvore(r) {
  const filhos = Object.fromEntries(r.ordem_visita.map((v) => [v, []]));
  const nivel = { [r.origem]: 0 };
  r.arestas_arvore.forEach(({ origem, destino }) => {
    filhos[origem].push(destino);
    nivel[destino] = nivel[origem] + 1;
  });
  const coluna = {};
  let proximaColuna = 0;
  r.ordem_visita.forEach((v) => {
    if (!filhos[v].length) coluna[v] = proximaColuna++;
  });
  [...r.ordem_visita].reverse().forEach((v) => {
    if (filhos[v].length) coluna[v] = (coluna[filhos[v][0]] + coluna[filhos[v].at(-1)]) / 2;
  });
  return { coluna, nivel };
}

function amostrasDaCurva(a, controle, b) {
  const pontos = [];
  for (let t = 0.1; t < 0.95; t += 0.1) {
    pontos.push({
      x: (1 - t) ** 2 * a.x + 2 * (1 - t) * t * controle.x + t ** 2 * b.x,
      y: (1 - t) ** 2 * a.y + 2 * (1 - t) * t * controle.y + t ** 2 * b.y,
    });
  }
  return pontos;
}

function segmentosCruzam(a, b, c, d) {
  const lado = (p, q, r) => (q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x);
  return lado(a, b, c) * lado(a, b, d) < 0 && lado(c, d, a) * lado(c, d, b) < 0;
}

// Escolhe o lado e a abertura da curva que menos cruzam linhas e passam sobre vértices.
// `segmentos` guarda as arestas da árvore e as curvas já desenhadas, como [p, q].
function melhorCurva(a, b, pontosDosNos, segmentos) {
  const vao = Math.abs(b.y - a.y) / 82;
  let melhor = null;
  [-1, 1].forEach((lado) => {
    [1, 1.6, 2.2].forEach((fator) => {
      const controle = {
        x: (a.x + b.x) / 2 + lado * fator * (34 + 12 * vao),
        y: (a.y + b.y) / 2,
      };
      const amostras = amostrasDaCurva(a, controle, b);
      const trecho = [a, ...amostras, b];
      let custo = fator;
      amostras.forEach((p) => {
        pontosDosNos.forEach((n) => {
          if (n !== a && n !== b && Math.hypot(p.x - n.x, p.y - n.y) < 26) custo += 100;
        });
      });
      for (let i = 1; i < trecho.length; i += 1) {
        segmentos.forEach(([p, q]) => {
          if (segmentosCruzam(trecho[i - 1], trecho[i], p, q)) custo += 30;
        });
      }
      if (!melhor || custo < melhor.custo) melhor = { custo, controle, amostras, trecho };
    });
  });
  return melhor;
}

function ajustarAoNo(de, para, raio = 21) {
  const distancia = Math.hypot(para.x - de.x, para.y - de.y) || 1;
  return {
    x: para.x - ((para.x - de.x) / distancia) * raio,
    y: para.y - ((para.y - de.y) / distancia) * raio,
  };
}

function desenharArvoreDfs(r) {
  const direcionado = estado.grafo.direcionado;
  const { coluna, nivel } = posicoesDaArvore(r);
  const largura = (v) => Math.max(36, v.length * 9 + 16);
  const passoX = Math.max(92, Math.max(...r.ordem_visita.map(largura)) + 56);
  const passoY = 82;
  const pos = Object.fromEntries(r.ordem_visita.map((v) => [v, {
    x: coluna[v] * passoX,
    y: nivel[v] * passoY,
  }]));

  const marcador = `folha-seta-${proximoMarcador++}`;
  const raiz = svg("svg", { class: "folha-arvore", role: "img", "aria-label": "Árvore DFS" });
  const defs = svg("defs");
  const ponta = svg("marker", {
    id: marcador, viewBox: "0 0 8 8", refX: "7", refY: "4", markerWidth: "7", markerHeight: "7", orient: "auto-start-reverse",
  });
  ponta.append(svg("path", { d: "M0 0 L8 4 L0 8 z", fill: "currentColor" }));
  defs.append(ponta);
  raiz.append(defs);

  const comSeta = direcionado ? { "marker-end": `url(#${marcador})` } : {};
  r.arestas_arvore.forEach(({ origem, destino }) => {
    const fim = direcionado ? ajustarAoNo(pos[origem], pos[destino]) : pos[destino];
    raiz.append(svg("line", {
      x1: pos[origem].x, y1: pos[origem].y, x2: fim.x, y2: fim.y, class: "folha-linha", ...comSeta,
    }));
  });

  const nos = Object.values(pos);
  const segmentos = r.arestas_arvore.map(({ origem, destino }) => [pos[origem], pos[destino]]);
  let extremoEsq = 0;
  let extremoDir = Math.max(...nos.map((n) => n.x));
  // As curvas curtas vão primeiro, para as longas contornarem por fora.
  const foraDaArvore = r.arestas_fora_da_arvore
    .filter((a) => a.origem !== a.destino)
    .map((a) => ({ ...a, vao: Math.abs(pos[a.origem].y - pos[a.destino].y) }))
    .sort((a, b) => a.vao - b.vao);
  foraDaArvore.forEach((aresta) => {
    const a = pos[aresta.origem];
    const b = pos[aresta.destino];
    const { controle, amostras, trecho } = melhorCurva(a, b, nos, segmentos);
    for (let i = 1; i < trecho.length; i += 1) segmentos.push([trecho[i - 1], trecho[i]]);
    const fim = direcionado ? ajustarAoNo(controle, b) : b;
    raiz.append(svg("path", {
      d: `M${a.x} ${a.y} Q${controle.x} ${controle.y} ${fim.x} ${fim.y}`,
      class: "folha-tracejada",
      ...comSeta,
    }));
    amostras.forEach((p) => {
      extremoEsq = Math.min(extremoEsq, p.x);
      extremoDir = Math.max(extremoDir, p.x);
    });
  });

  r.tabela.filter((l) => l.descoberta !== null).forEach((linha) => {
    const { x, y } = pos[linha.vertice];
    const w = largura(linha.vertice);
    raiz.append(svg("rect", {
      x: x - w / 2, y: y - 18, width: w, height: 36, rx: 18, class: linha.vertice === r.origem ? "folha-no raiz" : "folha-no",
    }));
    raiz.append(svg("text", { x, y: y + 5, class: "folha-rotulo" }, linha.vertice));
    raiz.append(svg("text", { x: x + w / 2 + 3, y: y - 12, class: "folha-tempo" }, `${linha.descoberta}/${linha.finalizacao}`));
  });

  const altura = Math.max(...nos.map((n) => n.y));
  const margem = 34;
  const larguraTotal = extremoDir - extremoEsq + passoX + 2 * margem;
  raiz.setAttribute("viewBox", `${extremoEsq - passoX / 2 - margem} ${-margem} ${larguraTotal} ${altura + 2 * margem}`);
  raiz.setAttribute("width", larguraTotal);
  raiz.setAttribute("height", altura + 2 * margem);
  return raiz;
}

function folhaDfs(r) {
  const direcionado = estado.grafo.direcionado;
  const simbolo = simboloVia(estado.grafo);
  const partes = [
    el("div", { classe: "folha-rolagem" }, desenharArvoreDfs(r)),
    el(
      "div",
      { classe: "folha-legenda" },
      el("span", {}, el("i", { classe: "traco cheio" }), "aresta da árvore"),
      el("span", {}, el("i", { classe: "traco pontilhado" }), "demais arestas"),
      el("span", {}, el("b", { texto: "d/f" }), " = descoberta/finalização"),
    ),
    el("p", { texto: `Ordem de visita: ${r.ordem_visita.join(", ")}` }),
  ];
  const fora = r.arestas_fora_da_arvore;
  if (fora.length) {
    const descrever = (a) => `${a.origem} ${simbolo} ${a.destino}`;
    const texto = direcionado
      ? Object.entries(TIPOS_ARESTA)
        .map(([tipo, nome]) => [nome, fora.filter((a) => a.tipo === tipo)])
        .filter(([, lista]) => lista.length)
        .map(([nome, lista]) => `${nome}: ${lista.map(descrever).join(", ")}`)
        .join(" | ")
      : `Arestas de retorno: ${fora.map(descrever).join(", ")}`;
    partes.push(el("p", { texto }));
  }
  if (r.nao_alcancaveis.length) {
    partes.push(el("p", { texto: `Não alcançados a partir de ${r.origem}: ${r.nao_alcancaveis.join(", ")}` }));
  }
  return el("div", { classe: "folha" }, ...partes);
}

// BFS

function filaComNiveis(vertices, niveis) {
  const itens = [];
  vertices.forEach((vertice, i) => {
    if (i) itens.push(el("span", { classe: "fila-virgula", texto: "," }));
    itens.push(el(
      "span",
      { classe: "fila-item" },
      el("small", { texto: String(niveis[vertice]) }),
      el("span", { texto: vertice }),
    ));
  });
  return el(
    "span",
    { classe: "fila" },
    el("span", { classe: "fila-colchete", texto: "[" }),
    ...itens,
    el("span", { classe: "fila-colchete", texto: "]" }),
  );
}

function folhaBfs(r) {
  const niveis = Object.fromEntries(r.tabela.map((l) => [l.vertice, l.nivel]));
  const linhas = [
    el("div", { classe: "fila-linha" }, el("b", { texto: "Ø" }), filaComNiveis([r.origem], niveis)),
    ...r.passos.map((p) => el(
      "div",
      { classe: "fila-linha" },
      el("b", { texto: p.removido }),
      filaComNiveis(p.fila, niveis),
    )),
  ];
  const partes = [
    el(
      "div",
      { classe: "folha-colunas" },
      el("div", {}, ...linhas),
      el("div", {}, el("p", { classe: "folha-rotulo-final", texto: "Ordem final" }), filaComNiveis(r.ordem_visita, niveis)),
    ),
  ];
  if (r.caminho_destino) {
    const rota = r.caminho_destino;
    partes.push(el("p", {
      texto: rota.alcancavel
        ? `Menos saltos até ${rota.destino}: ${rota.caminho.join(" → ")} (${rota.saltos} salto(s))`
        : `${rota.destino} não é alcançável a partir de ${r.origem}.`,
    }));
  }
  if (r.nao_alcancaveis.length) {
    partes.push(el("p", { texto: `Não alcançados a partir de ${r.origem}: ${r.nao_alcancaveis.join(", ")}` }));
  }
  return el("div", { classe: "folha" }, ...partes);
}

// Dijkstra

// Cada linha é o estado no início da iteração: os vértices já fechados ficam em branco
// e o circulado é o de menor distância, que será fechado nessa iteração.
function folhaDijkstra(r) {
  const vertices = estado.grafo.vertices;
  const distancia = Object.fromEntries(vertices.map((v) => [v, "∞"]));
  distancia[r.origem] = 0;
  const fechados = new Set();
  const linhas = r.passos.map((passo, i) => {
    const celulas = vertices.map((v) => {
      if (fechados.has(v)) return el("td", {});
      if (v === passo.vertice) return el("td", {}, el("span", { classe: "circulado", texto: String(distancia[v]) }));
      return el("td", { texto: String(distancia[v]) });
    });
    fechados.add(passo.vertice);
    passo.relaxacoes.filter((x) => x.atualizou).forEach((x) => {
      distancia[x.vizinho] = x.distancia_candidata;
    });
    return el("tr", {}, el("th", { classe: "iteracao", texto: String(i + 1) }), ...celulas);
  });
  const porVertice = Object.fromEntries(r.tabela.map((l) => [l.vertice, l]));
  const tabelaIteracoes = el(
    "table",
    { classe: "folha-tabela" },
    el("thead", {}, el("tr", {}, el("th", {}), ...vertices.map((v) => el("th", { texto: v })))),
    el("tbody", {}, ...linhas),
    el(
      "tfoot",
      {},
      el("tr", {}, el("th", { texto: "Dist." }), ...vertices.map((v) => el("td", { texto: String(porVertice[v].distancia) }))),
      el("tr", {}, el("th", { texto: "Pred." }), ...vertices.map((v) => el("td", { texto: exibir(porVertice[v].predecessor) }))),
    ),
  );
  const partes = [el("div", { classe: "folha-rolagem" }, tabelaIteracoes)];
  if (r.caminho_destino) {
    const rota = r.caminho_destino;
    partes.push(el("p", {
      texto: rota.alcancavel
        ? `Caminho até ${rota.destino}: ${rota.caminho.join(" → ")} (custo ${rota.custo})`
        : `${rota.destino} não é alcançável a partir de ${r.origem}.`,
    }));
  }
  return el("div", { classe: "folha" }, ...partes);
}

// Kruskal

function folhaKruskal(r) {
  const tabelaPassos = el(
    "table",
    { classe: "folha-tabela" },
    el("thead", {}, el("tr", {}, el("th", { texto: "Aresta" }), el("th", { texto: "Peso" }), el("th", { texto: "Decisão" }))),
    el("tbody", {}, ...r.passos.map((p) => el(
      "tr",
      {},
      el("td", { texto: `${p.origem} - ${p.destino}` }),
      el("td", { texto: String(p.peso) }),
      el("td", { texto: p.aceita ? "✓" : "✗ ciclo" }),
    ))),
  );
  const soma = r.arestas_selecionadas.map((a) => a.peso).join(" + ") || "0";
  return el(
    "div",
    { classe: "folha" },
    el("div", { classe: "folha-rolagem" }, tabelaPassos),
    el("p", { texto: `Selecionadas: ${r.arestas_selecionadas.map((a) => `${a.origem}-${a.destino}`).join(", ") || "nenhuma"}` }),
    el("p", {}, el("b", { texto: `Custo total: ${soma} = ${r.custo_total}` })),
  );
}

// Janela da folha

const SECOES_FOLHA = [
  ["dfs", "1. DFS", folhaDfs],
  ["bfs", "2. BFS", folhaBfs],
  ["dijkstra", "3. Dijkstra", folhaDijkstra],
  ["kruskal", "4. Kruskal", folhaKruskal],
];

async function preencherFolha() {
  const origem = $("#seletor-origem").value || null;
  const { vertices, arestas } = estado.estatisticas;
  const tipo = `${estado.grafo.direcionado ? "direcionado" : "não direcionado"}, ${estado.grafo.ponderado ? "ponderado" : "sem peso"}`;
  $("#folha-resumo").textContent = `${vertices} vértices | ${arestas} arestas | ${tipo} | origem ${origem}`;
  $("#folha-corpo").replaceChildren(el("p", { classe: "nota", texto: "Calculando..." }));

  const respostas = await Promise.allSettled(SECOES_FOLHA.map(([algoritmo]) => chamarApi(
    `/api/algoritmos/${algoritmo}`,
    { grafo: estado.grafo, origem, destino: $("#seletor-destino").value || null, grafo_id: estado.grafoSalvoId },
  )));
  estado.contadores.algoritmos += respostas.filter((r) => r.status === "fulfilled").length;
  salvarEstado();

  $("#folha-corpo").replaceChildren(...SECOES_FOLHA.map(([, titulo, desenhar], i) => {
    const resposta = respostas[i];
    // A tabela do Dijkstra cresce com o número de vértices, por isso ocupa a largura toda.
    return el(
      "section",
      { classe: i >= 2 ? "folha-secao larga" : "folha-secao" },
      el("h3", { texto: titulo }),
      ...(resposta.status === "fulfilled"
        ? [...resposta.value.avisos.map((texto) => el("p", { classe: "folha-aviso", texto })), desenhar(resposta.value)]
        : [el("p", { classe: "folha-aviso", texto: resposta.reason.message })]),
    );
  }));
}

function abrirFolha() {
  if (!estado.grafo.vertices.length) {
    avisar("Monte um grafo antes de abrir a folha de prova.", "erro");
    return;
  }
  $("#folha-janela").showModal();
  preencherFolha();
}

$("#botao-folha").addEventListener("click", abrirFolha);
$("#folha-atualizar").addEventListener("click", preencherFolha);
$("#folha-imprimir").addEventListener("click", () => window.print());
$("#folha-fechar").addEventListener("click", () => $("#folha-janela").close());
