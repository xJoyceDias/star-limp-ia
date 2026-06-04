import sqlite3
import unicodedata
from datetime import datetime
from utils import formatar_moeda, formatar_quantidade

BANCO = r"database/starlimp.db"

def normalizar(texto):
    texto = str(texto).lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto

def buscar_produto(termo):
    termo_normalizado = normalizar(termo)
    palavras = termo_normalizado.split()

    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT codigo, descricao, preco, categoria
        FROM produtos
    """)

    produtos = cursor.fetchall()
    conexao.close()

    encontrados = []

    for codigo, descricao, preco, categoria in produtos:
        descricao_normalizada = normalizar(descricao)
        pontos = 0

        for palavra in palavras:
            if palavra in descricao_normalizada:
                pontos += 1

        if pontos > 0:
            encontrados.append({
                "codigo": codigo,
                "descricao": descricao,
                "preco": preco,
                "categoria": categoria,
                "pontos": pontos
            })

    encontrados = sorted(
        encontrados,
        key=lambda produto: produto["pontos"],
        reverse=True
    )

    melhores = [
        produto for produto in encontrados
        if produto["pontos"] == len(palavras)
    ]

    if melhores:
        return melhores

    return encontrados[:5]

def buscar_cliente(nome):
    nome = normalizar(nome)

    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, nome, telefone, saldo_fiado
        FROM clientes
    """)

    clientes = cursor.fetchall()

    conexao.close()

    for cliente in clientes:
        if normalizar(cliente[1]) == nome:
            return cliente

    return None

def cadastrar_cliente(nome, telefone):
    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    data_cadastro = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO clientes (
            nome,
            telefone,
            saldo_fiado,
            data_cadastro
        )
        VALUES (?, ?, ?, ?)
    """, (
        nome,
        telefone,
        0,
        data_cadastro
    ))

    conexao.commit()
    cliente_id = cursor.lastrowid
    conexao.close()

    return cliente_id

def atualizar_saldo_cliente(cliente_id, novo_saldo):
    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("""
        UPDATE clientes
        SET saldo_fiado = ?
        WHERE id = ?
    """, (
        novo_saldo,
        cliente_id
    ))

    conexao.commit()
    conexao.close()

def salvar_venda(itens, total, forma_pagamento):
    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO vendas (
            data_hora,
            valor_total,
            forma_pagamento
        )
        VALUES (?, ?, ?)
    """, (
        data_hora,
        total,
        forma_pagamento
    ))

    venda_id = cursor.lastrowid

    for item in itens:
        cursor.execute("""
            INSERT INTO itens_venda (
                venda_id,
                codigo_produto,
                descricao,
                quantidade,
                preco_unitario,
                subtotal
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            venda_id,
            item["produto"]["codigo"],
            item["produto"]["descricao"],
            item["quantidade"],
            item["produto"]["preco"],
            item["subtotal"]
        ))

    conexao.commit()
    conexao.close()

    return venda_id, data_hora

def salvar_fiado(venda_id, cliente_id, cliente_nome, telefone, retirado_por, valor_compra, saldo_anterior, saldo_atual, data_hora):
    conexao = sqlite3.connect(BANCO)
    cursor = conexao.cursor()

    cursor.execute("""
        INSERT INTO fiados (
            venda_id,
            cliente_id,
            cliente_nome,
            telefone,
            retirado_por,
            valor_compra,
            saldo_anterior,
            saldo_atual,
            data_hora,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        venda_id,
        cliente_id,
        cliente_nome,
        telefone,
        retirado_por,
        valor_compra,
        saldo_anterior,
        saldo_atual,
        data_hora,
        "ABERTO"
    ))

    conexao.commit()
    conexao.close()

def montar_mensagem_fiado(cliente_nome, retirado_por, itens, valor_compra, saldo_anterior, saldo_atual, data_hora):
    data_obj = datetime.strptime(data_hora, "%Y-%m-%d %H:%M:%S")
    data_formatada = data_obj.strftime("%d/%m/%Y")
    hora_formatada = data_obj.strftime("%H:%M")

    produtos_texto = ""

    for item in itens:
        produtos_texto += (
    f"• {formatar_quantidade(item['quantidade'])}x "
    f"{item['produto']['descricao']} - "
    f"{formatar_moeda(item['subtotal'])}\n"
)

    mensagem = f"""
🏪 STAR LIMP FRAGRÂNCIAS E PRODUTOS

Olá {cliente_nome}!

Segue o resumo da sua compra realizada hoje.

📅 Data: {data_formatada}
🕒 Hora: {hora_formatada}

🛒 Produtos retirados:

{produtos_texto}
💰 Valor desta compra:
{formatar_moeda(valor_compra)}

👤 Retirado por:
{retirado_por}

━━━━━━━━━━━━━━━

📊 Resumo da conta

Saldo anterior:
{formatar_moeda(saldo_anterior)}

Compras realizadas hoje:
{formatar_moeda(valor_compra)}

Saldo atual:
{formatar_moeda(saldo_atual)}

━━━━━━━━━━━━━━━

💳 PIX para pagamento:

Chave PIX:
62 99999-9999

Favorecido:
Star Limp Fragrâncias e Produtos

Caso já tenha realizado o pagamento, desconsidere esta mensagem.

Em caso de pagamento, envie o comprovante para atualização do seu cadastro.

Obrigado pela preferência!

Star Limp Fragrâncias e Produtos
"""
    return mensagem

def escolher_produto(encontrados):
    if len(encontrados) == 1:
        return encontrados[0]

    print("\nEncontrei mais de uma opção:")

    for i, produto in enumerate(encontrados[:5], start=1):
        print(f"{i} - {produto['descricao']} - R$ {produto['preco']:.2f}")

    escolha = input("Escolha o número do produto: ")

    try:
        indice = int(escolha) - 1
        return encontrados[indice]
    except:
        print("Escolha inválida.")
        return None

def processar_venda():
    print("=== PDV STAR LIMP ===")
    print("Digite os produtos da venda.")
    print("Exemplo: 2 lavanda fresh 250g")
    print("Digite FIM para finalizar.\n")

    itens = []
    total = 0

    while True:
        entrada = input("Produto: ").strip()

        if entrada.lower() == "fim":
            break

        partes = entrada.split(" ", 1)

        if len(partes) < 2:
            print("Digite no formato: quantidade produto")
            continue

        try:
            quantidade = float(partes[0].replace(",", "."))
        except ValueError:
            print("Quantidade inválida.")
            continue

        termo = partes[1]

        encontrados = buscar_produto(termo)

        if not encontrados:
            print("Produto não encontrado.")
            continue

        produto = escolher_produto(encontrados)

        if not produto:
            continue

        subtotal = quantidade * produto["preco"]
        total += subtotal

        itens.append({
            "quantidade": quantidade,
            "produto": produto,
            "subtotal": subtotal
        })

        print(
    f"Adicionado: {formatar_quantidade(quantidade)}x "
    f"{produto['descricao']} - "
    f"{formatar_moeda(subtotal)}"
)

    if not itens:
        print("Nenhum item informado. Venda cancelada.")
        return

    print("\n=== RESUMO DA VENDA ===")

    for item in itens:
       print(
    f"{formatar_quantidade(item['quantidade'])}x "
    f"{item['produto']['descricao']} - "
    f"{formatar_moeda(item['subtotal'])}"
)
    print(f"\nTOTAL: {formatar_moeda(total)}")

    pagamento = input("\nForma de pagamento (pix/dinheiro/debito/credito/fiado): ").strip().lower()

    venda_id, data_hora = salvar_venda(
        itens,
        total,
        pagamento
    )

    print(f"\n✅ Venda salva com sucesso!")
    print(f"Venda Nº {venda_id}")
    print(f"Pagamento: {pagamento.upper()}")

    if pagamento == "fiado":
        print("\n=== DADOS DA CONTA CLIENTE ===")

        nome_cliente = input("Nome do cliente: ").strip()
        retirado_por = input("Retirado por: ").strip()

        cliente = buscar_cliente(nome_cliente)

        if cliente:
            cliente_id = cliente[0]
            cliente_nome = cliente[1]
            telefone = cliente[2]
            saldo_anterior = cliente[3] or 0
        else:
            print("Cliente não encontrado. Vamos cadastrar agora.")
            telefone = input("Telefone/WhatsApp do cliente: ").strip()
            cliente_id = cadastrar_cliente(nome_cliente, telefone)
            cliente_nome = nome_cliente
            saldo_anterior = 0

        saldo_atual = saldo_anterior + total

        atualizar_saldo_cliente(cliente_id, saldo_atual)

        salvar_fiado(
            venda_id,
            cliente_id,
            cliente_nome,
            telefone,
            retirado_por,
            total,
            saldo_anterior,
            saldo_atual,
            data_hora
        )

        mensagem = montar_mensagem_fiado(
            cliente_nome,
            retirado_por,
            itens,
            total,
            saldo_anterior,
            saldo_atual,
            data_hora
        )

        print("\n✅ Conta Cliente atualizada com sucesso!")
        print(f"Cliente: {cliente_nome}")
        print(f"Saldo anterior: {formatar_moeda(saldo_anterior)}")
        print(f"Saldo atual: {formatar_moeda(saldo_atual)}")

        print("\n===== MENSAGEM PARA ENVIAR AO CLIENTE =====")
        print(mensagem)

if __name__ == "__main__":
    processar_venda()