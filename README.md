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

- Cadastro de clientes
- Cadastro de produtos
- PDV
- Controle de estoque
- Controle de fiados
- Histórico de vendas
- Relatórios comerciais
- Integração com a API do Bling
- Autenticação OAuth 2.0
- Sincronização automática com ERP
- Geração de pedidos

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

O sistema também realiza comunicação com APIs REST externas, incluindo a API do Bling, utilizando autenticação OAuth 2.0 para sincronização e geração de pedidos.

---

## Como Executar o Projeto

1. Clone o repositório:

```bash
git clone https://github.com/xJoyceDias/estrela-limpa-ia.git
```

2. Acesse a pasta do projeto:

```bash
cd estrela-limpa-ia
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

---

## Fluxo Principal

1. O usuário cadastra clientes e produtos no sistema.
2. As vendas são registradas pelo PDV.
3. O estoque e os fiados são atualizados automaticamente.
4. O sistema pode sincronizar informações com o ERP Bling.
5. Relatórios e históricos ficam disponíveis para consulta.

---

## Aprendizados

Durante o desenvolvimento deste projeto, foram aplicados conhecimentos em:

- Desenvolvimento backend com Python
- Criação de APIs com FastAPI
- Integração com APIs externas
- Autenticação OAuth 2.0
- Modelagem e persistência de dados
- Deploy em ambiente cloud
- Versionamento com Git e GitHub
- Automação de processos comerciais
- Organização de arquitetura de software
- Resolução de problemas reais de negócio

---

## Desenvolvido por

Joyce Dias
