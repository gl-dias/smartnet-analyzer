// Desenho do grafo com vis-network e animação dos resultados dos algoritmos.

const CORES = {
  no: { background: "#222a34", border: "#4aa8ff" },
  visitado: { background: "#1d4f7d", border: "#4aa8ff" },
  atual: { background: "#e0a93b", border: "#ffd27a" },
  aresta: "#5a6778",
  destaque: "#4aa8ff",
  caminho: "#3fb96f",
  rejeitada: "#d9434a",
  apagada: "#333c48",
};
const INTERVALO_ANIMACAO_MS = 550;

const PESO = {
  fonte: "14px arial",
  cor: "#e4e9f0",
  contorno: "#11151b",
  // Pontos da aresta em que o peso pode ficar, do preferido ao último recurso.
  fracoes: [0.5, 0.42, 0.58, 0.34, 0.66, 0.26, 0.74],
  // Distância mínima, em pixels, até um vértice que não é extremo da aresta.
  folgaVertice: 34,
  custoSobreposicao: 1000,
  custoOutraAresta: 40,
  custoProximidade: 3,
  custoForaDoCentro: 20,
};

function distanciaAoSegmento(p, a, b) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const comprimento = dx * dx + dy * dy;
  const t = comprimento ? Math.min(1, Math.max(0, ((p.x - a.x) * dx + (p.y - a.y) * dy) / comprimento)) : 0;
  return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy));
}

function pontoNaAresta(aresta, fracao) {
  if (aresta.fromId !== aresta.toId) return aresta.edgeType.getPoint(fracao);
  // Laço: o peso fica na parte externa do círculo, que o vis-network desenha a 45° acima do vértice.
  const { x, y, shape } = aresta.from;
  const distancia = (Math.max(shape.width, shape.height) / 2 + 2 * aresta.options.selfReference.size) * Math.SQRT1_2;
  return { x: x + distancia, y: y - distancia };
}

class GrafoVisual {
  constructor(container) {
    this.temporizadores = [];
    this.grafo = null;
    this.pesos = new Map();
    this.rotulosPeso = [];
    this.chaveRotulos = null;
    this.disponivel = Boolean(window.vis);
    this.container = container;
    if (!this.disponivel) {
      this.mostrarMensagem("Não foi possível carregar o desenho do grafo (verifique a internet). Todo o restante funciona normalmente.");
      return;
    }
    this.nos = new vis.DataSet();
    this.arestas = new vis.DataSet();
    this.rede = new vis.Network(container, { nodes: this.nos, edges: this.arestas }, {
      nodes: {
        shape: "circle",
        margin: 10,
        borderWidth: 2,
        color: CORES.no,
        font: { color: "#e4e9f0", size: 15 },
      },
      edges: {
        color: { color: CORES.aresta, highlight: CORES.destaque, hover: CORES.destaque },
        width: 2,
      },
      physics: false,
      interaction: { hover: true },
    });
    this.rede.on("afterDrawing", (ctx) => this.desenharPesos(ctx));
  }

  // O vis-network fixa o rótulo no ponto médio da aresta, então duas arestas que se cruzam ao meio
  // teriam os pesos empilhados. Por isso os pesos são desenhados aqui, cada um no ponto da própria
  // aresta que não encosta em outro peso, em outra aresta nem em um vértice alheio.
  posicionarPesos(ctx) {
    const posicoes = this.rede.getPositions();
    const arestasDesenhadas = this.rede.body.edges;
    const chave = JSON.stringify([posicoes, [...this.pesos], Object.keys(arestasDesenhadas)]);
    // Só recalcula quando algo mudou de lugar: durante a animação os pesos não saltam.
    if (chave === this.chaveRotulos) return;
    this.chaveRotulos = chave;

    const nos = Object.keys(posicoes).map((id) => {
      const caixa = this.rede.getBoundingBox(id);
      const raio = Math.max(caixa.right - caixa.left, caixa.bottom - caixa.top) / 2;
      return { id, ...posicoes[id], raio };
    });
    const arestas = [...this.pesos.keys()].filter((id) => arestasDesenhadas[id]).map((id) => {
      const aresta = arestasDesenhadas[id];
      const tracado = aresta.fromId === aresta.toId
        ? [] // O círculo do laço fica colado no vértice, que já é evitado.
        : Array.from({ length: 9 }, (_, i) => aresta.edgeType.getPoint(i / 8));
      return { id, aresta, tracado };
    });

    this.rotulosPeso = [];
    arestas.forEach(({ id, aresta }) => {
      const texto = this.pesos.get(id);
      const raio = Math.hypot(ctx.measureText(texto).width, 14) / 2 + 3;
      const candidatos = PESO.fracoes.map((fracao) => {
        const ponto = pontoNaAresta(aresta, fracao);
        const custo = this.custoDoPeso(ponto, raio, fracao, aresta, nos, arestas);
        return { texto, raio, x: ponto.x, y: ponto.y, custo };
      });
      this.rotulosPeso.push(candidatos.reduce((melhor, c) => (c.custo < melhor.custo ? c : melhor)));
    });
  }

  custoDoPeso(ponto, raio, fracao, aresta, nos, arestas) {
    let custo = Math.abs(fracao - 0.5) * PESO.custoForaDoCentro;
    this.rotulosPeso.forEach((outro) => {
      if (Math.hypot(ponto.x - outro.x, ponto.y - outro.y) < raio + outro.raio) custo += PESO.custoSobreposicao;
    });
    nos.forEach((no) => {
      const vao = Math.hypot(ponto.x - no.x, ponto.y - no.y) - no.raio - raio;
      if (vao < 0) custo += PESO.custoSobreposicao;
      const extremo = no.id === String(aresta.fromId) || no.id === String(aresta.toId);
      if (!extremo && vao < PESO.folgaVertice) custo += (PESO.folgaVertice - vao) * PESO.custoProximidade;
    });
    arestas.forEach((outra) => {
      if (outra.aresta === aresta) return;
      const cruza = outra.tracado.slice(1).some((p, i) => distanciaAoSegmento(ponto, outra.tracado[i], p) < raio);
      if (cruza) custo += PESO.custoOutraAresta;
    });
    return custo;
  }

  desenharPesos(ctx) {
    if (!this.pesos.size) return;
    ctx.save();
    ctx.font = PESO.fonte;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.lineJoin = "round";
    ctx.lineWidth = 5;
    ctx.strokeStyle = PESO.contorno;
    ctx.fillStyle = PESO.cor;
    this.posicionarPesos(ctx);
    this.rotulosPeso.forEach(({ texto, x, y }) => {
      ctx.strokeText(texto, x, y);
      ctx.fillText(texto, x, y);
    });
    ctx.restore();
  }

  // Layout circular, na ordem alfabética: o desenho é sempre o mesmo para o mesmo grafo e,
  // com os vértices em posição convexa, nenhuma aresta passa por cima de outro vértice.
  posicoesEmCirculo(vertices) {
    const fator = Math.max(1, (vertices.length * 70) / (2 * Math.PI * 180));
    const raioX = Math.max(this.container.clientWidth / 2 - 60, 180) * fator;
    const raioY = Math.max(this.container.clientHeight / 2 - 50, 150) * fator;
    return Object.fromEntries(vertices.map((v, i) => {
      const angulo = -Math.PI / 2 + (2 * Math.PI * i) / vertices.length;
      return [v, { x: raioX * Math.cos(angulo), y: raioY * Math.sin(angulo) }];
    }));
  }

  mostrarMensagem(texto) {
    const aviso = document.createElement("div");
    aviso.className = "mapa-vazio";
    aviso.textContent = texto;
    this.container.replaceChildren(aviso);
  }

  idAresta(origem, destino) {
    return JSON.stringify([origem, destino]);
  }

  // Aresta guardada entre dois vértices. Em grafo não direcionado, o sentido não importa.
  localizarAresta(origem, destino) {
    const id = this.idAresta(origem, destino);
    if (this.arestas.get(id)) return id;
    const inverso = this.idAresta(destino, origem);
    if (!this.grafo.direcionado && this.arestas.get(inverso)) return inverso;
    return null;
  }

  atualizar(grafo, vertices) {
    this.cancelarAnimacao();
    this.grafo = grafo;
    if (!this.disponivel) return;

    const idsNos = new Set(vertices);
    // Só reposiciona quando o conjunto de vértices muda, para respeitar o que o usuário arrastou.
    const verticesMudaram =
      this.nos.getIds().some((id) => !idsNos.has(id)) || vertices.some((v) => !this.nos.get(v));
    const posicoes = verticesMudaram ? this.posicoesEmCirculo(vertices) : {};
    const nosNovos = vertices.map((v) => ({ id: v, label: v, color: CORES.no, ...posicoes[v] }));
    this.pesos = new Map(grafo.ponderado
      ? grafo.arestas.map((a) => [this.idAresta(a.origem, a.destino), String(a.peso)])
      : []);
    const arestasNovas = grafo.arestas.map((a) => ({
      id: this.idAresta(a.origem, a.destino),
      from: a.origem,
      to: a.destino,
      arrows: grafo.direcionado ? "to" : "",
      smooth: grafo.direcionado ? { enabled: true, type: "curvedCW", roundness: 0.12 } : { enabled: false },
      color: { color: CORES.aresta },
      width: 2,
      dashes: false,
    }));

    const idsArestas = new Set(arestasNovas.map((a) => a.id));
    this.arestas.remove(this.arestas.getIds().filter((id) => !idsArestas.has(id)));
    this.nos.remove(this.nos.getIds().filter((id) => !idsNos.has(id)));
    this.nos.update(nosNovos);
    this.arestas.update(arestasNovas);

    if (verticesMudaram && vertices.length) this.rede.fit({ animation: { duration: 300 } });
  }

  limparDestaque() {
    this.cancelarAnimacao();
    if (!this.disponivel || !this.grafo) return;
    this.nos.update(this.nos.getIds().map((id) => ({ id, label: id, color: CORES.no })));
    this.arestas.update(this.arestas.getIds().map((id) => ({
      id, color: { color: CORES.aresta }, width: 2, dashes: false,
    })));
  }

  destacarVertice(vertice) {
    if (this.disponivel && this.nos.get(vertice)) this.rede.selectNodes([vertice]);
  }

  removerSelecao() {
    if (this.disponivel) this.rede.unselectAll();
  }

  cancelarAnimacao() {
    this.temporizadores.forEach(clearTimeout);
    this.temporizadores = [];
  }

  executarEmSequencia(etapas) {
    etapas.forEach((etapa, i) => {
      this.temporizadores.push(setTimeout(etapa, i * INTERVALO_ANIMACAO_MS));
    });
  }

  pintarNo(vertice, cor, rotulo) {
    const alteracao = { id: vertice, color: cor };
    if (rotulo !== undefined) alteracao.label = rotulo;
    this.nos.update(alteracao);
  }

  pintarAresta(origem, destino, cor, largura = 4, dashes = false) {
    const id = this.localizarAresta(origem, destino);
    if (id) this.arestas.update({ id, color: { color: cor }, width: largura, dashes });
  }

  animar(resultado) {
    if (!this.disponivel) return;
    this.limparDestaque();
    if (resultado.algoritmo === "dfs" || resultado.algoritmo === "bfs") this.animarBusca(resultado);
    if (resultado.algoritmo === "dijkstra") this.animarDijkstra(resultado);
    if (resultado.algoritmo === "kruskal") this.animarKruskal(resultado);
  }

  // Numera os vértices na ordem de visita e pinta as arestas da árvore de busca.
  animarBusca(resultado) {
    const predecessores = {};
    resultado.tabela.forEach((linha) => { predecessores[linha.vertice] = linha.predecessor; });
    let anterior = null;
    const etapas = resultado.ordem_visita.map((vertice, i) => () => {
      if (anterior !== null) this.pintarNo(anterior, CORES.visitado);
      this.pintarNo(vertice, CORES.atual, `${vertice}\n#${i + 1}`);
      if (predecessores[vertice] !== null) {
        this.pintarAresta(predecessores[vertice], vertice, CORES.destaque);
      }
      anterior = vertice;
    });
    etapas.push(() => { if (anterior !== null) this.pintarNo(anterior, CORES.visitado); });
    this.executarEmSequencia(etapas);
  }

  // Mostra a árvore de caminhos mínimos e, havendo destino, realça a rota até ele.
  animarDijkstra(resultado) {
    const alcancados = resultado.tabela.filter((linha) => linha.distancia !== "∞");
    const etapas = alcancados.map((linha) => () => {
      this.pintarNo(linha.vertice, CORES.visitado, `${linha.vertice}\nd=${linha.distancia}`);
      if (linha.predecessor !== null) {
        this.pintarAresta(linha.predecessor, linha.vertice, CORES.destaque);
      }
    });
    const rota = resultado.caminho_destino;
    if (rota && rota.alcancavel) {
      etapas.push(() => {
        rota.caminho.forEach((vertice, i) => {
          this.pintarNo(vertice, CORES.atual);
          if (i > 0) this.pintarAresta(rota.caminho[i - 1], vertice, CORES.caminho, 6);
        });
      });
    }
    this.executarEmSequencia(etapas);
  }

  // Percorre as arestas em ordem de peso: as aceitas ficam verdes, as rejeitadas apagam.
  animarKruskal(resultado) {
    const etapas = [];
    resultado.passos.forEach((passo) => {
      if (passo.aceita) {
        etapas.push(() => {
          this.pintarAresta(passo.origem, passo.destino, CORES.caminho, 5);
          this.pintarNo(passo.origem, CORES.visitado);
          this.pintarNo(passo.destino, CORES.visitado);
        });
      } else {
        etapas.push(() => {
          this.pintarAresta(passo.origem, passo.destino, CORES.rejeitada, 3, true);
        });
        etapas.push(() => {
          this.pintarAresta(passo.origem, passo.destino, CORES.apagada, 1, true);
        });
      }
    });
    this.executarEmSequencia(etapas);
  }
}

window.GrafoVisual = GrafoVisual;
