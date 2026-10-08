# Arquitetura Cloudflare: Star Limp PDV

A arquitetura nova usa **Cloudflare Workers** para a API, **D1** para os dados e **Static Assets** para a interface. Ela substitui o FastAPI/SQLite somente depois da importação e validação dos dados.

## O que já está nesta branch

- `cloudflare/src/worker.js`: API do PDV.
- `cloudflare/public/`: painel, venda de balcão, produtos e impressão pelo navegador.
- `cloudflare/schema.sql`: tabelas D1.
- `cloudflare/exportar_sqlite_para_d1.py`: exporta o SQLite atual em SQL.
- `wrangler.toml`: configuração do Worker.

## Publicação

Execute localmente com Node.js 20+:

```bash
npm install -g wrangler
wrangler login
wrangler d1 create starlimp-pdv
```

Copie o `database_id` retornado para `wrangler.toml`.

Crie as tabelas:

```bash
wrangler d1 execute starlimp-pdv --remote --file=cloudflare/schema.sql
```

Exporte o banco atual e importe os dados:

```bash
python cloudflare/exportar_sqlite_para_d1.py database/starlimp.db cloudflare/dados-d1.sql
wrangler d1 execute starlimp-pdv --remote --file=cloudflare/dados-d1.sql
```

Publique:

```bash
wrangler deploy
```

## Antes de trocar o endereço público

1. Abra a URL do Worker.
2. Confira produtos e preços.
3. Faça uma venda de teste.
4. Imprima um recibo para a Atomo pelo diálogo do navegador.
5. Compare totais e clientes com a versão antiga.

> A arquitetura inicial migra o fluxo central de PDV e produtos. Recebimentos de fiado, clientes completos, relatórios e cancelamento devem ser portados antes de desligar a hospedagem anterior.
