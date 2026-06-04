import sqlite3
import unicodedata
from datetime import datetime

BANCO = "database/starlimp.db"

def normalizar(texto):
    texto = str(texto).lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto

def buscar_cliente(nome):
    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, nome, telefone, saldo_fiado
        FROM clientes
    """)

    clientes = cursor.fetchall()
    conexao.close()

    nome_normalizado = normalizar(nome)

    for cliente in clientes:
        if normalizar(cliente[1]) == nome_normalizado:
            return cliente

    return None

def atualizar_saldo(cliente_id, novo_saldo):
    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("""
        UPDATE clientes
        SET saldo_fiado = ?
        WHERE id = ?
    """, (
        novo_saldo,
        cliente_id
    ))

    conexao.commit()
    conexao.close()

def registrar_pagamento(cliente_id, valor_pago):
    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO pagamentos (
            cliente_id,
            valor,
            data_hora
        )
        VALUES (?, ?, ?)
    """, (
        cliente_id,
        valor_pago,
        data_hora
    ))

    conexao.commit()
    conexao.close()

print("\n===== RECEBIMENTO DE FIADO =====\n")

nome = input("Nome do cliente: ")

cliente = buscar_cliente(nome)

if not cliente:
    print("Cliente não encontrado.")
    exit()

cliente_id = cliente[0]
cliente_nome = cliente[1]
saldo_atual = cliente[3] or 0

print(f"\nCliente: {cliente_nome}")
print(f"Saldo atual: R$ {saldo_atual:.2f}")

valor_pago = float(
    input("\nValor recebido: ").replace(",", ".")
)

novo_saldo = saldo_atual - valor_pago

if novo_saldo < 0:
    novo_saldo = 0

atualizar_saldo(cliente_id, novo_saldo)
registrar_pagamento(cliente_id, valor_pago)

print("\n✅ Pagamento registrado!")

print(f"\nSaldo anterior: R$ {saldo_atual:.2f}")
print(f"Pagamento: R$ {valor_pago:.2f}")
print(f"Saldo atual: R$ {novo_saldo:.2f}")

if novo_saldo == 0:
    print("\n🎉 Cliente quitou toda a dívida!")