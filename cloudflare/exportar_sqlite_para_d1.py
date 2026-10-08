"""Exporta o banco SQLite do FastAPI para um arquivo SQL compatível com Cloudflare D1."""

import sqlite3
import sys
from pathlib import Path

TABELAS = ("clientes", "produtos", "vendas", "itens_venda", "fiados", "pagamentos_fiado")


def literal(valor):
    if valor is None:
        return "NULL"
    if isinstance(valor, (int, float)):
        return str(valor)
    return "'" + str(valor).replace("'", "''") + "'"


def exportar(origem: Path, destino: Path):
    conexao = sqlite3.connect(origem)
    cursor = conexao.cursor()
    linhas = ["PRAGMA foreign_keys = OFF;", "BEGIN TRANSACTION;"]

    for tabela in TABELAS:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tabela,)
        )
        if not cursor.fetchone():
            continue
        cursor.execute(f"SELECT * FROM {tabela}")
        colunas = [coluna[0] for coluna in cursor.description]
        for registro in cursor.fetchall():
            valores = ", ".join(literal(valor) for valor in registro)
            linhas.append(
                f"INSERT INTO {tabela} ({', '.join(colunas)}) VALUES ({valores});"
            )

    linhas.extend(["COMMIT;", "PRAGMA foreign_keys = ON;"])
    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    conexao.close()


if __name__ == "__main__":
    origem = Path(sys.argv[1] if len(sys.argv) > 1 else "database/starlimp.db")
    destino = Path(sys.argv[2] if len(sys.argv) > 2 else "cloudflare/dados-d1.sql")
    exportar(origem, destino)
    print(f"Arquivo gerado: {destino}")
