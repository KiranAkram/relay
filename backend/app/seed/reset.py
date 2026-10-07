"""Demo reset: wipe every handover and everything it produced, then re-seed.

    uv run python -m app.seed.reset --yes

Removes handovers, cards, tasks, flags, document references, the audit log
and the stored recordings, then upserts the seed census. Users and patients
stay (patients are refreshed by the seed).

Local development and demos only. The audit log is append-only by design and
patient data is never hard-deleted in the product; this command exists so a
demo can start clean, and a deployed system must not ship it.
"""

import argparse
import logging
import shutil
import sys
from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session

from app.core.config import settings
from app.core.db import engine
from app.seed.patients import seed_patients

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Children first; `handover` cascades to the others but the order keeps the
# intent readable. `audit_log` only allows TRUNCATE (append-only trigger).
WIPED_TABLES = (
    "flag",
    "task",
    "document_reference",
    "handover_patient",
    "handover",
    "audit_log",
)


def reset(session: Session) -> None:
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {', '.join(WIPED_TABLES)}"))
    logger.info("Wiped: %s", ", ".join(WIPED_TABLES))

    recordings = Path(settings.STORAGE_LOCAL_DIR) / "handovers"
    if recordings.is_dir():
        shutil.rmtree(recordings)
        logger.info("Removed stored recordings under %s", recordings)

    seed_patients(session)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--yes",
        action="store_true",
        help="confirm: this deletes every handover, task, flag and the audit log",
    )
    args = parser.parse_args(argv)
    if not args.yes:
        parser.print_help()
        return 2
    if settings.STORAGE_PROVIDER != "local":
        logger.error("Refusing to reset: storage is not local, this is not a dev setup")
        return 1
    with Session(engine) as session:
        reset(session)
    logger.info("Reset complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
