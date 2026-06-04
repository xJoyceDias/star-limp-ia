def formatar_moeda(valor):
    valor = float(valor or 0)
    texto = f"R$ {valor:,.2f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return texto


def formatar_quantidade(valor):
    valor = float(valor or 0)

    if valor.is_integer():
        return str(int(valor))

    return str(valor).replace(".", ",")