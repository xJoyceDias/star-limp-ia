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
    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("SELECT COUNT(*) FROM clientes")
    total_clientes = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM clientes WHERE saldo_fiado > 0")
    clientes_devendo = cursor.fetchone()[0] or 0

    cursor.execute("SELECT SUM(saldo_fiado) FROM clientes")
    total_receber = cursor.fetchone()[0] or 0

    conexao.close()

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "total_clientes": total_clientes,
            "clientes_devendo": clientes_devendo,
            "total_receber": total_receber
        }
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
    from datetime import datetime, timedelta

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

@app.get("/clientes")
def pagina_clientes(request: Request):
    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, nome, telefone, saldo_fiado
        FROM clientes
        ORDER BY nome
    """)

    clientes = cursor.fetchall()
    conexao.close()

    return templates.TemplateResponse(
        request,
        "clientes.html",
        {"clientes": clientes}
    )


@app.get("/clientes/{cliente_id}")
def extrato_cliente(request: Request, cliente_id: int):
    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, nome, telefone, saldo_fiado
        FROM clientes
        WHERE id = ?
    """, (cliente_id,))

    cliente = cursor.fetchone()

    cursor.execute("""
        SELECT id, venda_id, data_hora, valor_compra, saldo_anterior, saldo_atual, retirado_por
        FROM fiados
        WHERE cliente_id = ?
        ORDER BY data_hora DESC
    """, (cliente_id,))

    compras = cursor.fetchall()

    compras_com_itens = []

    for compra in compras:
        venda_id = compra[1]

        cursor.execute("""
            SELECT descricao, quantidade, preco_unitario, subtotal
            FROM itens_venda
            WHERE venda_id = ?
        """, (venda_id,))

        itens = cursor.fetchall()

        compras_com_itens.append({
            "compra": compra,
            "itens": itens
        })

    cursor.execute("""
        SELECT data_hora, valor_pago, saldo_anterior, saldo_atual, forma_pagamento
        FROM pagamentos_fiado
        WHERE cliente_id = ?
        ORDER BY data_hora DESC
    """, (cliente_id,))

    pagamentos = cursor.fetchall()

    conexao.close()

    return templates.TemplateResponse(
        request,
        "extrato_cliente.html",
        {
            "cliente": cliente,
            "compras": compras_com_itens,
            "pagamentos": pagamentos
        }
    )


@app.get("/receber-pagamento")
def pagina_receber_pagamento(request: Request):
    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, nome, telefone, saldo_fiado
        FROM clientes
        WHERE saldo_fiado > 0
        ORDER BY nome
    """)

    clientes = cursor.fetchall()
    conexao.close()

    return templates.TemplateResponse(
        request,
        "receber_pagamento.html",
        {"clientes": clientes}
    )
@app.post("/receber-pagamento")
def receber_pagamento(dados: dict = Body(...)):
    from datetime import datetime, timedelta

    cliente_id = int(dados.get("cliente_id"))

    valor_pago = str(dados.get("valor_pago", "0")).replace(",", ".")
    valor_pago = float(valor_pago)

    forma_pagamento = dados.get("forma_pagamento", "")

    data_hora = (datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")

    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT saldo_fiado
        FROM clientes
        WHERE id = ?
    """, (cliente_id,))

    cliente = cursor.fetchone()

    if not cliente:
        conexao.close()
        return {
            "sucesso": False,
            "mensagem": "Cliente não encontrado."
        }

    saldo_anterior = cliente[0] or 0
    saldo_atual = saldo_anterior - valor_pago

    if saldo_atual < 0:
        saldo_atual = 0

    cursor.execute("""
        UPDATE clientes
        SET saldo_fiado = ?
        WHERE id = ?
    """, (saldo_atual, cliente_id))

    cursor.execute("""
        INSERT INTO pagamentos_fiado (
            cliente_id,
            valor_pago,
            saldo_anterior,
            saldo_atual,
            data_hora,
            forma_pagamento
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        cliente_id,
        valor_pago,
        saldo_anterior,
        saldo_atual,
        data_hora,
        forma_pagamento
    ))

    conexao.commit()
    conexao.close()

    return {
        "sucesso": True,
        "mensagem": "Pagamento registrado com sucesso."
    }