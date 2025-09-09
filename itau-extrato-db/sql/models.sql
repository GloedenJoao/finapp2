PRAGMA foreign_keys = ON;

-- Tabela principal de movimentações do extrato
CREATE TABLE IF NOT EXISTS transactions (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  data             TEXT NOT NULL,          -- ISO YYYY-MM-DD
  lancamentos      TEXT NOT NULL,          -- descrição original
  lancamentos_norm TEXT NOT NULL,          -- descrição normalizada
  valor            REAL NOT NULL,          -- + crédito, - débito
  saldo_dia        REAL,                   -- snapshot de saldo do dia (se houver na linha)
  tipo_mov         TEXT,                   -- 'credito' | 'debito'
  categoria        TEXT,                   -- ex.: resgate_investimento, aplicacao_investimento
  detalhe_categoria TEXT,                  -- extra da descrição, se aplicável
  pagina           INTEGER,                -- nº página no PDF
  linha            INTEGER,                -- nº linha na página
  hash_unico       TEXT NOT NULL UNIQUE    -- deduplicação
);

-- Snapshots de saldo do dia
CREATE TABLE IF NOT EXISTS daily_balances (
  data      TEXT PRIMARY KEY,  -- 1 registro por dia
  saldo_dia REAL NOT NULL
);

-- View do saldo informado por dia (compatível com SQLite)
DROP VIEW IF EXISTS v_saldo_por_dia;

CREATE VIEW v_saldo_por_dia AS
SELECT d AS data, MAX(saldo) AS saldo
FROM (
  SELECT date(data) AS d, saldo_dia AS saldo FROM daily_balances
  UNION ALL
  SELECT date(data) AS d, saldo_dia AS saldo
  FROM transactions
  WHERE saldo_dia IS NOT NULL
) x
GROUP BY d;

----------------------------------------------------------------------
-- NOVO: saldos por aplicação (investimentos)
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS investment_balances (
  aplicacao TEXT NOT NULL,   -- ex.: "CDB COFRINHOS", "CDB DI" (usa transactions.detalhe_categoria)
  data      TEXT NOT NULL,   -- ISO YYYY-MM-DD
  saldo     REAL NOT NULL,
  PRIMARY KEY (aplicacao, data)
);

-- View com totais aplicado/resgatado por aplicação.
-- Regra solicitada:
--   Valor Aplicado    = soma de (Aplicações × -1)
--   Valor Resgatado   = soma de (Resgates   × -1)
DROP VIEW IF EXISTS v_aplicacoes_totais;
CREATE VIEW v_aplicacoes_totais AS
WITH base AS (
  SELECT
    COALESCE(NULLIF(TRIM(detalhe_categoria), ''), 'SEM_DETALHE') AS aplicacao,
    categoria,
    valor
  FROM transactions
  WHERE categoria IN ('aplicacao_investimento', 'resgate_investimento')
)
SELECT
  aplicacao,
  SUM(CASE WHEN categoria = 'aplicacao_investimento' THEN -valor ELSE 0 END) AS valor_aplicado,
  SUM(CASE WHEN categoria = 'resgate_investimento'   THEN -valor ELSE 0 END) AS valor_resgatado
FROM base
GROUP BY aplicacao;