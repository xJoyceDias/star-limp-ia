# Star Limp IA

Sistema de gestão comercial desenvolvido para automatizar processos de vendas, clientes, pagamentos, estoque e integração com o ERP Bling.

O projeto foi criado para atender uma empresa familiar, com o objetivo de reduzir tarefas manuais, centralizar informações comerciais e tornar a operação mais eficiente por meio de uma plataforma web integrada.

---

## Status do Projeto

Em desenvolvimento.

---

## Demonstração

A aplicação está publicada e pode ser acessada pelo link abaixo:

[Star Limp IA - Deploy](https://starlimpia-production.up.railway.app/)

---

## Objetivo

Automatizar processos comerciais que antes eram feitos manualmente, como cadastro de clientes, controle de produtos, vendas, fiados, estoque e geração de pedidos no ERP Bling.

---

## Funcionalidades

### Gestão Comercial

- Cadastro de clientes
- Cadastro de produtos
- Ponto de Venda (PDV)
- Controle de estoque
- Histórico de vendas
- Controle de pagamentos
- Gestão de vendas fiado

### Integração com ERP Bling

- Autenticação OAuth 2.0
- Sincronização automática de vendas
- Cadastro e consulta de clientes no Bling
- Geração automática de pedidos de venda
- Armazenamento do ID do pedido retornado pela API
- Geração e download do PDF do pedido de venda

### Automações

- Sincronização automática entre o sistema e o Bling
- Controle de vendas pendentes de sincronização
- Tratamento de erros de integração
- Registro de logs das operações

### Comunicação com o Cliente

- Abertura automática do WhatsApp
- Geração de mensagem personalizada com resumo da venda
- Envio do link do PDF do pedido para o cliente, quando disponível
- Agilidade no atendimento e na confirmação do pedido

---

## Diferenciais

- Integração real com o ERP Bling utilizando API REST e OAuth 2.0
- Sincronização automática das vendas com o ERP
- Geração automática de pedidos de venda
- Download do PDF do pedido diretamente pela aplicação
- Compartilhamento do pedido via WhatsApp com apenas um clique
- Projeto desenvolvido para atender uma necessidade real de uma empresa familiar
- Automação de processos comerciais que antes eram feitos manualmente

---

## Tecnologias Utilizadas

| Tecnologia | Finalidade |
|------------|------------|
| Python | Linguagem principal |
| FastAPI | Desenvolvimento da API/backend |
| SQLite | Banco de dados |
| HTML | Estrutura das páginas |
| CSS | Estilização |
| JavaScript | Interações no frontend |
| Jinja2 | Templates HTML |
| API REST | Comunicação entre sistemas |
| OAuth 2.0 | Autenticação com Bling |
| Git e GitHub | Versionamento |
| Railway | Deploy |
| Bling API | Integração com ERP |

---

## Arquitetura

A aplicação foi desenvolvida com FastAPI no backend, utilizando SQLite para persistência de dados e templates Jinja2 para renderização das páginas.

O sistema realiza comunicação com APIs REST externas, incluindo a API do Bling, utilizando autenticação OAuth 2.0 para sincronização de dados, geração de pedidos de venda e obtenção do PDF do pedido.

A estrutura do projeto separa a aplicação backend, banco de dados, arquivos estáticos e templates HTML, facilitando a manutenção e evolução do sistema.

---

## Fluxo Principal

1. O usuário cadastra clientes e produtos no sistema.
2. As vendas são registradas pelo PDV.
3. O estoque e os fiados são atualizados automaticamente.
4. O sistema gera o pedido de venda.
5. As informações podem ser sincronizadas com o ERP Bling.
6. O PDF do pedido pode ser baixado e compartilhado com o cliente.
7. Relatórios e históricos ficam disponíveis para consulta.

---

## Como Executar o Projeto

1. Clone o repositório:

```bash
git clone https://github.com/xJoyceDias/star-limp-ia.git
```

2. Acesse a pasta do projeto:

```bash
cd star-limp-ia
```

3. Instale as dependências:

```bash
pip install -r requirements.txt
```

4. Execute o servidor local:

```bash
uvicorn backend.app:app --reload
```

5. Acesse no navegador:

```text
http://127.0.0.1:8000
```

