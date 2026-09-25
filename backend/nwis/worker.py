"""Phase 1 worker process: validates DB connectivity and waits for future ingestion jobs."""

import logging
import signal
import time

from nwis.db import connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_running = True


def stop(_signal, _frame) -> None:
    global _running
    _running = False


def main() -> None:
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    logging.info("Worker started; ingestion handlers are scheduled for Phase 2")
    while _running:
        try:
            with connection() as conn:
                conn.execute("SELECT 1")
        except Exception:
            logging.exception("Worker database heartbeat failed")
        for _ in range(10):
            if not _running:
                break
            time.sleep(1)


if __name__ == "__main__":
    main()
