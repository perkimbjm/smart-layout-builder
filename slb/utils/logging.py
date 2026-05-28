"""Setup logging terpusat.

`configure_logging()` dipanggil sekali dari plugin.initGui(). Idempoten:
aman dipanggil berkali-kali (mis. saat plugin di-reload). Logging tidak boleh
membuat plugin crash. Lihat coding-standards.md §9.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from ..io.safe_paths import ensure_dir, user_dir

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def configure_logging() -> logging.Logger:
    """Konfigurasi logger 'slb' dengan RotatingFileHandler (1 MB x 3)."""
    log = logging.getLogger("slb")
    if log.handlers:  # sudah dikonfigurasi (mis. setelah reload) -> idempoten
        return log

    log.setLevel(logging.INFO)
    log.propagate = False
    try:
        log_dir = ensure_dir(user_dir() / "logs")
        handler = RotatingFileHandler(
            log_dir / "slb.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(_FORMAT))
        log.addHandler(handler)
    except Exception:  # noqa: BLE001 - logging tak boleh menggagalkan plugin
        log.addHandler(logging.NullHandler())
    return log
