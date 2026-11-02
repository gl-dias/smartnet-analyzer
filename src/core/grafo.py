"""Lista de adjacência implementada do zero (sem bibliotecas de grafos)."""

import json
import math
import re
import unicodedata

TAMANHO_MAXIMO_NOME = 60


class ErroGrafo(ValueError):
    """Operação inválida sobre o grafo. A mensagem é exibida ao usuário."""


def chave_ordem(nome):
    """Chave da ordem alfabética dos vértices.

    Ignora maiúsculas e acentos e compara números pelo valor, assim "2" vem
    antes de "10" e "Água" vem antes de "Centro". O nome original entra por
    último para desempatar nomes como "a" e "A", que são vértices distintos.
    """
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", nome) if not unicodedata.combining(c)
    )
    partes = tuple(
        (0, int(parte), "") if parte.isdigit() else (1, 0, parte)
        for parte in re.findall(r"\d+|\D+", sem_acento.casefold())
    )
    return (partes, nome)


def normalizar_numero(valor):
    """Remove ruído de ponto flutuante e mostra 2.0 como 2."""
    if isinstance(valor, float):
        valor = round(valor, 10)
        if valor.is_integer():
            return int(valor)
    return valor


def _posicao_insercao(itens, alvo, chave_de):
    """Busca binária: primeira posição cuja chave não é menor que alvo. O(log n)."""
    inicio, fim = 0, len(itens)
    while inicio < fim:
        meio = (inicio + fim) // 2
        if chave_de(itens[meio]) < alvo:
            inicio = meio + 1
        else:
            fim = meio
    return inicio


class ListaAdjacencia:
    """Grafo guardado como dicionário vértice -> lista de tuplas (vizinho, peso).

    Convenções:
        Vizinhos e vértices ficam sempre em ordem alfabética (ver chave_ordem),
        o que torna DFS, BFS e Dijkstra determinísticos.
        Grafo sem peso usa peso 1 internamente; a exibição esconde esse valor.
        Grafo não direcionado guarda a aresta nos dois sentidos, mas ela conta
        como uma única aresta.
        Arestas duplicadas são rejeitadas.
        Self-loops são permitidos com aviso (ver avisos): não alteram o resultado
        de nenhum algoritmo e rejeitá-los impediria carregar um grafo válido.
        No sentido não direcionado, o self-loop é guardado uma única vez.

    Complexidade (V = vértices, E = arestas, d = grau do vértice):
        Espaço: O(V + E).
        adicionar_vertice: O(V), busca binária mais deslocamento na lista ordenada.
        adicionar_aresta: O(d), busca binária mais deslocamento na lista de vizinhos.
        remover_aresta: O(d), busca binária mais deslocamento.
        alterar_peso: O(log d), só busca binária, sem deslocar a lista.
        tem_aresta: O(log d).
        remover_vertice: O(V + E), precisa retirar o vértice das listas dos demais.
        vizinhos: O(d).
        arestas, para_dict, para_json: O(V + E).
    """

    def __init__(self, direcionado=False, ponderado=True):
        self.direcionado = direcionado
        self.ponderado = ponderado
        self._adjacencia = {}
        self._ordem_vertices = []
        self._total_arestas = 0
        self._total_lacos = 0

    # Consultas

    def vertices(self):
        """Vértices em ordem alfabética. O(V)."""
        return list(self._ordem_vertices)

    def numero_vertices(self):
        return len(self._ordem_vertices)

    def numero_arestas(self):
        return self._total_arestas

    def tem_vertice(self, vertice):
        return vertice in self._adjacencia

    def tem_aresta(self, origem, destino):
        return (
            origem in self._adjacencia
            and destino in self._adjacencia
            and self._localizar(origem, destino) >= 0
        )

    def vizinhos(self, vertice):
        """Cópia da lista de tuplas (vizinho, peso) do vértice. O(d)."""
        self._exigir_vertice(vertice)
        return list(self._adjacencia[vertice])

    def arestas(self):
        """Lista de tuplas (origem, destino, peso), cada aresta uma única vez. O(V + E)."""
        indice = {v: i for i, v in enumerate(self._ordem_vertices)}
        resultado = []
        for origem in self._ordem_vertices:
            for destino, peso in self._adjacencia[origem]:
                if self.direcionado or indice[origem] <= indice[destino]:
                    resultado.append((origem, destino, peso))
        return resultado

    def densidade(self):
        """Fração das arestas possíveis que existem, sem contar self-loops."""
        v = len(self._ordem_vertices)
        if v < 2:
            return 0
        possiveis = v * (v - 1) if self.direcionado else v * (v - 1) / 2
        return normalizar_numero(round((self._total_arestas - self._total_lacos) / possiveis, 4))

    def avisos(self):
        """Observações sobre o grafo atual que o usuário precisa saber."""
        if not self._total_lacos:
            return []
        lacos = [v for v in self._ordem_vertices if self._localizar(v, v) >= 0]
        return [
            f"Self-loop em {', '.join(lacos)}: uma via de um bairro para ele mesmo é "
            "aceita, mas não altera o resultado de nenhum algoritmo."
        ]

    # Alterações

    def adicionar_vertice(self, vertice):
        vertice = self._normalizar_nome(vertice)
        if vertice in self._adjacencia:
            raise ErroGrafo(f"O vértice {vertice} já existe.")
        self._inserir_vertice(vertice)
        return vertice

    def remover_vertice(self, vertice):
        self._exigir_vertice(vertice)
        lista = self._adjacencia[vertice]
        removidas = len(lista)
        if self._localizar(vertice, vertice) >= 0:
            self._total_lacos -= 1
        if self.direcionado:
            for outro in self._ordem_vertices:
                posicao = -1 if outro == vertice else self._localizar(outro, vertice)
                if posicao >= 0:
                    del self._adjacencia[outro][posicao]
                    removidas += 1
        else:
            for vizinho, _ in lista:
                if vizinho != vertice:
                    del self._adjacencia[vizinho][self._localizar(vizinho, vertice)]
        del self._adjacencia[vertice]
        del self._ordem_vertices[
            _posicao_insercao(self._ordem_vertices, chave_ordem(vertice), chave_ordem)
        ]
        self._total_arestas -= removidas

    def adicionar_aresta(self, origem, destino, peso=1):
        """Adiciona a aresta, criando os vértices que ainda não existem."""
        origem = self._normalizar_nome(origem)
        destino = self._normalizar_nome(destino)
        peso = self._normalizar_peso(peso)
        if self.tem_aresta(origem, destino):
            seta = "->" if self.direcionado else "<->"
            raise ErroGrafo(f"A aresta {origem} {seta} {destino} já existe.")
        for vertice in (origem, destino):
            if vertice not in self._adjacencia:
                self._inserir_vertice(vertice)
        self._inserir_vizinho(origem, destino, peso)
        if origem == destino:
            self._total_lacos += 1
        elif not self.direcionado:
            self._inserir_vizinho(destino, origem, peso)
        self._total_arestas += 1

    def remover_aresta(self, origem, destino):
        self._exigir_aresta(origem, destino)
        del self._adjacencia[origem][self._localizar(origem, destino)]
        if origem == destino:
            self._total_lacos -= 1
        elif not self.direcionado:
            del self._adjacencia[destino][self._localizar(destino, origem)]
        self._total_arestas -= 1

    def alterar_peso(self, origem, destino, peso):
        if not self.ponderado:
            raise ErroGrafo("Este grafo não tem pesos. Ative a opção Ponderado primeiro.")
        self._exigir_aresta(origem, destino)
        peso = self._normalizar_peso(peso)
        self._adjacencia[origem][self._localizar(origem, destino)] = (destino, peso)
        if origem != destino and not self.direcionado:
            self._adjacencia[destino][self._localizar(destino, origem)] = (origem, peso)

    # Conversões

    def para_dict(self):
        """Estrutura para exibição: {vértice: [{vizinho, peso}, ...]}. Sem peso se não ponderado."""
        return {
            vertice: [
                {"vizinho": vizinho, "peso": peso} if self.ponderado else {"vizinho": vizinho}
                for vizinho, peso in self._adjacencia[vertice]
            ]
            for vertice in self._ordem_vertices
        }

    def para_json(self):
        """Representação no mesmo formato aceito por from_json."""
        return {
            "direcionado": self.direcionado,
            "ponderado": self.ponderado,
            "vertices": self.vertices(),
            "arestas": [
                {"origem": origem, "destino": destino, "peso": peso}
                if self.ponderado
                else {"origem": origem, "destino": destino}
                for origem, destino, peso in self.arestas()
            ],
        }

    @classmethod
    def from_json(cls, dados):
        """Constrói o grafo a partir de um dict ou texto JSON.

        Formato: {direcionado, ponderado, vertices: [...], arestas: [{origem, destino, peso}]}.
        O peso é ignorado quando ponderado é falso. O(V² + E * d) no pior caso, por
        manter as listas ordenadas durante a construção.
        """
        if isinstance(dados, str):
            try:
                dados = json.loads(dados)
            except json.JSONDecodeError as erro:
                raise ErroGrafo(f"JSON inválido: {erro.msg}.") from erro
        if not isinstance(dados, dict):
            raise ErroGrafo("O grafo deve ser um objeto JSON.")

        direcionado = dados.get("direcionado", False)
        ponderado = dados.get("ponderado", True)
        if not isinstance(direcionado, bool) or not isinstance(ponderado, bool):
            raise ErroGrafo("Os campos direcionado e ponderado devem ser verdadeiro ou falso.")
        vertices = dados.get("vertices", [])
        arestas = dados.get("arestas", [])
        if not isinstance(vertices, list) or not isinstance(arestas, list):
            raise ErroGrafo("Os campos vertices e arestas devem ser listas.")

        grafo = cls(direcionado=direcionado, ponderado=ponderado)
        for vertice in vertices:
            grafo.adicionar_vertice(vertice)
        for aresta in arestas:
            if not isinstance(aresta, dict) or "origem" not in aresta or "destino" not in aresta:
                raise ErroGrafo("Cada aresta precisa ter os campos origem e destino.")
            if ponderado and "peso" not in aresta:
                raise ErroGrafo(f"A aresta {aresta['origem']} e {aresta['destino']} está sem peso.")
            grafo.adicionar_aresta(aresta["origem"], aresta["destino"], aresta.get("peso", 1))
        return grafo

    # Apoio interno

    def _inserir_vertice(self, vertice):
        posicao = _posicao_insercao(self._ordem_vertices, chave_ordem(vertice), chave_ordem)
        self._ordem_vertices.insert(posicao, vertice)
        self._adjacencia[vertice] = []

    def _inserir_vizinho(self, vertice, vizinho, peso):
        lista = self._adjacencia[vertice]
        posicao = _posicao_insercao(lista, chave_ordem(vizinho), lambda item: chave_ordem(item[0]))
        lista.insert(posicao, (vizinho, peso))

    def _localizar(self, vertice, vizinho):
        """Posição de vizinho na lista de vertice, ou -1 se não estiver lá. O(log d)."""
        lista = self._adjacencia[vertice]
        posicao = _posicao_insercao(lista, chave_ordem(vizinho), lambda item: chave_ordem(item[0]))
        if posicao < len(lista) and lista[posicao][0] == vizinho:
            return posicao
        return -1

    def _exigir_vertice(self, vertice):
        if vertice not in self._adjacencia:
            raise ErroGrafo(f"O vértice {vertice} não existe.")

    def _exigir_aresta(self, origem, destino):
        self._exigir_vertice(origem)
        self._exigir_vertice(destino)
        if self._localizar(origem, destino) < 0:
            seta = "->" if self.direcionado else "<->"
            raise ErroGrafo(f"A aresta {origem} {seta} {destino} não existe.")

    @staticmethod
    def _normalizar_nome(nome):
        if isinstance(nome, int) and not isinstance(nome, bool):
            nome = str(nome)
        if not isinstance(nome, str):
            raise ErroGrafo("O nome de um vértice deve ser um texto.")
        nome = " ".join(nome.split())
        if not nome:
            raise ErroGrafo("O nome do vértice não pode ficar vazio.")
        if len(nome) > TAMANHO_MAXIMO_NOME:
            raise ErroGrafo(f"O nome do vértice aceita no máximo {TAMANHO_MAXIMO_NOME} caracteres.")
        return nome

    def _normalizar_peso(self, peso):
        if not self.ponderado:
            return 1
        if isinstance(peso, bool) or not isinstance(peso, (int, float)):
            raise ErroGrafo(f"O peso {peso!r} não é um número.")
        try:
            finito = math.isfinite(peso)
        except OverflowError:
            finito = False
        if not finito:
            raise ErroGrafo("O peso precisa ser um número finito.")
        return normalizar_numero(peso)
