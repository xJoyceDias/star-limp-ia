import sqlite3
import unicodedata
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

app = FastAPI()

templates = Jinja2Templates(directory="backend/templates")
BANCO = "database/starlimp.db"


def normalizar(texto):
    texto = str(texto).lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


def buscar_produtos_banco(termo):
    termo_normalizado = normalizar(termo)
    palavras = termo_normalizado.split()

    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT codigo, descricao, preco, categoria
        FROM produtos
    """)

    produtos = cursor.fetchall()
    conexao.close()

    encontrados = []

    for codigo, descricao, preco, categoria in produtos:
        descricao_normalizada = normalizar(descricao)
        pontos = 0

        for palavra in palavras:
            if palavra in descricao_normalizada:
                pontos += 1

        if pontos > 0:
            encontrados.append({
                "codigo": codigo,
                "descricao": descricao,
                "preco": preco,
                "categoria": categoria,
                "pontos": pontos
            })

    encontrados = sorted(
        encontrados,
        key=lambda produto: produto["pontos"],
        reverse=True
    )

    return encontrados[:5]

@app.get("/")
def inicio(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html"
    )
@app.get("/nova-venda")
def nova_venda(request: Request):
    return templates.TemplateResponse(
        request,
        "nova_venda.html"
    )    
@app.get("/buscar-produtos")
def buscar_produtos(termo: str):
    return buscar_produtos_banco(termo)
from fastapi import Body

@app.post("/finalizar-venda")
def finalizar_venda(dados: dict = Body(...)):
    from datetime import datetime

    itens = dados.get("itens", [])
    total = dados.get("total", 0)
    forma_pagamento = dados.get("forma_pagamento", "")

    if not itens:
        return {
            "sucesso": False,
            "mensagem": "Nenhum produto foi adicionado à venda."
        }

    data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("""
        INSERT INTO vendas (data_hora, valor_total, forma_pagamento)
        VALUES (?, ?, ?)
    """, (data_hora, total, forma_pagamento))

    venda_id = cursor.lastrowid

    for item in itens:
        cursor.execute("""
            INSERT INTO itens_venda (
                venda_id,
                codigo_produto,
                descricao,
                quantidade,
                preco_unitario,
                subtotal
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            venda_id,
            item.get("codigo"),
            item.get("produto"),
            item.get("quantidade"),
            item.get("preco"),
            item.get("subtotal")
        ))

    conexao.commit()
    conexao.close()

    return {
        "sucesso": True,
        "mensagem": f"Venda Nº {venda_id} registrada com sucesso"
    }