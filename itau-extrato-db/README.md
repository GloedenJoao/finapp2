# Importador de Extratos Itaú → SQLite

- Parser de PDFs Itaú
- Deduplicação por hash (data + descrição normalizada + valor absoluto + sinal)
- `transactions` (lançamentos) + `daily_balances` (snapshots “SALDO DO DIA”)
- View `v_saldo_por_dia` para consultar saldo informado por dia

## Como usar
1. Criar venv, instalar deps
2. `python main.py initdb`
3. `python main.py ingest data/raw/SEU_PDF.pdf`
4. `python main.py saldos`
