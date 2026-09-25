import hashlib
from uuid import UUID, uuid5

from nwis.config import get_settings
from nwis.db import connection

_NAMESPACE = UUID("f4e01f2c-85f4-47fb-a182-34c01d059ae8")


def bootstrap_users() -> None:
    settings = get_settings()
    roles = {
        "viewer": settings.viewer_token,
        "engineer": settings.engineer_token,
        "reviewer": settings.reviewer_token,
        "admin": settings.admin_token,
    }
    with connection() as conn:
        for role, token in roles.items():
            username = f"local-{role}"
            conn.execute(
                """INSERT INTO app_user(id, username, role, token_hash)
                   VALUES (%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET
                     role=excluded.role, token_hash=excluded.token_hash, active=true""",
                (uuid5(_NAMESPACE, username), username, role, hashlib.sha256(token.encode()).hexdigest()),
            )


if __name__ == "__main__":
    bootstrap_users()
