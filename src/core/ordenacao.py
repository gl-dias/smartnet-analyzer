"""Ordenação por intercalação (merge sort) implementada do zero."""


def merge_sort(itens, chave=None):
    """Devolve uma nova lista ordenada, sem alterar a original.

    A ordenação é estável: itens com a mesma chave mantêm a ordem relativa de
    entrada. O Kruskal depende disso para desempatar pesos iguais de forma
    determinística.

    Complexidade:
        Tempo: O(n log n) em todos os casos. A lista é dividida ao meio
        (log n níveis) e cada nível intercala n itens no total. Recorrência:
        T(n) = 2T(n/2) + O(n).
        Espaço: O(n), por causa das listas auxiliares da intercalação.
    """
    obter_chave = chave if chave is not None else (lambda item: item)
    decorados = [(obter_chave(item), item) for item in itens]
    return [item for _, item in _ordenar(decorados)]


def _ordenar(itens):
    if len(itens) <= 1:
        return itens
    meio = len(itens) // 2
    return _intercalar(_ordenar(itens[:meio]), _ordenar(itens[meio:]))


def _intercalar(esquerda, direita):
    """Intercala duas listas ordenadas em O(len(esquerda) + len(direita))."""
    resultado = []
    i = j = 0
    while i < len(esquerda) and j < len(direita):
        # Só passa o item da direita quando ele é estritamente menor: é isso
        # que mantém a ordenação estável.
        if direita[j][0] < esquerda[i][0]:
            resultado.append(direita[j])
            j += 1
        else:
            resultado.append(esquerda[i])
            i += 1
    resultado.extend(esquerda[i:])
    resultado.extend(direita[j:])
    return resultado
