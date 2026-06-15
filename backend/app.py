import sqlite3
import unicodedata
import os
import shutil
from datetime import datetime, timedelta
import requests
from urllib.parse import urlencode

from fastapi import FastAPI, Request, Body
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

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

PASTA_BACKUPS = "backups"
BLING_CLIENT_ID = os.getenv("BLING_CLIENT_ID")
BLING_CLIENT_SECRET = os.getenv("BLING_CLIENT_SECRET")
BLING_REDIRECT_URI = os.getenv(
    "BLING_REDIRECT_URI",
    "https://starlimpia-production.up.railway.app/bling/callback"
)

BLING_AUTH_URL = "https://www.bling.com.br/Api/v3/oauth/authorize"
BLING_TOKEN_URL = "https://www.bling.com.br/Api/v3/oauth/token"

def garantir_tabela_bling_pedidos():
    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bling_pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venda_id INTEGER NOT NULL,
            bling_venda_id TEXT,
            bling_pedido_id TEXT,
            status TEXT DEFAULT 'PENDENTE',
            data_criacao TEXT,
            data_atualizacao TEXT,
            erro TEXT
        )
    """)

    conexao.commit()
    conexao.close()


garantir_tabela_bling_pedidos()

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

@app.get("/bling")
def pagina_bling(request: Request):
    conexao = sqlite3.connect(BANCO)
    conexao.row_factory = sqlite3.Row
    cursor = conexao.cursor()

    cursor.execute("SELECT COUNT(*) FROM bling_sync")
    total = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM bling_sync WHERE status = 'SINCRONIZADO'")
    sincronizadas = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM bling_sync WHERE status = 'PENDENTE'")
    pendentes = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM bling_sync WHERE status = 'ERRO'")
    erros = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT *
        FROM bling_sync
        ORDER BY id DESC
        LIMIT 50
    """)

    registros = cursor.fetchall()

    conexao.close()

    return templates.TemplateResponse(
    request,
    "bling.html",
    {
        "total": total,
        "sincronizadas": sincronizadas,
        "pendentes": pendentes,
        "erros": erros,
        "registros": registros
    }
)

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

        produto_id, resposta_produto = buscar_produto_bling_por_codigo(item["codigo_produto"])

        if produto_id:
            itens_bling.append({
                "produto": {
                    "id": int(produto_id)
                },
                "descricao": item["descricao"],
                "quantidade": quantidade,
                "valor": valor_unitario
            })
        else:
            itens_bling.append({
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
        CREATE TABLE IF NOT EXISTS bling_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            access_token TEXT NOT NULL,
            refresh_token TEXT,
            expires_in INTEGER,
            criado_em TEXT
        )
    """)

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

def obter_ou_criar_contato_bling_para_venda(venda_id: int):
    conexao = sqlite3.connect(BANCO)
    conexao.row_factory = sqlite3.Row
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT *
        FROM fiados
        WHERE venda_id = ?
        LIMIT 1
    """, (venda_id,))

    fiado = cursor.fetchone()

    if not fiado:
        conexao.close()
        return None, None

    cliente_id = fiado["cliente_id"]
    nome = fiado["cliente_nome"] or "Cliente"
    telefone = fiado["telefone"]

    cursor.execute("""
        SELECT bling_contato_id
        FROM clientes
        WHERE id = ?
        LIMIT 1
    """, (cliente_id,))

    cliente = cursor.fetchone()

    if cliente and cliente["bling_contato_id"]:
        contato_id = cliente["bling_contato_id"]
        conexao.close()
        return contato_id, {
            "origem": "cliente_local",
            "contato_id": contato_id
        }

    contato_id, resposta = criar_contato_bling(
        nome=nome,
        telefone=telefone
    )

    if contato_id:
        cursor.execute("""
            UPDATE clientes
            SET bling_contato_id = ?
            WHERE id = ?
        """, (str(contato_id), cliente_id))

        conexao.commit()

    conexao.close()

    return contato_id, resposta

def obter_ou_criar_consumidor_final_bling():
    conexao = sqlite3.connect(BANCO)
    conexao.row_factory = sqlite3.Row
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes (
            chave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)

    cursor.execute("""
        SELECT valor
        FROM configuracoes
        WHERE chave = 'bling_consumidor_final_id'
        LIMIT 1
    """)

    config = cursor.fetchone()

    if config and config["valor"]:
        conexao.close()
        return config["valor"], {
            "origem": "configuracoes",
            "contato_id": config["valor"]
        }

    contato_id, resposta = criar_contato_bling(
        nome="Consumidor Final",
        telefone=None
    )

    if contato_id:
        cursor.execute("""
            INSERT OR REPLACE INTO configuracoes (chave, valor)
            VALUES (?, ?)
        """, ("bling_consumidor_final_id", str(contato_id)))

        conexao.commit()

    conexao.close()

    return contato_id, resposta

def buscar_produto_bling_por_codigo(codigo):
    access_token = obter_token_bling()

    if not access_token:
        return None, {
            "erro": "Token do Bling não encontrado."
        }

    url = "https://api.bling.com.br/Api/v3/produtos"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    params = {
        "codigo": str(codigo)
    }

    resposta = requests.get(url, headers=headers, params=params)

    try:
        resposta_json = resposta.json()
    except Exception:
        resposta_json = {"erro": resposta.text}

    if resposta.status_code == 200:
        produtos = resposta_json.get("data", [])

        if produtos:
            produto_id = produtos[0].get("id")
            return produto_id, resposta_json

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

@app.get("/bling/debug-token")
def bling_debug_token():
    token = obter_token_bling()

    return {
        "sucesso": token is not None,
        "token_inicio": token[:12] if token else None,
        "banco": BANCO
    }

@app.get("/bling/debug-sync-schema")
def bling_debug_sync_schema():
    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("PRAGMA table_info(bling_sync)")
    colunas = cursor.fetchall()

    conexao.close()

    return {
        "banco": BANCO,
        "colunas": colunas
    }

@app.get("/bling/pedidos")
def listar_pedidos_bling():

    conexao = sqlite3.connect(BANCO)
    conexao.row_factory = sqlite3.Row
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT *
        FROM bling_pedidos
        ORDER BY id DESC
    """)

    pedidos = [dict(linha) for linha in cursor.fetchall()]

    conexao.close()

    return {
        "total": len(pedidos),
        "pedidos": pedidos
    }

@app.post("/bling/corrigir-status-sincronizados")
def corrigir_status_sincronizados_bling():
    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("""
        UPDATE bling_sync
        SET status = 'SINCRONIZADO',
            erro = NULL
        WHERE bling_id IS NOT NULL
          AND bling_id != ''
    """)

    total_corrigidos = cursor.rowcount

    conexao.commit()
    conexao.close()

    return {
        "sucesso": True,
        "mensagem": "Status das vendas com Bling ID corrigido.",
        "total_corrigidos": total_corrigidos
    }

@app.get("/bling/testar-produto/{codigo}")
def testar_produto_bling(codigo: str):

    produto_id, resposta = buscar_produto_bling_por_codigo(codigo)

    return {
        "sucesso": produto_id is not None,
        "produto_id": produto_id,
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

    contato_id = None
    resposta_contato = None

    contato_id, resposta_contato = obter_ou_criar_contato_bling_para_venda(venda_id)

    if not contato_id and payload.get("contato", {}).get("nome") == "Consumidor Final":
        contato_id, resposta_contato = obter_ou_criar_consumidor_final_bling()

    if contato_id:
        payload["contato"] = {
            "id": int(contato_id)
        }
    else:
        return {
            "sucesso": False,
            "mensagem": "Não foi possível obter ou criar contato no Bling.",
            "resposta_contato": resposta_contato,
            "payload": payload
        }

    access_token = obter_token_bling()

    if not access_token:
        return {
            "sucesso": False,
            "mensagem": "Token do Bling não encontrado."
        }

    conexao = sqlite3.connect(BANCO)
    conexao.row_factory = sqlite3.Row
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT bling_id, status
        FROM bling_sync
        WHERE venda_id = ?
        LIMIT 1
    """, (venda_id,))

    sync_existente = cursor.fetchone()

    if sync_existente and sync_existente["bling_id"]:
        conexao.close()
        return {
            "sucesso": True,
            "mensagem": "Venda já estava sincronizada com o Bling.",
            "venda_id": venda_id,
            "bling_id": sync_existente["bling_id"]
        }

    url = "https://api.bling.com.br/Api/v3/pedidos/vendas"

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

@app.post("/bling/gerar-pedido/{venda_id}")
def gerar_pedido_bling(venda_id: int):

    conexao = sqlite3.connect(BANCO)
    conexao.row_factory = sqlite3.Row
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT venda_id, bling_id, status
        FROM bling_sync
        WHERE venda_id = ?
        LIMIT 1
    """, (venda_id,))

    sincronizacao = cursor.fetchone()

    if not sincronizacao:
        conexao.close()
        return {
            "sucesso": False,
            "mensagem": "Venda não encontrada na sincronização Bling."
        }

    if not sincronizacao["bling_id"]:
        conexao.close()
        return {
            "sucesso": False,
            "mensagem": "Venda ainda não possui Bling ID. Sincronize a venda antes de gerar pedido."
        }

    cursor.execute("""
        SELECT *
        FROM bling_pedidos
        WHERE venda_id = ?
        LIMIT 1
    """, (venda_id,))

    pedido_existente = cursor.fetchone()

    if pedido_existente:
        conexao.close()
        return {
            "sucesso": True,
            "mensagem": "Pedido já registrado para esta venda.",
            "pedido": dict(pedido_existente)
        }

    cursor.execute("""
        INSERT INTO bling_pedidos (
            venda_id,
            bling_venda_id,
            status,
            data_criacao,
            data_atualizacao
        )
        VALUES (?, ?, ?, datetime('now', '-3 hours'), datetime('now', '-3 hours'))
    """, (
        venda_id,
        sincronizacao["bling_id"],
        "PENDENTE"
    ))

    pedido_id_local = cursor.lastrowid

    conexao.commit()

    cursor.execute("""
        SELECT *
        FROM bling_pedidos
        WHERE id = ?
    """, (pedido_id_local,))

    pedido = cursor.fetchone()

    conexao.close()

    return {
        "sucesso": True,
        "mensagem": "Pedido registrado localmente. Próximo passo: integrar criação real no Bling.",
        "pedido": dict(pedido)
    }


@app.get("/bling/consultar-pedido/{bling_id}")
def consultar_pedido_bling(bling_id: str):
    access_token = obter_token_bling()

    if not access_token:
        return {
            "sucesso": False,
            "mensagem": "Token do Bling não encontrado."
        }

    url = f"https://api.bling.com.br/Api/v3/pedidos/vendas/{bling_id}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    resposta = requests.get(url, headers=headers)

    try:
        resposta_json = resposta.json()
    except Exception:
        resposta_json = {"erro": resposta.text}

    return {
        "sucesso": resposta.status_code == 200,
        "status_code": resposta.status_code,
        "bling_id": bling_id,
        "resposta_bling": resposta_json
    }

@app.get("/bling/pdf-pedido/{venda_id}")
def obter_pdf_pedido_bling(venda_id: int):
    conexao = sqlite3.connect(BANCO)
    conexao.row_factory = sqlite3.Row
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT bling_pedido_id, bling_venda_id, status
        FROM bling_pedidos
        WHERE venda_id = ?
        LIMIT 1
    """, (venda_id,))

    pedido = cursor.fetchone()
    conexao.close()

    if not pedido:
        return {
            "sucesso": False,
            "mensagem": "Pedido não encontrado na tabela bling_pedidos."
        }

    bling_id = pedido["bling_pedido_id"] or pedido["bling_venda_id"]

    if not bling_id:
        return {
            "sucesso": False,
            "mensagem": "Pedido ainda não possui ID do Bling."
        }

    access_token = obter_token_bling()

    if not access_token:
        return {
            "sucesso": False,
            "mensagem": "Token do Bling não encontrado."
        }

    url = f"https://api.bling.com.br/Api/v3/pedidos/vendas/{bling_id}/pdf"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    resposta = requests.get(url, headers=headers)

    try:
        resposta_json = resposta.json()
    except Exception:
        resposta_json = {"resposta": resposta.text}

    return {
        "sucesso": resposta.status_code in [200, 201],
        "status_code": resposta.status_code,
        "venda_id": venda_id,
        "bling_id": bling_id,
        "url_consultada": url,
        "resposta_bling": resposta_json
    }

@app.post("/bling/confirmar-pedido/{venda_id}")
def confirmar_pedido_bling(venda_id: int):
    conexao = sqlite3.connect(BANCO)
    conexao.row_factory = sqlite3.Row
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT venda_id, bling_id
        FROM bling_sync
        WHERE venda_id = ?
        LIMIT 1
    """, (venda_id,))

    sync = cursor.fetchone()

    if not sync or not sync["bling_id"]:
        conexao.close()
        return {
            "sucesso": False,
            "mensagem": "Venda ainda não possui pedido no Bling."
        }

    cursor.execute("""
        SELECT *
        FROM bling_pedidos
        WHERE venda_id = ?
        LIMIT 1
    """, (venda_id,))

    pedido = cursor.fetchone()

    if pedido:
        cursor.execute("""
            UPDATE bling_pedidos
            SET bling_venda_id = ?,
                bling_pedido_id = ?,
                status = 'GERADO',
                erro = NULL,
                data_atualizacao = datetime('now', '-3 hours')
            WHERE venda_id = ?
        """, (
            sync["bling_id"],
            sync["bling_id"],
            venda_id
        ))
    else:
        cursor.execute("""
            INSERT INTO bling_pedidos (
                venda_id,
                bling_venda_id,
                bling_pedido_id,
                status,
                data_criacao,
                data_atualizacao
            )
            VALUES (?, ?, ?, 'GERADO', datetime('now', '-3 hours'), datetime('now', '-3 hours'))
        """, (
            venda_id,
            sync["bling_id"],
            sync["bling_id"]
        ))

    conexao.commit()

    cursor.execute("""
        SELECT *
        FROM bling_pedidos
        WHERE venda_id = ?
        LIMIT 1
    """, (venda_id,))

    pedido_atualizado = cursor.fetchone()

    conexao.close()

    return {
        "sucesso": True,
        "mensagem": "Pedido confirmado como gerado no Bling.",
        "pedido": dict(pedido_atualizado)
    }

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
            <strong>Informações do Fiado</strong><br>
            Retirado por: {fiado["retirado_por"]}<br>
            Saldo anterior: R$ {moeda(fiado["saldo_anterior"])}<br>
            Compra atual: R$ {moeda(venda["valor_total"])}<br>
            Saldo atual: R$ {moeda(fiado["saldo_atual"])}
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
            margin-top:12px;
            font-size:22px;
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

        .pedido-info{{
            margin-top:20px;
            display:grid;
            grid-template-columns:repeat(2,1fr);
            gap:12px;
        }}

        .pedido-info div{{
            background:#f8fafc;
            border:1px solid #e5e7eb;
            border-radius:12px;
            padding:12px 14px;
        }}

        .pedido-info strong{{
            display:block;
            color:#64748b;
            font-size:12px;
            margin-bottom:4px;
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
            margin-top: 25px;
        }}

        th {{
            background: #020617;
            color: white;
            padding:14px;
            font-size:14px;
            text-transform:uppercase;
        }}

        td {{
            padding: 14px;
            border-bottom: 1px solid #e5e7eb;
            font-size:15px;
        }}

        tbody tr:hover{{
            background:#f8fafc;

        }}

        .total {{
            text-align: right;
            margin-top: 25px;
        }}

        .total-label{{
            color:#64748b;
            font-size:14px;
        }}

        .total-valor{{
            font-size:42px;
            font-weight:900;
            color:#020617;
        }}

        .acoes {{
            display:flex;
            justify-content:center;
            margin-top:30px;
        }}

        .btn {{
            bbackground:#1683ff;
            color:white;
            border:none;
            padding:16px 30px;
            border-radius:999px;
            cursor:pointer;
            font-size:16px;
            font-weight:bold;
            transition:.25s;
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
                box-shadow: none;
                border-radius: 0;
                max-width:none;
            }}

            .acoes {{
                display: none;
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

        <div class="pedido-info">

            <div>
                <strong>Cliente</strong>
                {cliente_nome}
        </div>

        <div>
            <strong>Telefone</strong>
            {telefone if telefone else "Não informado"}
        </div>

        <div>
            <strong>Pagamento</strong>
            {venda["forma_pagamento"].upper()}
        </div>

        <div>
            <strong>Data</strong>
            {data_formatada}
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
                <button class="btn" onclick="window.print()">
                    Imprimir / Salvar PDF
                </button>
            </div>

            <div class="rodape">
                Obrigado pela preferência ❤️
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

    resultado_bling = bling_enviar_venda(venda_id)

    if resultado_bling.get("sucesso"):
        mensagem_final = f"Venda Nº {venda_id} registrada e sincronizada com o Bling com sucesso"
    else:
        mensagem_final = (
            f"Venda Nº {venda_id} registrada com sucesso, "
            f"mas não foi possível sincronizar com o Bling automaticamente"
        )

    return {
        "sucesso": True,
        "mensagem": mensagem_final,
        "mensagem_whatsapp": mensagem_whatsapp,
        "telefone_whatsapp": telefone,
        "bling": resultado_bling
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
