import base64
import binascii
import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from nwis.config import get_settings
from nwis.db import close_pool, connection
from nwis.schemas import ComponentStatus, SeedResponse, SystemStatus, WellPage, WellSummary
from nwis.security import Principal, current_principal, require_role
from nwis.seed import load_fixture
from nwis.ingestion.api import router as ingestion_router
from nwis.intelligence import router as intelligence_router
from nwis.operations import router as operations_router
from nwis.prediction import router as prediction_router
from nwis.report_facts import router as report_facts_router
from nwis.real_ml_approval import router as real_ml_approval_router
from nwis.exploration import router as exploration_router
from nwis.pressure_window import router as pressure_window_router
from nwis.operational_views import router as operational_views_router
from nwis.telemetry_dossier import router as telemetry_dossier_router
from nwis.ertmac_feed import router as ertmac_router
from nwis.security import router as auth_router

# ── Rate-limit state (in-memory, per-IP) — Fix #6 ──────────────
_RATE_LIMIT: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW = 60.0  # seconds
_RATE_CAPS: dict[str, int] = {
    "/api/v1/auth/login": 10,
    "/api/v1/documents": 20,
    "/api/v1/voice-memos": 10,
}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialise shared resources on startup; clean them up on shutdown."""
    yield
    close_pool()  # Fix #1: gracefully drain the connection pool


app = FastAPI(
    title="NWIS API",
    version="0.2.0",
    description="Evidence ingestion and review",
    lifespan=lifespan,
)

# ── CORS — Fix #9 & Gap H ───────────────────────────────────────
raw_origins = os.getenv("NWIS_ALLOWED_ORIGINS", "*").strip()
_cors_origins = ["*"] if raw_origins == "*" else [o.strip() for o in raw_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True if _cors_origins != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(ingestion_router)
app.include_router(intelligence_router)
app.include_router(operations_router)
app.include_router(prediction_router)
app.include_router(report_facts_router)
app.include_router(real_ml_approval_router)
app.include_router(exploration_router)
app.include_router(pressure_window_router)
app.include_router(operational_views_router)
app.include_router(telemetry_dossier_router)
app.include_router(ertmac_router)

_fixture_path = Path(__file__).resolve().parents[1] / "specs/fixtures/golden-demo.json"
if not _fixture_path.is_file():
    _fixture_path = Path(__file__).resolve().parents[2] / "specs/fixtures/golden-demo.json"


def error(code: str, message: str, request_id: str, details: dict | None = None) -> dict:
    return {
        "error": {"code": code, "message": message, "details": details or {}},
        "request_id": request_id,
    }


# ── Request-ID middleware ───────────────────────────────────────
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request.state.request_id = str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


# ── Rate-limit middleware — Fix #6 ──────────────────────────────
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    cap = _RATE_CAPS.get(request.url.path)
    if cap is not None:
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        _RATE_LIMIT[ip] = [t for t in _RATE_LIMIT[ip] if now - t < _RATE_WINDOW]
        if len(_RATE_LIMIT[ip]) >= cap:
            return JSONResponse(
                status_code=429,
                content={"error": {"code": "rate_limited", "message": "Too many requests", "details": {}}},
            )
        _RATE_LIMIT[ip].append(now)
    return await call_next(request)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    code = {401: "unauthorized", 403: "forbidden", 404: "not_found", 409: "conflict"}.get(
        exc.status_code, "request_error"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error(code, str(exc.detail), request.state.request_id),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    fields = [".".join(str(part) for part in item["loc"]) for item in exc.errors()]
    return JSONResponse(
        status_code=422,
        content=error(
            "invalid_request",
            "Invalid request fields",
            request.state.request_id,
            {"fields": fields},
        ),
    )


@app.get("/healthz")
def healthz():
    return {"state": "running"}


@app.get("/api/v1/status", response_model=SystemStatus)
def system_status(_principal: Principal = Depends(current_principal)):
    settings = get_settings()
    database = ComponentStatus(state="degraded")
    spatial = ComponentStatus(state="unavailable")
    vector = ComponentStatus(state="unavailable")
    ingestion = ComponentStatus(state="degraded", detail="Worker heartbeat unavailable")
    datasets: list[str] = []
    try:
        with connection() as conn:
            row = conn.execute(
                """SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='postgis') AS postgis,
                          EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector') AS vector,
                          EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='dataset') AS migrated"""
            ).fetchone()
            database = ComponentStatus(state="ready" if row["migrated"] else "degraded")
            spatial = ComponentStatus(state="ready" if row["postgis"] else "unavailable")
            vector = ComponentStatus(state="ready" if row["vector"] else "unavailable")
            if row["migrated"]:
                datasets = [
                    r["kind"]
                    for r in conn.execute("SELECT DISTINCT kind FROM dataset ORDER BY kind")
                ]
                heartbeat = conn.execute("""SELECT last_seen_at > now() - interval '180 seconds' AS fresh
                    FROM service_heartbeat WHERE service='ingestion'""").fetchone()
                ingestion = ComponentStatus(
                    state="ready" if heartbeat and heartbeat["fresh"] else "degraded",
                    detail=f"Extraction: {settings.extraction_provider}; review required"
                    if heartbeat and heartbeat["fresh"]
                    else "Ingestion worker heartbeat missing or stale",
                )
    except Exception:
        database = ComponentStatus(state="degraded", detail="Database connection unavailable")
    # Dynamic source mode (Gap E) & active prediction model (Gap C)
    live_feed_fresh = False
    try:
        with connection() as conn:
            live_hb = conn.execute("""SELECT last_seen_at > now() - interval '60 seconds' AS fresh
                FROM service_heartbeat WHERE service='witsml_live'""").fetchone()
            if live_hb and live_hb["fresh"]:
                live_feed_fresh = True
    except Exception:
        pass

    effective_source_mode = "LIVE" if live_feed_fresh else settings.source_mode

    try:
        from nwis.hazard_model import get_active_model
        model = get_active_model()
        prediction = ComponentStatus(
            state="ready",
            detail=f"{model.get('model_version', 'mud-loss-detector')} (calibrated {model.get('algorithm', 'classifier')})",
        )
    except Exception:
        prediction = ComponentStatus(state="not_implemented", detail="No trained model")

    return SystemStatus(
        environment=settings.environment,
        source_mode=effective_source_mode,
        database=database,
        spatial=spatial,
        vector=vector,
        ingestion=ingestion,
        replay=ComponentStatus(
            state="available",
            detail="Fixed synthetic scenario; WebSocket snapshots with HTTP fallback; replay worker required for autoplay",
        ),
        prediction=prediction,
        datasets=datasets,
        checked_at=datetime.now(timezone.utc),
    )


def _offset(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        value = int(base64.urlsafe_b64decode(cursor.encode()).decode())
        if value < 0:
            raise ValueError
        return value
    except (ValueError, binascii.Error, UnicodeDecodeError):
        raise HTTPException(status_code=422, detail="Invalid cursor") from None


@app.get("/api/v1/wells", response_model=WellPage)
def wells(
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = None,
    kind: str | None = Query(default=None, pattern="^(synthetic|public|private)$"),
    _principal: Principal = Depends(current_principal),
):
    offset = _offset(cursor)
    with connection() as conn:
        rows = conn.execute(
            """SELECT w.id, w.external_id, w.name, w.basin_name, d.kind AS data_kind,
                      d.origin_kind,d.authorization_state,d.applicability,d.qualification_status,
                      ST_X(w.surface_point::geometry) AS longitude,
                      ST_Y(w.surface_point::geometry) AS latitude
               FROM well w JOIN dataset d ON d.id=w.dataset_id
               WHERE w.status<>'benchmark_unlocated'
                 AND (%s::text IS NULL OR d.kind=%s)
               ORDER BY d.kind, w.external_id, w.id LIMIT %s OFFSET %s""",
            (kind, kind, limit + 1, offset),
        ).fetchall()
    more = len(rows) > limit
    return WellPage(
        items=[WellSummary(**row) for row in rows[:limit]],
        next_cursor=base64.urlsafe_b64encode(str(offset + limit).encode()).decode()
        if more
        else None,
    )


@app.get("/api/v1/wells/nearby", response_model=WellPage)
def nearby_wells(
    active_well_id: UUID,
    radius_km: float = Query(ge=0.1, le=100),
    limit: int = Query(default=25, ge=1, le=100),
    _principal: Principal = Depends(current_principal),
):
    """Return wells within radius_km of the active well.

    Fix #7: The original query joined on w.dataset_id=a.dataset_id, silently
    excluding wells that live in a different dataset (e.g. public offset wells
    when the active well is in the private dataset). The fix drops that
    constraint so all spatially eligible wells are returned, regardless of
    which dataset they belong to.
    """
    with connection() as conn:
        active = conn.execute(
            "SELECT id, surface_point FROM well WHERE id=%s AND status<>'benchmark_unlocated'",
            (active_well_id,),
        ).fetchone()
        if active is None:
            raise HTTPException(status_code=404, detail="Active well not found")
        rows = conn.execute(
            """SELECT w.id, w.external_id, w.name, w.basin_name, d.kind AS data_kind,
                      d.origin_kind,d.authorization_state,d.applicability,d.qualification_status,
                      ST_X(w.surface_point::geometry) AS longitude,
                      ST_Y(w.surface_point::geometry) AS latitude,
                      ST_Distance(w.surface_point, a.surface_point) AS surface_distance_m
               FROM well a
               JOIN well w ON w.id<>a.id
               JOIN dataset d ON d.id=w.dataset_id
               WHERE a.id=%s AND w.status<>'benchmark_unlocated'
                 AND ST_DWithin(w.surface_point, a.surface_point, %s)
               ORDER BY surface_distance_m, w.id LIMIT %s""",
            (active_well_id, radius_km * 1000, limit),
        ).fetchall()
    return WellPage(items=[WellSummary(**row) for row in rows])


@app.post("/api/v1/admin/fixtures/golden", response_model=SeedResponse)
def seed_golden(principal: Principal = Depends(require_role("admin"))):
    if get_settings().environment == "production":
        raise HTTPException(status_code=403, detail="Fixture loading is disabled in production")
    with connection() as conn:
        result = load_fixture(conn, _fixture_path)
        conn.execute(
            """INSERT INTO audit_log(actor_name, action, entity_type, entity_id, details)
               VALUES (%s,'fixture_load_request','dataset',%s,%s::jsonb)""",
            (principal.name, result["dataset_id"], '{"fixture":"golden"}'),
        )
    return SeedResponse(**result)
