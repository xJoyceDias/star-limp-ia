import sqlite3
import unicodedata
import os
import shutil
from datetime import datetime, timedelta

from fastapi import FastAPI, Request, Body
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from backend.migrate_remove_bling import migrar_banco

app = FastAPI()

app.mount("/static", StaticFiles(directory="backend/static"), name="static")

templates = Jinja2Templates(directory="backend/templates")
if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_SERVICE_NAME"):
    BANCO = "/data/starlimp.db"
else:
    BANCO = "database/starlimp.db"

if BANCO.startswith("/data"):
    os.makedirs("/data", exist_ok=True)

    precisa_copiar_banco = not os.path.exists(BANCO)

    if not precisa_copiar_banco:
        try:
            conexao_teste = sqlite3.connect(BANCO)
            cursor_teste = conexao_teste.cursor()
            cursor_teste.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='produtos'")
            precisa_copiar_banco = cursor_teste.fetchone() is None
            conexao_teste.close()
        except Exception:
            precisa_copiar_banco = True

    if precisa_copiar_banco:
        shutil.copyfile("database/starlimp.db", BANCO)

migrar_banco(BANCO)

PASTA_BACKUPS = "backups"

def moeda(valor):
    try:
        valor = float(valor or 0)
        return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "0,00"


def criar_backup_banco():
    if not os.path.exists(BANCO):
        return

    os.makedirs(PASTA_BACKUPS, exist_ok=True)

    agora = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    nome_backup = f"starlimp_{agora}.db"
    caminho_backup = os.path.join(PASTA_BACKUPS, nome_backup)

    shutil.copy2(BANCO, caminho_backup)

    backups = sorted(
        [
            os.path.join(PASTA_BACKUPS, arquivo)
            for arquivo in os.listdir(PASTA_BACKUPS)
            if arquivo.endswith(".db")
        ],
        key=os.path.getmtime
    )

    while len(backups) > 30:
        backup_antigo = backups.pop(0)
        os.remove(backup_antigo)


@app.on_event("startup")
def ao_iniciar_sistema():
    criar_backup_banco()


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

@app.get("/pedido/{venda_id}", response_class=HTMLResponse)
def pagina_pedido_cliente(venda_id: int):

    conexao = sqlite3.connect(BANCO)
    conexao.row_factory = sqlite3.Row
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT *
        FROM vendas
        WHERE id = ?
        LIMIT 1
    """, (venda_id,))

    venda = cursor.fetchone()

    if not venda:
        conexao.close()
        return "<h1>Pedido não encontrado</h1>"

    cursor.execute("""
        SELECT descricao, quantidade, preco_unitario, subtotal
        FROM itens_venda
        WHERE venda_id = ?
    """, (venda_id,))

    itens = cursor.fetchall()

    cursor.execute("""
        SELECT cliente_nome,
               telefone,
               retirado_por,
               saldo_anterior,
               saldo_atual
        FROM fiados
        WHERE venda_id = ?
        LIMIT 1
    """, (venda_id,))

    fiado = cursor.fetchone()

    conexao.close()

    try:
        data_formatada = datetime.strptime(
            venda["data_hora"],
            "%Y-%m-%d %H:%M:%S"
        ).strftime("%d/%m/%Y às %H:%M")
    except:
        data_formatada = venda["data_hora"]

    cliente_nome = "Consumidor Final"
    telefone = ""
    bloco_fiado = ""

    if fiado:
        cliente_nome = fiado["cliente_nome"] or "Cliente"
        telefone = fiado["telefone"] or ""

        bloco_fiado = f"""
        <div class="box destaque">
            <strong>Conta Cliente</strong><br>
            Retirado por: {fiado["retirado_por"]}<br>
            Saldo devedor anterior: R$ {moeda(fiado["saldo_anterior"])}<br>
            Compra atual: R$ {moeda(venda["valor_total"])}<br>
            Saldo devedor atual: R$ {moeda(fiado["saldo_atual"])}
        </div>
        """

    linhas_itens = ""

    for item in itens:
        linhas_itens += f"""
        <tr>
            <td>{item["descricao"]}</td>
            <td>{item["quantidade"]}</td>
            <td>R$ {moeda(item["preco_unitario"])}</td>
            <td>R$ {moeda(item["subtotal"])}</td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">

    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">

        <title>Pedido #{venda_id}</title>

        <style>

        body{{
            margin:0;
            padding:25px;
            min-height:100vh;

            background:
                radial-gradient(circle at top, rgba(22,131,255,.20), transparent 35%),
                linear-gradient(180deg,#020617,#0f172a);

            font-family:Arial, Helvetica, sans-serif;
        }}

        .card {{
            max-width:760px;
            margin:auto;
            background:white;
            border-radius:28px;
            padding:35px;
            box-shadow:
                0 30px 80px rgba(0,0,0,.35);

            overflow:hidden;
        }}

        .topo {{
            text-align:center;
            position:relative;
            padding-bottom:25px;
        }}

        .topo::after{{
            content:"";
            display:block;
            height:1px;
            background:#e5e7eb;
            margin-top:20px;
        }}

        .logo{{
            width:300px;
            max-width:92%;
            margin-bottom:10px;
        }}

        .empresa {{
            font-size:18px;
            font-weight:900;
            color:#020617;
            letter-spacing:2px;
            text-transform:uppercase;
        }}

        .contato-topo{{
            margin-top:10px;
            display:flex;
            justify-content:center;
            gap:10px;
            flex-wrap:wrap;
            color:#64748b;
            font-size:14px;
        }}

        .contato-topo span{{
            background:#f8fafc;
            border:1px solid #e5e7eb;
            border-radius:999px;
            padding:7px 12px;
        }}

        .pedido-titulo{{
            margin-top:08px;
            font-size:16px;
            font-weight:700;
            color:#334155;
        }}
        
        .sub {{
            color: #64748b;
            margin-top: 8px;
            font-size:18px;
        }}

        .status{{
            display:inline-block;
            margin-top:15px;
            padding:8px 16px;

            background:#dcfce7;
            color:#166534;

            border-radius:999px;

            font-size:13px;
            font-weight:bold;
        }}

        .box {{
            margin-top:18px;
            background:#f8fafc;
            border:1px solid #dbe3ef;
            border-left:4px solid #1683ff;
            border-radius:14px;
            padding:14px 18px;
            font-size:15px;
        }}

        .pedido-detalhes{{
            margin-top:25px;
            display:grid;
            grid-template-columns:repeat(2,1fr);
            gap:12px;
        }}

        .pedido-detalhes div{{
            background:white;
            border:1px solid #e5e7eb;
            border-radius:10px;
            padding:14px;
        }}

        .pedido-detalhes strong{{
            color:#64748b;
            font-size:12px;
            text-transform:uppercase;
            letter-spacing:.5px;
        }}
        
        .destaque {{
            background: #ecfdf5;
            border-left:5px solid #22c55e;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 22px;
            background:white;
        }}

        th {{
            background: #f1f5f9;
            color: #0f172a;
            padding:12px;
            font-size:13px;
            text-transform:uppercase;
            border:1px solid #e5e7eb;
        }}

        td {{
            background:white;
            color:#020617;
            padding:12px;
            border:1px solid #e5e7eb;
            font-size:14px;
        }}

        body{{
            margin:0;
            padding:20px;
            min-height:100vh;
            background:#f3f6fb;
            font-family:Arial, Helvetica, sans-serif;
            color:#020617;
        }}

        .total {{
            text-align:center;
            margin-top:20px;
            padding-top:15px;
            border-top:1px solid #e5e7eb;
        }}

        .total-label{{
            font-size:12px;
            color:#64748b;
            text-transform:uppercase;
            letter-spacing:1px;
        }}

        .total-valor{{
            font-size:20px;
            font-weight:800;
            color:#020617;
        }}

        .acoes {{
            display:flex;
            justify-content:center;
            gap:12px;
            margin-top:25px;
            flex-wrap:wrap;
        }}

        .btn {{
            background:#020617;
            color:white !important;
            border:none;
            padding:13px 22px;
            border-radius:10px;
            cursor:pointer;
            font-size:14px;
            font-weight:bold;
            transition:.25s;
        }}

        .btn:hover{{
    background:#0f172a;
    color:white !important;
        }}

        .btn-whats{{
            background:#22c55e;
            color:white;
            text-decoration:none;
            padding:13px 22px;
            border-radius:10px;
            font-weight:bold;
            font-size:14px;
        }}

        .btn:hover{{
            transform:translateY(-2px);
            background:#0f6ed8;
        }}

        .rodape {{
            margin-top:35px;
            text-align:center;
            color:#64748b;
            font-size:14px;
            line-height:1.8;
        }}

        @media print {{

            body {{
                background: white;
                padding: 0;
            }}

            .card {{
                width:100%;
                max-width:760px;
                margin:0 auto;
                box-shadow:none;
                border:none;
                border-radius:0;
                padding:20px;
            }}

            .acoes {{
                display: none;
            }}

            .logo{{
                width:200px;
            }}
        
            .total-valor{{
                font-size:24px !important;
                font-weight:700;;
            }}
        }}

        </style>
    </head>

    <body>

        <div class="card">

            <div class="topo">

                <img src="/static/logo.png?v=2" class="logo">
            <div class="empresa">
                STAR LIMP FRAGRÂNCIAS E PRODUTOS
            </div>

            <div class="contato-topo">
                <span>WhatsApp: (62) 98436-2772</span>
                <span>Instagram: @starlimp_</span>
            </div>

            <div class="pedido-titulo">
                Pedido Nº #{venda_id}
</div>

    </div>

    <div class="pedido-detalhes">

        <div>
            <strong>Cliente</strong><br>
            {cliente_nome}
    </div>

    <div>
            <strong>Telefone</strong><br>
            {telefone if telefone else "Não informado"}
    </div>

    <div>
            <strong>Pagamento</strong><br>
            {venda["forma_pagamento"].upper()}
    </div>

    <div>
            <strong>Data</strong><br>
            {data_formatada}
    </div>

    </div>

    </div>

            {bloco_fiado}

            <table>

                <thead>
                    <tr>
                        <th>Produto</th>
                        <th>Qtd</th>
                        <th>Valor Unitário</th>
                        <th>Subtotal</th>
                    </tr>
                </thead>

                <tbody>
                    {linhas_itens}
                </tbody>

            </table>

                <div class="total">
                    <div class="total-label">
                    VALOR TOTAL
                </div>

                <div class="total-valor">
                    R$ {moeda(venda["valor_total"])}
            </div>
        </div>

                <div class="acoes">

        <a
            class="btn-whats"
            target="_blank"
            href="https://wa.me/?text=Olá!%20%F0%9F%91%8B%0A%0ASegue%20o%20seu%20pedido%20da%20Star%20Limp:%0A%0Ahttps://starlimpia-production.up.railway.app/pedido/{venda_id}%0A%0AQualquer%20dúvida,%20estamos%20à%20disposição."
        >
            Enviar Pedido
    </a>

        <button class="btn" onclick="window.print()">
            Imprimir PDF
        </button>

        </div>
            </div>

            <div class="rodape">
                Obrigado pela preferência!
            </div>

        </div>

    </body>
    </html>
    """

    return html

@app.get("/")
def inicio(request: Request):
    agora = datetime.utcnow() - timedelta(hours=3)

    hoje = agora.strftime("%Y-%m-%d")
    inicio_semana = (agora - timedelta(days=agora.weekday())).strftime("%Y-%m-%d")
    inicio_mes = agora.replace(day=1).strftime("%Y-%m-%d")

    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("SELECT COUNT(*) FROM clientes")
    total_clientes = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM clientes WHERE saldo_fiado > 0")
    clientes_devendo = cursor.fetchone()[0] or 0

    cursor.execute("SELECT SUM(saldo_fiado) FROM clientes")
    total_receber = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT SUM(valor_total)
        FROM vendas
        WHERE date(data_hora) = ?
    """, (hoje,))
    vendas_hoje = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT SUM(valor_total)
        FROM vendas
        WHERE date(data_hora) BETWEEN ? AND ?
    """, (inicio_semana, hoje))
    vendas_semana = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT SUM(valor_total)
        FROM vendas
        WHERE date(data_hora) BETWEEN ? AND ?
    """, (inicio_mes, hoje))
    vendas_mes = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT SUM(valor_pago)
        FROM pagamentos_fiado
        WHERE date(data_hora) = ?
    """, (hoje,))
    recebido_hoje = cursor.fetchone()[0] or 0

    conexao.close()

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "total_clientes": total_clientes,
            "clientes_devendo": clientes_devendo,
            "total_receber": total_receber,
            "vendas_hoje": vendas_hoje,
            "vendas_semana": vendas_semana,
            "vendas_mes": vendas_mes,
            "recebido_hoje": recebido_hoje
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


@app.post("/finalizar-venda")
def finalizar_venda(dados: dict = Body(...)):
    itens = dados.get("itens", [])
    total = float(dados.get("total", 0) or 0)
    forma_pagamento = dados.get("forma_pagamento", "").strip().lower()

    cliente_nome = dados.get("cliente_nome", "").strip()
    retirado_por = dados.get("retirado_por", "").strip()
    cliente_telefone = dados.get("cliente_telefone", "").strip()

    if not itens:
        return {
            "sucesso": False,
            "mensagem": "Nenhum produto foi adicionado à venda."
        }

    if forma_pagamento == "fiado" and not cliente_nome:
        return {
            "sucesso": False,
            "mensagem": "Informe o nome do cliente para venda fiada."
        }

    agora = datetime.utcnow() - timedelta(hours=3)

    data_hora = agora.strftime("%Y-%m-%d %H:%M:%S")

    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    mensagem_whatsapp = ""
    telefone = cliente_telefone
    saldo_anterior = 0
    saldo_atual = 0

    try:
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

        if forma_pagamento == "fiado":
            telefone_limpo = ''.join(filter(str.isdigit, cliente_telefone or ""))

            cliente = None

            if telefone_limpo:
                cursor.execute("""
                    SELECT id, saldo_fiado, telefone
                    FROM clientes
                    WHERE REPLACE(REPLACE(REPLACE(REPLACE(telefone, '(', ''), ')', ''), '-',''), ' ', '') = ?
                    LIMIT 1
                """, (telefone_limpo,))

                cliente = cursor.fetchone()

            if not cliente:
                cursor.execute("""
                    SELECT id, saldo_fiado, telefone
                    FROM clientes
                    WHERE lower(trim(nome)) = lower(trim(?))
                    LIMIT 1
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
                telefone = cliente_telefone

            saldo_atual = saldo_anterior + total

            cursor.execute("""
                UPDATE clientes
                SET saldo_fiado = ?,
                    telefone = ?
                WHERE id = ?
            """, (saldo_atual, telefone, cliente_id))

            cursor.execute("""
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

            itens_mensagem = ""

            for item in itens:
                produto = item.get("produto", "")
                quantidade = item.get("quantidade", 0)
                preco = float(item.get("preco", 0) or 0)
                subtotal = float(item.get("subtotal", 0) or 0)

                itens_mensagem += (
                    f"• {produto}\n"
                    f"{quantidade}x R$ {moeda(preco)} = R$ {moeda(subtotal)}\n\n"
                )

            data_formatada = agora.strftime("%d/%m/%Y às %H:%M")

            mensagem_whatsapp = (
                f"STAR LIMP FRAGRÂNCIAS E PRODUTOS\n\n"
                f"Olá {cliente_nome}!\n\n"
                f"Sua compra foi registrada com sucesso.\n\n"
                f"Acesse seu pedido:\n"
                f"https://starlimpia-production.up.railway.app/pedido/{venda_id}\n\n"
                f"Data: {data_formatada}\n"
                f"Retirado por: {retirado_por}\n\n"
                f"PRODUTOS RETIRADOS:\n\n"
                f"{itens_mensagem}"
                f"━━━━━━━━━━━━━━━\n"
                f" TOTAL DA COMPRA: R$ {moeda(total)}\n"
                f"━━━━━━━━━━━━━━━\n\n"
                f"Saldo anterior: R$ {moeda(saldo_anterior)}\n"
                f"Compra atual: R$ {moeda(total)}\n"
                f"Saldo devedor atual: R$ {moeda(saldo_atual)}\n\n"
                f"Agradecemos a preferência!\n\n"
                f"Star Limp Fragrâncias e Produtos \n"
                f"(62) 98436-2772"
            )
        

        conexao.commit()

    except Exception as erro:
        conexao.rollback()
        return {
            "sucesso": False,
            "mensagem": f"Erro ao finalizar venda: {erro}"
        }

    finally:
        conexao.close()

        criar_backup_banco()

    return {
        "sucesso": True,
        "mensagem": f"Venda Nº {venda_id} registrada com sucesso.",
        "venda_id": venda_id,
        "mensagem_whatsapp": mensagem_whatsapp,
        "telefone_whatsapp": telefone
    }

@app.get("/buscar-clientes")
def buscar_clientes(termo: str = ""):

    conexao = sqlite3.connect(BANCO)
    conexao.row_factory = sqlite3.Row
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, nome, telefone
        FROM clientes
        WHERE nome LIKE ?
        ORDER BY nome
        LIMIT 10
    """, (f"%{termo}%",))

    clientes = [
        dict(cliente)
        for cliente in cursor.fetchall()
    ]

    conexao.close()

    return clientes

@app.get("/clientes")
def pagina_clientes(request: Request):
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


@app.get("/relatorios")
def pagina_relatorios(request: Request, data_inicio: str = None, data_fim: str = None):
    hoje = (datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%d")
    data_inicio = data_inicio or hoje
    data_fim = data_fim or data_inicio

    try:
        inicio = datetime.strptime(data_inicio, "%Y-%m-%d").date()
        fim = datetime.strptime(data_fim, "%Y-%m-%d").date()
        if inicio > fim:
            inicio, fim = fim, inicio
            data_inicio, data_fim = inicio.isoformat(), fim.isoformat()
    except ValueError:
        data_inicio = data_fim = hoje

    conexao = sqlite3.connect(BANCO)
    conexao.row_factory = sqlite3.Row
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, data_hora, valor_total, forma_pagamento
        FROM vendas
        WHERE date(data_hora) BETWEEN ? AND ?
        ORDER BY data_hora DESC
    """, (data_inicio, data_fim))
    vendas = cursor.fetchall()

    vendas_com_itens = []
    for venda in vendas:
        cursor.execute("""
            SELECT descricao, quantidade, preco_unitario, subtotal
            FROM itens_venda
            WHERE venda_id = ?
        """, (venda["id"],))
        vendas_com_itens.append({"venda": dict(venda), "itens": cursor.fetchall()})

    cursor.execute("""
        SELECT SUM(valor_total), COUNT(*)
        FROM vendas
        WHERE date(data_hora) BETWEEN ? AND ?
    """, (data_inicio, data_fim))
    total_vendido, quantidade_vendas = cursor.fetchone()
    conexao.close()

    return templates.TemplateResponse(
        request,
        "relatorios.html",
        {
            "vendas": vendas_com_itens,
            "total_vendido": total_vendido or 0,
            "quantidade_vendas": quantidade_vendas or 0,
            "hoje": hoje,
            "data_inicio": data_inicio,
            "data_fim": data_fim
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
        {
            "clientes": clientes
        }
    )


@app.post("/receber-pagamento")
def receber_pagamento(dados: dict = Body(...)):
    cliente_id = dados.get("cliente_id")
    valor_pago = dados.get("valor_pago")
    forma_pagamento = dados.get("forma_pagamento", "").strip()

    if not cliente_id:
        return {"sucesso": False, "mensagem": "Selecione um cliente."}

    try:
        cliente_id = int(cliente_id)
        valor_pago = float(valor_pago)
    except:
        return {"sucesso": False, "mensagem": "Informe um valor válido."}

    if valor_pago <= 0:
        return {"sucesso": False, "mensagem": "Informe um valor maior que zero."}

    agora = datetime.utcnow() - timedelta(hours=3)

    data_hora = agora.strftime("%Y-%m-%d %H:%M:%S")

    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, nome, saldo_fiado
        FROM clientes
        WHERE id = ?
    """, (cliente_id,))

    cliente = cursor.fetchone()

    if not cliente:
        conexao.close()
        return {"sucesso": False, "mensagem": "Cliente não encontrado."}

    saldo_anterior = cliente[2] or 0
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
            forma_pagamento,
            data_hora
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        cliente_id,
        valor_pago,
        saldo_anterior,
        saldo_atual,
        forma_pagamento,
        data_hora
    ))

    conexao.commit()
    conexao.close()

    criar_backup_banco()

    return {
        "sucesso": True,
        "mensagem": "Pagamento registrado com sucesso."
    }


@app.get("/cancelar-venda")
def pagina_cancelar_venda(request: Request):
    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, data_hora, valor_total, forma_pagamento
        FROM vendas
        ORDER BY id DESC
        LIMIT 50
    """)

    vendas_banco = cursor.fetchall()

    formas = {
        "pix": "PIX",
        "credito": "Crédito",
        "debito": "Débito",
        "dinheiro": "Dinheiro",
        "fiado": "Fiado"
    }

    vendas = []

    for venda in vendas_banco:
        venda_id = venda[0]

        forma = formas.get(
            str(venda[3]).lower(),
            venda[3]
        )

        try:
            data = datetime.strptime(
                venda[1],
                "%Y-%m-%d %H:%M:%S"
            ).strftime("%d/%m/%Y às %H:%M")
        except:
            data = venda[1]

        cursor.execute("""
            SELECT descricao, quantidade, preco_unitario, subtotal
            FROM itens_venda
            WHERE venda_id = ?
        """, (venda_id,))

        itens = cursor.fetchall()

        vendas.append({
            "id": venda_id,
            "data_hora": data,
            "valor_total": venda[2],
            "forma_pagamento": forma,
            "itens": itens
        })

    conexao.close()

    return templates.TemplateResponse(
        request,
        "cancelar_venda.html",
        {
            "request": request,
            "vendas": vendas
        }
    )


@app.post("/cancelar-venda")
def cancelar_venda(dados: dict = Body(...)):
    venda_id = int(dados.get("venda_id"))

    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, forma_pagamento
        FROM vendas
        WHERE id = ?
    """, (venda_id,))

    venda = cursor.fetchone()

    if not venda:
        conexao.close()
        return {
            "sucesso": False,
            "mensagem": "Venda não encontrada."
        }

    forma_pagamento = venda[1]

    if forma_pagamento == "fiado":
        cursor.execute("""
            SELECT cliente_id, valor_compra
            FROM fiados
            WHERE venda_id = ?
        """, (venda_id,))

        fiado = cursor.fetchone()

        if fiado:
            cliente_id = fiado[0]
            valor_compra = fiado[1]

            cursor.execute("""
                SELECT saldo_fiado
                FROM clientes
                WHERE id = ?
            """, (cliente_id,))

            cliente = cursor.fetchone()

            if cliente:
                saldo_atual = cliente[0] or 0
                novo_saldo = saldo_atual - valor_compra

                if novo_saldo < 0:
                    novo_saldo = 0

                cursor.execute("""
                    UPDATE clientes
                    SET saldo_fiado = ?
                    WHERE id = ?
                """, (
                    novo_saldo,
                    cliente_id
                ))

        cursor.execute("""
            DELETE FROM fiados
            WHERE venda_id = ?
        """, (venda_id,))

    cursor.execute("""
        DELETE FROM itens_venda
        WHERE venda_id = ?
    """, (venda_id,))

    cursor.execute("""
        DELETE FROM vendas
        WHERE id = ?
    """, (venda_id,))

    conexao.commit()
    conexao.close()

    criar_backup_banco()

    return {
        "sucesso": True,
        "mensagem": f"Venda Nº {venda_id} cancelada com sucesso."
    }


# Gestão de produtos para o PDV
@app.get("/produtos")
def pagina_produtos(request: Request):
    return templates.TemplateResponse(request, "produtos.html")


@app.get("/api/produtos")
def listar_produtos(termo: str = ""):
    conexao = sqlite3.connect(BANCO)
    conexao.row_factory = sqlite3.Row
    cursor = conexao.cursor()
    cursor.execute("""
        SELECT id, codigo, descricao, unidade, preco, situacao, estoque, categoria
        FROM produtos
        WHERE lower(coalesce(codigo, '')) LIKE ? OR lower(coalesce(descricao, '')) LIKE ?
        ORDER BY descricao COLLATE NOCASE
        LIMIT 200
    """, (f"%{termo.lower()}%", f"%{termo.lower()}%"))
    produtos = [dict(produto) for produto in cursor.fetchall()]
    conexao.close()
    return produtos


@app.post("/api/produtos")
def criar_produto(dados: dict = Body(...)):
    descricao = str(dados.get("descricao", "")).strip()
    codigo = str(dados.get("codigo", "")).strip()
    if not descricao:
        return {"sucesso": False, "mensagem": "Informe a descrição do produto."}
    try:
        preco = float(dados.get("preco", 0) or 0)
        estoque = float(dados.get("estoque", 0) or 0)
    except (TypeError, ValueError):
        return {"sucesso": False, "mensagem": "Preço e estoque devem ser numéricos."}
    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()
    cursor.execute("""
        INSERT INTO produtos (codigo, descricao, unidade, preco, situacao, estoque, categoria)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (codigo, descricao, str(dados.get("unidade", "UN")).strip() or "UN", preco,
          str(dados.get("situacao", "Ativo")).strip() or "Ativo", estoque,
          str(dados.get("categoria", "")).strip()))
    produto_id = cursor.lastrowid
    conexao.commit()
    conexao.close()
    return {"sucesso": True, "id": produto_id, "mensagem": "Produto cadastrado com sucesso."}


@app.put("/api/produtos/{produto_id}")
def atualizar_produto(produto_id: int, dados: dict = Body(...)):
    descricao = str(dados.get("descricao", "")).strip()
    if not descricao:
        return {"sucesso": False, "mensagem": "Informe a descrição do produto."}
    try:
        preco = float(dados.get("preco", 0) or 0)
        estoque = float(dados.get("estoque", 0) or 0)
    except (TypeError, ValueError):
        return {"sucesso": False, "mensagem": "Preço e estoque devem ser numéricos."}
    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()
    cursor.execute("""
        UPDATE produtos
        SET codigo = ?, descricao = ?, unidade = ?, preco = ?, situacao = ?, estoque = ?, categoria = ?
        WHERE id = ?
    """, (str(dados.get("codigo", "")).strip(), descricao,
          str(dados.get("unidade", "UN")).strip() or "UN", preco,
          str(dados.get("situacao", "Ativo")).strip() or "Ativo", estoque,
          str(dados.get("categoria", "")).strip(), produto_id))
    atualizado = cursor.rowcount > 0
    conexao.commit()
    conexao.close()
    if not atualizado:
        return {"sucesso": False, "mensagem": "Produto não encontrado."}
    return {"sucesso": True, "mensagem": "Produto atualizado com sucesso."}
