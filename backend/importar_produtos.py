import sqlite3
import pandas as pd

ARQUIVO_EXCEL = r"imports/Cópia de produtos.xls"
BANCO = r"database/starlimp.db"

def numero(valor):
    if valor is None:
        return 0

    texto = str(valor).strip()

    if texto == "" or texto.lower() == "nan":
        return 0

    return float(texto.replace(",", "."))

df = pd.read_excel(ARQUIVO_EXCEL)

conexao = sqlite3.connect(BANCO)
cursor = conexao.cursor()

cursor.execute("DELETE FROM produtos")

total_importados = 0

for _, linha in df.iterrows():

    cursor.execute("""
        INSERT INTO produtos (
            codigo,
            descricao,
            unidade,
            preco,
            situacao,
            estoque,
            preco_custo,
            fornecedor,
            marca,
            categoria
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(linha.get("ID", "")),
        str(linha.get("Código", "")),
        str(linha.get("Descrição", "")),
        str(linha.get("Unidade", "")),
        numero(linha.get("Preço")),
        str(linha.get("Situação", "")),
        numero(linha.get("Estoque")),
        numero(linha.get("Preço de custo")),
        str(linha.get("Fornecedor", "")),
        str(linha.get("Marca", "")),
        str(linha.get("Categoria do produto", ""))
    ))

    total_importados += 1

conexao.commit()
conexao.close()

print(f"Produtos importados com sucesso: {total_importados}")