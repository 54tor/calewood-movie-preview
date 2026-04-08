from __future__ import annotations

import argparse
import logging

from .config import Settings
from .logging import configure_logging
from .tasks import list_fiche
from .workflow import run


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--just-do-it", action="store_true")
    parser.add_argument("--single-id", type=int)
    parser.add_argument("--list-fiche", action="store_true")
    args = parser.parse_args()

    settings = Settings()
    if args.single_id is not None:
        settings = settings.model_copy(update={"calewood_api_single_id": args.single_id})
    configure_logging(settings.log_level, settings.log_format)
    if args.list_fiche:
        return list_fiche(settings)
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
