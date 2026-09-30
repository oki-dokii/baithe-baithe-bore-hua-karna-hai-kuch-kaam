import hashlib
import hmac
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from nwis.config import Settings, get_settings
from nwis.db import connection


@dataclass(frozen=True)
class Principal:
    name: str
    role: str


_bearer = HTTPBearer(auto_error=False)


def principal_for_token(token: str, settings: Settings | None = None) -> Principal | None:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    try:
        with connection() as conn:
            row = conn.execute(
                "SELECT username, role, token_hash FROM app_user WHERE token_hash=%s AND active=true",
                (token_hash,),
            ).fetchone()
        if row and hmac.compare_digest(row["token_hash"], token_hash):
            return Principal(name=row["username"], role=row["role"])
    except Exception:
        # Connection failure fallback (e.g. unit tests without DB)
        pass

    # Check against settings role tokens (Fix #5: constant-time compare)
    try:
        active_settings = settings or get_settings()
        role_tokens = {
            active_settings.viewer_token: ("local-viewer", "viewer"),
            active_settings.engineer_token: ("local-engineer", "engineer"),
            active_settings.reviewer_token: ("local-reviewer", "reviewer"),
            active_settings.admin_token: ("local-admin", "admin"),
        }
        for candidate, (uname, r) in role_tokens.items():
            if hmac.compare_digest(token, candidate):
                return Principal(name=uname, role=r)
    except Exception:
        pass

    return None


def current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> Principal:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    principal = principal_for_token(credentials.credentials, settings=settings)
    if principal:
        return principal
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def require_role(*allowed: str):
    def dependency(principal: Principal = Depends(current_principal)) -> Principal:
        if principal.role != "admin" and principal.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return principal

    return dependency


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    role: str | None = None
    token: str | None = None


@router.get("/roles")
def list_roles():
    return {
        "roles": [
            {
                "role": "viewer",
                "label": "Read-Only Viewer",
                "description": "View approved subsurface claims, nearby well maps, and offset briefs.",
                "permissions": ["view_approved", "search_rag", "explore_basin"],
            },
            {
                "role": "engineer",
                "label": "Drilling Operations Engineer",
                "description": "Upload telemetry & daily reports, record verbal shift memos, and simulate hazard risk.",
                "permissions": [
                    "view_approved",
                    "search_rag",
                    "explore_basin",
                    "upload_reports",
                    "record_voice",
                    "run_prediction",
                ],
            },
            {
                "role": "reviewer",
                "label": "Wellsite Verification Reviewer",
                "description": "Inspect unreviewed documents, compare candidate claims against raw sources, and approve/reject claims.",
                "permissions": [
                    "view_approved",
                    "search_rag",
                    "explore_basin",
                    "review_candidates",
                    "audit_provenance",
                    "listen_audio",
                ],
            },
            {
                "role": "admin",
                "label": "Observatory Administrator",
                "description": "System configuration, dataset seeding, retention purging, and ML model retraining approval.",
                "permissions": ["*"],
            },
        ]
    }


@router.get("/session")
def get_session(principal: Principal = Depends(current_principal)):
    return {
        "authenticated": True,
        "username": principal.name,
        "role": principal.role,
    }


@router.post("/login")
def login(payload: LoginRequest, settings: Settings = Depends(get_settings)):
    token = payload.token
    if payload.role and not token:
        role_map = {
            "viewer": settings.viewer_token,
            "engineer": settings.engineer_token,
            "reviewer": settings.reviewer_token,
            "admin": settings.admin_token,
        }
        token = role_map.get(payload.role)
        if not token:
            raise HTTPException(status_code=400, detail=f"Unknown role: {payload.role}")

    if not token:
        raise HTTPException(status_code=400, detail="Token or role is required")

    principal = principal_for_token(token, settings=settings)
    if not principal:
        raise HTTPException(status_code=401, detail="Invalid credentials or token")

    return {
        "authenticated": True,
        "token": token,
        "username": principal.name,
        "role": principal.role,
    }
