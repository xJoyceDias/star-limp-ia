import sqlite3
import unicodedata

BANCO = r"database/starlimp.db"

def normalizar(texto):
    texto = str(texto).lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto

def buscar_produtos(termo):
    termo_normalizado = normalizar(termo)

    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT codigo, descricao, preco, categoria
        FROM produtos
    """)

    produtos = cursor.fetchall()
    conexao.close()

    resultados = []

    for codigo, descricao, preco, categoria in produtos:
        descricao_normalizada = normalizar(descricao)

        if termo_normalizado in descricao_normalizada:
            resultados.append({
                "codigo": codigo,
                "descricao": descricao,
                "preco": preco,
                "categoria": categoria
            })

    return resultados

if __name__ == "__main__":
    termo = input("Digite o produto que deseja buscar: ")

    encontrados = buscar_produtos(termo)

    print("\nProdutos encontrados:")

    if not encontrados:
        print("Nenhum produto encontrado.")
    else:
        for i, produto in enumerate(encontrados, start=1):
            print(f"\n{i}. {produto['descricao']}")
            print(f"   Código: {produto['codigo']}")
            print(f"   Preço: R$ {produto['preco']:.2f}")
            print(f"   Categoria: {produto['categoria']}")