import base64
import binascii
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from nwis.config import get_settings
from nwis.db import connection
from nwis.schemas import ComponentStatus, SeedResponse, SystemStatus, WellPage, WellSummary
from nwis.security import Principal, current_principal, require_role
from nwis.seed import load_fixture
from nwis.ingestion.api import router as ingestion_router

app = FastAPI(title="NWIS API", version="0.2.0", description="Evidence ingestion and review")
app.include_router(ingestion_router)
_fixture_path = Path("/app/specs/fixtures/golden-demo.json")


def error(code: str, message: str, request_id: str, details: dict | None = None) -> dict:
    return {
        "error": {"code": code, "message": message, "details": details or {}},
        "request_id": request_id,
    }


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request.state.request_id = str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


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
    return SystemStatus(
        environment=settings.environment,
        source_mode="SIMULATED",
        database=database,
        spatial=spatial,
        vector=vector,
        ingestion=ingestion,
        replay=ComponentStatus(state="not_implemented", detail="Scheduled for Phase 4"),
        prediction=ComponentStatus(state="not_implemented", detail="No trained model"),
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
                      ST_X(w.surface_point::geometry) AS longitude,
                      ST_Y(w.surface_point::geometry) AS latitude
               FROM well w JOIN dataset d ON d.id=w.dataset_id
               WHERE (%s::text IS NULL OR d.kind=%s)
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
    with connection() as conn:
        active = conn.execute(
            "SELECT id, dataset_id, surface_point FROM well WHERE id=%s", (active_well_id,)
        ).fetchone()
        if active is None:
            raise HTTPException(status_code=404, detail="Active well not found")
        rows = conn.execute(
            """SELECT w.id, w.external_id, w.name, w.basin_name, d.kind AS data_kind,
                      ST_X(w.surface_point::geometry) AS longitude,
                      ST_Y(w.surface_point::geometry) AS latitude,
                      ST_Distance(w.surface_point, a.surface_point) AS surface_distance_m
               FROM well a JOIN well w ON w.dataset_id=a.dataset_id AND w.id<>a.id
               JOIN dataset d ON d.id=w.dataset_id
               WHERE a.id=%s AND ST_DWithin(w.surface_point, a.surface_point, %s)
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
