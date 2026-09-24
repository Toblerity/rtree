from __future__ import annotations

__all__ = ["RTreeError", "InvalidHandleException"]


class RTreeError(Exception):
    "RTree exception, indicates a RTree-related error."

    pass


class InvalidHandleException(Exception):
    """Handle has been destroyed and can no longer be used"""
