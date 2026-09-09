#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Servidor de TESTE para adicionar ReBEC AI Search ao app.py existente.

Não altera app.py. Importa o FastAPI já existente e anexa o novo router.
Execute com:
    uvicorn app_ai_test:app --host 127.0.0.1 --port 8010 --reload
"""
import os

# Reutiliza exatamente o app FastAPI e o config do app.py atual.
from api.app import app, config as legacy_config

# Passa a configuração existente para o módulo isolado antes de importá-lo.
os.environ.setdefault(
    "REBEC_AI_MYSQL_HOST",
    str(legacy_config.get("mysql_host", "127.0.0.1")),
)
os.environ.setdefault(
    "REBEC_AI_MYSQL_PORT",
    str(legacy_config.get("mysql_port", 3306)),
)
os.environ.setdefault(
    "REBEC_AI_MYSQL_USER",
    str(legacy_config.get("mysql_user", "")),
)
os.environ.setdefault(
    "REBEC_AI_MYSQL_PASSWORD",
    str(legacy_config.get("mysql_password", "")),
)
os.environ.setdefault(
    "REBEC_AI_MYSQL_DATABASE",
    str(legacy_config.get("mysql_db", "")),
)

# O Qwen local continua no llama.cpp da máquina.
os.environ.setdefault(
    "REBEC_AI_LLM_URL",
    "http://127.0.0.1:8080/v1/chat/completions",
)

from rebec_ai.router import router as ai_search_router

app.include_router(
    ai_search_router,
    prefix="/ai-search",
)
