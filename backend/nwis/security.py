import hashlib
import hmac
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from nwis.db import connection


@dataclass(frozen=True)
class Principal:
    name: str
    role: str


_bearer = HTTPBearer(auto_error=False)


def current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    token_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    with connection() as conn:
        row = conn.execute(
            "SELECT username, role, token_hash FROM app_user WHERE token_hash=%s AND active=true",
            (token_hash,),
        ).fetchone()
    if row and hmac.compare_digest(row["token_hash"], token_hash):
        return Principal(name=row["username"], role=row["role"])
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def require_role(*allowed: str):
    def dependency(principal: Principal = Depends(current_principal)) -> Principal:
        if principal.role != "admin" and principal.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return principal

    return dependency
