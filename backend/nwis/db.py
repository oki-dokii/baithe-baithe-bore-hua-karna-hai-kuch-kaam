from collections.abc import Iterator
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from nwis.config import get_settings

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    """Return the shared connection pool, creating it on first call."""
    global _pool
    if _pool is None:
        dsn = get_settings().database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        _pool = ConnectionPool(
            dsn,
            kwargs={"row_factory": dict_row, "connect_timeout": 3},
            min_size=2,
            max_size=10,
            open=True,
        )
    return _pool


def close_pool() -> None:
    """Gracefully close the pool. Call from the app lifespan shutdown."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def connection() -> Iterator:  # yields psycopg.Connection with dict_row
    with get_pool().connection() as conn:
        yield conn
