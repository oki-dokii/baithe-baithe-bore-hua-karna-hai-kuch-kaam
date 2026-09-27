from pathlib import Path
from types import SimpleNamespace

import pytest

from nwis import public_benchmark_ingest as staging


def settings(**changes):
    values = {
        "environment": "local",
        "extraction_provider": "local_rules",
        "database_url": "postgresql+psycopg://nwis:secret@127.0.0.1:5432/nwis_public_benchmark",
        "storage_root": Path(__file__).resolve().parents[1] / "storage/public-benchmark",
        "document_max_pages": 200,
    }
    values.update(changes)
    return SimpleNamespace(**values)


def test_staging_guard_accepts_only_dedicated_local_database_and_storage(monkeypatch):
    monkeypatch.setattr(staging, "get_settings", lambda: settings())
    staging.guard()


@pytest.mark.parametrize(
    "change",
    [
        {"environment": "production"},
        {"extraction_provider": "openai_compatible"},
        {"database_url": "postgresql+psycopg://nwis:secret@127.0.0.1:5432/nwis"},
        {"database_url": "postgresql+psycopg://nwis:secret@example.com:5432/nwis_public_benchmark"},
        {"storage_root": Path("/tmp/other")},
        {"document_max_pages": 50},
    ],
)
def test_staging_guard_rejects_unsafe_configuration(monkeypatch, change):
    monkeypatch.setattr(staging, "get_settings", lambda: settings(**change))
    with pytest.raises(ValueError):
        staging.guard()
