# -*- coding: utf-8 -*-
"""Configuration for the ReBEC AI Search module."""
import os

# DEBUG -> exposes detailed diagnostics in the UI
# PROD  -> hides prompts, SQL, raw model output and internal logs
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
