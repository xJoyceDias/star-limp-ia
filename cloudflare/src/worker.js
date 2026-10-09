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
    DB.prepare("SELECT COALESCE(SUM(valor_total), 0) valor FROM vendas WHERE COALESCE(status, 'CONCLUIDA') <> 'CANCELADA' AND substr(data_hora, 1, 10) = ?").bind(inicioHoje),
    DB.prepare("SELECT COALESCE(SUM(valor_total), 0) valor FROM vendas WHERE COALESCE(status, 'CONCLUIDA') <> 'CANCELADA' AND date(data_hora) >= date(?, 'weekday 1', '-7 days')").bind(inicioHoje),
    DB.prepare("SELECT COALESCE(SUM(valor_total), 0) valor FROM vendas WHERE COALESCE(status, 'CONCLUIDA') <> 'CANCELADA' AND substr(data_hora, 1, 7) = substr(?, 1, 7)").bind(inicioHoje),
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

async function proximoCodigoProduto(DB) {
  const resultado = await DB.prepare("SELECT codigo FROM produtos WHERE trim(coalesce(codigo,'')) <> ''").all();
  const usados = new Set(resultado.results.map((produto) => {
    const texto = String(produto.codigo || "").trim();
    return /^\d+$/.test(texto) ? Number(texto) : null;
  }).filter((codigo) => Number.isInteger(codigo) && codigo > 0));
  let proximo = 1;
  while (usados.has(proximo)) proximo++;
  return String(proximo);
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
  const codigo = String(dados.codigo || "").trim() || await proximoCodigoProduto(env.DB);
  const comando = env.DB.prepare(
    "INSERT INTO produtos (codigo, descricao, unidade, preco, situacao, estoque, categoria) VALUES (?, ?, ?, ?, ?, ?, ?)"
  ).bind(codigo, String(dados.descricao).trim(), String(dados.unidade || "UN").trim(), numero(dados.preco), String(dados.situacao || "Ativo"), numero(dados.estoque), String(dados.categoria || "").trim());
  const resultado = await comando.run();
  return json({ sucesso: true, id: resultado.meta.last_row_id, codigo, mensagem: "Produto cadastrado com sucesso." });
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
  let cliente = null;
  const clienteId = Number(dados.cliente_id);
  if (clienteId) {cliente = await env.DB.prepare("SELECT id, nome, telefone, cpf_cnpj, saldo_fiado FROM clientes WHERE id=?").bind(clienteId).first();if (!cliente) return erro("Cliente não encontrado.", 404);}
  if (forma === "fiado" && !cliente) return erro("Selecione ou cadastre o cliente para vender fiado.");
  const venda = await env.DB.prepare("INSERT INTO vendas (data_hora, valor_total, forma_pagamento, cliente_id) VALUES (?, ?, ?, ?)").bind(dataHora, total, forma, cliente?.id || null).run();
  const vendaId = venda.meta.last_row_id;
  const comandos = itens.map((item) => env.DB.prepare(
    "INSERT INTO itens_venda (venda_id, codigo_produto, descricao, quantidade, preco_unitario, subtotal) VALUES (?, ?, ?, ?, ?, ?)"
  ).bind(vendaId, item.codigo, item.produto, item.quantidade, item.preco, item.subtotal));
  if (cliente && forma === "fiado") {
    const saldoAnterior = numero(cliente.saldo_fiado);
    const saldoAtual = Number((saldoAnterior + total).toFixed(2));
    comandos.push(
      env.DB.prepare("INSERT INTO fiados (venda_id, cliente_id, cliente_nome, telefone, retirado_por, valor_compra, saldo_anterior, saldo_atual, data_hora, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ABERTO')")
        .bind(vendaId, cliente.id, cliente.nome, cliente.telefone || "", String(dados.retirado_por || cliente.nome), total, saldoAnterior, saldoAtual, dataHora),
      env.DB.prepare("UPDATE clientes SET saldo_fiado=? WHERE id=?").bind(saldoAtual, cliente.id)
    );
    cliente={...cliente,saldo_fiado:saldoAtual};
  }
  await env.DB.batch(comandos);
  return json({ sucesso: true, venda_id: vendaId, mensagem: forma === "fiado" ? "Venda fiada registrada com sucesso." : "Venda registrada com sucesso.", total, cliente });
}

async function detalheRecebivel(env, clienteId) {
  const cliente=await env.DB.prepare("SELECT id,nome,telefone,cpf_cnpj,saldo_fiado FROM clientes WHERE id=?").bind(clienteId).first();
  if(!cliente)return erro("Cliente não encontrado.",404);
  const [compras,pagamentos]=await env.DB.batch([
    env.DB.prepare("SELECT f.id,f.venda_id,f.valor_compra,f.data_hora,f.retirado_por, GROUP_CONCAT(i.descricao || ' (' || i.quantidade || 'x)', ' · ') itens FROM fiados f LEFT JOIN itens_venda i ON i.venda_id=f.venda_id WHERE f.cliente_id=? AND f.status<>'CANCELADO' GROUP BY f.id ORDER BY f.data_hora,f.id").bind(clienteId),
    env.DB.prepare("SELECT id,valor_pago,data_hora,forma_pagamento,observacao FROM pagamentos_fiado WHERE cliente_id=? ORDER BY data_hora,id").bind(clienteId)
  ]);
  let recebido=pagamentos.results.reduce((total,pagamento)=>total+numero(pagamento.valor_pago),0);
  const linhas=compras.results.map(compra=>{const pago=Math.min(numero(compra.valor_compra),recebido);recebido-=pago;const saldo=Number((numero(compra.valor_compra)-pago).toFixed(2));return {...compra,pago_na_compra:pago,saldo_aberto:saldo,status:saldo>0?'EM ABERTO':'QUITADA'}});
  return json({cliente,compras:linhas,pagamentos:pagamentos.results});
}
async function receberFiado(request, env) {
  if (request.method === "GET") {
    const resultado=await env.DB.prepare("SELECT id,nome,telefone,cpf_cnpj,saldo_fiado FROM clientes WHERE saldo_fiado>0 ORDER BY nome COLLATE NOCASE").all();
    return json(resultado.results);
  }
  const dados=await request.json(),clienteId=Number(dados.cliente_id),valor=numero(dados.valor_pago);
  if(!clienteId||valor<=0)return erro("Selecione o cliente e informe o valor recebido.");
  const cliente=await env.DB.prepare("SELECT id,nome,telefone,cpf_cnpj,saldo_fiado FROM clientes WHERE id=?").bind(clienteId).first();
  if(!cliente)return erro("Cliente não encontrado.",404);
  const saldoAnterior=numero(cliente.saldo_fiado),recebido=Math.min(valor,saldoAnterior),saldoAtual=Number((saldoAnterior-recebido).toFixed(2)),data=agora(),forma=String(dados.forma_pagamento||"pix");
  await env.DB.batch([
    env.DB.prepare("INSERT INTO pagamentos_fiado (cliente_id,valor_pago,data_hora,forma_pagamento,observacao) VALUES (?, ?, ?, ?, ?)").bind(clienteId,recebido,data,forma,String(dados.observacao||"").trim()),
    env.DB.prepare("UPDATE clientes SET saldo_fiado=? WHERE id=?").bind(saldoAtual,clienteId)
  ]);
  return json({sucesso:true,valor:recebido,saldo_anterior:saldoAnterior,saldo_atual:saldoAtual,data_hora:data,forma_pagamento:forma,cliente:{...cliente,saldo_fiado:saldoAtual},mensagem:"Pagamento registrado."});
}

async function listarVendas(env) {
  const resultado = await env.DB.prepare("SELECT v.id, v.data_hora, v.valor_total, v.forma_pagamento, v.status, f.cliente_nome FROM vendas v LEFT JOIN fiados f ON f.venda_id=v.id ORDER BY v.id DESC LIMIT 200").all();
  return json(resultado.results);
}
async function atualizarVenda(request, env, id) {
  const atual = await env.DB.prepare("SELECT * FROM vendas WHERE id=?").bind(id).first();
  if (!atual) return erro("Venda não encontrada.",404);
  if (atual.status === "CANCELADA") return erro("Não é possível editar uma venda cancelada.");
  const dados = await request.json();
  const forma = String(dados.forma_pagamento || atual.forma_pagamento).toLowerCase();
  await env.DB.prepare("UPDATE vendas SET forma_pagamento=? WHERE id=?").bind(forma,id).run();
  return json({sucesso:true,mensagem:"Forma de pagamento atualizada."});
}
async function cancelarVenda(env, id) {
  const venda = await env.DB.prepare("SELECT * FROM vendas WHERE id=?").bind(id).first();
  if (!venda) return erro("Venda não encontrada.",404);
  if (venda.status === "CANCELADA") return erro("Esta venda já está cancelada.");
  const fiado = await env.DB.prepare("SELECT * FROM fiados WHERE venda_id=? AND status='ABERTO'").bind(id).first();
  const comandos=[env.DB.prepare("UPDATE vendas SET status='CANCELADA' WHERE id=?").bind(id)];
  if(fiado){comandos.push(env.DB.prepare("UPDATE clientes SET saldo_fiado=MAX(0,saldo_fiado-?) WHERE id=?").bind(fiado.valor_compra,fiado.cliente_id),env.DB.prepare("UPDATE fiados SET status='CANCELADO' WHERE id=?").bind(fiado.id))}
  await env.DB.batch(comandos);
  return json({sucesso:true,mensagem:"Venda cancelada e histórico preservado."});
}

async function venda(env, id) {
  const cabecalho = await env.DB.prepare("SELECT * FROM vendas WHERE id = ?").bind(id).first();
  if (!cabecalho) return erro("Venda não encontrada.", 404);
  const itens = await env.DB.prepare("SELECT descricao, quantidade, preco_unitario, subtotal FROM itens_venda WHERE venda_id = ?").bind(id).all();
  const cliente = cabecalho.cliente_id ? await env.DB.prepare("SELECT id, nome, telefone, cpf_cnpj, saldo_fiado FROM clientes WHERE id=?").bind(cabecalho.cliente_id).first() : null;
  const fiado = cabecalho.cliente_id ? await env.DB.prepare("SELECT retirado_por, saldo_anterior, saldo_atual FROM fiados WHERE venda_id=?").bind(id).first() : null;
  return json({ venda: cabecalho, itens: itens.results, cliente, fiado });
}

const normalizarCliente = valor => String(valor||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/\s+/g,' ').trim();
async function clientes(request,env,url){if(request.method==='GET'){const r=await env.DB.prepare("SELECT id,nome,telefone,cpf_cnpj,saldo_fiado,data_cadastro FROM clientes ORDER BY nome COLLATE NOCASE").all();return json(r.results)}const d=await request.json(),nome=String(d.nome||'').trim(),telefone=String(d.telefone||'').replace(/\D/g,''),documento=String(d.cpf_cnpj||'').replace(/\D/g,'');if(!nome)return erro('Informe o nome do cliente.');const e=await env.DB.prepare("SELECT id,nome,telefone,cpf_cnpj,saldo_fiado FROM clientes").all(),found=e.results.find(c=>normalizarCliente(c.nome)===normalizarCliente(nome)||(telefone&&String(c.telefone||'').replace(/\D/g,'')===telefone)||(documento&&String(c.cpf_cnpj||'').replace(/\D/g,'')===documento));if(found)return json({sucesso:true,existente:true,id:found.id,cliente:found,mensagem:'Cliente já cadastrado e selecionado.'});const r=await env.DB.prepare("INSERT INTO clientes (nome,telefone,cpf_cnpj,saldo_fiado,data_cadastro) VALUES (?, ?, ?, 0, ?)").bind(nome,telefone,documento,agora()).run();return json({sucesso:true,id:r.meta.last_row_id,cliente:{id:r.meta.last_row_id,nome,telefone,cpf_cnpj:documento,saldo_fiado:0},mensagem:'Cliente cadastrado com sucesso.'})}
async function atualizarCliente(request,env,id){const d=await request.json(),nome=String(d.nome||'').trim(),telefone=String(d.telefone||'').replace(/\D/g,''),documento=String(d.cpf_cnpj||'').replace(/\D/g,'');if(!nome)return erro('Informe o nome do cliente.');const current=await env.DB.prepare("SELECT id FROM clientes WHERE id=?").bind(id).first();if(!current)return erro('Cliente não encontrado.',404);const e=await env.DB.prepare("SELECT id,nome,telefone,cpf_cnpj FROM clientes WHERE id<>?").bind(id).all(),dup=e.results.find(c=>normalizarCliente(c.nome)===normalizarCliente(nome)||(telefone&&String(c.telefone||'').replace(/\D/g,'')===telefone)||(documento&&String(c.cpf_cnpj||'').replace(/\D/g,'')===documento));if(dup)return erro('Já existe outro cliente com esse nome, telefone ou CPF/CNPJ.');await env.DB.prepare("UPDATE clientes SET nome=?,telefone=?,cpf_cnpj=? WHERE id=?").bind(nome,telefone,documento,id).run();return json({sucesso:true,mensagem:'Cliente atualizado.'})}
async function excluirCliente(env,id){const c=await env.DB.prepare("SELECT id,saldo_fiado FROM clientes WHERE id=?").bind(id).first();if(!c)return erro('Cliente não encontrado.',404);if(numero(c.saldo_fiado)>0)return erro('Não é possível remover um cliente com saldo em aberto.');const [v,f,p]=await env.DB.batch([env.DB.prepare("SELECT COUNT(*) quantidade FROM vendas WHERE cliente_id=?").bind(id),env.DB.prepare("SELECT COUNT(*) quantidade FROM fiados WHERE cliente_id=?").bind(id),env.DB.prepare("SELECT COUNT(*) quantidade FROM pagamentos_fiado WHERE cliente_id=?").bind(id)]);if(numero(v.results[0].quantidade)||numero(f.results[0].quantidade)||numero(p.results[0].quantidade))return erro('Não é possível remover um cliente com histórico de vendas ou pagamentos.');await env.DB.prepare("DELETE FROM clientes WHERE id=?").bind(id).run();return json({sucesso:true,mensagem:'Cliente removido.'})}

async function contasPagar(request, env, url) {
  if (request.method === "GET") {
    const status = url.searchParams.get("status") || "";
    const comando = status ? env.DB.prepare("SELECT c.*, COALESCE((SELECT SUM(valor_pago) FROM baixas_conta_pagar b WHERE b.conta_id=c.id),0) AS total_baixado FROM contas_pagar c WHERE c.status=? ORDER BY CASE c.status WHEN 'PENDENTE' THEN 0 ELSE 1 END, c.vencimento, c.id DESC").bind(status) : env.DB.prepare("SELECT c.*, COALESCE((SELECT SUM(valor_pago) FROM baixas_conta_pagar b WHERE b.conta_id=c.id),0) AS total_baixado FROM contas_pagar c ORDER BY CASE c.status WHEN 'PENDENTE' THEN 0 ELSE 1 END, c.vencimento, c.id DESC");
    const resultado = await comando.all();
    return json(resultado.results);
  }
  const dados = await request.json();
  if (!numero(dados.valor) || numero(dados.valor) <= 0) return erro("Informe o valor do boleto.");
  const criadoEm = agora();
  const resultado = await env.DB.prepare("INSERT INTO contas_pagar (fornecedor, descricao, linha_digitavel, valor, vencimento, status, arquivo_nome, criado_em) VALUES (?, ?, ?, ?, ?, 'PENDENTE', ?, ?)")
    .bind(String(dados.fornecedor || "").trim(), String(dados.descricao || "Boleto importado").trim(), String(dados.linha_digitavel || "").replace(/\D/g, ""), numero(dados.valor), String(dados.vencimento || "").trim() || null, String(dados.arquivo_nome || "").trim(), criadoEm).run();
  return json({ sucesso:true, id:resultado.meta.last_row_id, mensagem:"Conta a pagar cadastrada." });
}

async function excluirConta(env, id) {
  const conta = await env.DB.prepare("SELECT status FROM contas_pagar WHERE id=?").bind(id).first();
  if (!conta) return erro("Conta não encontrada.",404);
  if (conta.status !== "PENDENTE") return erro("Não é possível excluir uma conta já baixada.");
  await env.DB.prepare("DELETE FROM contas_pagar WHERE id=?").bind(id).run();
  return json({sucesso:true,mensagem:"Conta removida."});
}

async function baixarConta(request, env, id) {
  const conta = await env.DB.prepare("SELECT * FROM contas_pagar WHERE id=?").bind(id).first();
  if (!conta) return erro("Conta não encontrada.", 404);
  if (conta.status === "PAGO") return erro("Esta conta já foi baixada.");
  const dados = await request.json();
  const valor = numero(dados.valor_pago);
  if (valor <= 0) return erro("Informe o valor pago.");
  if (!String(dados.banco || "").trim()) return erro("Informe o banco ou a forma de pagamento.");
  await env.DB.batch([
    env.DB.prepare("INSERT INTO baixas_conta_pagar (conta_id, banco, valor_pago, data_pagamento, observacao) VALUES (?, ?, ?, ?, ?)")
      .bind(id, String(dados.banco).trim(), valor, String(dados.data_pagamento || agora().slice(0,10)), String(dados.observacao || "").trim()),
    env.DB.prepare("UPDATE contas_pagar SET status='PAGO' WHERE id=?").bind(id)
  ]);
  return json({ sucesso:true, mensagem:"Baixa registrada no balanço." });
}

async function resumoContasPagar(env) {
  const [pendente, pago] = await env.DB.batch([
    env.DB.prepare("SELECT COALESCE(SUM(valor),0) valor, COUNT(*) quantidade FROM contas_pagar WHERE status='PENDENTE'"),
    env.DB.prepare("SELECT COALESCE(SUM(valor_pago),0) valor, COUNT(*) quantidade FROM baixas_conta_pagar WHERE substr(data_pagamento,1,7)=substr(?,1,7)").bind(agora())
  ]);
  return { pendente:pendente.results[0], pago_mes:pago.results[0] };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (!url.pathname.startsWith("/api/")) return env.ASSETS.fetch(request);
    try {
      if (url.pathname === "/api/dashboard" && request.method === "GET") return json(await dashboard(env.DB));
      if (url.pathname === "/api/products/next-code" && request.method === "GET") return json({ codigo: await proximoCodigoProduto(env.DB) });
      if (url.pathname === "/api/products" && (request.method === "GET" || request.method === "POST")) return produtos(request, env, url);
      if (url.pathname === "/api/clients" && (request.method === "GET" || request.method === "POST")) return clientes(request, env, url);
      const clienteId = url.pathname.match(/^\/api\/clients\/(\d+)$/);
      if (clienteId && request.method === "PUT") return atualizarCliente(request, env, Number(clienteId[1]));
      if (clienteId && request.method === "DELETE") return excluirCliente(env, Number(clienteId[1]));
      if (url.pathname === "/api/receivables" && (request.method === "GET" || request.method === "POST")) return receberFiado(request, env);
      const contaCliente = url.pathname.match(/^\/api\/receivables\/(\d+)$/);
      if (contaCliente && request.method === "GET") return detalheRecebivel(env, Number(contaCliente[1]));
      const produto = url.pathname.match(/^\/api\/products\/(\d+)$/);
      if (produto && request.method === "PUT") return atualizarProduto(request, env, Number(produto[1]));
      if (url.pathname === "/api/sales" && request.method === "POST") return criarVenda(request, env);
      if (url.pathname === "/api/sales" && request.method === "GET") return listarVendas(env);
      if (url.pathname === "/api/payables" && (request.method === "GET" || request.method === "POST")) return contasPagar(request, env, url);
      if (url.pathname === "/api/payables/summary" && request.method === "GET") return json(await resumoContasPagar(env));
      const contaId = url.pathname.match(/^\/api\/payables\/(\d+)\/settlements$/);
      if (contaId && request.method === "POST") return baixarConta(request, env, Number(contaId[1]));
      const excluirContaId = url.pathname.match(/^\/api\/payables\/(\d+)$/);
      if (excluirContaId && request.method === "DELETE") return excluirConta(env, Number(excluirContaId[1]));
      const vendaId = url.pathname.match(/^\/api\/sales\/(\d+)$/);
      if (vendaId && request.method === "GET") return venda(env, Number(vendaId[1]));
      if (vendaId && request.method === "PUT") return atualizarVenda(request, env, Number(vendaId[1]));
      const cancelarId = url.pathname.match(/^\/api\/sales\/(\d+)\/cancel$/);
      if (cancelarId && request.method === "POST") return cancelarVenda(env, Number(cancelarId[1]));
      return erro("Rota não encontrada.", 404);
    } catch (error) {
      console.error(error);
      return erro("Não foi possível concluir a operação.", 500);
    }
  },
};
