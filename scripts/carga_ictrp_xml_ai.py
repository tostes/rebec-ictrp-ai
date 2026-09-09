#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrapper de carga ICTRP adaptado ao rebecAPI atual.

Reutiliza as credenciais definidas no config do app.py e chama o loader
que cria/atualiza também ictrp_trial_xml.
"""
import os

from api.app import config as legacy_config

os.environ.setdefault("REBEC_AI_MYSQL_HOST", str(legacy_config.get("mysql_host", "127.0.0.1")))
os.environ.setdefault("REBEC_AI_MYSQL_PORT", str(legacy_config.get("mysql_port", 3306)))
os.environ.setdefault("REBEC_AI_MYSQL_USER", str(legacy_config.get("mysql_user", "")))
os.environ.setdefault("REBEC_AI_MYSQL_PASSWORD", str(legacy_config.get("mysql_password", "")))
os.environ.setdefault("REBEC_AI_MYSQL_DATABASE", str(legacy_config.get("mysql_db", "")))

from rebec_ai.carga_ictrp_xml import main

if __name__ == "__main__":
    main()
