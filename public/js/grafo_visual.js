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

class GrafoVisual {
  constructor(container) {
    this.temporizadores = [];
    this.grafo = null;
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
        font: { color: "#e4e9f0", size: 14, strokeWidth: 5, strokeColor: "#11151b" },
        width: 2,
      },
      physics: false,
      interaction: { hover: true },
    });
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
    const arestasNovas = grafo.arestas.map((a) => ({
      id: this.idAresta(a.origem, a.destino),
      from: a.origem,
      to: a.destino,
      label: grafo.ponderado ? String(a.peso) : "",
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
