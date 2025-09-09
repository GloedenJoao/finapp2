from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import sqlite3
import re
from datetime import date

from src.settings import PROJECT_ROOT, DB_PATH, DATA_RAW_DIR
from src.db import get_conn, init_db
from src.ingest import ingest_itau_pdf
from src.db import upsert_investment_balance  # já existe no seu projeto

from markupsafe import Markup, escape  # topo do arquivo, junto dos imports
app = FastAPI(title="Extrato Itaú • UI", version="1.0")
app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "static"), name="static")
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))

# ---- Filtros Jinja para formatação amigável ----
def fmt_money(v):
    if v is None: return "—"
    try:
        s = f"{float(v):,.2f}"
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return s
    except Exception:
        return str(v)

def fmt_date(d):
    try:
        y,m,dd = str(d).split("-")
        return f"{dd}/{m}/{y}"
    except Exception:
        return str(d)

templates.env.filters["fmt_money"] = fmt_money
templates.env.filters["fmt_date"] = fmt_date

def _ptbr_money(v) -> str:
    s = f"{abs(float(v)) :,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s

def money(v):
    if v is None or v == "":
        return Markup('<span class="money">—</span>')
    try:
        f = float(v)
    except Exception:
        return Markup(f'<span class="money">{escape(v)}</span>')
    sign = "+" if f > 0 else ("−" if f < 0 else "")
    cls  = "pos" if f > 0 else ("neg" if f < 0 else "")
    html = f'<span class="money {cls}">{sign}{_ptbr_money(f)}</span>'
    return Markup(html)

templates.env.filters["fmt_date"] = fmt_date
templates.env.filters["money"]    = money

# ---------- helpers ----------
def rows_to_dicts(cursor, rows):
    cols = [c[0] for c in cursor.description] if cursor.description else []
    return cols, [dict(zip(cols, r)) for r in rows]

def list_tables_and_views(conn: sqlite3.Connection):
    sql = """
    SELECT name, type, sql
    FROM sqlite_master
    WHERE type IN ('table','view')
      AND name NOT LIKE 'sqlite_%'
    ORDER BY type DESC, name;
    """
    cur = conn.execute(sql)
    return cur.fetchall()

def safe_select(sql: str) -> tuple[bool, str]:
    s = sql.strip().rstrip(";").strip()
    if not s:
        return False, "SQL vazio."
    if not re.match(r"(?is)^(with\s+.+?select|select)\s", s):
        return False, "Somente consultas SELECT são permitidas."
    if re.search(r"(?is)\b(insert|update|delete|drop|create|alter|attach|pragma|replace|vacuum|transaction|begin|commit|rollback)\b", s):
        return False, "Comando não permitido no Sandbox."
    return True, s

# ---------- rotas existentes (home/input/saldo/sql) ----------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return RedirectResponse(url="/input")

@app.get("/input", response_class=HTMLResponse)
def input_form(request: Request):
    return templates.TemplateResponse("input.html", {"request": request})

@app.post("/input", response_class=HTMLResponse)
async def upload_pdf(request: Request, pdf: UploadFile = File(...)):
    init_db()
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_RAW_DIR / pdf.filename
    with out.open("wb") as f:
        f.write(await pdf.read())
    ingest_itau_pdf(str(out))
    return templates.TemplateResponse(
        "input.html",
        {"request": request, "ok": True, "file_name": pdf.filename},
    )

@app.get("/saldo-do-dia", response_class=HTMLResponse)
def saldo_do_dia(
    request: Request,
    data: str | None = None,
    tipo: str | None = None,
    categoria: str | None = None,
):
    init_db()
    with get_conn() as conn:
        saldo = None
        if data:
            c1 = conn.execute(
                "SELECT saldo FROM v_saldo_por_dia WHERE data = ?;",
                (data,),
            ).fetchone()
            saldo = c1[0] if c1 else None

        params = []
        where = []
        if data:
            where.append("date(data) = date(?)")
            params.append(data)
        if tipo in ("credito", "debito"):
            where.append("tipo_mov = ?")
            params.append(tipo)
        if categoria in ("aplicacao_investimento", "resgate_investimento"):
            where.append("categoria = ?")
            params.append(categoria)

        wh = "WHERE " + " AND ".join(where) if where else "WHERE 1=1"
        sql_tx = f"""
            SELECT date(data) AS data, lancamentos, valor, tipo_mov, categoria, detalhe_categoria, saldo_dia
            FROM transactions
            {wh}
            ORDER BY data DESC, saldo_dia desc,id
            LIMIT 100;
        """
        cur = conn.execute(sql_tx, params)
        cols, rows = rows_to_dicts(cur, cur.fetchall())

    return templates.TemplateResponse(
        "saldo_dia.html",
        {
            "request": request,
            "sel_data": data,
            "sel_tipo": tipo,
            "sel_categoria": categoria,
            "saldo": saldo,
            "cols": cols,
            "rows": rows,
        },
    )

@app.get("/sql-tabelas", response_class=HTMLResponse)
def sql_tabelas(request: Request, name: str | None = None):
    init_db()
    with get_conn() as conn:
        items = list_tables_and_views(conn)
        ddl = None
        preview_cols, preview_rows = [], []
        chosen = name

        if name:
            row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE name = ?;",
                (name,),
            ).fetchone()
            ddl = row[0] if row else "-- (sem DDL registrada)"
            try:
                cur = conn.execute(f'SELECT * FROM "{name}" LIMIT 10;')
                preview_cols, preview_rows = rows_to_dicts(cur, cur.fetchall())
            except Exception as e:
                ddl = (ddl or "") + f"\n-- Preview indisponível: {e}"

    return templates.TemplateResponse(
        "sql_browser.html",
        {
            "request": request,
            "items": items,
            "chosen": chosen,
            "ddl": ddl,
            "preview_cols": preview_cols,
            "preview_rows": preview_rows,
        },
    )

@app.get("/sql-sandbox", response_class=HTMLResponse)
def sql_sandbox_form(request: Request):
    return templates.TemplateResponse(
        "sql_sandbox.html",
        {"request": request, "sql": "SELECT * FROM transactions"}
    )

@app.post("/sql-sandbox", response_class=HTMLResponse)
def sql_sandbox_run(request: Request, sql: str = Form(...)):
    ok, s = safe_select(sql)
    if not ok:
        return templates.TemplateResponse(
            "sql_sandbox.html",
            {"request": request, "sql": sql, "error": s},
        )

    init_db()
    wrapped = f"SELECT * FROM ({s}) AS _safe LIMIT 100"
    with get_conn() as conn:
        try:
            cur = conn.execute(wrapped)
            cols, rows = rows_to_dicts(cur, cur.fetchall())
            return templates.TemplateResponse(
                "sql_sandbox.html",
                {"request": request, "sql": s, "cols": cols, "rows": rows},
            )
        except Exception as e:
            return templates.TemplateResponse(
                "sql_sandbox.html",
                {"request": request, "sql": s, "error": str(e)},
            )


# ---------- INVESTIMENTOS (atualizado com filtros e UX) ----------
@app.get("/investimentos", response_class=HTMLResponse)
def investimentos(
    request: Request,
    # filtros de visualização:
    start: str | None = None,          # YYYY-MM-DD
    end: str | None = None,            # YYYY-MM-DD
    app_filter: str | None = None,     # filtra os cards por uma aplicação específica
    # painel de saldo:
    aplicacao: str | None = None,      # aplicação para consulta/lançamento
    data: str | None = None,           # data do saldo consultado
    show_form: int | None = None       # 1 para abrir o painel ao carregar (apenas via botão do card)
):
    init_db()
    today = date.today().isoformat()

    with get_conn() as conn:
        # WHERE dinâmico para transações de investimento (mesma lógica de antes)
        params = []
        where = ["categoria IN ('aplicacao_investimento','resgate_investimento')"]
        if start:
            where.append("date(data) >= date(?)"); params.append(start)
        if end:
            where.append("date(data) <= date(?)"); params.append(end)
        if app_filter:
            where.append("""COALESCE(NULLIF(TRIM(detalhe_categoria), ''), 'SEM_DETALHE') = ?""")
            params.append(app_filter)

        wh = "WHERE " + " AND ".join(where)

        # Totais por aplicação respeitando os filtros
        sql_totais = f"""
            WITH base AS (
              SELECT
                COALESCE(NULLIF(TRIM(detalhe_categoria), ''), 'SEM_DETALHE') AS aplicacao,
                categoria,
                valor
              FROM transactions
              {wh}
            )
            SELECT
              aplicacao,
              SUM(CASE WHEN categoria='aplicacao_investimento' THEN -valor ELSE 0 END) AS valor_aplicado,
              SUM(CASE WHEN categoria='resgate_investimento'   THEN -valor ELSE 0 END) AS valor_resgatado
            FROM base
            GROUP BY aplicacao
            ORDER BY aplicacao;
        """
        cur = conn.execute(sql_totais, params)
        apps_cols, apps_rows = rows_to_dicts(cur, cur.fetchall())

        # Lista completa de aplicações para dropdowns
        cur_all = conn.execute("""
            SELECT DISTINCT COALESCE(NULLIF(TRIM(detalhe_categoria), ''), 'SEM_DETALHE') AS aplicacao
            FROM transactions
            WHERE categoria IN ('aplicacao_investimento','resgate_investimento')
            ORDER BY aplicacao;
        """)
        opcoes = [r[0] for r in cur_all.fetchall()]

        # NOVO: "saldo atual" por aplicação (último saldo conhecido <= hoje)
        cur_bal = conn.execute("""
            WITH ult AS (
              SELECT aplicacao, MAX(date(data)) AS dref
              FROM investment_balances
              WHERE date(data) <= date(?)
              GROUP BY aplicacao
            )
            SELECT ib.aplicacao, ib.data, ib.saldo
            FROM investment_balances ib
            JOIN ult u
              ON u.aplicacao = ib.aplicacao AND date(ib.data) = date(u.dref);
        """, (today,))
        latest_balances = { row[0]: {"data": row[1], "saldo": row[2]} for row in cur_bal.fetchall() }

        # Área de saldo (abre apenas se veio do botão do card)
        saldo_info = None
        aviso_replicado = None
        needs_attention_today = False
        has_exact_for_selected = False  # <-- NOVO

        if aplicacao and data:
            exact = conn.execute(
                "SELECT saldo FROM investment_balances WHERE aplicacao = ? AND date(data) = date(?)",
                (aplicacao, data),
            ).fetchone()
            if exact:
                has_exact_for_selected = True  # <-- NOVO
                saldo_info = {"aplicacao": aplicacao, "data": data, "saldo": exact[0], "replicado": False}
            else:
                prev = conn.execute(
                    """
                    SELECT saldo, data
                    FROM investment_balances
                    WHERE aplicacao = ?
                      AND date(data) <= date(?)
                    ORDER BY date(data) DESC
                    LIMIT 1
                    """,
                    (aplicacao, data),
                ).fetchone()
                if prev:
                    saldo_info = {"aplicacao": aplicacao, "data": data, "saldo": prev[0], "replicado": True}
                    aviso_replicado = f"Saldo replicado do dia {prev[1]} — insira o saldo de {data}."
                else:
                    saldo_info = {"aplicacao": aplicacao, "data": data, "saldo": None, "replicado": None}

        if aplicacao:
            has_today = conn.execute(
                "SELECT 1 FROM investment_balances WHERE aplicacao = ? AND date(data) = date(?)",
                (aplicacao, today),
            ).fetchone()
            needs_attention_today = (has_today is None)

    return templates.TemplateResponse(
        "investimentos.html",
        {
            "request": request,
            "start": start, "end": end, "app_filter": app_filter,
            "opcoes": opcoes,
            "apps_cols": apps_cols, "apps_rows": apps_rows,
            "latest_balances": latest_balances,   # <- NOVO para os cards
            "sel_aplicacao": aplicacao, "sel_data": data,
            "saldo_info": saldo_info, "aviso_replicado": aviso_replicado,
            "needs_attention_today": needs_attention_today,
            "has_exact_for_selected": has_exact_for_selected,  # <-- NOVO
            "show_form": show_form == 1,
            "today": today,
        },
    )

# --- NOVO: remover saldo do dia ---
@app.post("/investimentos/remove-saldo", response_class=HTMLResponse)
def investimentos_remove_saldo(
    request: Request,
    aplicacao: str = Form(...),
    data: str = Form(...),  # YYYY-MM-DD
):
    init_db()
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM investment_balances WHERE aplicacao = ? AND date(data) = date(?)",
            (aplicacao, data),
        )
        conn.commit()
    # volta mantendo o painel aberto, para o usuário relançar se quiser
    return RedirectResponse(
        url=f"/investimentos?aplicacao={aplicacao}&data={data}&show_form=1",
        status_code=303
    )

@app.get("/health")
def health():
    return PlainTextResponse("ok")
