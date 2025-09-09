import hashlib
import re
from unidecode import unidecode

_SPACES_RE = re.compile(r"\s+")

def norm_text(s: str) -> str:
    """
    Normaliza descrições:
    - remove acentos
    - upper
    - colapsa espaços
    - strip
    """
    if s is None:
        return ""
    s = unidecode(s).upper().strip()
    s = _SPACES_RE.sub(" ", s)
    return s

def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def money_to_float(txt: str) -> float:
    """
    Converte strings de valor do extrato Itaú para float.
    Aceita formatos com ponto de milhar e vírgula decimal (pt-BR).
    Ex.: '1.234,56' -> 1234.56
    """
    if txt is None:
        return 0.0
    t = txt.replace(".", "").replace(",", ".")
    return float(t)

def validate_row(r: dict) -> dict:
    if r["descricao"] != "SALDO DO DIA" and r.get("saldo_dia") is not None:
        r["saldo_dia"] = None
    if r["descricao"] == "SALDO DO DIA":
        r["valor"] = None
    return r

