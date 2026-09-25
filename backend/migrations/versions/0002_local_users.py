"""Store local account identities and hashed bearer credentials.

Revision ID: 0002_local_users
Revises: 0001_foundation
"""

from alembic import op

revision = "0002_local_users"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app_user (
            id uuid PRIMARY KEY,
            username text NOT NULL UNIQUE,
            role text NOT NULL CHECK (role IN ('viewer','engineer','reviewer','admin')),
            token_hash text NOT NULL UNIQUE CHECK (token_hash ~ '^[0-9a-f]{64}$'),
            active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE app_user")
