"""Leased document ingestion worker."""

import logging
import signal
import time

from nwis.config import get_settings
from nwis.ingestion.jobs import tick
from nwis.semantic import index_approved
from nwis.voice_retention import purge_expired_audio

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_running = True


def stop(_signal, _frame) -> None:
    global _running
    _running = False


def main() -> None:
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    logging.info("Document ingestion worker started")
    next_semantic_scan = 0.0
    next_voice_purge = 0.0
    while _running:
        try:
            worked = tick()
            if time.monotonic() >= next_voice_purge:
                purge_expired_audio()
                next_voice_purge = time.monotonic() + 3600
            if get_settings().semantic_enabled and time.monotonic() >= next_semantic_scan:
                try:
                    index_approved()
                except Exception:
                    logging.exception("Local semantic indexing unavailable; full-text search remains usable")
                next_semantic_scan = time.monotonic() + 30
            if worked:
                continue
        except Exception:
            logging.exception("Worker database heartbeat failed")
        for _ in range(max(1, int(get_settings().worker_poll_s))):
            if not _running:
                break
            time.sleep(1)


if __name__ == "__main__":
    main()
