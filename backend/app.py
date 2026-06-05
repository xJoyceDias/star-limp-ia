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
    cliente_nome = dados.get("cliente_nome", "").strip()
    retirado_por = dados.get("retirado_por", "").strip()
    cliente_telefone = dados.get("cliente_telefone", "").strip()

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
    if forma_pagamento == "fiado":
     if not cliente_nome:
        conexao.close()
        return {
            "sucesso": False,
            "mensagem": "Informe o nome do cliente para venda fiada."
        }

    cursor.execute("""
        SELECT id, saldo_fiado, telefone
        FROM clientes
        WHERE lower(nome) = lower(?)
    """, (cliente_nome,))

    cliente = cursor.fetchone()

    if cliente:
        cliente_id = cliente[0]
        saldo_anterior = cliente[1] or 0
        telefone = cliente_telefone or cliente[2] or ""
    else:
        cursor.execute("""
            INSERT INTO clientes (nome, telefone, saldo_fiado, data_cadastro)
            VALUES (?, ?, ?, ?)
        """, (cliente_nome, cliente_telefone, 0, data_hora))

        cliente_id = cursor.lastrowid
        saldo_anterior = 0
        telefone = ""

    saldo_atual = saldo_anterior + total

    cursor.execute("""
    UPDATE clientes
    SET saldo_fiado = ?,
        telefone = ?
    WHERE id = ?
    """, (saldo_atual, telefone, cliente_id))

    cursor.execute ("""
        INSERT INTO fiados (
            venda_id,
            cliente_id,
            cliente_nome,
            telefone,
            retirado_por,
            valor_compra,
            saldo_anterior,
            saldo_atual,
            data_hora,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        venda_id,
        cliente_id,
        cliente_nome,
        telefone,
        retirado_por,
        total,
        saldo_anterior,
        saldo_atual,
        data_hora,
        "ABERTO"
    ))
    mensagem_whatsapp = ""

    if forma_pagamento == "fiado":
        mensagem_whatsapp = (
            f"STAR LIMP FRAGRANCIAS E PRODUTOS\n\n"
            f"Olá {cliente_nome}!\n\n"
            f"Sua compra foi registrada com sucesso.\n\n"
            f"Data/Hora: {data_hora}\n\n"
            f"Valor da compra: R$ {total:.2f}\n"
            f"Saldo anterior: R$ {saldo_anterior:.2f}\n"
            f"Compra atual: R$ {total:.2f}\n\n"
            f"Saldo devedor atual: R$ {saldo_atual:.2f}\n\n"
            f"Retirado por: {retirado_por}\n\n"
            f"Agradecemos a preferência!\n"
            f"Star Limp Fragrâncias e Produtos"
        )

    conexao.commit()
    conexao.close()

    return {
        "sucesso": True,
        "mensagem": f"Venda Nº {venda_id} registrada com sucesso",
        "mensagem_whatsapp": mensagem_whatsapp,
        "telefone_whatsapp": telefone
    }