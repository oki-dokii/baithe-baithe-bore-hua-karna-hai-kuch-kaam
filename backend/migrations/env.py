from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from nwis.config import get_settings

config = context.config
if config.config_file_name and config.file_config.has_section("loggers"):
    fileConfig(config.config_file_name)


def run_migrations_online() -> None:
    engine = create_engine(get_settings().database_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations_online()
