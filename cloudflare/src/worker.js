const json = (data, init = {}) =>
  new Response(JSON.stringify(data), {
    ...init,
    headers: { "content-type": "application/json; charset=utf-8", ...(init.headers || {}) },
  });

const erro = (mensagem, status = 400) => json({ sucesso: false, mensagem }, { status });
const agora = () => new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString().slice(0, 19).replace("T", " ");
const numero = (valor) => Number(valor || 0);
const normalizarItens = (itens) => itens.map((item) => {
  const quantidade = numero(item.quantidade);
  const preco = numero(item.preco);
  const subtotal = Number((quantidade * preco - numero(item.desconto)).toFixed(2));
  return { codigo: String(item.codigo || ""), produto: String(item.produto || "").trim(), quantidade, preco, subtotal };
});

async function dashboard(DB) {
  const inicioHoje = new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString().slice(0, 10);
  const [hoje, semana, mes, receber, devendo, clientes] = await DB.batch([
    DB.prepare("SELECT COALESCE(SUM(valor_total), 0) valor FROM vendas WHERE substr(data_hora, 1, 10) = ?").bind(inicioHoje),
    DB.prepare("SELECT COALESCE(SUM(valor_total), 0) valor FROM vendas WHERE date(data_hora) >= date(?, 'weekday 1', '-7 days')").bind(inicioHoje),
    DB.prepare("SELECT COALESCE(SUM(valor_total), 0) valor FROM vendas WHERE substr(data_hora, 1, 7) = substr(?, 1, 7)").bind(inicioHoje),
    DB.prepare("SELECT COALESCE(SUM(saldo_fiado), 0) valor FROM clientes"),
    DB.prepare("SELECT COUNT(*) quantidade FROM clientes WHERE saldo_fiado > 0"),
    DB.prepare("SELECT COUNT(*) quantidade FROM clientes"),
  ]);
  return {
    vendas_hoje: hoje.results[0].valor,
    vendas_semana: semana.results[0].valor,
    vendas_mes: mes.results[0].valor,
    total_receber: receber.results[0].valor,
    clientes_devendo: devendo.results[0].quantidade,
    total_clientes: clientes.results[0].quantidade,
  };
}

async function produtos(request, env, url) {
  if (request.method === "GET") {
    const termo = (url.searchParams.get("termo") || "").toLowerCase();
    const busca = "%" + termo + "%";
    const resultado = await env.DB.prepare(
      "SELECT id, codigo, descricao, unidade, preco, situacao, estoque, categoria FROM produtos WHERE lower(coalesce(codigo,'')) LIKE ? OR lower(descricao) LIKE ? ORDER BY descricao COLLATE NOCASE LIMIT 200"
    ).bind(busca, busca).all();
    return json(resultado.results);
  }
  const dados = await request.json();
  if (!String(dados.descricao || "").trim()) return erro("Informe a descrição do produto.");
  const comando = env.DB.prepare(
    "INSERT INTO produtos (codigo, descricao, unidade, preco, situacao, estoque, categoria) VALUES (?, ?, ?, ?, ?, ?, ?)"
  ).bind(String(dados.codigo || "").trim(), String(dados.descricao).trim(), String(dados.unidade || "UN").trim(), numero(dados.preco), String(dados.situacao || "Ativo"), numero(dados.estoque), String(dados.categoria || "").trim());
  const resultado = await comando.run();
  return json({ sucesso: true, id: resultado.meta.last_row_id, mensagem: "Produto cadastrado com sucesso." });
}

async function atualizarProduto(request, env, id) {
  const dados = await request.json();
  if (!String(dados.descricao || "").trim()) return erro("Informe a descrição do produto.");
  const resultado = await env.DB.prepare(
    "UPDATE produtos SET codigo=?, descricao=?, unidade=?, preco=?, situacao=?, estoque=?, categoria=? WHERE id=?"
  ).bind(String(dados.codigo || "").trim(), String(dados.descricao).trim(), String(dados.unidade || "UN").trim(), numero(dados.preco), String(dados.situacao || "Ativo"), numero(dados.estoque), String(dados.categoria || "").trim(), id).run();
  return resultado.meta.changes ? json({ sucesso: true, mensagem: "Produto atualizado com sucesso." }) : erro("Produto não encontrado.", 404);
}

async function criarVenda(request, env) {
  const dados = await request.json();
  const itens = normalizarItens(Array.isArray(dados.itens) ? dados.itens : []).filter((item) => item.produto && item.quantidade > 0);
  if (!itens.length) return erro("Adicione pelo menos um produto.");
  const forma = String(dados.forma_pagamento || "pix").toLowerCase();
  const total = Number(itens.reduce((soma, item) => soma + item.subtotal, 0).toFixed(2));
  const dataHora = agora();
  const venda = await env.DB.prepare("INSERT INTO vendas (data_hora, valor_total, forma_pagamento) VALUES (?, ?, ?)").bind(dataHora, total, forma).run();
  const vendaId = venda.meta.last_row_id;
  await env.DB.batch(itens.map((item) => env.DB.prepare(
    "INSERT INTO itens_venda (venda_id, codigo_produto, descricao, quantidade, preco_unitario, subtotal) VALUES (?, ?, ?, ?, ?, ?)"
  ).bind(vendaId, item.codigo, item.produto, item.quantidade, item.preco, item.subtotal)));
  return json({ sucesso: true, venda_id: vendaId, mensagem: "Venda registrada com sucesso.", total });
}

async function venda(env, id) {
  const cabecalho = await env.DB.prepare("SELECT * FROM vendas WHERE id = ?").bind(id).first();
  if (!cabecalho) return erro("Venda não encontrada.", 404);
  const itens = await env.DB.prepare("SELECT descricao, quantidade, preco_unitario, subtotal FROM itens_venda WHERE venda_id = ?").bind(id).all();
  return json({ venda: cabecalho, itens: itens.results });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (!url.pathname.startsWith("/api/")) return env.ASSETS.fetch(request);
    try {
      if (url.pathname === "/api/dashboard" && request.method === "GET") return json(await dashboard(env.DB));
      if (url.pathname === "/api/products" && (request.method === "GET" || request.method === "POST")) return produtos(request, env, url);
      const produto = url.pathname.match(/^\/api\/products\/(\d+)$/);
      if (produto && request.method === "PUT") return atualizarProduto(request, env, Number(produto[1]));
      if (url.pathname === "/api/sales" && request.method === "POST") return criarVenda(request, env);
      const vendaId = url.pathname.match(/^\/api\/sales\/(\d+)$/);
      if (vendaId && request.method === "GET") return venda(env, Number(vendaId[1]));
      return erro("Rota não encontrada.", 404);
    } catch (error) {
      console.error(error);
      return erro("Não foi possível concluir a operação.", 500);
    }
  },
};
