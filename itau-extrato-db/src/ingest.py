from typing import Iterable, Dict
from .db import init_db, get_conn, insert_transaction, upsert_daily_balance
from .utils import norm_text, money_to_float
from .rules import classify, make_unique_hash
from .parsers.itau_pdf import parse_itau_pdf

def ingest_itau_pdf(pdf_path: str):
    init_db()
    rows: Iterable[Dict] = parse_itau_pdf(pdf_path)
    with get_conn() as conn:
        for r in rows:
            data_iso = r["data_iso"]
            desc = r["descricao"]
            lanc_norm = norm_text(desc)

            valor = r["valor"]
            valor_f = money_to_float(valor) if valor is not None else 0.0

            # tipo/categorias
            categoria, detalhe, tipo = classify(lanc_norm, valor_f)

            # hash_unico: mesmo PDF reimportado não duplica
            h = make_unique_hash(data_iso, lanc_norm, valor_f)

            payload = {
                "data": data_iso,
                "lancamentos": desc,
                "lancamentos_norm": lanc_norm,
                "valor": valor_f,
                "saldo_dia": money_to_float(r["saldo_dia"]) if r.get("saldo_dia") else None,
                "tipo_mov": tipo,
                "categoria": categoria,
                "detalhe_categoria": detalhe,
                "pagina": r.get("pagina"),
                "linha": r.get("linha"),
                "hash_unico": h,
            }

            # Se a linha for realmente um SALDO DO DIA (snapshot), normalmente valor None
            if desc == "SALDO DO DIA" and payload["saldo_dia"] is not None:
                upsert_daily_balance(conn, data_iso, payload["saldo_dia"])

            # Insere o lançamento (com INSERT OR IGNORE por causa do índice único)
            insert_transaction(conn, payload)
