import sqlite3

BANCO = "database/starlimp.db"

conexao = sqlite3.connect(BANCO)
cursor = conexao.cursor()

cursor.execute("""
SELECT
    forma_pagamento,
    COUNT(*),
    SUM(valor_total)
FROM vendas
GROUP BY forma_pagamento
""")

resultado = cursor.fetchall()

print("\n===== RELATÓRIO STAR LIMP =====\n")

total_geral = 0
quantidade_vendas = 0

for forma, qtd, valor in resultado:
    print(f"{forma.upper()}: R$ {valor:.2f} ({qtd} venda(s))")

    total_geral += valor
    quantidade_vendas += qtd

print("\n------------------------")
print(f"TOTAL GERAL: R$ {total_geral:.2f}")
print(f"QUANTIDADE DE VENDAS: {quantidade_vendas}")

conexao.close()