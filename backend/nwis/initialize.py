"""Apply migrations and synchronize local account identities from environment secrets."""

from alembic import command
from alembic.config import Config

from nwis.bootstrap import bootstrap_users


def main() -> None:
    command.upgrade(Config("alembic.ini"), "head")
    bootstrap_users()


if __name__ == "__main__":
    main()
