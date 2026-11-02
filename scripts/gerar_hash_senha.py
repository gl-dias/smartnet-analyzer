"""Pede uma senha no terminal e imprime o hash bcrypt para a variável APP_SENHA_HASH."""

import getpass
import sys

import bcrypt

TAMANHO_MINIMO = 8
TAMANHO_MAXIMO_BYTES = 72


def gerar_hash(senha):
    if len(senha) < TAMANHO_MINIMO:
        raise ValueError(f"A senha precisa ter ao menos {TAMANHO_MINIMO} caracteres.")
    if len(senha.encode()) > TAMANHO_MAXIMO_BYTES:
        raise ValueError(f"A senha aceita no máximo {TAMANHO_MAXIMO_BYTES} bytes (limite do bcrypt).")
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def main():
    senha = getpass.getpass("Senha: ")
    if senha != getpass.getpass("Repita a senha: "):
        sys.exit("As senhas não coincidem.")
    try:
        print(gerar_hash(senha))
    except ValueError as erro:
        sys.exit(str(erro))


if __name__ == "__main__":
    main()
