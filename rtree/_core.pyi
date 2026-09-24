"""
Compiled bindings to the libspatialindex C API.
"""

from __future__ import annotations

import collections.abc
import typing

import numpy

__all__: list[str] = [
    "ErrorRef",
    "HAS_ARRAY_API",
    "HAS_CONTAINS",
    "IndexHandle",
    "IndexItem",
    "PropertyHandle",
    "SIDX_VERSION_COMPILED",
    "new_buffer",
    "sidx_version",
]

class ErrorRef:
    """
    Mutable error code passed to CustomStorage callbacks.

    Compatible with the old ctypes pointer: both ``err.value = X`` and
    ``err.contents.value = X`` set the code.
    """
    @property
    def contents(self) -> ErrorRef: ...
    @property
    def value(self) -> int: ...
    @value.setter
    def value(self, arg0: typing.SupportsInt | typing.SupportsIndex) -> None: ...

class IndexHandle:
    """
    Owned libspatialindex index.
    """
    @staticmethod
    def from_arrays(
        properties: PropertyHandle,
        ids: numpy.ndarray[typing.Any, numpy.dtype[typing.Any]],
        mins: numpy.ndarray[typing.Any, numpy.dtype[typing.Any]],
        maxs: numpy.ndarray[typing.Any, numpy.dtype[typing.Any]],
    ) -> IndexHandle: ...
    @staticmethod
    def from_stream(
        properties: PropertyHandle,
        next_item: collections.abc.Callable[
            [], tuple[int, list[float], list[float], bytes | None] | None
        ],
    ) -> IndexHandle:
        """
        Bulk-load from ``next_item()`` which returns ``(id, mins, maxs, data)``
        tuples and ``None`` when exhausted.
        """
    def __bool__(self) -> bool: ...
    def __init__(self, properties: PropertyHandle) -> None: ...
    def bounds(self) -> tuple[list[float], list[float]] | None:
        """
        (mins, maxs) of the whole index, or None.
        """
    def clear_buffer(self) -> None: ...
    def contains_id(
        self,
        mins: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        maxs: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
    ) -> list[int]: ...
    def contains_obj(
        self,
        mins: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        maxs: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
    ) -> list[IndexItem]: ...
    def delete(
        self,
        id: typing.SupportsInt | typing.SupportsIndex,
        mins: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        maxs: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
    ) -> None: ...
    def destroy(self) -> None: ...
    def flush(self) -> None: ...
    def insert(
        self,
        id: typing.SupportsInt | typing.SupportsIndex,
        mins: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        maxs: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        data: bytes | None = None,
    ) -> None: ...
    def intersects_count(
        self,
        mins: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        maxs: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
    ) -> int: ...
    def intersects_id(
        self,
        mins: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        maxs: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
    ) -> list[int]: ...
    def intersects_id_v(
        self,
        mins: numpy.ndarray[typing.Any, numpy.dtype[typing.Any]],
        maxs: numpy.ndarray[typing.Any, numpy.dtype[typing.Any]],
        ids: numpy.ndarray[typing.Any, numpy.dtype[typing.Any]],
        counts: numpy.ndarray[typing.Any, numpy.dtype[typing.Any]],
    ) -> int: ...
    def intersects_obj(
        self,
        mins: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        maxs: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
    ) -> list[IndexItem]: ...
    def is_valid(self) -> bool: ...
    def leaves(self) -> list[tuple[int, list[int], list[float]]]:
        """
        List of (leaf id, child ids, [mins..., maxs...]) tuples.
        """
    def nearest_id(
        self,
        mins: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        maxs: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        num_results: typing.SupportsInt | typing.SupportsIndex,
    ) -> list[int]: ...
    def nearest_id_v(
        self,
        knn: typing.SupportsInt | typing.SupportsIndex,
        mins: numpy.ndarray[typing.Any, numpy.dtype[typing.Any]],
        maxs: numpy.ndarray[typing.Any, numpy.dtype[typing.Any]],
        ids: numpy.ndarray[typing.Any, numpy.dtype[typing.Any]],
        counts: numpy.ndarray[typing.Any, numpy.dtype[typing.Any]],
        dists: numpy.ndarray | None = None,
    ) -> int: ...
    def nearest_obj(
        self,
        mins: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        maxs: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        num_results: typing.SupportsInt | typing.SupportsIndex,
    ) -> list[IndexItem]: ...
    def tp_delete(
        self,
        id: typing.SupportsInt | typing.SupportsIndex,
        mins: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        maxs: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        vmins: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        vmaxs: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        t_start: typing.SupportsFloat | typing.SupportsIndex,
        t_end: typing.SupportsFloat | typing.SupportsIndex,
    ) -> None: ...
    def tp_insert(
        self,
        id: typing.SupportsInt | typing.SupportsIndex,
        mins: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        maxs: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        vmins: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        vmaxs: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        t_start: typing.SupportsFloat | typing.SupportsIndex,
        t_end: typing.SupportsFloat | typing.SupportsIndex,
        data: bytes | None = None,
    ) -> None: ...
    def tp_intersects_count(
        self,
        mins: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        maxs: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        vmins: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        vmaxs: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        t_start: typing.SupportsFloat | typing.SupportsIndex,
        t_end: typing.SupportsFloat | typing.SupportsIndex,
    ) -> int: ...
    def tp_intersects_id(
        self,
        mins: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        maxs: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        vmins: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        vmaxs: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        t_start: typing.SupportsFloat | typing.SupportsIndex,
        t_end: typing.SupportsFloat | typing.SupportsIndex,
    ) -> list[int]: ...
    def tp_intersects_obj(
        self,
        mins: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        maxs: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        vmins: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        vmaxs: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        t_start: typing.SupportsFloat | typing.SupportsIndex,
        t_end: typing.SupportsFloat | typing.SupportsIndex,
    ) -> list[IndexItem]: ...
    def tp_nearest_id(
        self,
        mins: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        maxs: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        vmins: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        vmaxs: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        t_start: typing.SupportsFloat | typing.SupportsIndex,
        t_end: typing.SupportsFloat | typing.SupportsIndex,
        num_results: typing.SupportsInt | typing.SupportsIndex,
    ) -> list[int]: ...
    def tp_nearest_obj(
        self,
        mins: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        maxs: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        vmins: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        vmaxs: collections.abc.Sequence[typing.SupportsFloat | typing.SupportsIndex],
        t_start: typing.SupportsFloat | typing.SupportsIndex,
        t_end: typing.SupportsFloat | typing.SupportsIndex,
        num_results: typing.SupportsInt | typing.SupportsIndex,
    ) -> list[IndexItem]: ...
    @property
    def result_set_limit(self) -> int: ...
    @result_set_limit.setter
    def result_set_limit(
        self, arg1: typing.SupportsInt | typing.SupportsIndex
    ) -> None: ...
    @property
    def result_set_offset(self) -> int: ...
    @result_set_offset.setter
    def result_set_offset(
        self, arg1: typing.SupportsInt | typing.SupportsIndex
    ) -> None: ...

class IndexItem:
    """
    An entry returned by an ``*_obj`` query.
    """
    @property
    def bounds(self) -> tuple[list[float], list[float]] | None:
        """
        (mins, maxs) of the entry, or None for an empty entry.
        """
    @property
    def data(self) -> bytes | None:
        """
        The raw stored bytes, or None if nothing was stored.
        """
    @property
    def id(self) -> int: ...

class PropertyHandle:
    """
    Owned libspatialindex property set.
    """

    dat_extension: str
    filename: str
    idx_extension: str
    def __bool__(self) -> bool: ...
    def __init__(self) -> None: ...
    def destroy(self) -> None: ...
    def set_python_storage(self, storage: typing.Any) -> None:
        """
        Route RT_Custom storage callbacks to a Python CustomStorage object.
        """
    @property
    def buffering_capacity(self) -> int: ...
    @buffering_capacity.setter
    def buffering_capacity(
        self, arg1: typing.SupportsInt | typing.SupportsIndex
    ) -> None: ...
    @property
    def custom_storage_callbacks(self) -> int | None:
        """
        Raw address of a CustomStorageManagerCallbacks struct (advanced use).
        """
    @custom_storage_callbacks.setter
    def custom_storage_callbacks(
        self, arg1: typing.SupportsInt | typing.SupportsIndex
    ) -> None: ...
    @property
    def custom_storage_callbacks_size(self) -> int: ...
    @custom_storage_callbacks_size.setter
    def custom_storage_callbacks_size(
        self, arg1: typing.SupportsInt | typing.SupportsIndex
    ) -> None: ...
    @property
    def dimension(self) -> int: ...
    @dimension.setter
    def dimension(self, arg1: typing.SupportsInt | typing.SupportsIndex) -> None: ...
    @property
    def ensure_tight_mbrs(self) -> int: ...
    @ensure_tight_mbrs.setter
    def ensure_tight_mbrs(
        self, arg1: typing.SupportsInt | typing.SupportsIndex
    ) -> None: ...
    @property
    def fill_factor(self) -> float: ...
    @fill_factor.setter
    def fill_factor(
        self, arg1: typing.SupportsFloat | typing.SupportsIndex
    ) -> None: ...
    @property
    def index_capacity(self) -> int: ...
    @index_capacity.setter
    def index_capacity(
        self, arg1: typing.SupportsInt | typing.SupportsIndex
    ) -> None: ...
    @property
    def index_id(self) -> int: ...
    @index_id.setter
    def index_id(self, arg1: typing.SupportsInt | typing.SupportsIndex) -> None: ...
    @property
    def index_pool_capacity(self) -> int: ...
    @index_pool_capacity.setter
    def index_pool_capacity(
        self, arg1: typing.SupportsInt | typing.SupportsIndex
    ) -> None: ...
    @property
    def index_storage(self) -> int: ...
    @index_storage.setter
    def index_storage(
        self, arg1: typing.SupportsInt | typing.SupportsIndex
    ) -> None: ...
    @property
    def index_type(self) -> int: ...
    @index_type.setter
    def index_type(self, arg1: typing.SupportsInt | typing.SupportsIndex) -> None: ...
    @property
    def index_variant(self) -> int: ...
    @index_variant.setter
    def index_variant(
        self, arg1: typing.SupportsInt | typing.SupportsIndex
    ) -> None: ...
    @property
    def leaf_capacity(self) -> int: ...
    @leaf_capacity.setter
    def leaf_capacity(
        self, arg1: typing.SupportsInt | typing.SupportsIndex
    ) -> None: ...
    @property
    def leaf_pool_capacity(self) -> int: ...
    @leaf_pool_capacity.setter
    def leaf_pool_capacity(
        self, arg1: typing.SupportsInt | typing.SupportsIndex
    ) -> None: ...
    @property
    def near_minimum_overlap_factor(self) -> int: ...
    @near_minimum_overlap_factor.setter
    def near_minimum_overlap_factor(
        self, arg1: typing.SupportsInt | typing.SupportsIndex
    ) -> None: ...
    @property
    def overwrite(self) -> int: ...
    @overwrite.setter
    def overwrite(self, arg1: typing.SupportsInt | typing.SupportsIndex) -> None: ...
    @property
    def pagesize(self) -> int: ...
    @pagesize.setter
    def pagesize(self, arg1: typing.SupportsInt | typing.SupportsIndex) -> None: ...
    @property
    def point_pool_capacity(self) -> int: ...
    @point_pool_capacity.setter
    def point_pool_capacity(
        self, arg1: typing.SupportsInt | typing.SupportsIndex
    ) -> None: ...
    @property
    def region_pool_capacity(self) -> int: ...
    @region_pool_capacity.setter
    def region_pool_capacity(
        self, arg1: typing.SupportsInt | typing.SupportsIndex
    ) -> None: ...
    @property
    def reinsert_factor(self) -> float: ...
    @reinsert_factor.setter
    def reinsert_factor(
        self, arg1: typing.SupportsFloat | typing.SupportsIndex
    ) -> None: ...
    @property
    def split_distribution_factor(self) -> float: ...
    @split_distribution_factor.setter
    def split_distribution_factor(
        self, arg1: typing.SupportsFloat | typing.SupportsIndex
    ) -> None: ...
    @property
    def tpr_horizon(self) -> float: ...
    @tpr_horizon.setter
    def tpr_horizon(
        self, arg1: typing.SupportsFloat | typing.SupportsIndex
    ) -> None: ...
    @property
    def write_through(self) -> int: ...
    @write_through.setter
    def write_through(
        self, arg1: typing.SupportsInt | typing.SupportsIndex
    ) -> None: ...

def new_buffer(size: typing.SupportsInt | typing.SupportsIndex) -> int:
    """
    Allocate ``size`` bytes with libspatialindex's allocator and return the
    address.  For CustomStorageBase.loadByteArray implementations; the
    library takes ownership of the buffer.
    """

def sidx_version() -> str:
    """
    Version string of the libspatialindex C library that is linked at runtime.
    """

HAS_ARRAY_API: bool
HAS_CONTAINS: bool
SIDX_VERSION_COMPILED: tuple[int, int, int]
