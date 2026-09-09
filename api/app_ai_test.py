#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standalone FastAPI entry point for the ReBEC ICTRP AI search module.

Run with:
    uvicorn api.app_ai_test:app --host 127.0.0.1 --port 8010 --reload
"""
from fastapi import FastAPI

from rebec_ai.router import router as ai_search_router

app = FastAPI(title="ReBEC ICTRP AI")
app.include_router(ai_search_router, prefix="/ai-search")
