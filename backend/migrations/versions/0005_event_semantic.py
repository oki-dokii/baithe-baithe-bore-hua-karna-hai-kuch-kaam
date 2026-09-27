"""Index approved event claims without embedding unreviewed report pages.

Revision ID: 0005_event_semantic
Revises: 0004_operations
"""

from alembic import op

revision = "0005_event_semantic"
down_revision = "0004_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE event_embedding (
            event_id uuid PRIMARY KEY REFERENCES drilling_event(id) ON DELETE CASCADE,
            model_id text NOT NULL,
            content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
            embedding vector(384) NOT NULL,
            indexed_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_event_embedding_cosine ON event_embedding
            USING hnsw (embedding vector_cosine_ops);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE event_embedding")
