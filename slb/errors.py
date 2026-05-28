"""Hirarki error untuk Smart Layout Builder.

UI menangkap SLBError, menampilkan `str(e)` sebagai headline + `hint` sebagai
detail. Exception tak terduga ditangkap di batas dock, di-log, lalu ditampilkan
generik. Lihat coding-standards.md §8.
"""

from __future__ import annotations


class SLBError(Exception):
    """Base untuk semua error user-facing SLB."""

    def __init__(self, message: str, *, hint: str = "") -> None:
        super().__init__(message)
        self.hint = hint


class ValidationError(SLBError):
    """Input tidak valid. User bisa memperbaiki."""


class ExportError(SLBError):
    """Sebuah export gagal."""


class ExportCancelled(ExportError):
    """User membatalkan export. Bukan kegagalan sebenarnya."""


class PresetError(SLBError):
    """File preset hilang, tidak valid, atau gagal disimpan."""
