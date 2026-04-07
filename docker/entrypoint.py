import json
import os
import platform
import sys


def main() -> int:
    payload = {
        "status": "stub",
        "message": "Dummy container image only. Workflow not implemented yet.",
        "platform": platform.platform(),
        "machine": platform.machine(),
        "dry_run": os.getenv("DRY_RUN", "false"),
    }
    json.dump(payload, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
