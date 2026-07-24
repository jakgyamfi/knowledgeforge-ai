"""Private operational and outbound-audit logging.

Logs intentionally contain operational metadata, not prompts, transcripts,
API keys, or model responses. Rotated files are gzip-compressed automatically.
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import shutil
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


def _gzip_rotator(source: str, destination: str) -> None:
    """Compress a completed log segment and remove the uncompressed copy."""
    with open(source, "rb") as incoming, gzip.open(destination, "wb") as outgoing:
        shutil.copyfileobj(incoming, outgoing)
    os.remove(source)


def _rotating_handler(path: Path, max_bytes: int, backups: int) -> RotatingFileHandler:
    handler = RotatingFileHandler(path, maxBytes=max_bytes, backupCount=backups, encoding="utf-8")
    handler.namer = lambda name: f"{name}.gz"
    handler.rotator = _gzip_rotator
    return handler


def configure_private_logging(
    log_dir: Path,
    *,
    verbose: bool = False,
    max_mb: int = 10,
    backups: int = 10,
) -> None:
    """Configure console, application, and metadata-only egress audit logs."""
    log_dir.mkdir(parents=True, exist_ok=True)
    max_bytes = max(1, max_mb) * 1024 * 1024
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    application = _rotating_handler(log_dir / "knowledgeforge.log", max_bytes, max(1, backups))
    application.setFormatter(formatter)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        handlers=[console, application],
        force=True,
    )

    audit = logging.getLogger("knowledgeforge.egress")
    audit.propagate = False
    audit.setLevel(logging.INFO)
    audit.handlers.clear()
    audit_handler = _rotating_handler(log_dir / "egress-audit.jsonl", max_bytes, max(1, backups))
    audit_handler.setFormatter(logging.Formatter("%(message)s"))
    audit.addHandler(audit_handler)


def audit_egress(event: str, **metadata: Any) -> None:
    """Write one redacted JSON audit event.

    Callers may pass provider/model/host/status/elapsed/byte counts. They must
    never pass source text, prompts, responses, authorization headers, or keys.
    """
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **{key: value for key, value in metadata.items() if value is not None},
    }
    logging.getLogger("knowledgeforge.egress").info(
        json.dumps(record, ensure_ascii=True, separators=(",", ":"), default=str)
    )
