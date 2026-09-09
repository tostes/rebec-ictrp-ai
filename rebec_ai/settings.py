# -*- coding: utf-8 -*-
"""Configuração isolada do módulo ReBEC AI Search.

APP_MODE é deliberadamente hardcoded, conforme solicitado.
As credenciais do banco são recebidas por variáveis de ambiente que o
app_ai_test.py preenche automaticamente a partir do config já existente
no app.py atual do rebecAPI.
"""
import os

# ============================================================
# FLAG HARDCODE
# ============================================================
# DEBUG -> expõe log detalhado na interface
# PROD  -> não expõe prompt, SQL, resposta bruta do LLM ou logs internos
APP_MODE = "DEBUG"

MYSQL_CONFIG = {
    "host": os.getenv("REBEC_AI_MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("REBEC_AI_MYSQL_PORT", "3306")),
    "user": os.getenv("REBEC_AI_MYSQL_USER", ""),
    "password": os.getenv("REBEC_AI_MYSQL_PASSWORD", ""),
    "database": os.getenv("REBEC_AI_MYSQL_DATABASE", ""),
    "charset": "utf8mb4",
}

LLM_URL = os.getenv(
    "REBEC_AI_LLM_URL",
    "http://127.0.0.1:8080/v1/chat/completions",
)
