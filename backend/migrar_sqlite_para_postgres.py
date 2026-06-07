import os
import sqlite3
import psycopg2
from psycopg2.extras import execute_values

SQLITE_DB = "database/starlimp.db"
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise Exception("DATABASE_URL não encontrada.")

sqlite_conn = sqlite3.connect(SQLITE_DB)
sqlite_cursor = sqlite_conn.cursor()

pg_conn = psycopg2.connect(DATABASE_URL)
pg_cursor = pg_conn.cursor()

pg_cursor.execute("""
CREATE TABLE IF NOT EXISTS produtos (
    id SERIAL PRIMARY KEY,
    id_bling TEXT,
    codigo TEXT,
    descricao TEXT,
    unidade TEXT,
    preco NUMERIC,
    situacao TEXT,
    estoque NUMERIC,
    preco_custo NUMERIC,
    fornecedor TEXT,
    marca TEXT,
    categoria TEXT
);

CREATE TABLE IF NOT EXISTS vendas (
    id SERIAL PRIMARY KEY,
    data_hora TEXT,
    valor_total NUMERIC,
    forma_pagamento TEXT
);

CREATE TABLE IF NOT EXISTS itens_venda (
    id SERIAL PRIMARY KEY,
    venda_id INTEGER REFERENCES vendas(id),
    codigo_produto TEXT,
    descricao TEXT,
    quantidade NUMERIC,
    preco_unitario NUMERIC,
    subtotal NUMERIC
);

CREATE TABLE IF NOT EXISTS clientes (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    telefone TEXT,
    saldo_fiado NUMERIC DEFAULT 0,
    data_cadastro TEXT
);

CREATE TABLE IF NOT EXISTS fiados (
    id SERIAL PRIMARY KEY,
    venda_id INTEGER REFERENCES vendas(id),
    cliente_id INTEGER REFERENCES clientes(id),
    cliente_nome TEXT,
    telefone TEXT,
    retirado_por TEXT,
    valor_compra NUMERIC,
    saldo_anterior NUMERIC,
    saldo_atual NUMERIC,
    data_hora TEXT,
    status TEXT DEFAULT 'ABERTO'
);

CREATE TABLE IF NOT EXISTS pagamentos_fiado (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER NOT NULL,
    valor_pago NUMERIC NOT NULL,
    saldo_anterior NUMERIC NOT NULL,
    saldo_atual NUMERIC NOT NULL,
    data_hora TEXT NOT NULL,
    forma_pagamento TEXT
);
""")

pg_conn.commit()


def migrar_tabela(nome_tabela, colunas):
    sqlite_cursor.execute(f"SELECT {', '.join(colunas)} FROM {nome_tabela}")
    dados = sqlite_cursor.fetchall()

    if not dados:
        print(f"{nome_tabela}: sem dados.")
        return

    campos = ", ".join(colunas)

    query = f"""
        INSERT INTO {nome_tabela} ({campos})
        VALUES %s
    """

    execute_values(pg_cursor, query, dados)
    pg_conn.commit()

    print(f"{nome_tabela}: {len(dados)} registros migrados.")


migrar_tabela("produtos", [
    "id_bling", "codigo", "descricao", "unidade", "preco",
    "situacao", "estoque", "preco_custo", "fornecedor", "marca", "categoria"
])

migrar_tabela("vendas", [
    "id", "data_hora", "valor_total", "forma_pagamento"
])

migrar_tabela("itens_venda", [
    "id", "venda_id", "codigo_produto", "descricao",
    "quantidade", "preco_unitario", "subtotal"
])

migrar_tabela("clientes", [
    "id", "nome", "telefone", "saldo_fiado", "data_cadastro"
])

migrar_tabela("fiados", [
    "id", "venda_id", "cliente_id", "cliente_nome", "telefone",
    "retirado_por", "valor_compra", "saldo_anterior",
    "saldo_atual", "data_hora", "status"
])

migrar_tabela("pagamentos_fiado", [
    "id", "cliente_id", "valor_pago", "saldo_anterior",
    "saldo_atual", "data_hora", "forma_pagamento"
])

pg_cursor.close()
pg_conn.close()
sqlite_conn.close()

print("Migração concluída com sucesso.")