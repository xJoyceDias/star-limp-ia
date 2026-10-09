const app=document.querySelector('#app'), views={dashboard:document.querySelector('#dashboard'),products:document.querySelector('#products'),sales:document.querySelector('#sales'),receivables:document.querySelector('#receivables'),clients:document.querySelector('#clients'),payables:document.querySelector('#payables'),sale:document.querySelector('#sale')};let cart=[],selected=null,selectedClient=null,editing=null,currentSale=null,timer,saleDiscount=0;
const money=v=>Number(v||0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});const api=(url,opt)=>fetch('/api'+url,opt).then(async r=>{const d=await r.json();if(!r.ok)throw new Error(d.mensagem||'Erro na operação');return d});const clone=n=>views[n].content.cloneNode(true);
function render(name){app.replaceChildren(clone(name));document.querySelectorAll('.nav').forEach(x=>x.classList.toggle('active',x.dataset.view===name));document.querySelectorAll('[data-go]').forEach(x=>x.onclick=()=>render(x.dataset.go));if(name==='dashboard')loadDashboard();if(name==='products')loadProducts();if(name==='sales')loadSales();if(name==='receivables')loadReceivables();if(name==='clients')loadClients();if(name==='payables')loadPayables();if(name==='sale')setupSale()}
async function loadDashboard(){const d=await api('/dashboard');document.querySelector('#today').textContent=money(d.vendas_hoje);document.querySelector('#week').textContent=money(d.vendas_semana);document.querySelector('#receivable').textContent=money(d.total_receber);document.querySelector('#debtors').textContent=(d.clientes_devendo||0)+' cliente(s) com saldo'}

async function loadPayables(){
  const importButton=document.querySelector('#new-payable');
  importButton.onclick=openPayable;
  try{
    const [contas,resumo]=await Promise.all([api('/payables'),api('/payables/summary')]);
    document.querySelector('#payable-pending').textContent=money(resumo.pendente?.valor);
    document.querySelector('#payable-pending-count').textContent=(resumo.pendente?.quantidade||0)+' conta(s) aguardando pagamento';
    document.querySelector('#payable-paid-month').textContent=money(resumo.pago_mes?.valor);
    document.querySelector('#payable-paid-count').textContent=(resumo.pago_mes?.quantidade||0)+' baixa(s) registrada(s) neste mês';
    const rows=document.querySelector('#payable-rows');
    rows.innerHTML=contas.map(c=>'<tr><td>'+escape(formatDate(c.vencimento))+'</td><td><b>'+escape(c.fornecedor||'Fornecedor não identificado')+'</b><br><small>'+escape(c.descricao||'')+'</small></td><td>'+money(c.valor)+'</td><td><span class="status '+(c.status==='PAGO'?'paid':'pending')+'">'+escape(c.status)+'</span></td><td>'+((c.status==='PENDENTE')?'<button class="secondary settle" data-id="'+c.id+'">Baixar</button> <button class="danger delete-payable" data-id="'+c.id+'">Excluir</button>':'<small>Pago: '+money(c.total_baixado)+'</small>')+'</td></tr>').join('');
    document.querySelector('#empty-payables').textContent=contas.length?'':'Nenhuma conta cadastrada.';
    rows.querySelectorAll('.settle').forEach(button=>button.onclick=()=>openSettlement(contas.find(c=>String(c.id)===button.dataset.id)));rows.querySelectorAll('.delete-payable').forEach(button=>button.onclick=async()=>{const conta=contas.find(c=>String(c.id)===button.dataset.id);if(!confirm('Excluir a conta de '+money(conta.valor)+'? Esta ação não pode ser desfeita.'))return;await api('/payables/'+conta.id,{method:'DELETE'});loadPayables()});
  }catch(error){
    document.querySelector('#empty-payables').textContent='Não foi possível carregar o resumo agora. Você ainda pode importar um boleto.';
  }
}
function formatDate(value){if(!value)return '—';const m=String(value).match(/^(\d{4})-(\d{2})-(\d{2})/);return m?m[3]+'/'+m[2]+'/'+m[1]:value}
function openPayable(){
  const dialog=document.querySelector('#payable-dialog'),file=document.querySelector('#boleto-file'),status=document.querySelector('#pdf-status'),preview=document.querySelector('#installments-preview');let boletos=[],parcelas=[];
  const current=()=>({fornecedor:document.querySelector('#p-supplier').value.trim(),descricao:document.querySelector('#p-description').value.trim()||'Boleto importado',linha_digitavel:document.querySelector('#p-line').value.replace(/\D/g,''),valor:Number(document.querySelector('#p-value').value),vencimento:document.querySelector('#p-due').value});
  const renderParcelas=()=>{preview.innerHTML=parcelas.length?'<b>'+parcelas.length+' parcela(s) preparada(s)</b>'+parcelas.map((parcela,index)=>'<div>Parcela '+(index+1)+': '+money(parcela.valor)+' · '+escape(formatDate(parcela.vencimento))+' <button type="button" data-remove="'+index+'">×</button></div>').join(''):'';preview.querySelectorAll('[data-remove]').forEach(button=>button.onclick=()=>{parcelas.splice(Number(button.dataset.remove),1);renderParcelas()})};
  const validar=parcela=>{if(!parcela.valor||parcela.valor<=0)throw new Error('Informe o valor da parcela.');if(!parcela.vencimento)throw new Error('Informe o vencimento da parcela.');return parcela};
  dialog.querySelector('form').reset();document.querySelector('#p-description').value='Boleto importado';document.querySelector('#boleto-file-name').textContent='Selecionar boleto em PDF';status.textContent='';renderParcelas();
  file.onchange=async()=>{const selected=file.files[0];if(!selected)return;document.querySelector('#boleto-file-name').textContent=selected.name;status.textContent='Lendo boleto…';try{const pages=await pdfToPages(selected);boletos=pages.map(extractBoleto).filter(boleto=>boleto.linha_digitavel||boleto.valor>0);if(!boletos.length)throw new Error('Sem dados');fillBoleto(boletos[0]);status.textContent=boletos.length===1?'Dados extraídos. Confira e cadastre.':boletos.length+' parcelas encontradas. Clique em “Cadastrar conta(s)” para salvar todas.'}catch(error){boletos=[];status.textContent='Não foi possível ler automaticamente este PDF. Preencha as parcelas manualmente.'}};
  document.querySelector('#add-installment').onclick=()=>{try{parcelas.push(validar(current()));renderParcelas();document.querySelector('#p-line').value='';document.querySelector('#p-value').value='';document.querySelector('#p-due').value='';status.textContent='Parcela adicionada. Você pode incluir outra ou cadastrar as preparadas.'}catch(error){status.textContent=error.message}};
  dialog.showModal();
  dialog.querySelector('form').onsubmit=async event=>{if(event.submitter?.id!=='save-payable')return;event.preventDefault();try{let registros=boletos.length?[...boletos]:[...parcelas];const preenchido=current();if(!boletos.length&&preenchido.valor>0)registros.push(validar(preenchido));if(!registros.length)throw new Error('Adicione pelo menos uma parcela ou informe valor e vencimento.');registros=registros.map((boleto,index)=>({...boleto,fornecedor:index===0&&preenchido.fornecedor?preenchido.fornecedor:boleto.fornecedor,descricao:boletos.length>1?preenchido.descricao+' — parcela '+(index+1)+'/'+boletos.length:boleto.descricao||preenchido.descricao}));status.textContent='Salvando '+registros.length+' conta(s)…';for(const boleto of registros){await api('/payables',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({fornecedor:boleto.fornecedor,descricao:boleto.descricao,linha_digitavel:boleto.linha_digitavel,valor:boleto.valor,vencimento:boleto.vencimento,arquivo_nome:file.files[0]?.name||''})})}status.textContent=registros.length+' conta(s) cadastrada(s) com sucesso.';setTimeout(()=>{dialog.close();loadPayables()},500)}catch(error){status.textContent='Não foi possível cadastrar: '+error.message}};
}
async function pdfToPages(file){
  const pdfjs=await import('https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.min.mjs');
  const doc=await pdfjs.getDocument({data:await file.arrayBuffer()}).promise,pages=[];
  for(let page=1;page<=doc.numPages;page++){const content=await (await doc.getPage(page)).getTextContent();pages.push(content.items.map(item=>item.str).join(' '))}
  return pages;
}
function extractBoleto(text){
  const lines=text.match(/\b\d{5}\.\d{5}\s+\d{5}\.\d{6}\s+\d{5}\.\d{6}\s+\d\s+\d{14}\b/g)||[];
  const linha_digitavel=(lines[0]||((text.match(/\d[\d .-]{43,}/g)||[]).find(value=>value.replace(/\D/g,'').length>=44)||'')).replace(/\D/g,'');
  const values=[...(text.matchAll(/R\$\s*([\d.]+,\d{2}|\d+,\d{2}|\d+\.\d{2})/gi))].map(match=>Number(match[1].replace(/\./g,'').replace(',','.'))).filter(value=>value>0);
  const date=text.match(/(?:vencimento|venc\.?)[^\d]*(\d{2})[\/.\-](\d{2})[\/.\-](\d{4})/i);
  const supplier=text.match(/Benefici[aá]rio\s+Ag[êe]ncia\/C[oó]digo\s+Benefici[aá]rio\s+(.+?)(?:\s+CNPJ|\s+\d{4}\/)/i)||text.match(/(?:benefici[aá]rio|cedente|fornecedor)\s*[:\-]?\s*([^\n]{3,100})/i);
  return {linha_digitavel,valor:values[0]||0,vencimento:date?date[3]+'-'+date[2]+'-'+date[1]:'',fornecedor:(supplier?.[1]||'').trim()};
}
function fillBoleto(boleto){document.querySelector('#p-line').value=boleto.linha_digitavel||'';document.querySelector('#p-value').value=boleto.valor?Number(boleto.valor).toFixed(2):'';document.querySelector('#p-due').value=boleto.vencimento||'';document.querySelector('#p-supplier').value=boleto.fornecedor||'';}
function openSettlement(conta){
  const dialog=document.querySelector('#settlement-dialog');document.querySelector('#settlement-title').textContent=(conta.fornecedor||'Conta')+' — '+money(conta.valor);document.querySelector('#s-value').value=Number(conta.valor).toFixed(2);document.querySelector('#s-date').value=new Date().toISOString().slice(0,10);document.querySelector('#s-bank').value='';document.querySelector('#s-note').value='';
  dialog.showModal();dialog.querySelector('form').onsubmit=async event=>{if(event.submitter?.id!=='save-settlement')return;event.preventDefault();await api('/payables/'+conta.id+'/settlements',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({banco:document.querySelector('#s-bank').value,valor_pago:document.querySelector('#s-value').value,data_pagamento:document.querySelector('#s-date').value,observacao:document.querySelector('#s-note').value})});dialog.close();loadPayables()};
}


const normalizarBusca=value=>String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/\s+/g,' ').trim();
const correspondeBusca=(item,termo,campos)=>{const parts=normalizarBusca(termo).split(' ').filter(Boolean);const text=campos.map(campo=>normalizarBusca(item[campo])).join(' ');return parts.every(part=>text.includes(part))};
let productCache=null;
const todosProdutos=()=>productCache||(productCache=api('/products'));
async function loadReceivables(){const clients=await api('/receivables'),select=document.querySelector('#receive-client'),rows=document.querySelector('#receivable-rows');select.innerHTML='<option value="">Selecione o cliente</option>'+clients.map(client=>'<option value="'+client.id+'">'+escape(client.nome)+' — '+money(client.saldo_fiado)+'</option>').join('');rows.innerHTML=clients.map(client=>'<tr><td><b>'+escape(client.nome)+'</b></td><td>'+escape(client.telefone||'—')+'</td><td>'+money(client.saldo_fiado)+'</td><td><button class="secondary receive-client" data-id="'+client.id+'">Receber</button></td></tr>').join('');document.querySelector('#empty-receivables').textContent=clients.length?'':'Nenhum cliente com saldo em aberto.';rows.querySelectorAll('.receive-client').forEach(button=>button.onclick=()=>{const client=clients.find(item=>String(item.id)===button.dataset.id);select.value=client.id;document.querySelector('#receive-value').value=Number(client.saldo_fiado).toFixed(2);window.scrollTo({top:0,behavior:'smooth'})});document.querySelector('#save-receivable').onclick=async()=>{const client=clients.find(item=>String(item.id)===select.value),value=Number(document.querySelector('#receive-value').value);if(!client||value<=0)return alert('Selecione o cliente e informe o valor recebido.');await api('/receivables',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({cliente_id:client.id,valor_pago:value,forma_pagamento:document.querySelector('#receive-method').value,observacao:document.querySelector('#receive-note').value})});alert('Baixa registrada com sucesso.');loadReceivables()}}
async function loadSales(){
  const search=document.querySelector('#sales-search'),all=await api('/sales');
  const cancelSale=async sale=>{
    if(!confirm('Cancelar a venda #'+sale.id+'? O histórico será preservado.'))return;
    await api('/sales/'+sale.id+'/cancel',{method:'POST'});loadSales();
  };
  const draw=()=>{
    const rowsData=all.filter(sale=>correspondeBusca(sale,search.value,['id','cliente_nome','forma_pagamento','status'])),rows=document.querySelector('#sales-rows');
    rows.innerHTML=rowsData.map(sale=>'<tr class="sale-row" data-id="'+sale.id+'"><td><b>#'+sale.id+'</b><small>Ver detalhes</small></td><td>'+escape(formatDocumentDate(sale.data_hora))+'</td><td>'+escape(sale.cliente_nome||'Consumidor final')+'</td><td>'+escape(sale.forma_pagamento.toUpperCase())+'</td><td><b>'+money(sale.valor_total)+'</b></td><td><span class="status '+(sale.status==='CANCELADA'?'pending':'paid')+'">'+escape(sale.status)+'</span></td><td>'+(sale.status==='CANCELADA'?'—':'<button class="secondary sale-edit" data-id="'+sale.id+'">Editar</button> <button class="secondary sale-cancel" data-id="'+sale.id+'">Cancelar</button>')+'</td></tr>').join('');
    document.querySelector('#empty-sales').textContent=rowsData.length?'':'Nenhuma venda encontrada.';
    rows.querySelectorAll('.sale-row').forEach(row=>row.onclick=event=>{if(!event.target.closest('button'))openSaleDetails(row.dataset.id)});
    rows.querySelectorAll('.sale-edit').forEach(button=>button.onclick=event=>{event.stopPropagation();openSaleEdit(all.find(sale=>String(sale.id)===button.dataset.id))});
    rows.querySelectorAll('.sale-cancel').forEach(button=>button.onclick=event=>{event.stopPropagation();cancelSale(all.find(sale=>String(sale.id)===button.dataset.id))});
  };
  search.oninput=draw;draw();
}
async function openSaleDetails(id){
  const data=await api('/sales/'+id),sale=data.venda,client=data.cliente,credit=data.fiado,dialog=document.querySelector('#sale-details-dialog');
  const clientInfo=client?'<section class="detail-customer"><span>CLIENTE</span><b>'+escape(client.nome)+'</b><small>'+escape(client.telefone||'Telefone não informado')+(client.cpf_cnpj?' · '+escape(client.cpf_cnpj):'')+'</small>'+(credit?'<small>Retirado por: '+escape(credit.retirado_por||client.nome)+'</small>':'')+'</section>':'<section class="detail-customer"><span>CLIENTE</span><b>Consumidor final</b></section>';
  document.querySelector('#sale-details-title').textContent='Venda #'+sale.id;
  document.querySelector('#sale-details-content').innerHTML='<div class="detail-meta"><span>'+formatDocumentDate(sale.data_hora)+'</span><span class="status '+(sale.status==='CANCELADA'?'pending':'paid')+'">'+escape(sale.status)+'</span></div>'+clientInfo+'<table class="detail-items"><thead><tr><th>Item</th><th>Qtd.</th><th>Unitário</th><th>Total</th></tr></thead><tbody>'+data.itens.map(item=>'<tr><td>'+escape(item.descricao)+'</td><td>'+item.quantidade+'</td><td>'+money(item.preco_unitario)+'</td><td>'+money(item.subtotal)+'</td></tr>').join('')+'</tbody></table><div class="detail-total"><span>FORMA DE PAGAMENTO<br><b>'+escape(sale.forma_pagamento).toUpperCase()+'</b></span><strong>'+money(sale.valor_total)+'</strong></div>';
  const edit=document.querySelector('#detail-edit-sale'),cancel=document.querySelector('#detail-cancel-sale');
  edit.hidden=sale.status==='CANCELADA';cancel.hidden=sale.status==='CANCELADA';
  edit.onclick=()=>{dialog.close();openSaleEdit(sale)};
  cancel.onclick=async()=>{if(!confirm('Cancelar a venda #'+sale.id+'? O histórico será preservado.'))return;await api('/sales/'+sale.id+'/cancel',{method:'POST'});dialog.close();loadSales()};
  document.querySelector('#detail-print-order').onclick=()=>print(sale.id,false);
  document.querySelector('#detail-print-receipt').onclick=()=>print(sale.id,true);
  dialog.showModal();
}
function openSaleEdit(sale){
  const dialog=document.querySelector('#sale-edit-dialog');
  document.querySelector('#sale-edit-title').textContent='Venda #'+sale.id+' — '+money(sale.valor_total);
  document.querySelector('#sale-edit-payment').value=sale.forma_pagamento;dialog.showModal();
  dialog.querySelector('form').onsubmit=async event=>{
    if(event.submitter?.id!=='save-sale-edit')return;
    event.preventDefault();
    await api('/sales/'+sale.id,{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify({forma_pagamento:document.querySelector('#sale-edit-payment').value})});
    dialog.close();loadSales();
  };
}
async function loadClients(){const search=document.querySelector('#client-search');const all=await api('/clients');const draw=()=>{const clients=all.filter(client=>correspondeBusca(client,search.value,['nome','telefone','cpf_cnpj']));const rows=document.querySelector('#client-rows');rows.innerHTML=clients.map(client=>'<tr><td><b>'+escape(client.nome)+'</b></td><td>'+escape(client.telefone||'—')+'</td><td>'+money(client.saldo_fiado)+'</td></tr>').join('');document.querySelector('#empty-clients').textContent=clients.length?'':'Nenhum cliente encontrado.'};search.oninput=draw;draw();document.querySelector('#new-client').onclick=()=>openClientDialog(()=>loadClients())}
function openClientDialog(onSaved){
  const dialog=document.querySelector('#client-dialog'),form=dialog.querySelector('form'),status=document.querySelector('#client-status'),save=document.querySelector('#save-client');
  form.reset();status.textContent='';save.disabled=false;save.textContent='Salvar cliente';dialog.showModal();
  form.onsubmit=async event=>{
    if(event.submitter?.id!=='save-client')return;
    event.preventDefault();
    const payload={nome:document.querySelector('#c-name').value.trim(),telefone:document.querySelector('#c-phone').value.trim(),cpf_cnpj:document.querySelector('#c-document').value.trim()};
    if(!payload.nome){status.textContent='Informe o nome do cliente.';return}
    save.disabled=true;save.textContent='Salvando…';status.textContent='';
    try{
      const result=await api('/clients',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload)});
      status.textContent=result.existente?'Cliente já existia e foi selecionado.':'Cliente salvo e selecionado.';
      const client=result.cliente||{...payload,id:result.id,saldo_fiado:0};
      setTimeout(()=>{dialog.close();onSaved?.(client)},250);
    }catch(error){
      status.textContent=error.message||'Não foi possível salvar o cliente.';
      save.disabled=false;save.textContent='Salvar cliente';
    }
  };
}

async function loadProducts(){const q=document.querySelector('#product-search');q.oninput=()=>listProducts(q.value);document.querySelector('#new-product').onclick=()=>openProduct();listProducts('')}
async function listProducts(term){const products=(await todosProdutos()).filter(product=>correspondeBusca(product,term,['descricao','codigo','categoria']));const rows=document.querySelector('#product-rows');rows.innerHTML=products.map(p=>'<tr><td>'+escape(p.descricao)+'</td><td>'+escape(p.codigo||'—')+'</td><td>'+Number(p.estoque||0)+' '+escape(p.unidade||'UN')+'</td><td>'+money(p.preco)+'</td><td><button class="secondary edit" data-id="'+p.id+'">Editar</button></td></tr>').join('');document.querySelector('#empty-products').textContent=products.length?'':'Nenhum produto encontrado.';rows.querySelectorAll('.edit').forEach(b=>b.onclick=()=>openProduct(products.find(p=>p.id==b.dataset.id)))}
function escape(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function openProduct(p){
  editing=p||null;
  const dialog=document.querySelector('#product-dialog');
  document.querySelector('#dialog-title').textContent=p?'Editar produto':'Novo produto';
  ['code','unit','description','price','stock','category','status'].forEach(key=>document.querySelector('#f-'+key).value=p?({code:p.codigo,unit:p.unidade,description:p.descricao,price:p.preco,stock:p.estoque,category:p.categoria,status:p.situacao}[key]??''):(key==='unit'?'UN':key==='stock'?'0':key==='status'?'Ativo':''));
  if(!p){
    document.querySelector('#f-code').value='Gerando código…';
    document.querySelector('#f-code').readOnly=true;
    try{document.querySelector('#f-code').value=(await api('/products/next-code')).codigo}catch(error){document.querySelector('#f-code').value=''}
    document.querySelector('#f-code').readOnly=false;
  }
  dialog.showModal();
  dialog.querySelector('form').onsubmit=async event=>{
    if(event.submitter?.id!=='save-product')return;
    event.preventDefault();
    const data={codigo:f('code'),unidade:f('unit'),descricao:f('description'),preco:f('price'),estoque:f('stock'),categoria:f('category'),situacao:f('status')};
    await api('/products'+(editing?'/'+editing.id:''),{method:editing?'PUT':'POST',headers:{'content-type':'application/json'},body:JSON.stringify(data)});
    dialog.close();productCache=null;listProducts(document.querySelector('#product-search').value);
  };
}
const f=k=>document.querySelector('#f-'+k).value;
async function setupSale(){
  const search=document.querySelector('#sale-search'),suggestions=document.querySelector('#suggestions'),payment=document.querySelector('#payment'),quickClient=document.querySelector('#quick-client'),finishButton=document.querySelector('#finish-sale'),clientSearch=document.querySelector('#sale-client-search'),clientSuggestions=document.querySelector('#client-suggestions'),selectedClientLabel=document.querySelector('#selected-client'),discountInput=document.querySelector('#discount-input');
  let clientsCache=[];
  try{clientsCache=await api('/clients')}catch(error){console.error(error)}
  const selectClient=client=>{
    selectedClient=client;
    clientSearch.value=client.nome;
    document.querySelector('#withdrawn-by').value=client.nome;
    clientSuggestions.innerHTML='';
    selectedClientLabel.textContent='Cliente selecionado: '+client.nome+(client.telefone?' · '+client.telefone:'');
    selectedClientLabel.hidden=false;
    quickClient.textContent='Cadastrar outro cliente';
  };
  const renderClientMatches=()=>{
    const term=clientSearch.value.trim();
    if(!term){clientSuggestions.innerHTML='';return}
    const matches=clientsCache.filter(client=>correspondeBusca(client,term,['nome','telefone','cpf_cnpj'])).slice(0,6);
    clientSuggestions.innerHTML=matches.length?matches.map(client=>'<button type="button" data-id="'+client.id+'"><b>'+escape(client.nome)+'</b><span>'+escape(client.telefone||client.cpf_cnpj||'Sem telefone/CPF')+'</span></button>').join(''):'<p>Nenhum cliente encontrado. Use “Cadastrar cliente”.</p>';
    clientSuggestions.querySelectorAll('button').forEach(button=>button.onclick=()=>selectClient(clientsCache.find(client=>String(client.id)===button.dataset.id)));
  };
  const resetSale=()=>{
    cart=[];selected=null;selectedClient=null;
    search.value='';suggestions.innerHTML='';document.querySelector('#quantity').value=1;
    payment.value='pix';saleDiscount=0;discountInput.value='';clientSearch.value='';document.querySelector('#withdrawn-by').value='';clientSuggestions.innerHTML='';selectedClientLabel.hidden=true;selectedClientLabel.textContent='';
    quickClient.textContent='+ Cadastrar cliente';
    finishButton.disabled=false;finishButton.textContent='Finalizar venda';
    drawCart();search.focus();
  };
  payment.onchange=()=>{if(payment.value==='fiado'&&!selectedClient)clientSearch.focus()};
  discountInput.oninput=()=>{saleDiscount=String(discountInput.value).replace(',','.');drawCart()};
  clientSearch.oninput=()=>{
    if(selectedClient&&normalizarBusca(clientSearch.value)!==normalizarBusca(selectedClient.nome)){
      selectedClient=null;selectedClientLabel.hidden=true;selectedClientLabel.textContent='';quickClient.textContent='+ Cadastrar cliente';
    }
    renderClientMatches();
  };
  clientSearch.onkeydown=event=>{if(event.key==='Enter'){const first=clientSuggestions.querySelector('button');if(first){event.preventDefault();first.click()}}};
  quickClient.onclick=()=>openClientDialog(client=>{
    const index=clientsCache.findIndex(item=>String(item.id)===String(client.id));
    if(index>=0)clientsCache[index]=client;else clientsCache.push(client);
    selectClient(client);
  });
  const addProduct=product=>{
    const quantity=Number(document.querySelector('#quantity').value);
    if(!Number.isFinite(quantity)||quantity<=0)return alert('Informe uma quantidade válida.');
    const existing=cart.find(item=>String(item.codigo)===String(product.codigo)&&item.produto===product.descricao&&Number(item.preco)===Number(product.preco));
    if(existing)existing.quantidade+=quantity;else cart.push({produto_id:product.id,codigo:product.codigo,produto:product.descricao,quantidade:quantity,preco:Number(product.preco)});
    selected=null;search.value='';suggestions.innerHTML='';document.querySelector('#quantity').value=1;drawCart();search.focus();
  };
  search.oninput=async()=>{
    if(search.value.trim().length<1){suggestions.innerHTML='';return}
    const products=(await todosProdutos()).filter(product=>correspondeBusca(product,search.value,['descricao','codigo','categoria']));
    suggestions.innerHTML=products.slice(0,8).map(product=>'<button type="button" class="suggestion" data-id="'+product.id+'"><span><b>'+escape(product.descricao)+'</b><small>'+escape(product.codigo||'Sem código')+'</small></span><strong>'+money(product.preco)+'</strong></button>').join('')||'<p class="no-result">Nenhum produto encontrado.</p>';
    suggestions.querySelectorAll('.suggestion').forEach(element=>element.onclick=()=>addProduct(products.find(product=>String(product.id)===element.dataset.id)));
  };
  search.onkeydown=event=>{
    if(event.key==='Enter'){
      const first=suggestions.querySelector('.suggestion');
      if(first){event.preventDefault();first.click()}
    }
  };
  finishButton.onclick=async()=>{
    if(!cart.length)return alert('Adicione pelo menos um produto.');
    const forma=payment.value;
    if(forma==='fiado'&&!selectedClient)return alert('Para venda a prazo, localize ou cadastre o cliente.');
    const withdrawnBy=document.querySelector('#withdrawn-by').value.trim();
    if(forma==='fiado'&&!withdrawnBy)return alert('Informe o nome de quem retirou os produtos.');
    finishButton.disabled=true;finishButton.textContent='Registrando venda…';
    try{
      const gross=cartGross(),totalDiscount=Number(discountAmount().toFixed(2));
      let allocated=0;
      const items=cart.map((item,index)=>{
        const discount=index===cart.length-1?Number((totalDiscount-allocated).toFixed(2)):Number((totalDiscount*(item.preco*item.quantidade)/gross).toFixed(2));
        allocated=Number((allocated+discount).toFixed(2));
        return {...item,desconto:discount};
      });
      const result=await api('/sales',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({itens:items,forma_pagamento:forma,cliente_id:selectedClient?.id,retirado_por:withdrawnBy})});
      currentSale=result.venda_id;resetSale();
      const dialog=document.querySelector('#receipt-dialog');
      document.querySelector('#receipt-message').textContent=result.mensagem;
      document.querySelector('#print-receipt').onclick=()=>print(currentSale,true);
      document.querySelector('#print-order').onclick=()=>print(currentSale,false);
      const whats=document.querySelector('#send-whatsapp');
      whats.hidden=!result.cliente?.telefone;whats.onclick=()=>sendWhatsApp(currentSale,result.cliente,withdrawnBy);
      dialog.showModal();
    }catch(error){alert(error.message||'Não foi possível finalizar a venda.');finishButton.disabled=false;finishButton.textContent='Finalizar venda'}
  };
  drawCart();search.focus();
}
function cartGross(){return cart.reduce((sum,item)=>sum+item.preco*item.quantidade,0)}
function discountAmount(){
  const gross=cartGross(),value=Math.max(0,Number(String(saleDiscount).replace(',','.'))||0);
  return Math.min(gross,value);
}
function drawCart(){
  const box=document.querySelector('#cart'),gross=cartGross(),discount=discountAmount(),total=Math.max(0,gross-discount);
  box.classList.toggle('empty',!cart.length);
  box.innerHTML=cart.length?'<div class="cart-head"><span>Item</span><span>Qtd.</span><span>Subtotal</span></div>'+cart.map((item,index)=>'<div class="cart-item"><span><b>'+escape(item.produto)+'</b><small>'+money(item.preco)+' cada</small></span><span>'+item.quantidade+'</span><button type="button" class="price-edit" data-price-index="'+index+'" title="Clique para alterar e salvar o preço">'+money(item.preco*item.quantidade)+'</button><button type="button" aria-label="Remover item" data-i="'+index+'">×</button></div>').join(''):'<div class="empty-cart"><b>Seu carrinho está vazio</b><span>Pesquise um produto acima para começar a venda.</span></div>';
  box.querySelectorAll('button[data-i]').forEach(button=>button.onclick=()=>{cart.splice(Number(button.dataset.i),1);drawCart()});
  box.querySelectorAll('.price-edit').forEach(button=>button.onclick=()=>openQuickPrice(Number(button.dataset.priceIndex)));
  document.querySelector('#sale-subtotal').textContent=money(gross);
  document.querySelector('#sale-discount-value').textContent='− '+money(discount);
  document.querySelector('#sale-discount-row').hidden=discount<=0;
  document.querySelector('#sale-total').textContent=money(total);
  document.querySelector('#cart-count').textContent=cart.reduce((sum,item)=>sum+item.quantidade,0)+' item(ns)';
}
async function openQuickPrice(index){
  const item=cart[index];
  if(!item?.produto_id)return alert('Este item foi incluído antes da atualização. Remova-o e adicione novamente para editar o preço.');
  const dialog=document.querySelector('#quick-price-dialog'),input=document.querySelector('#quick-price'),name=document.querySelector('#quick-price-name'),status=document.querySelector('#quick-price-status'),save=document.querySelector('#save-quick-price');
  name.textContent=item.produto;input.value=Number(item.preco).toFixed(2).replace('.',',');status.textContent='';save.disabled=false;dialog.showModal();input.select();
  dialog.querySelector('form').onsubmit=async event=>{
    if(event.submitter?.id!=='save-quick-price')return;
    event.preventDefault();
    const rawPrice=String(input.value).replace(/[^\d,\.]/g,'');
    const price=rawPrice.includes(',')?Number(rawPrice.replace(/\./g,'').replace(',','.')):Number(rawPrice);
    if(!Number.isFinite(price)||price<0){status.textContent='Informe um preço válido.';return}
    save.disabled=true;save.textContent='Atualizando…';
    try{
      const products=await todosProdutos(),product=products.find(entry=>String(entry.id)===String(item.produto_id));
      if(!product)throw new Error('Produto não encontrado. Atualize a tela e tente novamente.');
      await api('/products/'+product.id,{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify({...product,preco:price})});
      cart.filter(entry=>String(entry.produto_id)===String(product.id)).forEach(entry=>entry.preco=price);
      productCache=null;dialog.close();drawCart();
    }catch(error){status.textContent=error.message||'Não foi possível atualizar o preço.';save.disabled=false;save.textContent='Atualizar preço'}
  };
}

async function sendWhatsApp(id,cliente,withdrawnBy){
  let phone=String(cliente.telefone||'').replace(/\D/g,'');
  if(phone.length===10||phone.length===11)phone='55'+phone;
  if(phone.length<12)return alert('Cadastre um telefone válido para enviar a notinha.');
  const data=await api('/sales/'+id);
  const lines=data.itens.map(item=>item.quantidade+'x '+item.descricao+' — '+money(item.subtotal)).join('\n');
  const balance=money(cliente.saldo_fiado||data.cliente?.saldo_fiado||0);
  const message='*STAR LIMP — COMPROVANTE DE VENDA*\nPedido #'+id+'\n'+formatDocumentDate(data.venda.data_hora)+'\n\n*Cliente responsável:* '+cliente.nome+'\n*Retirado por:* '+(withdrawnBy||cliente.nome)+'\n\n'+lines+'\n\n*VALOR DESTA COMPRA: '+money(data.venda.valor_total)+'*\n*SALDO DEVEDOR ATUAL: '+balance+'*\n\nEste pedido foi lançado na conta do cliente.\nObrigado pela preferência!';
  window.open('https://wa.me/'+phone+'?text='+encodeURIComponent(message),'_blank');
}
async function print(id,thermal){const d=await api('/sales/'+id);const v=d.venda,lines=d.itens.map(i=>'<tr><td>'+escape(i.descricao)+'</td><td>'+i.quantidade+'x</td><td>'+money(i.subtotal)+'</td></tr>').join('');const body=thermal?'<h2>STAR LIMP</h2><p>RECIBO #'+v.id+'</p>':'<h1>Pedido de venda #'+v.id+'</h1>';const w=window.open('','_blank');w.document.write('<html><style>body{font:14px Arial;margin:25px;max-width:'+(thermal?'58mm':'700px')+'}h1,h2,p{text-align:center}table{width:100%;border-collapse:collapse}td{padding:6px;border-bottom:1px solid #ddd}td:last-child{text-align:right}.total{text-align:right;font-size:18px;font-weight:bold}@media print{button{display:none}}</style><body>'+body+'<p>'+v.data_hora+'</p><table>'+lines+'</table><p class="total">TOTAL: '+money(v.valor_total)+'</p><p>Pagamento: '+v.forma_pagamento.toUpperCase()+'</p><button onclick="print()">Imprimir</button></body></html>');w.document.close();w.focus()}
document.querySelectorAll('.nav').forEach(x=>x.onclick=()=>render(x.dataset.view));

function formatDocumentDate(value){
  const parsed=new Date(String(value||'').replace(' ','T')+'-03:00');
  return Number.isNaN(parsed.getTime())?String(value||''):parsed.toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo',dateStyle:'short',timeStyle:'short'});
}
function print(id,thermal){
  api('/sales/'+id).then(d=>{
    const sale=d.venda;
    const date=formatDocumentDate(sale.data_hora);
    const company={
      address:'Av. da Inconfidência, Quadra 07 - Lote 11 - Capuava, Goiânia - GO, 74463-020',
      phone:'(62) 98436-2772'
    };
    const items=d.itens.map(item=>'<tr><td>'+escape(item.descricao)+'</td><td>'+item.quantidade+'</td><td>'+money(Number(item.subtotal)/Number(item.quantidade))+'</td><td>'+money(item.subtotal)+'</td></tr>').join('');
    const client=d.cliente||null;
    const clientBlock=client?'<section class="customer"><div><span>CLIENTE</span><strong>'+escape(client.nome)+'</strong></div><div><span>TELEFONE</span><strong>'+escape(client.telefone||'Não informado')+'</strong></div><div><span>CPF / CNPJ</span><strong>'+escape(client.cpf_cnpj||'Não informado')+'</strong></div></section>':'<section class="customer without-customer"><div><span>CLIENTE</span><strong>Consumidor final</strong></div></section>';
    const w=window.open('','_blank');
    if(!w)return alert('Permita pop-ups no navegador para abrir a impressão.');
    if(thermal){
      const thermalItems=d.itens.map(item=>'<tr><td>'+escape(item.descricao)+'<br><small>'+item.quantidade+' x '+money(Number(item.subtotal)/Number(item.quantidade))+'</small></td><td>'+money(item.subtotal)+'</td></tr>').join('');
      w.document.write('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Recibo #'+sale.id+'</title><style>@page{size:58mm auto;margin:3mm}*{box-sizing:border-box}body{margin:0;width:52mm;color:#000;font:10px "Courier New",monospace}.center{text-align:center}.brand{font-weight:900;font-size:14px;line-height:1.1}.sub{font-size:8px;letter-spacing:.5px}.line{border-top:1px dashed #000;margin:7px 0}.title{font-size:11px;font-weight:900;margin:6px 0}table{width:100%;border-collapse:collapse}td{padding:4px 0;vertical-align:top}td:last-child{text-align:right;white-space:nowrap}small{font-size:8px}.total{text-align:right;font-size:14px;font-weight:900;margin:8px 0}.foot{font-size:8px;line-height:1.35}@media print{button{display:none}}button{display:block;margin:12px auto;padding:8px;border:0;background:#000;color:#fff}</style></head><body><div class="center brand">STAR LIMP</div><div class="center sub">FRAGRÂNCIAS E PRODUTOS</div><div class="line"></div><div class="center title">RECIBO DE VENDA #'+sale.id+'</div><div class="center">'+date+'</div>'+(client?'<div class="line"></div><div>CLIENTE: '+escape(client.nome)+'</div>':'')+'<div class="line"></div><table>'+thermalItems+'</table><div class="line"></div><div class="total">TOTAL: '+money(sale.valor_total)+'</div><div class="center">PAGAMENTO: '+escape(sale.forma_pagamento).toUpperCase()+'</div><div class="line"></div><div class="center foot">'+escape(company.phone)+'<br>Obrigado pela preferência!</div><button onclick="window.print()">IMPRIMIR</button><script>window.onload=()=>setTimeout(()=>window.print(),250)<\/script></body></html>');
    }else{
      w.document.write('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Pedido de venda #'+sale.id+'</title><style>@page{size:A4;margin:13mm}*{box-sizing:border-box}body{margin:0;color:#10213d;font:12px Arial,sans-serif}.sheet{max-width:190mm;margin:0 auto}.header{display:flex;align-items:center;justify-content:space-between;gap:18px;padding-bottom:12px;border-bottom:3px solid #1565d8}.logo{width:190px;max-height:72px;object-fit:contain;object-position:left center}.company{text-align:right;color:#405270;font-size:10px;line-height:1.55}.company b{color:#10213d;font-size:11px}.document-bar{display:flex;justify-content:space-between;align-items:flex-end;margin:20px 0 16px}.document-bar span,.customer span,.summary-label{display:block;color:#61708a;font-size:9px;font-weight:800;letter-spacing:1px}.document-bar h1{margin:3px 0 0;color:#10213d;font-size:24px;letter-spacing:.3px}.number{text-align:right}.number strong{display:block;color:#1565d8;font-size:22px;margin-top:3px}.customer{display:grid;grid-template-columns:2fr 1.25fr 1.25fr;gap:16px;padding:13px 15px;border:1px solid #ccd7e7;border-left:4px solid #1565d8;border-radius:5px;background:#f7faff;margin-bottom:20px}.customer strong{display:block;margin-top:4px;font-size:12px;color:#182945}.without-customer{grid-template-columns:1fr}table{width:100%;border-collapse:collapse}thead{background:#132f5f;color:#fff}th{padding:10px 9px;text-align:left;font-size:9px;letter-spacing:.7px}th:nth-child(2),th:nth-child(3),th:nth-child(4),td:nth-child(2),td:nth-child(3),td:nth-child(4){text-align:right}td{padding:12px 9px;border-bottom:1px solid #dce4ee;font-size:11px}tbody tr:nth-child(even){background:#f7f9fc}.bottom{display:flex;justify-content:space-between;gap:32px;margin-top:24px}.payment{flex:1;padding:13px 15px;border:1px solid #d5deeb;border-radius:5px;background:#fff}.payment strong{display:block;margin-top:5px;color:#132f5f;font-size:13px}.total-box{min-width:230px;padding:13px 16px;border-radius:5px;background:#1565d8;color:#fff;text-align:right}.total-box .summary-label{color:#dbe8ff}.total-box strong{display:block;font-size:24px;margin-top:4px}.footer{margin-top:45px;padding-top:12px;border-top:1px solid #ccd7e7;text-align:center;color:#61708a;font-size:9px;line-height:1.6}.footer b{color:#173b78}@media print{button{display:none}}button{display:block;margin:16px auto;padding:10px 20px;border:0;border-radius:6px;background:#1565d8;color:#fff;font-weight:700}</style></head><body><main class="sheet"><header class="header"><img class="logo" src="/assets/ChatGPT%20Image%2014%20de%20jul.%20de%202026%2C%2017_04_50.png" alt="Star Limp"><div class="company"><b>STAR LIMP — FRAGRÂNCIAS E PRODUTOS</b><br>'+escape(company.address)+'<br>WhatsApp: '+escape(company.phone)+'</div></header><section class="document-bar"><div><span>DOCUMENTO COMERCIAL</span><h1>PEDIDO DE VENDA</h1></div><div class="number"><span>PEDIDO Nº</span><strong>#'+sale.id+'</strong><small>Emissão: '+date+'</small></div></section>'+clientBlock+'<table><thead><tr><th>DESCRIÇÃO DO PRODUTO</th><th>QTD.</th><th>VALOR UNITÁRIO</th><th>TOTAL</th></tr></thead><tbody>'+items+'</tbody></table><section class="bottom"><div class="payment"><span class="summary-label">FORMA DE PAGAMENTO</span><strong>'+escape(sale.forma_pagamento).toUpperCase()+'</strong></div><div class="total-box"><span class="summary-label">VALOR TOTAL DO PEDIDO</span><strong>'+money(sale.valor_total)+'</strong></div></section><footer class="footer"><b>STAR LIMP — FRAGRÂNCIAS E PRODUTOS</b><br>'+escape(company.address)+' · WhatsApp: '+escape(company.phone)+'<br>Obrigado pela preferência!</footer></main><button onclick="window.print()">Imprimir / Salvar em PDF</button><script>window.onload=()=>setTimeout(()=>window.print(),300)<\/script></body></html>');
    }
    w.document.close();
    w.focus();
  }).catch(()=>alert('Não foi possível gerar o documento desta venda.'));
}
render('dashboard');