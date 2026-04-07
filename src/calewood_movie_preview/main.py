from __future__ import annotations

import argparse
import logging

from .config import Settings
from .logging import configure_logging
from .workflow import run


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--just-do-it", action="store_true")
    args = parser.parse_args()

    settings = Settings()
    configure_logging(settings.log_level)
    log = logging.getLogger("calewood_movie_preview.main")
    try:
        return run(settings, force_live=args.just_do_it)
    except KeyboardInterrupt:
        log.warning(
            "Keyboard interrupt received, stopping execution",
            extra={"event": "shutdown_requested", "signal": "keyboard_interrupt"},
        )
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
