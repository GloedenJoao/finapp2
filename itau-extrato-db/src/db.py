import sqlite3
from pathlib import Path
from .settings import DB_PATH, MODELS_SQL

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    with open(MODELS_SQL, "r", encoding="utf-8") as f:
        ddl = f.read()
    with get_conn() as conn:
        conn.executescript(ddl)


def insert_transaction(conn, row: dict):
    """
    row esperado:
      data, lancamentos, lancamentos_norm, valor, saldo_dia,
      tipo_mov, categoria, detalhe_categoria, pagina, linha, hash_unico
    """
    conn.execute(
        """
        INSERT OR IGNORE INTO transactions
        (data, lancamentos, lancamentos_norm, valor, saldo_dia, tipo_mov,
         categoria, detalhe_categoria, pagina, linha, hash_unico)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["data"], row["lancamentos"], row["lancamentos_norm"],
            row["valor"], row.get("saldo_dia"),
            row.get("tipo_mov"), row.get("categoria"), row.get("detalhe_categoria"),
            row.get("pagina"), row.get("linha"), row["hash_unico"]
        ),
    )

def upsert_daily_balance(conn, data_iso: str, saldo_dia: float):
    conn.execute(
        """
        INSERT INTO daily_balances (data, saldo_dia)
        VALUES (?, ?)
        ON CONFLICT(data) DO UPDATE SET saldo_dia=excluded.saldo_dia
        """,
        (data_iso, saldo_dia),
    )

# NOVO: saldo diário por aplicação (investimento)
def upsert_investment_balance(conn, aplicacao: str, data_iso: str, saldo: float):
    conn.execute(
        """
        INSERT INTO investment_balances (aplicacao, data, saldo)
        VALUES (?, ?, ?)
        ON CONFLICT(aplicacao, data) DO UPDATE SET saldo=excluded.saldo
        """,
        (aplicacao, data_iso, saldo),
    )