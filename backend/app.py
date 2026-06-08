import sqlite3
import unicodedata
import os
import shutil
from datetime import datetime, timedelta
import requests
from urllib.parse import urlencode

from fastapi import FastAPI, Request, Body
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.mount("/static", StaticFiles(directory="backend/static"), name="static")

templates = Jinja2Templates(directory="backend/templates")
BANCO = "database/starlimp.db"
PASTA_BACKUPS = "backups"
BLING_CLIENT_ID = os.getenv("BLING_CLIENT_ID")
BLING_CLIENT_SECRET = os.getenv("BLING_CLIENT_SECRET")
BLING_REDIRECT_URI = os.getenv(
    "BLING_REDIRECT_URI",
    "https://starlimpia-production.up.railway.app/bling/callback"
)

BLING_AUTH_URL = "https://www.bling.com.br/Api/v3/oauth/authorize"
BLING_TOKEN_URL = "https://www.bling.com.br/Api/v3/oauth/token"


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

@app.get("/bling/login")
def bling_login():
    if not BLING_CLIENT_ID or not BLING_REDIRECT_URI:
        return {
            "sucesso": False,
            "mensagem": "Configurações do Bling não encontradas."
        }

    parametros = {
        "response_type": "code",
        "client_id": BLING_CLIENT_ID,
        "redirect_uri": BLING_REDIRECT_URI,
        "state": "starlimpia"
    }

    url = f"{BLING_AUTH_URL}?{urlencode(parametros)}"

    return RedirectResponse(url)


@app.get("/bling/callback")
def bling_callback(code: str = None, state: str = None, error: str = None):
    if error:
        return {
            "sucesso": False,
            "mensagem": f"Autorização negada pelo Bling: {error}"
        }

    if not code:
        return {
            "sucesso": False,
            "mensagem": "Código de autorização não recebido."
        }

    if not BLING_CLIENT_ID or not BLING_CLIENT_SECRET:
        return {
            "sucesso": False,
            "mensagem": "Client ID ou Client Secret do Bling não configurados."
        }

    resposta = requests.post(
        BLING_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": BLING_REDIRECT_URI
        },
        auth=(BLING_CLIENT_ID, BLING_CLIENT_SECRET),
        headers={
            "Accept": "application/json",
            "enable-jwt": "1"
        }
    )

    if resposta.status_code not in [200, 201]:
        return {
            "sucesso": False,
            "mensagem": "Erro ao trocar código por token no Bling.",
            "status_code": resposta.status_code,
            "resposta": resposta.text
        }

    dados_token = resposta.json()

    access_token = dados_token.get("access_token")
    refresh_token = dados_token.get("refresh_token")
    expires_in = dados_token.get("expires_in")

    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bling_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            access_token TEXT,
            refresh_token TEXT,
            expires_in INTEGER,
            criado_em TEXT
        )
    """)

    cursor.execute("DELETE FROM bling_tokens")

    cursor.execute("""
        INSERT INTO bling_tokens (
            access_token,
            refresh_token,
            expires_in,
            criado_em
        )
        VALUES (?, ?, ?, ?)
    """, (
        access_token,
        refresh_token,
        expires_in,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conexao.commit()
    conexao.close()

    return {
        "sucesso": True,
        "mensagem": "Bling conectado com sucesso ao Star Limp IA."
    }

@app.get("/bling/status")
def bling_status():

    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT access_token, criado_em
        FROM bling_tokens
        ORDER BY id DESC
        LIMIT 1
    """)

    token = cursor.fetchone()

    conexao.close()

    if not token:
        return {
            "sucesso": False,
            "mensagem": "Nenhum token do Bling encontrado."
        }

    return {
        "sucesso": True,
        "mensagem": "Token encontrado.",
        "criado_em": token[1]
    }

@app.get("/bling/preparar-sincronizacao")
def preparar_sincronizacao():

    conexao = sqlite3.connect(BANCO)
    conexao.row_factory = sqlite3.Row
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT *
        FROM bling_sync
        WHERE status = 'PENDENTE'
        ORDER BY id
    """)

    pendencias = cursor.fetchall()

    resultado = []

    for pendencia in pendencias:

        venda_id = pendencia["venda_id"]

        cursor.execute("""
            SELECT *
            FROM vendas
            WHERE id = ?
        """, (venda_id,))

        venda = cursor.fetchone()

        if not venda:
            continue

        cursor.execute("""
            SELECT
                codigo_produto,
                descricao,
                quantidade,
                preco_unitario,
                subtotal
            FROM itens_venda
            WHERE venda_id = ?
        """, (venda_id,))

        itens = [dict(item) for item in cursor.fetchall()]

        resultado.append({
            "venda_id": venda["id"],
            "data_hora": venda["data_hora"],
            "valor_total": venda["valor_total"],
            "forma_pagamento": venda["forma_pagamento"],
            "itens": itens
        })

    conexao.close()

    return {
        "quantidade_pendencias": len(resultado),
        "vendas": resultado
    }

def montar_payload_bling(venda_id: int):

    conexao = sqlite3.connect(BANCO)
    conexao.row_factory = sqlite3.Row
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT *
        FROM vendas
        WHERE id = ?
    """, (venda_id,))

    venda = cursor.fetchone()

    if not venda:
        conexao.close()
        return None

    cursor.execute("""
        SELECT
            codigo_produto,
            descricao,
            quantidade,
            preco_unitario,
            subtotal
        FROM itens_venda
        WHERE venda_id = ?
    """, (venda_id,))

    itens = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM fiados
        WHERE venda_id = ?
        LIMIT 1
    """, (venda_id,))

    fiado = cursor.fetchone()

    contato = {
        "nome": "Consumidor Final"
    }

    origem_cliente = "consumidor_final"

    if fiado:
        contato = {
            "nome": fiado["cliente_nome"] or "Cliente Fiado"
        }

        if fiado["telefone"]:
            contato["telefone"] = fiado["telefone"]

        origem_cliente = "fiado"

    elif venda["pedido_bling_solicitado"] == 1:
        contato = {
            "nome": venda["cliente_nome_bling"] or "Cliente"
        }

        if venda["cliente_telefone_bling"]:
            contato["telefone"] = venda["cliente_telefone_bling"]

        if venda["cliente_documento_bling"]:
            contato["numeroDocumento"] = venda["cliente_documento_bling"]

        origem_cliente = "pedido_solicitado"

    itens_bling = []
    total_itens = 0


    for item in itens:
        quantidade = float(item["quantidade"])
        valor_unitario = float(item["preco_unitario"])
        subtotal = float(item["subtotal"])

        total_itens += quantidade * valor_unitario

        itens_bling.append({
            "codigo": str(item["codigo_produto"]),
            "descricao": item["descricao"],
            "quantidade": quantidade,
            "valor": valor_unitario
        })

    valor_total_venda = float(venda["valor_total"])
    desconto = round(total_itens - valor_total_venda, 2)
        

    data_venda = venda["data_hora"][:10] if venda["data_hora"] else None

    payload = {
        "data": data_venda,
        "contato": contato,
        "itens": itens_bling,
        "parcelas": [
            {
                "dataVencimento": data_venda,
                "valor": float(venda["valor_total"]),
                "observacoes": f"Forma de pagamento: {venda['forma_pagamento']}"
            }
        ],
        "observacoes": f"Venda gerada pelo Star Limp IA. Forma de pagamento: {venda['forma_pagamento']}. Origem cliente: {origem_cliente}."
    }
    if desconto > 0:
        payload["desconto"] = {
            "valor": desconto
        }

    conexao.close()

    return payload

def obter_token_bling():
    conexao = sqlite3.connect(BANCO)
    conexao.row_factory = sqlite3.Row
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT access_token
        FROM bling_tokens
        ORDER BY id DESC
        LIMIT 1
    """)

    token = cursor.fetchone()
    conexao.close()

    if not token:
        return None

    return token["access_token"]

def criar_contato_bling(nome, telefone=None, documento=None):
    access_token = obter_token_bling()

    if not access_token:
        return None, {
            "erro": "Token do Bling não encontrado."
        }

    url = "https://api.bling.com.br/Api/v3/contatos"

    payload = {
    "nome": nome,
    "tipo": "F",
    "situacao": "A"
}

    if telefone:
        payload["telefone"] = telefone

    if documento:
        payload["numeroDocumento"] = documento

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    resposta = requests.post(url, json=payload, headers=headers)

    try:
        resposta_json = resposta.json()
    except Exception:
        resposta_json = {"erro": resposta.text}

    if resposta.status_code in [200, 201]:
        contato_id = resposta_json.get("data", {}).get("id")
        return contato_id, resposta_json

    return None, resposta_json

@app.post("/bling/testar-contato")
def testar_contato_bling():
    contato_id, resposta = criar_contato_bling(
        nome="Teste Star Limp IA",
        telefone="62999999999"
    )

    return {
        "sucesso": contato_id is not None,
        "contato_id": contato_id,
        "resposta_bling": resposta
    }

@app.get("/bling/payload-teste/{venda_id}")
def bling_payload_teste(venda_id: int):

    payload = montar_payload_bling(venda_id)

    if not payload:
        return {
            "sucesso": False,
            "mensagem": "Venda não encontrada."
        }

    return {
        "sucesso": True,
        "venda_id": venda_id,
        "payload": payload
    }

@app.post("/bling/enviar-venda/{venda_id}")
def bling_enviar_venda(venda_id: int):

    payload = montar_payload_bling(venda_id)

    if not payload:
        return {
            "sucesso": False,
            "mensagem": "Venda não encontrada."
        }

    conexao = sqlite3.connect(BANCO)
    conexao.row_factory = sqlite3.Row
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT access_token
        FROM bling_tokens
        ORDER BY id DESC
        LIMIT 1
    """)

    token = cursor.fetchone()

    if not token:
        conexao.close()
        return {
            "sucesso": False,
            "mensagem": "Token do Bling não encontrado."
        }

    url = "https://api.bling.com.br/Api/v3/pedidos/vendas"

    headers = {
        "Authorization": f"Bearer {token['access_token']}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    resposta = requests.post(url, json=payload, headers=headers)

    try:
        resposta_json = resposta.json()
    except Exception:
        resposta_json = {"erro": resposta.text}

    if resposta.status_code in [200, 201]:
        bling_id = None

        if isinstance(resposta_json, dict):
            bling_id = resposta_json.get("data", {}).get("id")

        cursor.execute("""
            UPDATE bling_sync
            SET status = 'SINCRONIZADO',
                bling_id = ?,
                data_sincronizacao = datetime('now', '-3 hours'),
                erro = NULL
            WHERE venda_id = ?
        """, (bling_id, venda_id))

        conexao.commit()
        conexao.close()

        return {
            "sucesso": True,
            "mensagem": "Venda enviada ao Bling com sucesso.",
            "venda_id": venda_id,
            "bling_id": bling_id,
            "resposta_bling": resposta_json
        }

    cursor.execute("""
        UPDATE bling_sync
        SET status = 'ERRO',
            erro = ?
        WHERE venda_id = ?
    """, (str(resposta_json), venda_id))

    conexao.commit()
    conexao.close()

    return {
        "sucesso": False,
        "mensagem": "Erro ao enviar venda para o Bling.",
        "status_code": resposta.status_code,
        "payload_enviado": payload,
        "resposta_bling": resposta_json
    }

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
                    WHERE REPLACE(REPLACE(REPLACE(REPLACE(telefone, '(', ''), ')', ''), '-', ''), ' ', '') = ?
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
        
        cursor.execute("""
            INSERT INTO bling_sync (
                venda_id,
                status,
                data_criacao
            )
            VALUES (?, ?, ?)
        """, (
            venda_id,
            "PENDENTE",
            data_hora
        ))

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
def pagina_relatorios(request: Request):
    hoje = (datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%d")

    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, data_hora, valor_total, forma_pagamento
        FROM vendas
        WHERE date(data_hora) = ?
        ORDER BY data_hora DESC
    """, (hoje,))

    vendas = cursor.fetchall()

    vendas_com_itens = []

    for venda in vendas:
        venda_id = venda[0]

        cursor.execute("""
            SELECT descricao, quantidade, preco_unitario, subtotal
            FROM itens_venda
            WHERE venda_id = ?
        """, (venda_id,))

        itens = cursor.fetchall()

        vendas_com_itens.append({
            "venda": venda,
            "itens": itens
        })

    cursor.execute("""
        SELECT SUM(valor_total)
        FROM vendas
        WHERE date(data_hora) = ?
    """, (hoje,))

    total_vendido = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COUNT(*)
        FROM vendas
        WHERE date(data_hora) = ?
    """, (hoje,))

    quantidade_vendas = cursor.fetchone()[0] or 0

    conexao.close()

    return templates.TemplateResponse(
        request,
        "relatorios.html",
        {
            "vendas": vendas_com_itens,
            "total_vendido": total_vendido,
            "quantidade_vendas": quantidade_vendas,
            "hoje": hoje
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
