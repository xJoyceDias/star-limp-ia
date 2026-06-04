import sqlite3

BANCO = "database/starlimp.db"

conexao = sqlite3.connect(BANCO)
cursor = conexao.cursor()

cursor.execute("""
SELECT
    nome,
    telefone,
    saldo_fiado
FROM clientes
WHERE saldo_fiado > 0
ORDER BY nome
""")

clientes = cursor.fetchall()

print("\n===== FIADOS EM ABERTO =====\n")

total_a_receber = 0

if not clientes:
    print("Nenhum fiado em aberto.")
else:
    for cliente in clientes:
        nome = cliente[0]
        telefone = cliente[1]
        saldo = cliente[2] or 0

        print(f"Cliente: {nome}")
        print(f"Telefone: {telefone}")
        print(f"Saldo em aberto: R$ {saldo:.2f}")
        print("----------------------")

        total_a_receber += saldo

print(f"\nTOTAL A RECEBER: R$ {total_a_receber:.2f}")

conexao.close()