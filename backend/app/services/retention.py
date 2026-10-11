"""Purge recordings older than AUDIO_RETENTION_DAYS.

There is no scheduler (decided): `purge_expired` runs at the end of every
upload, in its own transaction, so a purge problem can never fail the upload
that triggered it. Transcripts, cards, tasks and flags are untouched; only the
audio object goes. Every document reference sharing the object's key (the
handover-level row and the per-patient rows written at confirm) is stamped
`purged_at`, and one audit row per handover records what happened.

Production answer: an S3 lifecycle rule with the same number of days, and this
function then only stamps the rows.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, col, select

from app import audit
from app.core.config import Settings
from app.models import DocumentReference, DocumentType
from app.services.storage import Storage, StorageError

logger = logging.getLogger(__name__)


def purge_expired(
    session: Session,
    storage: Storage,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> int:
    """Purge recordings stored more than AUDIO_RETENTION_DAYS ago.

    Returns the number of objects purged. Commits on success; on an unexpected
    error rolls back and logs, so the caller (the upload route) is unaffected.
    """
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=settings.AUDIO_RETENTION_DAYS)
    try:
        expired = session.exec(
            select(DocumentReference)
            .where(
                DocumentReference.type == DocumentType.audio,
                col(DocumentReference.purged_at).is_(None),
                col(DocumentReference.created_at) < cutoff,
            )
            .order_by(col(DocumentReference.created_at))
        ).all()
        by_key: dict[str, list[DocumentReference]] = {}
        for doc in expired:
            by_key.setdefault(doc.storage_key, []).append(doc)

        for key, docs in by_key.items():
            try:
                removed = storage.delete(key)
            except StorageError:
                logger.exception("purge: cannot delete %s", key)
                continue
            for doc in docs:
                doc.purged_at = now
                session.add(doc)
            audit.record(
                session,
                "document.purged",
                "document_reference",
                actor_id=None,
                handover_id=docs[0].handover_id,
                entity_id=docs[0].id,
                details={
                    "storage_key": key,
                    "rows": len(docs),
                    "object_missing": not removed,
                    "retention_days": settings.AUDIO_RETENTION_DAYS,
                },
            )
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("purge: failed, upload unaffected")
        return 0
    if by_key:
        logger.info("purge: removed %d recording(s)", len(by_key))
    return len(by_key)
