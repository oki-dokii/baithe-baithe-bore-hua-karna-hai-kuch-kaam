import logging
import time

from nwis.operations import replay_tick


def main():
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            if replay_tick():
                continue
        except Exception:
            logging.exception("Synthetic replay tick failed; transaction rolled back")
        time.sleep(0.5)


if __name__ == "__main__":
    main()
