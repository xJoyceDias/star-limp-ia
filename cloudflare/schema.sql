PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS clientes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nome TEXT NOT NULL,
  telefone TEXT,
  cpf_cnpj TEXT,
  saldo_fiado REAL NOT NULL DEFAULT 0,
  data_cadastro TEXT,
  endereco TEXT
);

CREATE TABLE IF NOT EXISTS produtos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  codigo TEXT,
  descricao TEXT NOT NULL,
  unidade TEXT DEFAULT 'UN',
  preco REAL NOT NULL DEFAULT 0,
  situacao TEXT DEFAULT 'Ativo',
  estoque REAL NOT NULL DEFAULT 0,
  preco_custo REAL,
  fornecedor TEXT,
  marca TEXT,
  categoria TEXT
);

CREATE TABLE IF NOT EXISTS vendas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  data_hora TEXT NOT NULL,
  valor_total REAL NOT NULL,
  forma_pagamento TEXT NOT NULL,
  cliente_id INTEGER,
  status TEXT NOT NULL DEFAULT 'CONCLUIDA',
  taxa_entrega REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS itens_venda (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  venda_id INTEGER NOT NULL,
  codigo_produto TEXT,
  descricao TEXT NOT NULL,
  quantidade REAL NOT NULL,
  preco_unitario REAL NOT NULL,
  subtotal REAL NOT NULL,
  FOREIGN KEY (venda_id) REFERENCES vendas(id)
);

CREATE TABLE IF NOT EXISTS fiados (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  venda_id INTEGER NOT NULL,
  cliente_id INTEGER,
  cliente_nome TEXT,
  telefone TEXT,
  retirado_por TEXT,
  valor_compra REAL NOT NULL,
  saldo_anterior REAL NOT NULL DEFAULT 0,
  saldo_atual REAL NOT NULL DEFAULT 0,
  data_hora TEXT NOT NULL,
  status TEXT DEFAULT 'ABERTO',
  FOREIGN KEY (venda_id) REFERENCES vendas(id),
  FOREIGN KEY (cliente_id) REFERENCES clientes(id)
);

CREATE TABLE IF NOT EXISTS pagamentos_fiado (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  cliente_id INTEGER NOT NULL,
  valor_pago REAL NOT NULL,
  data_hora TEXT NOT NULL,
  forma_pagamento TEXT,
  observacao TEXT,
  FOREIGN KEY (cliente_id) REFERENCES clientes(id)
);

CREATE INDEX IF NOT EXISTS idx_produtos_descricao ON produtos(descricao);
CREATE INDEX IF NOT EXISTS idx_vendas_data ON vendas(data_hora);
CREATE INDEX IF NOT EXISTS idx_itens_venda_venda ON itens_venda(venda_id);


CREATE TABLE IF NOT EXISTS contas_pagar (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fornecedor TEXT,
  descricao TEXT,
  linha_digitavel TEXT,
  valor REAL NOT NULL DEFAULT 0,
  vencimento TEXT,
  status TEXT NOT NULL DEFAULT 'PENDENTE',
  arquivo_nome TEXT,
  criado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS baixas_conta_pagar (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conta_id INTEGER NOT NULL,
  banco TEXT NOT NULL,
  valor_pago REAL NOT NULL,
  data_pagamento TEXT NOT NULL,
  observacao TEXT,
  FOREIGN KEY (conta_id) REFERENCES contas_pagar(id)
);

CREATE INDEX IF NOT EXISTS idx_contas_pagar_status ON contas_pagar(status);
CREATE INDEX IF NOT EXISTS idx_baixas_conta ON baixas_conta_pagar(conta_id);
