# src/itau_pdf.py
import re
from typing import Iterator, Dict, Optional
from dateutil.parser import parse as parse_date
from pypdf import PdfReader

# ---------------------------
# Padrões e utilitários
# ---------------------------

# Data no início da linha: DD/MM/AAAA
DATE_RE = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+")

# Dinheiro pt-BR com possível sinal negativo:
# exemplos: -61,20 | 1.749,47 | 0,00 | -2.314,88
PAT_MONEY = re.compile(r'(?<!\d)(-?\d{1,3}(?:\.\d{3})*,\d{2})(?!\d)')

def _to_iso(date_str: str) -> str:
    """dd/mm/aaaa -> yyyy-mm-dd"""
    dt = parse_date(date_str, dayfirst=True)
    return dt.date().isoformat()

def _extract_last_money(txt: str) -> Optional[str]:
    """Captura o ÚLTIMO valor monetário na linha (padrão dos extratos Itaú)."""
    matches = PAT_MONEY.findall(txt)
    if not matches:
        return None
    return matches[-1]

_SPACES_RE = re.compile(r"\s+")
def _clean_desc(txt: str) -> str:
    """Limpa espaços extras na descrição."""
    txt = txt.strip()
    txt = _SPACES_RE.sub(" ", txt)
    return txt

# ---------------------------
# Parser
# ---------------------------

def parse_itau_pdf(path: str) -> Iterator[Dict]:
    """
    Gera dicionários com:
      - data_iso: 'YYYY-MM-DD'
      - descricao: texto sem o valor monetário
      - valor: string pt-BR do valor (ex.: '-61,20') ou None em SALDO DO DIA
      - saldo_dia: string pt-BR do saldo (apenas em SALDO DO DIA), senão None
      - pagina: número da página (1-based)
      - linha: número da linha (1-based)
    """
    reader = PdfReader(path)
    for p_idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        for l_idx, raw in enumerate(text.splitlines(), start=1):
            line = raw.strip()
            if not line:
                continue

            # 1) Data no início da linha?
            m_date = DATE_RE.match(line)
            if not m_date:
                continue  # linhas de cabeçalho/rodapé/aviso são ignoradas

            date_str = m_date.group(1)                 # DD/MM/AAAA
            rest = line[m_date.end():].strip()         # após a data
            data_iso = _to_iso(date_str)

            # 2) Snapshot "SALDO DO DIA"?
            #    Ex.: "SALDO DO DIA 91,24"
            upper = rest.upper()
            if "SALDO DO DIA" in upper:
                # O saldo vem como último número na linha
                saldo_txt = _extract_last_money(rest)
                if saldo_txt is None:
                    # Não deveria acontecer; se acontecer, emite registro mínimo
                    yield {
                        "data_iso": data_iso,
                        "descricao": "SALDO DO DIA",
                        "valor": None,
                        "saldo_dia": None,
                        "pagina": p_idx,
                        "linha": l_idx,
                    }
                else:
                    yield {
                        "data_iso": data_iso,
                        "descricao": "SALDO DO DIA",
                        "valor": None,           # snapshot, não é lançamento
                        "saldo_dia": saldo_txt,  # string pt-BR
                        "pagina": p_idx,
                        "linha": l_idx,
                    }
                continue

            # 3) Linha de lançamento "normal":
            #    Padrão Itaú: ... <DESCRIÇÃO LIVRE> ... <VALOR> [<SALDO>]
            #    Tomamos SEMPRE o último valor como "valor da transação".
            valor_txt = _extract_last_money(rest)
            if valor_txt is None:
                # Linha sem dinheiro (raro) — ignora ou poderia logar
                continue

            # Remove TODOS os tokens monetários da descrição
            desc = PAT_MONEY.sub("", rest)
            desc = _clean_desc(desc)

            # Em alguns PDFs aparecem números "códigos" no meio (ex.: "0609")
            # Isso é parte da descrição; não tentamos interpretar como saldo.

            yield {
                "data_iso": data_iso,
                "descricao": desc,
                "valor": valor_txt,   # string pt-BR, ex.: "-61,20"
                "saldo_dia": None,    # nunca preenche em lançamentos comuns
                "pagina": p_idx,
                "linha": l_idx,
            }
