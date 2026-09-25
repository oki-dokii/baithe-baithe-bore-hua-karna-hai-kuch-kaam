from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import Connection, connect
from psycopg.rows import dict_row

from nwis.config import get_settings


@contextmanager
def connection() -> Iterator[Connection]:
    dsn = get_settings().database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    with connect(dsn, row_factory=dict_row, connect_timeout=3) as conn:
        yield conn
