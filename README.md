# Star Limp Business

> **Sistema web de gestão comercial desenvolvido para automatizar processos de vendas, estoque, clientes, pagamentos e integração com ERP, criado inicialmente para atender uma empresa real do segmento de produtos de limpeza e evoluído para uma plataforma de gestão comercial.**

O **Star Limp Business** nasceu para resolver um problema real de uma empresa familiar, substituindo controles manuais por uma plataforma web centralizada. Atualmente, o projeto evolui para uma solução de gestão comercial capaz de atender diferentes tipos de negócios, automatizando processos e integrando operações com o ERP Bling.

---

# 🚀 Status do Projeto
 Em desenvolvimento ativo.

Sistema em produção e em constante evolução com novas funcionalidades.

---

# Demonstração

A aplicação está disponível em produção:

**https://star-limp-ia.onrender.com/**

---

# Objetivo

Centralizar a gestão comercial em uma única plataforma, automatizando processos de vendas, estoque, clientes, pagamentos e integração com ERPs, reduzindo retrabalho e aumentando a eficiência operacional.

---

# Funcionalidades

## Gestão Comercial

- Cadastro de clientes
- Cadastro de produtos
- Ponto de Venda (PDV)
- Controle de estoque
- Histórico de vendas
- Controle de pagamentos
- Gestão de contas de clientes
- Dashboard gerencial
- Relatórios comerciais

## Integração com ERP Bling

- Autenticação OAuth 2.0
- Sincronização automática de vendas
- Cadastro e consulta de clientes
- Associação automática entre clientes locais e clientes do ERP
- Associação automática entre produtos locais e produtos cadastrados no Bling
- Geração automática de pedidos de venda
- Armazenamento do ID do pedido retornado pela API
- Consulta automática do pedido no ERP
- Geração e download do PDF do pedido de venda
- Controle de sincronizações
- Tratamento de falhas de integração

## Automações

- Sincronização automática entre sistema e ERP
- Atualização automática do estoque
- Registro de logs
- Controle das vendas pendentes
- Automação do fluxo comercial

## Comunicação

- Geração automática de mensagens para WhatsApp
- Compartilhamento das informações da venda
- Compartilhamento do PDF do pedido com o cliente
- Atendimento mais rápido ao cliente

---

# Diferenciais

- Desenvolvido para resolver um problema real de negócio.
- Sistema utilizado em ambiente de produção.
- Interface otimizada para computadores e dispositivos móveis.
- Integração completa com a API REST do Bling utilizando OAuth 2.0.
- Backend desenvolvido com FastAPI.
- Deploy em produção utilizando Render.
- Arquitetura preparada para expansão e novas integrações.
- Geração automática de pedidos de venda no ERP.
- Download do PDF oficial do pedido diretamente pela aplicação.
- Compartilhamento do pedido via WhatsApp com apenas um clique.

---

# Tecnologias Utilizadas

| Tecnologia | Finalidade |
|------------|------------|
| Python | Linguagem principal |
| FastAPI | Backend |
| SQLite | Banco de dados |
| HTML5 | Interface |
| CSS3 | Estilização |
| JavaScript | Funcionalidades do frontend |
| Jinja2 | Templates |
| REST API | Comunicação entre sistemas |
| OAuth 2.0 | Autenticação |
| Bling API | Integração com ERP |
| Git | Versionamento |
| GitHub | Repositório |
| Render | Deploy |
| PWA | Aplicação instalável |

---

# Arquitetura

```text
Usuário
    │
    ▼
Frontend (HTML + CSS + JavaScript + Jinja2)
    │
    ▼
FastAPI
    │
    ├── SQLite
    │
    ├── API REST do Bling (OAuth 2.0)
    │
    └── WhatsApp
```

A aplicação foi desenvolvida utilizando FastAPI no backend, SQLite para persistência dos dados e templates Jinja2 para renderização das páginas. A integração com o ERP Bling é realizada por meio de API REST utilizando OAuth 2.0, permitindo sincronizar automaticamente clientes, produtos e vendas.

---

# Fluxo da Aplicação

1. Cadastro de clientes e produtos.
2. Registro da venda pelo PDV.
3. Atualização automática do estoque.
4. Registro financeiro da venda.
5. Inclusão da venda na fila de sincronização.
6. Envio automático para o ERP Bling.
7. Geração automática do pedido de venda.
8. Consulta do pedido no ERP.
9. Geração do PDF oficial do pedido.
10. Compartilhamento do pedido com o cliente via WhatsApp.

---

# Desafios Técnicos

O principal desafio do projeto foi integrar a aplicação ao ERP Bling utilizando OAuth 2.0 e manter a sincronização consistente entre os dados locais e o ERP.

Para resolver esse desafio foram implementados:

- Gerenciamento automático de tokens OAuth.
- Associação entre clientes locais e clientes cadastrados no Bling.
- Associação automática de produtos por código.
- Fila de sincronização para vendas pendentes.
- Tratamento de falhas na comunicação com a API.
- Registro dos identificadores retornados pelo ERP para rastreabilidade das vendas.

Essas implementações permitiram automatizar um processo que anteriormente era realizado manualmente, reduzindo retrabalho e aumentando a confiabilidade das informações.

---

# Como Executar

Clone o repositório:

```bash
git clone https://github.com/xJoyceDias/star-limp-ia.git
```

Entre na pasta:

```bash
cd star-limp-ia
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

Execute:

```bash
uvicorn backend.app:app --reload
```

Acesse:

```
http://127.0.0.1:8000
```

---

# Próximas Melhorias

- Controle de fornecedores.
- Controle de compras.
- Dashboard com gráficos.
- Relatórios avançados.
- Módulo financeiro completo.
- Novas integrações via API.
- Controle de múltiplas empresas.

---

# Autora

**Joyce Dias**

Estudante de Engenharia de Software com foco em desenvolvimento backend, automação de processos e integração de sistemas.

O **Star Limp Business** foi desenvolvido para solucionar um problema real de negócio, aplicando conceitos de Engenharia de Software, APIs REST, OAuth 2.0, FastAPI e arquitetura de aplicações web.
