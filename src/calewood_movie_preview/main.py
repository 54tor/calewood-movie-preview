from __future__ import annotations

import argparse

from .config import Settings
from .logging import configure_logging
from .workflow import run


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--just-do-it", action="store_true")
    args = parser.parse_args()

    settings = Settings()
    configure_logging(settings.log_level)
    return run(settings, force_live=args.just_do_it)


if __name__ == "__main__":
    raise SystemExit(main())
