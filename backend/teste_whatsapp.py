import webbrowser
import urllib.parse

telefone = "5562991457036"

mensagem = """
STAR LIMP

Olá Joyce!

Este é um teste do sistema Star Limp IA.

WhatsApp integrado com sucesso.

Obrigado pela preferência.
"""

mensagem_codificada = urllib.parse.quote(mensagem)

link = f"https://wa.me/{telefone}?text={mensagem_codificada}"

print("Abrindo WhatsApp...")

webbrowser.open(link)