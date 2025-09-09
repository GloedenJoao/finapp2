from typing import Tuple, Optional

def classify(lanc_norm: str, valor: float) -> Tuple[str, Optional[str], str]:
    """
    Retorna (categoria, detalhe_categoria, tipo_mov)
    - tipo_mov: 'credito' se valor > 0, 'debito' se valor < 0
    - regras simples para RESGATE/APLICACAO
    """
    tipo = "credito" if valor > 0 else "debito"

    categoria = None
    detalhe = None

    if "RESGATE" in lanc_norm:
        categoria = "resgate_investimento"
        # detalhe após a palavra RESGATE (se existir)
        partes = lanc_norm.split("RESGATE", 1)
        if len(partes) > 1:
            detalhe = partes[1].strip()

    elif "APLICACAO" in lanc_norm or "APLICAÇÃO" in lanc_norm:
        categoria = "aplicacao_investimento"
        partes = lanc_norm.split("APLICACAO", 1)
        if len(partes) == 1:
            partes = lanc_norm.split("APLICAÇÃO", 1)
        if len(partes) > 1:
            detalhe = partes[1].strip()

    # Outras regras podem ser adicionadas futuramente (PIX, SAQUE, TARIFA...)
    return categoria, detalhe, tipo

def make_unique_hash(data_iso: str, lanc_norm: str, valor: float) -> str:
    """
    Gera hash estável:
      data ISO + descrição normalizada + abs(valor) com 2 casas + sinal (C/D)
    """
    sign = "C" if valor > 0 else "D"
    base = f"{data_iso}|{lanc_norm}|{abs(valor):.2f}|{sign}"
    import hashlib
    return hashlib.sha1(base.encode("utf-8")).hexdigest()
