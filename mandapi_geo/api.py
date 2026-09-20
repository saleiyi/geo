"""API HTTP + entrega das páginas.

Rodar:
    uvicorn mandapi_geo.api:app --reload --port 8000

Dívida técnica consciente (priorizar só após validação comercial):
  - rate limit por IP usando FREE_SCAN_DAILY_LIMIT (hoje só existe a config)
  - captura de e-mail antes do relatório completo (é o gancho comercial)
  - persistência dos scans para histórico (hoje é stateless)
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .models import ScanReport
from .scanner import ScanError, scan

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(
    title="MandAPI GEO",
    version="0.1.0",
    description="AI Search Visibility + SEO Content Intelligence (mercado brasileiro)",
)


class ScanIn(BaseModel):
    url: str
    keyword: str | None = None
    ai_summary: bool = False


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "engine": "rules-v1"}


@app.post("/api/scan", response_model=ScanReport)
def api_scan(payload: ScanIn) -> ScanReport:
    try:
        return scan(payload.url, keyword=payload.keyword, ai_summary=payload.ai_summary)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ScanError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")