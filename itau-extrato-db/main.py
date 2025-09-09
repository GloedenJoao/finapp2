import sys
from src.db import init_db, get_conn
from src.ingest import ingest_itau_pdf

def cmd_initdb():
    init_db()
    print("OK: estrutura do banco criada/atualizada.")

def cmd_ingest(pdf_path: str):
    ingest_itau_pdf(pdf_path)
    print(f"OK: arquivo ingerido -> {pdf_path}")

def cmd_saldos():
    with get_conn() as conn:
        # versão compatível com a view alternativa sugerida em models.sql
        sql = """
        SELECT data, saldo
        FROM v_saldo_por_dia
        ORDER BY data;
        """
        cur = conn.execute(sql)
        rows = cur.fetchall()
        for d, s in rows:
            print(d, s)

def main():
    if len(sys.argv) < 2:
        print("Uso:")
        print("  python main.py initdb")
        print("  python main.py ingest <caminho_pdf>")
        print("  python main.py saldos")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "initdb":
        cmd_initdb()
    elif cmd == "ingest":
        if len(sys.argv) < 3:
            print("Faltou o caminho do PDF.")
            sys.exit(1)
        cmd_ingest(sys.argv[2])
    elif cmd == "saldos":
        cmd_saldos()
    else:
        print(f"Comando desconhecido: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()
