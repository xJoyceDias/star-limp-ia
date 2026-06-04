import sqlite3
import unicodedata

BANCO = "database/starlimp.db"

def normalizar(texto):
    texto = str(texto).lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(
        c for c in texto
        if unicodedata.category(c) != "Mn"
    )
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

print("\n===== EXTRATO DO CLIENTE =====\n")

nome = input("Nome do cliente: ")

cliente = buscar_cliente(nome)

if not cliente:
    print("Cliente não encontrado.")
    exit()

cliente_id = cliente[0]
cliente_nome = cliente[1]
telefone = cliente[2]
saldo = cliente[3]

conexao = sqlite3.connect(BANCO)
cursor = conexao.cursor()

print(f"\nCliente: {cliente_nome}")
print(f"Telefone: {telefone}")

print("\n===== COMPRAS FIADO =====\n")

cursor.execute("""
    SELECT
        data_hora,
        valor_compra,
        retirado_por
    FROM fiados
    WHERE cliente_id = ?
    ORDER BY data_hora
""", (cliente_id,))

compras = cursor.fetchall()

if not compras:
    print("Nenhuma compra encontrada.")
else:
    for compra in compras:
        print(f"Data: {compra[0]}")
        print(f"Valor: R$ {compra[1]:.2f}")
        print(f"Retirado por: {compra[2]}")
        print("----------------------")

print("\n===== PAGAMENTOS =====\n")

cursor.execute("""
    SELECT
        data_hora,
        valor
    FROM pagamentos
    WHERE cliente_id = ?
    ORDER BY data_hora
""", (cliente_id,))

pagamentos = cursor.fetchall()

if not pagamentos:
    print("Nenhum pagamento encontrado.")
else:
    for pagamento in pagamentos:
        print(f"Data: {pagamento[0]}")
        print(f"Pagamento: R$ {pagamento[1]:.2f}")
        print("----------------------")

print(f"\nSALDO ATUAL: R$ {saldo:.2f}")

conexao.close()