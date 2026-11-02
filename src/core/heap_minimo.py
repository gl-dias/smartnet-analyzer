"""Min-heap binário implementado do zero, usado como fila de prioridade no Dijkstra."""


class HeapMinimo:
    """Árvore binária completa guardada em um vetor.

    Para o índice i: pai em (i - 1) // 2, filhos em 2i + 1 e 2i + 2. Todo pai é
    menor ou igual aos filhos, logo o menor item está sempre no índice 0.

    Complexidade (n = itens no heap):
        inserir: O(log n), sobe no máximo a altura da árvore.
        extrair_minimo: O(log n), desce no máximo a altura da árvore.
        minimo, esta_vazio, __len__: O(1).
        Espaço: O(n).
    """

    def __init__(self):
        self._itens = []

    def __len__(self):
        return len(self._itens)

    def esta_vazio(self):
        return not self._itens

    def minimo(self):
        if not self._itens:
            raise IndexError("O heap está vazio.")
        return self._itens[0]

    def inserir(self, item):
        self._itens.append(item)
        self._subir(len(self._itens) - 1)

    def extrair_minimo(self):
        if not self._itens:
            raise IndexError("O heap está vazio.")
        menor = self._itens[0]
        ultimo = self._itens.pop()
        if self._itens:
            self._itens[0] = ultimo
            self._descer(0)
        return menor

    def _subir(self, indice):
        while indice > 0:
            pai = (indice - 1) // 2
            if not self._itens[indice] < self._itens[pai]:
                break
            self._trocar(indice, pai)
            indice = pai

    def _descer(self, indice):
        tamanho = len(self._itens)
        while True:
            menor = indice
            for filho in (2 * indice + 1, 2 * indice + 2):
                if filho < tamanho and self._itens[filho] < self._itens[menor]:
                    menor = filho
            if menor == indice:
                break
            self._trocar(indice, menor)
            indice = menor

    def _trocar(self, i, j):
        self._itens[i], self._itens[j] = self._itens[j], self._itens[i]
