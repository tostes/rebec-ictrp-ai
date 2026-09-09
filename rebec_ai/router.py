# -*- coding: utf-8 -*-
import io
import json
import time
import uuid
import zipfile
import traceback
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from .settings import APP_MODE
from .ai_search_engine import run_search_api
from .repository import (
    get_options,
    get_trial_detail,
    get_trial_xml,
    get_trials_xml,
)
from .ui import PAGE_HTML


router = APIRouter(tags=["ReBEC AI Search"])
DEBUG_MODE = APP_MODE.upper() == "DEBUG"

# Cache simples de buscas para o ambiente de teste.
# Em produção, trocar por Redis ou outro backend compartilhado.
SEARCH_TTL_SECONDS = 3600
SEARCH_SESSIONS: Dict[str, Dict] = {}


def _model_dump(model):
    """Compatível com Pydantic v1 e v2."""
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


class SearchFilters(BaseModel):
    condition: Optional[str] = None
    intervention: Optional[str] = None
    title: Optional[str] = None
    recruitment_status: Optional[str] = None
    phase: Optional[str] = None
    gender: Optional[str] = None
    age_min_years: Optional[float] = None
    age_max_years: Optional[float] = None
    country: Optional[str] = None
    sponsor: Optional[str] = None
    study_type: Optional[str] = None
    registration_date_from: Optional[str] = None
    registration_date_to: Optional[str] = None


class SearchRequest(BaseModel):
    query: str = ""
    language: Literal["pt", "en", "es"] = "pt"
    filters: SearchFilters = Field(default_factory=SearchFilters)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    threshold: float = Field(default=0.70, ge=0.1, le=1.0)


class ExportRequest(BaseModel):
    search_id: str
    scope: Literal["all", "selected"] = "all"
    trial_ids: List[str] = Field(default_factory=list)


def _cleanup_search_sessions():
    now = time.time()
    expired = [
        key
        for key, item in SEARCH_SESSIONS.items()
        if now - item["created_at"] > SEARCH_TTL_SECONDS
    ]
    for key in expired:
        SEARCH_SESSIONS.pop(key, None)


@router.get("/", response_class=HTMLResponse)
def search_page():
    return HTMLResponse(
        PAGE_HTML.replace(
            "__APP_MODE__",
            APP_MODE.upper(),
        )
    )


@router.get("/api/options")
def api_options():
    try:
        return {
            "app_mode": APP_MODE.upper(),
            "debug": DEBUG_MODE,
            "options": get_options(),
            "age_presets": [
                {"label": "Todas as idades", "min": None, "max": None},
                {"label": "Crianças (0–17)", "min": 0, "max": 17},
                {"label": "Adultos (18–59)", "min": 18, "max": 59},
                {"label": "Idosos (60+)", "min": 60, "max": None},
            ],
        }
    except Exception as exc:
        if DEBUG_MODE:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": str(exc),
                    "type": type(exc).__name__,
                    "traceback": traceback.format_exc(),
                },
            )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@router.post("/api/search")
def api_search(payload: SearchRequest):
    try:
        result = run_search_api(
            query=payload.query,
            structured_filters=_model_dump(payload.filters),
            language=payload.language,
            page=payload.page,
            page_size=payload.page_size,
            threshold_ratio=payload.threshold,
            debug=DEBUG_MODE,
            translate=True,
        )

        _cleanup_search_sessions()

        full_results = result.pop("_all_results_internal", [])
        all_trial_ids = result.pop("all_trial_ids", [])

        search_id = uuid.uuid4().hex

        SEARCH_SESSIONS[search_id] = {
            "created_at": time.time(),
            "trial_ids": all_trial_ids,
            "results": full_results,
            "query": payload.query,
            "filters": _model_dump(payload.filters),
            "language": payload.language,
            "page_size": payload.page_size,
            "total_results": result.get("total_results", len(full_results)),
            "primary_count": result.get("primary_count", 0),
            "related_count": result.get("related_count", 0),
            "threshold_score": result.get("threshold_score", 0),
            "db_stats": result.get("db_stats", {}),
        }

        result["search_id"] = search_id
        result["app_mode"] = APP_MODE.upper()
        return result

    except ValueError as exc:
        if DEBUG_MODE:
            detail = {
                "message": str(exc),
                "debug_log": (
                    "===== ReBEC AI SEARCH ERROR =====\n"
                    f"type: ValueError\n"
                    f"message: {exc}\n\n"
                    "===== REQUEST PAYLOAD =====\n"
                    + json.dumps(
                        _model_dump(payload),
                        indent=2,
                        ensure_ascii=False,
                        default=str,
                    )
                ),
            }
            raise HTTPException(status_code=400, detail=detail)
        raise HTTPException(status_code=400, detail=str(exc))

    except Exception as exc:
        if DEBUG_MODE:
            debug_log = (
                "===== ReBEC AI SEARCH ERROR =====\n"
                f"type: {type(exc).__name__}\n"
                f"message: {exc}\n\n"
                "===== REQUEST PAYLOAD =====\n"
                + json.dumps(
                    _model_dump(payload),
                    indent=2,
                    ensure_ascii=False,
                    default=str,
                )
                + "\n\n===== TRACEBACK =====\n"
                + traceback.format_exc()
            )
            raise HTTPException(
                status_code=500,
                detail={"message": str(exc), "debug_log": debug_log},
            )
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/search/{search_id}/page")
def api_search_page(
    search_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """Paginação rápida usando o resultado já calculado em memória."""
    _cleanup_search_sessions()
    session = SEARCH_SESSIONS.get(search_id)

    if not session:
        raise HTTPException(status_code=404, detail="Search session expired or not found")

    results = session.get("results", [])
    total = len(results)
    offset = (page - 1) * page_size
    page_results = results[offset:offset + page_size]

    return {
        "search_id": search_id,
        "page": page,
        "page_size": page_size,
        "total_results": total,
        "primary_count": session.get("primary_count", 0),
        "related_count": session.get("related_count", 0),
        "threshold_score": session.get("threshold_score", 0),
        "db_stats": {
            **session.get("db_stats", {}),
            "pagination_source": "memory_cache",
        },
        "results": page_results,
        "debug": {
            "enabled": DEBUG_MODE,
            "text": (
                "===== ReBEC AI SEARCH PAGINATION =====\n"
                f"search_id: {search_id}\n"
                f"page: {page}\n"
                f"page_size: {page_size}\n"
                f"total_results: {total}\n"
                "source: SEARCH_SESSIONS memory cache\n"
                "LLM called: false\n"
                "SQL search executed: false\n"
                "ranking executed: false\n"
            ) if DEBUG_MODE else "",
        },
    }


@router.get("/api/trials/{trial_id}")
def api_trial_detail(trial_id: str):
    try:
        trial = get_trial_detail(trial_id)
        if not trial:
            raise HTTPException(status_code=404, detail="Trial not found")
        return json.loads(json.dumps(trial, default=str, ensure_ascii=False))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/trials/{trial_id}/xml")
def api_trial_xml(trial_id: str):
    try:
        xml = get_trial_xml(trial_id)
        if not xml:
            raise HTTPException(status_code=404, detail="XML not found. Populate ictrp_trial_xml first.")

        body = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml
        return Response(
            content=body,
            media_type="application/xml; charset=utf-8",
            headers={"Content-Disposition": f'inline; filename="{trial_id}.xml"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/export")
def api_export(payload: ExportRequest):
    _cleanup_search_sessions()
    session = SEARCH_SESSIONS.get(payload.search_id)
    if not session:
        raise HTTPException(status_code=404, detail="Search session expired or not found")

    if payload.scope == "all":
        trial_ids = session["trial_ids"]
    else:
        allowed = set(session["trial_ids"])
        trial_ids = [x for x in payload.trial_ids if x in allowed]

    if not trial_ids:
        raise HTTPException(status_code=400, detail="No trials selected for export")

    rows = get_trials_xml(trial_ids)
    if not rows:
        raise HTTPException(status_code=404, detail="No XML payloads found. Populate ictrp_trial_xml first.")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for row in rows:
            trial_id = row["trial_id"]
            body = '<?xml version="1.0" encoding="UTF-8"?>\n' + row["trial_xml"]
            zf.writestr(f"{trial_id}.xml", body)

        manifest = {
            "search_id": payload.search_id,
            "requested": len(trial_ids),
            "exported": len(rows),
            "trial_ids": [x["trial_id"] for x in rows],
        }
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    buffer.seek(0)
    filename = f"rebec_ai_search_{payload.search_id[:8]}.zip"

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
