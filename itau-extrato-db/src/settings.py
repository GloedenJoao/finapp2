from pathlib import Path

# Raiz do projeto
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Banco de dados
DB_PATH = PROJECT_ROOT / "bank.db"

# Pastas de dados
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# DDL
MODELS_SQL = PROJECT_ROOT / "sql" / "models.sql"
