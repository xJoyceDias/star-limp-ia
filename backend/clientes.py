import sqlite3
from datetime import datetime

BANCO = "database/starlimp.db"

def buscar_cliente(nome):
    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, nome, telefone, saldo_fiado
        FROM clientes
        WHERE LOWER(nome) = LOWER(?)
    """, (nome,))

    cliente = cursor.fetchone()
    conexao.close()

    return cliente

def cadastrar_cliente(nome, telefone):
    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    data_cadastro = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO clientes (
            nome,
            telefone,
            saldo_fiado,
            data_cadastro
        )
        VALUES (?, ?, ?, ?)
    """, (
        nome,
        telefone,
        0,
        data_cadastro
    ))

    conexao.commit()
    conexao.close()

    print("Cliente cadastrado com sucesso!")

def listar_clientes():
    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, nome, telefone, saldo_fiado
        FROM clientes
        ORDER BY nome
    """)

    clientes = cursor.fetchall()
    conexao.close()

    print("\n===== CLIENTES CADASTRADOS =====\n")

    if not clientes:
        print("Nenhum cliente cadastrado.")
        return

    for cliente in clientes:
        print(f"ID: {cliente[0]}")
        print(f"Nome: {cliente[1]}")
        print(f"Telefone: {cliente[2]}")
        print(f"Saldo fiado: R$ {cliente[3]:.2f}")
        print("----------------------")

if __name__ == "__main__":
    print("1 - Cadastrar cliente")
    print("2 - Listar clientes")

    opcao = input("Escolha uma opção: ")

    if opcao == "1":
        nome = input("Nome do cliente: ")
        telefone = input("Telefone/WhatsApp: ")
        cadastrar_cliente(nome, telefone)

    elif opcao == "2":
        listar_clientes()

    else:
        print("Opção inválida.")