"""
config.py  (pronto)
-------------------
Caminhos do projeto e credenciais do banco (lidas do .env, que NAO vai para o Git).
"""

import os
from pathlib import Path

PASTA_RAIZ = Path(__file__).resolve().parents[1]
PASTA_RAW = PASTA_RAIZ / "data" / "raw"      # base BRUTA fornecida (CSV, tudo texto)
PASTA_PROCESSED = PASTA_RAIZ / "data" / "processed"  # onde voce grava as tabelas limpas
PASTA_SQL = PASTA_RAIZ / "sql"
PASTA_REPORTS = PASTA_RAIZ / "reports"


def carregar_env():
    """Le o .env (se existir) e joga as variaveis em os.environ (sem biblioteca externa)."""
    arquivo_env = PASTA_RAIZ / ".env"
    if not arquivo_env.exists():
        return
    for linha in arquivo_env.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip())


carregar_env()

PG_CONFIG = {
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": int(os.environ.get("PG_PORT", "5432")),
    "user": os.environ.get("PG_USER", "postgres"),
    "password": os.environ.get("PG_PASSWORD", ""),
}
PG_DATABASE = os.environ.get("PG_DATABASE", "pncp_controladoria")
