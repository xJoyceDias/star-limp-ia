# Star Limp Business

> **Star Limp Business é um sistema comercial independente para gestão de produtos, estoque, vendas, clientes, contas e operações da loja.**

## Status

Em desenvolvimento ativo, com interface web responsiva e suporte a instalação como PWA.

## Demonstração

https://star-limp-ia.onrender.com/

## Funcionalidades

- Ponto de venda (PDV)
- Registro e consulta de vendas
- Cadastro, consulta e importação de produtos
- Controle de estoque
- Cadastro e consulta de clientes
- Contas de clientes (fiado)
- Registro de pagamentos
- Extrato de cliente
- Relatórios comerciais por período
- Mensagens de venda via WhatsApp
- Backup automático do banco de dados
- PWA instalável

## Tecnologias

| Tecnologia | Uso |
|---|---|
| Python | Linguagem principal |
| FastAPI | Aplicação web e API |
| SQLite | Persistência dos dados comerciais |
| Jinja2 | Templates HTML |
| HTML, CSS e JavaScript | Interface atual |
| Uvicorn | Servidor ASGI |
| Render | Deploy |
| PWA | Aplicação instalável |

## Arquitetura

```text
Usuário
  ↓
Interface web (HTML, CSS, JavaScript e Jinja2)
  ↓
FastAPI
  ↓
SQLite
```

Os dados comerciais são mantidos no banco próprio da aplicação. Vendas atualizam o estoque, registram os itens e mantêm as contas de clientes e pagamentos quando aplicável.

## Executar localmente

```bash
git clone https://github.com/xJoyceDias/star-limp-ia.git
cd star-limp-ia
git switch refactor/remove-bling
pip install -r requirements.txt
uvicorn backend.app:app --reload
```

Acesse http://127.0.0.1:8000.

## Migração do banco existente

Ao iniciar, a aplicação executa uma migração segura apenas se encontrar estruturas da antiga integração. Antes de qualquer mudança, ela cria um backup integral em database/backups/ (ou /data/backups/ em produção).

A migração preserva produtos, clientes, vendas, itens de venda, estoque, contas e pagamentos.

## Próximas melhorias

- Controle de fornecedores
- Controle de compras
- Dashboard com gráficos
- Relatórios avançados
- Módulo financeiro ampliado
- Múltiplas empresas

## Autora

Joyce Dias
