"""Funções de apoio compartilhadas pelos algoritmos de busca e caminho."""

from src.core.grafo import ErroGrafo


def exigir_vertices(grafo, origem, destino=None):
    """Valida a origem (obrigatória) e o destino (opcional) antes de executar."""
    if origem is None or origem == "":
        raise ErroGrafo("Escolha um vértice de origem.")
    if not grafo.tem_vertice(origem):
        raise ErroGrafo(f"O vértice de origem {origem} não existe no grafo.")
    if destino is not None and not grafo.tem_vertice(destino):
        raise ErroGrafo(f"O vértice de destino {destino} não existe no grafo.")


def reconstruir_caminho(predecessores, destino):
    """Caminho da origem até destino, seguindo os predecessores. O(V)."""
    caminho = []
    atual = destino
    while atual is not None:
        caminho.append(atual)
        atual = predecessores[atual]
    caminho.reverse()
    return caminho
