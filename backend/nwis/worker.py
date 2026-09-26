"""Leased document ingestion worker."""

import logging
import signal
import time

from nwis.config import get_settings
from nwis.ingestion.jobs import tick

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_running = True


def stop(_signal, _frame) -> None:
    global _running
    _running = False


def main() -> None:
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    logging.info("Document ingestion worker started")
    while _running:
        try:
            if tick():
                continue
        except Exception:
            logging.exception("Worker database heartbeat failed")
        for _ in range(max(1, int(get_settings().worker_poll_s))):
            if not _running:
                break
            time.sleep(1)


if __name__ == "__main__":
    main()
