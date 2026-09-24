"""Low-level access to libspatialindex.

Historically this module held hand-written :mod:`ctypes` prototypes for every
function in the libspatialindex C API (``core.rt``).  Those are now provided by
the compiled :mod:`rtree._core` extension, which is type-checked against the
real C headers at build time and ships a ``.pyi`` stub for static typing.
"""

from __future__ import annotations

from ._core import (  # noqa: F401
    HAS_ARRAY_API,
    HAS_CONTAINS,
    SIDX_VERSION_COMPILED,
    ErrorRef,
    IndexHandle,
    IndexItem,
    PropertyHandle,
    new_buffer,
    sidx_version,
)

__all__ = [
    "HAS_ARRAY_API",
    "HAS_CONTAINS",
    "SIDX_VERSION_COMPILED",
    "ErrorRef",
    "IndexHandle",
    "IndexItem",
    "PropertyHandle",
    "new_buffer",
    "sidx_version",
]
