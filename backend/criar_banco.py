import sqlite3

BANCO = "database/starlimp.db"

conexao = sqlite3.connect(BANCO)
cursor = conexao.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS produtos (
    id_bling TEXT,
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
CREATE TABLE IF NOT EXISTS vendas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_hora TEXT,
    valor_total REAL,
    forma_pagamento TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS itens_venda (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venda_id INTEGER,
    codigo_produto TEXT,
    descricao TEXT,
    quantidade REAL,
    preco_unitario REAL,
    subtotal REAL,
    FOREIGN KEY (venda_id) REFERENCES vendas(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    telefone TEXT,
    saldo_fiado REAL DEFAULT 0,
    data_cadastro TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS fiados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venda_id INTEGER,
    cliente_id INTEGER,
    cliente_nome TEXT,
    telefone TEXT,
    retirado_por TEXT,
    valor_compra REAL,
    saldo_anterior REAL,
    saldo_atual REAL,
    data_hora TEXT,
    status TEXT DEFAULT 'ABERTO',
    FOREIGN KEY (venda_id) REFERENCES vendas(id),
    FOREIGN KEY (cliente_id) REFERENCES clientes(id)
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS pagamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER,
    valor REAL,
    data_hora TEXT
)
""")
conexao.commit()
conexao.close()

print("Banco atualizado com clientes e fiados!")