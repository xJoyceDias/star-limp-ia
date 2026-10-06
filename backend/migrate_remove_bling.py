"""Migração segura que remove somente estruturas históricas da integração Bling."""

import os
import shutil
import sqlite3
from datetime import datetime


COLUNAS_REMOVIDAS = {
    "clientes": {"bling_contato_id"},
    "produtos": {"id_bling"},
    "vendas": {
        "pedido_bling_solicitado",
        "cliente_nome_bling",
        "cliente_telefone_bling",
        "cliente_documento_bling",
    },
}


def _colunas(cursor, tabela):
    cursor.execute(f"PRAGMA table_info({tabela})")
    return [linha[1] for linha in cursor.fetchall()]


def _precisa_migrar(cursor):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name IN ('bling_tokens', 'bling_sync', 'bling_pedidos')"
    )
    if cursor.fetchone():
        return True

    for tabela, colunas in COLUNAS_REMOVIDAS.items():
        if any(coluna in _colunas(cursor, tabela) for coluna in colunas):
            return True

    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'configuracoes'"
    )
    if cursor.fetchone():
        cursor.execute(
            "SELECT 1 FROM configuracoes WHERE chave = ? LIMIT 1",
            ("bling_consumidor_final_id",),
        )
        return cursor.fetchone() is not None

    return False


def _backup(caminho_banco):
    diretorio = os.path.join(os.path.dirname(caminho_banco) or ".", "backups")
    os.makedirs(diretorio, exist_ok=True)
    data = datetime.now().strftime("%Y%m%d-%H%M%S")
    destino = os.path.join(diretorio, f"starlimp-before-remove-bling-{data}.db")
    shutil.copy2(caminho_banco, destino)
    return destino


def _recriar_clientes(cursor):
    cursor.execute("""
        CREATE TABLE clientes_novo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            telefone TEXT,
            saldo_fiado REAL DEFAULT 0,
            data_cadastro TEXT
        )
    """)
    cursor.execute("""
        INSERT INTO clientes_novo (id, nome, telefone, saldo_fiado, data_cadastro)
        SELECT id, nome, telefone, saldo_fiado, data_cadastro FROM clientes
    """)
    cursor.execute("DROP TABLE clientes")
    cursor.execute("ALTER TABLE clientes_novo RENAME TO clientes")


def _recriar_produtos(cursor):
    cursor.execute("""
        CREATE TABLE produtos_novo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT,
            descricao TEXT,
            unidade TEXT,
            preco REAL,
            situacao TEXT,
            estoque REAL,
            preco_custo REAL,
            fornecedor TEXT,
            marca TEXT,
            categoria TEXT
        )
    """)
    cursor.execute("""
        INSERT INTO produtos_novo (
            codigo, descricao, unidade, preco, situacao, estoque,
            preco_custo, fornecedor, marca, categoria
        )
        SELECT
            codigo, descricao, unidade, preco, situacao, estoque,
            preco_custo, fornecedor, marca, categoria
        FROM produtos
    """)
    cursor.execute("DROP TABLE produtos")
    cursor.execute("ALTER TABLE produtos_novo RENAME TO produtos")


def _recriar_vendas(cursor):
    cursor.execute("""
        CREATE TABLE vendas_novo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT,
            valor_total REAL,
            forma_pagamento TEXT
        )
    """)
    cursor.execute("""
        INSERT INTO vendas_novo (id, data_hora, valor_total, forma_pagamento)
        SELECT id, data_hora, valor_total, forma_pagamento FROM vendas
    """)
    cursor.execute("DROP TABLE vendas")
    cursor.execute("ALTER TABLE vendas_novo RENAME TO vendas")


def migrar_banco(caminho_banco):
    """Aplica a migração uma única vez, sempre após criar um backup integral."""
    if not os.path.exists(caminho_banco):
        return None

    conexao = sqlite3.connect(caminho_banco)
    cursor = conexao.cursor()

    if not _precisa_migrar(cursor):
        conexao.close()
        return None

    backup = _backup(caminho_banco)

    try:
        if "bling_contato_id" in _colunas(cursor, "clientes"):
            _recriar_clientes(cursor)
        if "id_bling" in _colunas(cursor, "produtos"):
            _recriar_produtos(cursor)
        if "pedido_bling_solicitado" in _colunas(cursor, "vendas"):
            _recriar_vendas(cursor)

        for tabela in ("bling_tokens", "bling_sync", "bling_pedidos"):
            cursor.execute(f"DROP TABLE IF EXISTS {tabela}")

        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'configuracoes'"
        )
        if cursor.fetchone():
            cursor.execute(
                "DELETE FROM configuracoes WHERE chave = ?",
                ("bling_consumidor_final_id",),
            )

        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()

    return backup
