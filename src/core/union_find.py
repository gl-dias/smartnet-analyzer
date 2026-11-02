"""Union-Find (conjuntos disjuntos) implementado do zero, usado no Kruskal."""


class UnionFind:
    """Floresta de conjuntos com compressão de caminho e união por rank.

    Complexidade:
        criar: O(n).
        encontrar e unir: O(α(n)) amortizado, em que α é a inversa da função de
        Ackermann (na prática, no máximo 4 para qualquer entrada real).
        Espaço: O(n).
    """

    def __init__(self, elementos):
        self._pai = {elemento: elemento for elemento in elementos}
        self._rank = {elemento: 0 for elemento in self._pai}
        self.total_conjuntos = len(self._pai)

    def encontrar(self, elemento):
        """Devolve o representante do conjunto e comprime o caminho percorrido."""
        raiz = elemento
        while self._pai[raiz] != raiz:
            raiz = self._pai[raiz]
        while self._pai[elemento] != raiz:
            self._pai[elemento], elemento = raiz, self._pai[elemento]
        return raiz

    def unir(self, a, b):
        """Une os conjuntos de a e b. Devolve False se já estavam no mesmo conjunto."""
        raiz_a = self.encontrar(a)
        raiz_b = self.encontrar(b)
        if raiz_a == raiz_b:
            return False
        if self._rank[raiz_a] < self._rank[raiz_b]:
            raiz_a, raiz_b = raiz_b, raiz_a
        self._pai[raiz_b] = raiz_a
        if self._rank[raiz_a] == self._rank[raiz_b]:
            self._rank[raiz_a] += 1
        self.total_conjuntos -= 1
        return True
