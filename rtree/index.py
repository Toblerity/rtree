from __future__ import annotations

import ctypes
import json
import os
import os.path
import pprint
import sys
import warnings
from collections.abc import Callable, Iterable, Iterator, Sequence
from typing import TYPE_CHECKING, Any, Literal, TypeVar, overload

import numpy as np

from . import _core
from .exceptions import InvalidHandleException, RTreeError

if TYPE_CHECKING:
    from typing import TypeAlias

    import numpy.typing as npt

    #: Result of an id query: a 1-D ``int64`` array of entry ids.
    IdArray: TypeAlias = npt.NDArray[np.int64]

#: Coordinates may be any float sequence, including a NumPy array.
Coordinates = Sequence[float]

_T = TypeVar("_T")

INDEX_JSON_SERIALIZATION_LIMIT_SIZE = 1024

RT_Memory = 0
RT_Disk = 1
RT_Custom = 2

RT_Linear = 0
RT_Quadratic = 1
RT_Star = 2

RT_RTree = 0
RT_MVRTree = 1
RT_TPRTree = 2

__c_api_version__: bytes = _core.sidx_version().encode("utf-8")

major_version, minor_version, patch_version = (
    int(t) for t in __c_api_version__.decode("utf-8").split(".")
)

if (major_version, minor_version, patch_version) < (1, 8, 5):
    raise Exception("Rtree requires libspatialindex 1.8.5 or greater")

__all__ = ["Rtree", "Index", "Property"]


def _format_bounds(
    bounds: tuple[list[float], list[float]] | None, interleaved: bool
) -> list[float] | None:
    if bounds is None:
        return None
    mins, maxs = bounds
    results = mins + maxs
    if interleaved:  # they want bbox order.
        return results
    return Index.deinterleave(results)


class Index:
    """An R-Tree, MVR-Tree, or TPR-Tree indexing object"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Creates a new index

        :param filename:
            The first argument in the constructor is assumed to be a filename
            determining that a file-based storage for the index should be used.
            If the first argument is not of type basestring, it is then assumed
            to be an instance of ICustomStorage or derived class.
            If the first argument is neither of type basestring nor an instance
            of ICustomStorage, it is then assumed to be an input index item
            stream.

        :param stream:
            If the first argument in the constructor is not of type basestring,
            it is assumed to be an iterable stream of data that will raise a
            StopIteration.  It must be in the form defined by the
            :attr:`interleaved` attribute of the index. The following example
            would assume :attr:`interleaved` is False::

                (id,
                 (minx, maxx, miny, maxy, minz, maxz, ..., ..., mink, maxk),
                 object)

            The object can be None, but you must put a place holder of
            ``None`` there.

            For a TPR-Tree, this would be in the form::

                (id,
                 ((minx, maxx, miny, maxy, ..., ..., mink, maxk),
                  (minvx, maxvx, minvy, maxvy, ..., ..., minvk, maxvk),
                  time),
                 object)

        :param storage:
            If the first argument in the constructor is an instance of
            ICustomStorage then the given custom storage is used.

        :param interleaved: True or False, defaults to True.
            This parameter determines the coordinate order for all methods that
            take in coordinates.

        :param properties: An :class:`index.Property` object.
            This object sets both the creation and instantiation properties
            for the object and they are passed down into libspatialindex.
            A few properties are curried from instantiation parameters
            for you like ``pagesize`` and ``overwrite``
            to ensure compatibility with previous versions of the library.  All
            other properties must be set on the object.

        .. warning::
            The coordinate ordering for all functions are sensitive the
            index's :attr:`interleaved` data member.  If :attr:`interleaved`
            is False, the coordinates must be in the form
            [xmin, xmax, ymin, ymax, ..., ..., kmin, kmax]. If
            :attr:`interleaved` is True, the coordinates must be in the form
            [xmin, ymin, ..., kmin, xmax, ymax, ..., kmax]. This also applies
            to velocities when using a TPR-Tree.

        A basic example
        ::

            >>> from rtree import index
            >>> p = index.Property()

            >>> idx = index.Index(properties=p)
            >>> idx  # doctest: +NORMALIZE_WHITESPACE
            rtree.index.Index(bounds=[1.7976931348623157e+308,
                                    1.7976931348623157e+308,
                                    -1.7976931348623157e+308,
                                    -1.7976931348623157e+308],
                                    size=0)

        Insert an item into the index::

            >>> idx.insert(4321,
            ...            (34.3776829412, 26.7375853734, 49.3776829412,
            ...             41.7375853734),
            ...            obj=42)

        Query::

            >>> hits = idx.intersection((0, 0, 60, 60), objects=True)
            >>> for i in hits:
            ...     if i.id == 4321:
            ...         i.object
            ...         i.bbox
            ... # doctest: +ELLIPSIS
            42
            [34.37768294..., 26.73758537..., 49.37768294..., 41.73758537...]


        Using custom serializers::

            >>> class JSONIndex(index.Index):
            ...     def dumps(self, obj):
            ...         # This import is nested so that the doctest doesn't
            ...         # require simplejson.
            ...         import simplejson
            ...         return simplejson.dumps(obj).encode('ascii')
            ...
            ...     def loads(self, string):
            ...         import simplejson
            ...         return simplejson.loads(string.decode('ascii'))

            >>> stored_obj = {"nums": [23, 45], "letters": "abcd"}
            >>> json_idx = JSONIndex()
            >>> try:
            ...     json_idx.insert(1, (0, 1, 0, 1), stored_obj)
            ...     list(json_idx.nearest((0, 0), 1,
            ...                           objects="raw")) == [stored_obj]
            ... except ImportError:
            ...     True
            True

        """
        self.properties: Property = kwargs.get("properties", Property())
        self.handle: _core.IndexHandle | None
        self._exception: BaseException | None = None

        # interleaved True gives 'bbox' order.
        self.interleaved = bool(kwargs.get("interleaved", True))

        stream: Iterable[Any] | None = None
        arrays: tuple[Any, Any, Any] | None = None
        basename: str | bytes | None = None
        storage: ICustomStorage | None = None
        if args:
            if isinstance(args[0], str) or isinstance(args[0], bytes):
                # they sent in a filename
                basename = args[0]
                # they sent in a filename, stream or filename, buffers
                if len(args) > 1:
                    if isinstance(args[1], tuple):
                        arrays = args[1]
                    else:
                        stream = args[1]
            elif isinstance(args[0], ICustomStorage):
                storage = args[0]
                # they sent in a storage, stream
                if len(args) > 1:
                    stream = args[1]
            elif isinstance(args[0], tuple):
                arrays = args[0]
            else:
                stream = args[0]

        if basename:
            self.properties.storage = RT_Disk
            self.properties.filename = basename

            # check we can read the file
            f = str(basename) + "." + self.properties.idx_extension
            p = os.path.abspath(f)

            # assume if the file exists, we're not going to overwrite it
            # unless the user explicitly set the property to do so
            if os.path.exists(p):
                self.properties.overwrite = bool(kwargs.get("overwrite", False))

                # assume we're fetching the first index_id.  If the user
                # set it, we'll fetch that one.
                if not self.properties.overwrite:
                    try:
                        self.properties.index_id
                    except RTreeError:
                        self.properties.index_id = 1

            d = os.path.dirname(p)
            if not os.access(d, os.W_OK):
                message = f"Unable to open file '{f}' for index storage"
                raise OSError(message)
        elif storage:
            self.properties.storage = RT_Custom
            if storage.hasData:
                self.properties.overwrite = bool(kwargs.get("overwrite", False))
                if not self.properties.overwrite:
                    try:
                        self.properties.index_id
                    except RTreeError:
                        self.properties.index_id = 1
                else:
                    storage.clear()
            self.customstorage = storage
            storage.registerCallbacks(self.properties)
        else:
            self.properties.storage = RT_Memory

        ps = kwargs.get("pagesize", None)
        if ps:
            self.properties.pagesize = int(ps)

        if stream and self.properties.type == RT_RTree:
            self._exception = None
            self.handle = self._create_idx_from_stream(stream)
            if self._exception:
                raise self._exception
        elif arrays and self.properties.type == RT_RTree:
            self._exception = None

            if not _core.HAS_ARRAY_API:
                raise NotImplementedError(
                    "libspatialindex >= 2.1 needed for bulk insert"
                )
            self.handle = self._create_idx_from_array(*arrays)

            if self._exception:
                raise self._exception
        else:
            self.handle = _core.IndexHandle(self.properties.handle)
            if stream:  # Bulk insert not supported, so add one by one
                for item in stream:
                    self.insert(*item)
            elif arrays:
                raise NotImplementedError("Bulk insert only supported for RTrees")

    def get_size(self) -> int:
        warnings.warn(
            "index.get_size() is deprecated, use len(index) instead", DeprecationWarning
        )
        return len(self)

    def __len__(self) -> int:
        """The number of entries in the index.

        :return: number of entries
        """
        try:
            return self.count(self.bounds)
        except RTreeError:
            return 0

    def __repr__(self) -> str:
        return f"rtree.index.Index(bounds={self.bounds}, size={len(self)})"

    def __getstate__(self) -> dict[str, Any]:
        state = self.__dict__.copy()
        del state["handle"]
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)
        self.handle = _core.IndexHandle(self.properties.handle)

    @property
    def _h(self) -> _core.IndexHandle:
        """The live index handle; raises if the index was closed."""
        if self.handle is None:
            raise InvalidHandleException("Index has been closed")
        return self.handle

    # https://docs.python.org/3/library/json.html
    #
    # Be cautious when parsing JSON data from untrusted sources. A malicious JSON
    # string may cause the decoder to consume considerable CPU and memory resources.
    # Limiting the size of data to be parsed is recommended.
    def dumps(self, obj: object) -> bytes:
        if sys.getsizeof(obj) < INDEX_JSON_SERIALIZATION_LIMIT_SIZE:
            return bytes(json.dumps(obj), "utf-8")
        else:
            raise TimeoutError("Object is too large to quickly encode")

    def loads(self, string: bytes) -> Any:
        if len(string) < INDEX_JSON_SERIALIZATION_LIMIT_SIZE:
            return json.loads(str(string, "utf-8"))
        else:
            raise TimeoutError(
                "Unable to load serialized index data. The JSON string is above "
                f"the serialization limit of {INDEX_JSON_SERIALIZATION_LIMIT_SIZE}"
            )

    def close(self) -> None:
        """Force a flush of the index to storage. Renders index
        inaccessible."""
        if self.handle:
            self.handle.destroy()
            self.handle = None
        else:
            raise OSError("Unclosable index")

    def flush(self) -> None:
        """Force a flush of the index to storage."""
        if self.handle:
            self.handle.flush()

    def get_coordinate_pointers(
        self, coordinates: Coordinates
    ) -> tuple[list[float], list[float]]:
        """Split ``coordinates`` into ``(mins, maxs)`` lists of floats.

        (The name is historical; no pointers are involved any more.)
        """
        dimension = self.properties.dimension
        coords = [float(c) for c in coordinates]

        # Point
        if len(coords) == dimension:
            return coords, coords
        if len(coords) != 2 * dimension:
            raise ValueError(
                f"Expected {dimension} or {2 * dimension} coordinates, "
                f"got {len(coords)}"
            )

        # Interleaved box
        if self.interleaved:
            p = coords[:dimension]
            q = coords[dimension:]
        # Non-interleaved box
        else:
            p = coords[::2]
            q = coords[1::2]

        if not p <= q:
            raise RTreeError("Coordinates must not have minimums more than maximums")

        return p, q

    @staticmethod
    def _get_time_doubles(times: Sequence[float]) -> tuple[float, float]:
        if times[0] > times[1]:
            raise RTreeError("Start time must be less than end time")
        return float(times[0]), float(times[1])

    def _serialize(self, obj: object) -> bytes | None:
        if obj is None:
            return None
        return self.dumps(obj)

    # NOTE: the ctypes bindings had these two pairs cross-wired
    # (``result_limit`` drove Index_*ResultSetOffset and vice versa), which the
    # round-trip tests could not detect.  Named, typed bindings make the
    # mismatch obvious.
    def set_result_limit(self, value: int) -> None:
        self._h.result_set_limit = value

    def get_result_limit(self) -> int:
        return self._h.result_set_limit

    result_limit = property(get_result_limit, set_result_limit)

    def set_result_offset(self, value: int) -> None:
        self._h.result_set_offset = value

    def get_result_offset(self) -> int:
        return self._h.result_set_offset

    result_offset = property(get_result_offset, set_result_offset)

    def insert(self, id: int, coordinates: Any, obj: object = None) -> None:
        """Inserts an item into the index with the given coordinates.

        :param id: A long integer that is the identifier for this index entry.  IDs
            need not be unique to be inserted into the index, and it is up
            to the user to ensure they are unique if this is a requirement.

        :param coordinates: This may be an object that satisfies the numpy array
            protocol, providing the index's dimension * 2 coordinate
            pairs representing the `mink` and `maxk` coordinates in
            each dimension defining the bounds of the query window.
            For a TPR-Tree, this must be a 3-element sequence including
            not only the positional coordinate pairs but also the
            velocity pairs `minvk` and `maxvk` and a time value as a float.

        :param obj: a JSON-like object.  If not None, this object will be
            stored in the index with the :attr:`id`.

        The following example inserts an entry into the index with id `4321`,
        and the object it stores with that id is the number `42`.  The
        coordinate ordering in this instance is the default (interleaved=True)
        ordering::

            >>> from rtree import index
            >>> idx = index.Index()
            >>> idx.insert(4321,
            ...            (34.3776829412, 26.7375853734, 49.3776829412,
            ...             41.7375853734),
            ...            obj=42)

        This example is inserting the same object for a TPR-Tree, additionally
        including a set of velocities at time `3`::

            >>> p = index.Property(type=index.RT_TPRTree)  # doctest: +SKIP
            >>> idx = index.Index(properties=p)  # doctest: +SKIP
            >>> idx.insert(4321,
            ...            ((34.3776829412, 26.7375853734, 49.3776829412,
            ...             41.7375853734),
            ...             (0.5, 2, 1.5, 2.5),
            ...            3.0),
            ...            obj=42)  # doctest: +SKIP

        """
        if self.properties.type == RT_TPRTree:
            # https://github.com/python/mypy/issues/6799
            return self._insertTP(id, *coordinates, obj=obj)  # type: ignore[misc]

        self._h.insert(id, coordinates, self.interleaved, self._serialize(obj))

    add = insert

    def _insertTP(
        self,
        id: int,
        coordinates: Sequence[float],
        velocities: Sequence[float],
        time: float,
        obj: object = None,
    ) -> None:
        mins, maxs = self.get_coordinate_pointers(coordinates)
        vmins, vmaxs = self.get_coordinate_pointers(velocities)
        # End time isn't used
        t_start, t_end = self._get_time_doubles((time, time + 1))
        self._h.tp_insert(
            id, mins, maxs, vmins, vmaxs, t_start, t_end, self._serialize(obj)
        )

    def count(self, coordinates: Any) -> int:
        """Return number of objects that intersect the given coordinates.

        :param coordinates: This may be an object that satisfies the numpy array
            protocol, providing the index's dimension * 2 coordinate
            pairs representing the `mink` and `maxk` coordinates in
            each dimension defining the bounds of the query window.
            For a TPR-Tree, this must be a 3-element sequence including
            not only the positional coordinate pairs but also the
            velocity pairs `minvk` and `maxvk` and a time pair for the
            time range as a float.

        The following example queries the index for any objects any objects
        that were stored in the index intersect the bounds given in the
        coordinates::

            >>> from rtree import index
            >>> idx = index.Index()
            >>> idx.insert(4321,
            ...            (34.3776829412, 26.7375853734, 49.3776829412,
            ...             41.7375853734),
            ...            obj=42)

            >>> print(idx.count((0, 0, 60, 60)))
            1

        This example is similar for a TPR-Tree::

            >>> p = index.Property(type=index.RT_TPRTree)  # doctest: +SKIP
            >>> idx = index.Index(properties=p)  # doctest: +SKIP
            >>> idx.insert(4321,
            ...            ((34.3776829412, 26.7375853734, 49.3776829412,
            ...             41.7375853734),
            ...             (0.5, 2, 1.5, 2.5),
            ...             3.0),
            ...            obj=42)  # doctest: +SKIP

            >>> print(idx.count(((0, 0, 60, 60), (0, 0, 0, 0), (3, 5))))
            ... # doctest: +SKIP
            1

        """
        if self.properties.type == RT_TPRTree:
            return self._countTP(*coordinates)
        return self._h.count(coordinates, self.interleaved)

    def _countTP(
        self,
        coordinates: Coordinates,
        velocities: Coordinates,
        times: Sequence[float],
    ) -> int:
        mins, maxs = self.get_coordinate_pointers(coordinates)
        vmins, vmaxs = self.get_coordinate_pointers(velocities)
        t_start, t_end = self._get_time_doubles(times)
        return self._h.tp_intersects_count(mins, maxs, vmins, vmaxs, t_start, t_end)

    @overload
    def contains(self, coordinates: Any, objects: Literal[True]) -> Iterator[Item]: ...

    @overload
    def contains(
        self, coordinates: Any, objects: Literal[False] = False
    ) -> IdArray | None: ...

    @overload
    def contains(
        self, coordinates: Any, objects: Literal["raw"]
    ) -> Iterator[object]: ...

    def contains(
        self, coordinates: Any, objects: bool | Literal["raw"] = False
    ) -> Iterator[Item | object] | IdArray | None:
        """Return ids or objects in the index that contains within the given
        coordinates.

        :param coordinates: This may be an object that satisfies the numpy array
            protocol, providing the index's dimension * 2 coordinate
            pairs representing the `mink` and `maxk` coordinates in
            each dimension defining the bounds of the query window.

        :param objects: If True, the intersection method will return index objects that
            were serialized when they were stored with each index entry, as well
            as the id and bounds of the index entries. If 'raw', the objects
            will be returned without the :class:`rtree.index.Item` wrapper.

        The following example queries the index for any objects any objects
        that were stored in the index intersect the bounds given in the
        coordinates::

            >>> from rtree import index
            >>> idx = index.Index()
            >>> idx.insert(4321,
            ...            (34.3776829412, 26.7375853734, 49.3776829412,
            ...             41.7375853734),
            ...            obj=42)

            >>> hits = list(idx.contains((0, 0, 60, 60), objects=True))
            ... # doctest: +NORMALIZE_WHITESPACE +ELLIPSIS +SKIP
            >>> [(item.object, item.bbox) for item in hits if item.id == 4321]
            ... # doctest: +NORMALIZE_WHITESPACE +ELLIPSIS +SKIP
            [(42, [34.37768294..., 26.73758537..., 49.37768294...,
                   41.73758537...])]

        If the :class:`rtree.index.Item` wrapper is not used, it is faster to
        request the 'raw' objects::

            >>> list(idx.contains((0, 0, 60, 60), objects="raw"))
            ... # doctest: +NORMALIZE_WHITESPACE +ELLIPSIS +SKIP
            [42]

        """

        if not _core.HAS_CONTAINS:
            return None
        if objects:
            return self._contains_obj(coordinates, objects)

        return self._h.contains(coordinates, self.interleaved)

    def __and__(self, other: Index) -> Index:
        """Take the intersection of two Index objects.

        :param other: another index
        :return: a new index
        :raises AssertionError: if self and other have different interleave or dimension
        """
        assert self.interleaved == other.interleaved
        assert self.properties.dimension == other.properties.dimension

        i = 0
        new_idx = Index(interleaved=self.interleaved, properties=self.properties)

        # For each Item in self...
        for item1 in self.intersection(self.bounds, objects=True):
            if self.interleaved:
                # For each Item in other that intersects...
                for item2 in other.intersection(item1.bbox, objects=True):
                    # Compute the intersection bounding box
                    bbox = []
                    for j in range(len(item1.bbox)):
                        if j < len(item1.bbox) // 2:
                            bbox.append(max(item1.bbox[j], item2.bbox[j]))
                        else:
                            bbox.append(min(item1.bbox[j], item2.bbox[j]))

                    new_idx.insert(i, bbox, (item1.object, item2.object))
                    i += 1

            else:
                # For each Item in other that intersects...
                for item2 in other.intersection(item1.bounds, objects=True):
                    # Compute the intersection bounding box
                    bounds = []
                    for j in range(len(item1.bounds)):
                        if j % 2 == 0:
                            bounds.append(max(item1.bounds[j], item2.bounds[j]))
                        else:
                            bounds.append(min(item1.bounds[j], item2.bounds[j]))

                    new_idx.insert(i, bounds, (item1.object, item2.object))
                    i += 1

        return new_idx

    def __or__(self, other: Index) -> Index:
        """Take the union of two Index objects.

        :param other: another index
        :return: a new index
        :raises AssertionError: if self and other have different interleave or dimension
        """
        assert self.interleaved == other.interleaved
        assert self.properties.dimension == other.properties.dimension

        new_idx = Index(interleaved=self.interleaved, properties=self.properties)

        # For each index...
        for old_idx in [self, other]:
            # For each item...
            for item in old_idx.intersection(old_idx.bounds, objects=True):
                if self.interleaved:
                    new_idx.insert(item.id, item.bbox, item.object)
                else:
                    new_idx.insert(item.id, item.bounds, item.object)

        return new_idx

    @overload
    def intersection(
        self, coordinates: Any, objects: Literal[True]
    ) -> Iterator[Item]: ...

    @overload
    def intersection(
        self, coordinates: Any, objects: Literal[False] = False
    ) -> IdArray: ...

    @overload
    def intersection(
        self, coordinates: Any, objects: Literal["raw"]
    ) -> Iterator[object]: ...

    def intersection(
        self, coordinates: Any, objects: bool | Literal["raw"] = False
    ) -> Iterator[Item | object] | IdArray:
        """Return ids or objects in the index that intersect the given
        coordinates.

        :param coordinates: This may be an object that satisfies the numpy array
            protocol, providing the index's dimension * 2 coordinate
            pairs representing the `mink` and `maxk` coordinates in
            each dimension defining the bounds of the query window.
            For a TPR-Tree, this must be a 3-element sequence including
            not only the positional coordinate pairs but also the
            velocity pairs `minvk` and `maxvk` and a time pair for the
            time range as a float.

        :param objects: If True, the intersection method will return index objects that
            were serialized when they were stored with each index entry, as well
            as the id and bounds of the index entries. If 'raw', the objects
            will be returned without the :class:`rtree.index.Item` wrapper.

        The following example queries the index for any objects any objects
        that were stored in the index intersect the bounds given in the
        coordinates::

            >>> from rtree import index
            >>> idx = index.Index()
            >>> idx.insert(4321,
            ...            (34.3776829412, 26.7375853734, 49.3776829412,
            ...             41.7375853734),
            ...            obj=42)

            >>> hits = list(idx.intersection((0, 0, 60, 60), objects=True))
            >>> [(item.object, item.bbox) for item in hits if item.id == 4321]
            ... # doctest: +NORMALIZE_WHITESPACE +ELLIPSIS
            [(42, [34.37768294..., 26.73758537..., 49.37768294...,
                   41.73758537...])]

        If the :class:`rtree.index.Item` wrapper is not used, it is faster to
        request the 'raw' objects::

            >>> list(idx.intersection((0, 0, 60, 60), objects="raw"))
            [42]

        Similar for the TPR-Tree::

            >>> p = index.Property(type=index.RT_TPRTree)  # doctest: +SKIP
            >>> idx = index.Index(properties=p)  # doctest: +SKIP
            >>> idx.insert(4321,
            ...            ((34.3776829412, 26.7375853734, 49.3776829412,
            ...             41.7375853734),
            ...             (0.5, 2, 1.5, 2.5),
            ...             3.0),
            ...            obj=42)  # doctest: +SKIP

            >>> hits = list(idx.intersection(
            ...     ((0, 0, 60, 60), (0, 0, 0, 0), (3, 5)), objects=True))
            ...  # doctest: +SKIP
            >>> [(item.object, item.bbox) for item in hits if item.id == 4321]
            ... # doctest: +SKIP
            [(42, [34.37768294..., 26.73758537..., 49.37768294...,
                   41.73758537...])]

        """
        if self.properties.type == RT_TPRTree:
            # https://github.com/python/mypy/issues/6799
            return self._intersectionTP(  # type: ignore[misc]
                *coordinates, objects=objects
            )
        if objects:
            return self._intersection_obj(coordinates, objects)

        return self._h.intersection(coordinates, self.interleaved)

    def _intersectionTP(
        self,
        coordinates: Coordinates,
        velocities: Coordinates,
        times: Sequence[float],
        objects: bool | Literal["raw"] = False,
    ) -> Iterator[Item | object] | IdArray:
        mins, maxs = self.get_coordinate_pointers(coordinates)
        vmins, vmaxs = self.get_coordinate_pointers(velocities)
        t_start, t_end = self._get_time_doubles(times)
        if objects:
            items = self._h.tp_intersects_obj(mins, maxs, vmins, vmaxs, t_start, t_end)
            return self._get_objects(items, objects)
        return self._h.tp_intersects_id(mins, maxs, vmins, vmaxs, t_start, t_end)

    def _intersection_obj(
        self, coordinates: Coordinates, objects: Literal[True, "raw"]
    ) -> Iterator[Item | object]:
        items = self._h.intersection_obj(coordinates, self.interleaved)
        return self._get_objects(items, objects)

    def _contains_obj(
        self, coordinates: Coordinates, objects: Literal[True, "raw"]
    ) -> Iterator[Item | object]:
        items = self._h.contains_obj(coordinates, self.interleaved)
        return self._get_objects(items, objects)

    def _get_objects(
        self, items: list[_core.IndexItem], objects: Literal[True, "raw"]
    ) -> Iterator[Item | object]:
        # Items own their C handles and free them when garbage collected.
        if objects != "raw":
            for it in items:
                yield Item(self.loads, it)
        else:
            for it in items:
                data = it.data
                yield None if data is None else self.loads(data)

    def _nearest_obj(
        self,
        coordinates: Coordinates,
        num_results: int,
        objects: Literal[True, "raw"],
    ) -> Iterator[Item | object]:
        items = self._h.nearest_obj(coordinates, self.interleaved, num_results)
        return self._get_objects(items, objects)

    @overload
    def nearest(
        self, coordinates: Any, num_results: int, objects: Literal[True]
    ) -> Iterator[Item]: ...

    @overload
    def nearest(
        self, coordinates: Any, num_results: int, objects: Literal[False] = False
    ) -> IdArray: ...

    @overload
    def nearest(
        self, coordinates: Any, num_results: int, objects: Literal["raw"]
    ) -> Iterator[object]: ...

    def nearest(
        self,
        coordinates: Any,
        num_results: int = 1,
        objects: bool | Literal["raw"] = False,
    ) -> Iterator[Item | object] | IdArray:
        """Returns the ``k``-nearest objects to the given coordinates.

        :param coordinates: This may be an object that satisfies the numpy array
            protocol, providing the index's dimension * 2 coordinate
            pairs representing the `mink` and `maxk` coordinates in
            each dimension defining the bounds of the query window.
            For a TPR-Tree, this must be a 3-element sequence including
            not only the positional coordinate pairs but also the
            velocity pairs `minvk` and `maxvk` and a time pair for the
            time range as a float.

        :param num_results: The number of results to return nearest to the given
            coordinates. If two index entries are equidistant, *both* are returned.
            This property means that :attr:`num_results` may return more
            items than specified

        :param objects: If True, the nearest method will return index objects that
            were serialized when they were stored with each index entry, as
            well as the id and bounds of the index entries.
            If 'raw', it will return the object as entered into the database
            without the :class:`rtree.index.Item` wrapper.

        .. warning::
            This is currently not implemented for the TPR-Tree.

        Example of finding the three items nearest to this one::

            >>> from rtree import index
            >>> idx = index.Index()
            >>> idx.insert(4321, (34.37, 26.73, 49.37, 41.73), obj=42)
            >>> hits = idx.nearest((0, 0, 10, 10), 3, objects=True)
        """
        if self.properties.type == RT_TPRTree:
            # https://github.com/python/mypy/issues/6799
            return self._nearestTP(*coordinates, objects=objects)  # type: ignore[misc]

        if objects:
            return self._nearest_obj(coordinates, num_results, objects)
        # If multiple neighbors are at the same distance, all are returned, so
        # the result may be longer than ``num_results``.
        return self._h.nearest(coordinates, self.interleaved, num_results)

    def intersection_v(
        self, mins: npt.ArrayLike, maxs: npt.ArrayLike
    ) -> tuple[npt.NDArray[np.int64], npt.NDArray[np.uint64]]:
        """Bulk intersection query for obtaining the ids of entries
        which intersect with the provided bounding boxes.  The return
        value is a tuple consisting of two 1D NumPy arrays: one of
        intersecting ids and another containing the counts for each
        bounding box.

        :param mins: A NumPy array of shape `(n, d)` containing the
            minima to query.

        :param maxs: A NumPy array of shape `(n, d)` containing the
            maxima to query.
        """
        import numpy as np

        mins, maxs = self._prepare_v_arrays(mins, maxs)

        # Extract counts
        n, d = mins.shape

        ids = np.empty(2 * n, dtype=np.int64)
        counts = np.empty(n, dtype=np.uint64)
        offn, offi = 0, 0

        while True:
            nr = self._h.intersects_id_v(
                mins[offn:], maxs[offn:], ids[offi:], counts[offn:]
            )

            # If we got the expected number of results then return
            if nr == n - offn:
                return ids[: counts.sum()], counts
            # Otherwise, if our array is too small then resize
            else:
                offi += counts[offn : offn + nr].sum()
                offn += nr

                ids.resize(2 * len(ids) + counts[offn], refcheck=False)

    def nearest_v(
        self,
        mins: npt.ArrayLike,
        maxs: npt.ArrayLike,
        *,
        num_results: int = 1,
        max_dists: npt.ArrayLike | None = None,
        strict: bool = False,
        return_max_dists: bool = False,
    ) -> (
        tuple[npt.NDArray[np.int64], npt.NDArray[np.uint64]]
        | tuple[npt.NDArray[np.int64], npt.NDArray[np.uint64], npt.NDArray[np.float64]]
    ):
        """Bulk ``k``-nearest query for the given bounding boxes.  The
        return value is a tuple consisting of, by default, two 1D NumPy
        arrays: one of intersecting ids and another containing the
        counts for each bounding box.

        :param mins: A NumPy array of shape `(n, d)` containing the
            minima to query.

        :param maxs: A NumPy array of shape `(n, d)` containing the
            maxima to query.

        :param num_results: The maximum number of neighbors to return
            for each bounding box.  If there are multiple equidistant
            furthest neighbors then, by default, they are *all*
            returned.  Hence, the actual number of results can be
            greater than requested.

        :param max_dists: Optional; a NumPy array of shape `(n,)`
            containing the maximum distance to consider for each
            bounding box.

        :param strict: If True then each point will never return more
            than `num_results` even in cases of equidistant furthest
            neighbors.

        :param return_max_dists: If True, the distance of the furthest
            neighbor for each bounding box will also be returned.
        """
        import numpy as np

        mins, maxs = self._prepare_v_arrays(mins, maxs)

        # Extract counts
        n, d = mins.shape

        ids = np.empty(n * num_results, dtype=np.int64)
        counts = np.empty(n, dtype=np.uint64)
        offn, offi = 0, 0

        dists: npt.NDArray[np.float64] | None
        if max_dists is not None:
            dists = np.ascontiguousarray(np.atleast_1d(max_dists), dtype=np.float64)
            if dists.ndim != 1:
                raise ValueError("max_dists must have 1 dimension")
            if len(dists) != n:
                raise ValueError(f"max_dists must have length {n}")
        elif return_max_dists:
            dists = np.zeros(n)
        else:
            dists = None

        while True:
            nr = self._h.nearest_id_v(
                num_results if not strict else -num_results,
                mins[offn:],
                maxs[offn:],
                ids[offi:],
                counts[offn:],
                dists[offn:] if dists is not None else None,
            )

            # If we got the expected number of results then return
            if nr == n - offn:
                if return_max_dists:
                    assert dists is not None
                    return ids[: counts.sum()], counts, dists
                else:
                    return ids[: counts.sum()], counts
            # Otherwise, if our array is too small then resize
            else:
                offi += counts[offn : offn + nr].sum()
                offn += nr

                ids.resize(2 * len(ids) + counts[offn], refcheck=False)

    def _prepare_v_arrays(
        self, mins: npt.ArrayLike, maxs: npt.ArrayLike
    ) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        import numpy as np

        # Ensure inputs are 2D float64 arrays
        if mins is maxs:
            mins = maxs = np.atleast_2d(mins).astype(np.float64)
        else:
            mins = np.atleast_2d(mins).astype(np.float64)
            maxs = np.atleast_2d(maxs).astype(np.float64)

        if mins.ndim != 2 or maxs.ndim != 2:
            raise ValueError("mins/maxs must have 2 dimensions: (n, d)")
        if mins.shape != maxs.shape:
            raise ValueError("mins and maxs shapes not equal")
        if mins.strides != maxs.strides:
            raise ValueError("mins and maxs strides not equal")

        # Handle invalid strides
        if any(s % mins.itemsize for s in mins.strides):
            if mins is maxs:
                mins = maxs = mins.copy()
            else:
                mins = mins.copy()
                maxs = maxs.copy()

        return mins, maxs

    def _nearestTP(
        self,
        coordinates: Coordinates,
        velocities: Coordinates,
        times: Sequence[float],
        num_results: int = 1,
        objects: bool | Literal["raw"] = False,
    ) -> Iterator[Item | object] | IdArray:
        mins, maxs = self.get_coordinate_pointers(coordinates)
        vmins, vmaxs = self.get_coordinate_pointers(velocities)
        t_start, t_end = self._get_time_doubles(times)
        if objects:
            items = self._h.tp_nearest_obj(
                mins, maxs, vmins, vmaxs, t_start, t_end, num_results
            )
            return self._get_objects(items, objects)
        return self._h.tp_nearest_id(
            mins, maxs, vmins, vmaxs, t_start, t_end, num_results
        )

    def get_bounds(self, coordinate_interleaved: bool | None = None) -> Any:
        """Returns the bounds of the index

        :param coordinate_interleaved: If True, the coordinates are turned
            in the form [xmin, ymin, ..., kmin, xmax, ymax, ..., kmax],
            otherwise they are returned as
            [xmin, xmax, ymin, ymax, ..., ..., kmin, kmax].  If not specified,
            the :attr:`interleaved` member of the index is used, which
            defaults to True.
        """
        if coordinate_interleaved is None:
            coordinate_interleaved = self.interleaved
        return _format_bounds(self._h.bounds(), coordinate_interleaved)

    bounds = property(get_bounds)

    def delete(self, id: int, coordinates: Any) -> None:
        """Deletes an item from the index with the given ``'id'`` and
           coordinates given by the ``coordinates`` sequence. As the index can
           contain multiple items with the same ID and coordinates, deletion
           is not guaranteed to delete all items in the index with the given ID
           and coordinates.

        :param id: A long integer ID for the entry, which need not be unique. The
            index can contain multiple entries with identical IDs and
            coordinates. Uniqueness of items should be enforced at the
            application level by the user.

        :param coordinates: Dimension * 2 coordinate pairs, representing the min
            and max coordinates in each dimension of the item to be
            deleted from the index. Their ordering will depend on the
            index's :attr:`interleaved` data member.
            These are not the coordinates of a space containing the
            item, but those of the item itself. Together with the
            id parameter, they determine which item will be deleted.
            This may be an object that satisfies the numpy array protocol.
            For a TPR-Tree, this must be a 3-element sequence including
            not only the positional coordinate pairs but also the
            velocity pairs `minvk` and `maxvk` and a time pair for the
            original time the object was inserted and the current time
            as a float.

        Example::

            >>> from rtree import index
            >>> idx = index.Index()
            >>> idx.delete(4321,
            ...            (34.3776829412, 26.7375853734, 49.3776829412,
            ...             41.7375853734))

        For the TPR-Tree::

            >>> p = index.Property(type=index.RT_TPRTree)  # doctest: +SKIP
            >>> idx = index.Index(properties=p)  # doctest: +SKIP
            >>> idx.delete(4321,
            ...            ((34.3776829412, 26.7375853734, 49.3776829412,
            ...             41.7375853734),
            ...             (0.5, 2, 1.5, 2.5),
            ...             (3.0, 5.0)))  # doctest: +SKIP

        """
        if self.properties.type == RT_TPRTree:
            return self._deleteTP(id, *coordinates)
        self._h.delete(id, coordinates, self.interleaved)

    def _deleteTP(
        self,
        id: int,
        coordinates: Coordinates,
        velocities: Coordinates,
        times: Sequence[float],
    ) -> None:
        mins, maxs = self.get_coordinate_pointers(coordinates)
        vmins, vmaxs = self.get_coordinate_pointers(velocities)
        t_start, t_end = self._get_time_doubles(times)
        self._h.tp_delete(id, mins, maxs, vmins, vmaxs, t_start, t_end)

    def valid(self) -> bool:
        return self._h.is_valid()

    def clearBuffer(self) -> None:
        self._h.clear_buffer()

    @classmethod
    def deinterleave(self, interleaved: Sequence[_T]) -> list[_T]:
        """
        [xmin, ymin, xmax, ymax] => [xmin, xmax, ymin, ymax]

        >>> Index.deinterleave([0, 10, 1, 11])
        [0, 1, 10, 11]

        >>> Index.deinterleave([0, 1, 2, 10, 11, 12])
        [0, 10, 1, 11, 2, 12]

        """
        assert len(interleaved) % 2 == 0, "must be a pairwise list"
        dimension = len(interleaved) // 2
        di = []
        for i in range(dimension):
            di.extend([interleaved[i], interleaved[i + dimension]])
        return di

    @classmethod
    def interleave(self, deinterleaved: Sequence[_T]) -> list[_T]:
        """
        [xmin, xmax, ymin, ymax, zmin, zmax]
            => [xmin, ymin, zmin, xmax, ymax, zmax]

        >>> Index.interleave([0, 1, 10, 11])
        [0, 10, 1, 11]

        >>> Index.interleave([0, 10, 1, 11, 2, 12])
        [0, 1, 2, 10, 11, 12]

        >>> Index.interleave((-1, 1, 58, 62, 22, 24))
        [-1, 58, 22, 1, 62, 24]

        """
        assert len(deinterleaved) % 2 == 0, "must be a pairwise list"
        #  dimension = len(deinterleaved) / 2
        interleaved = []
        for i in range(2):
            interleaved.extend(
                [deinterleaved[i + j] for j in range(0, len(deinterleaved), 2)]
            )
        return interleaved

    def _create_idx_from_stream(self, stream: Iterable[Any]) -> _core.IndexHandle:
        """This function is used to instantiate the index given an
        iterable stream of data."""

        # Iteration, coordinate parsing and serialization all happen in C++;
        # an exception raised by the iterator propagates unchanged.
        return _core.IndexHandle.from_stream(
            self.properties.handle, stream, self.interleaved, self.dumps
        )

    def _create_idx_from_array(
        self, ibuf: npt.ArrayLike, minbuf: npt.ArrayLike, maxbuf: npt.ArrayLike
    ) -> _core.IndexHandle:
        import numpy as np

        # Prepare the arrays
        ids = np.asarray(ibuf).astype(np.int64)
        mins, maxs = self._prepare_v_arrays(minbuf, maxbuf)

        if len(ids) != len(mins):
            raise ValueError("index and point counts different")

        # Handle misaligned data
        if ids.strides[0] % ids.itemsize:
            ids = ids.copy()

        return _core.IndexHandle.from_arrays(self.properties.handle, ids, mins, maxs)

    def leaves(self) -> list[tuple[int, list[int], list[float]]]:
        return self._h.leaves()


# An alias to preserve backward compatibility
Rtree = Index


class Item:
    """A container for index entries"""

    __slots__ = ("handle", "owned", "id", "object", "bounds")

    def __init__(
        self,
        loads: Callable[[bytes], Any],
        handle: _core.IndexItem,
        owned: bool = False,
    ) -> None:
        """There should be no reason to instantiate these yourself. Items are
        created automatically when you call
        :meth:`rtree.index.Index.intersection` (or other index querying
        methods) with objects=True given the parameters of the function."""

        self.handle = handle
        self.owned = owned

        # RtreeContainer sets this to None on the items it yields.
        self.id: int = handle.id

        self.object: Any = None
        self.object = self.get_object(loads)
        self.bounds: list[float] = _format_bounds(handle.bounds, False) or []

    def __lt__(self, other: Item) -> bool:
        return self.id < other.id

    def __gt__(self, other: Item) -> bool:
        return self.id > other.id

    @property
    def bbox(self) -> list[float]:
        """Returns the bounding box of the index entry"""
        return Index.interleave(self.bounds)

    def get_object(self, loads: Callable[[bytes], Any]) -> Any:
        # short circuit this so we only do it at construction time
        if self.object is not None:
            return self.object
        data = self.handle.data
        if data is None:
            return None
        return loads(data)


# Kept as aliases so ``from rtree.index import IndexHandle`` keeps working.
IndexHandle = _core.IndexHandle
PropertyHandle = _core.PropertyHandle


class Property:
    """An index property object is a container that contains a number of
    settable index properties.  Many of these properties must be set at
    index creation times, while others can be used to adjust performance
    or behavior."""

    pkeys = (
        "buffering_capacity",
        "custom_storage_callbacks",
        "custom_storage_callbacks_size",
        "dat_extension",
        "dimension",
        "filename",
        "fill_factor",
        "idx_extension",
        "index_capacity",
        "index_id",
        "leaf_capacity",
        "near_minimum_overlap_factor",
        "overwrite",
        "pagesize",
        "point_pool_capacity",
        "region_pool_capacity",
        "reinsert_factor",
        "split_distribution_factor",
        "storage",
        "tight_mbr",
        "tpr_horizon",
        "type",
        "variant",
        "writethrough",
    )

    def __init__(
        self,
        handle: _core.PropertyHandle | None = None,
        owned: bool = True,
        **kwargs: Any,
    ) -> None:
        if handle is None:
            handle = _core.PropertyHandle()
        self.handle: _core.PropertyHandle = handle
        self.initialize_from_dict(kwargs)

    def initialize_from_dict(self, state: dict[str, Any]) -> None:
        for k, v in state.items():
            if v is not None:
                setattr(self, k, v)

        # Consistency checks
        if "near_minimum_overlap_factor" not in state:
            nmof = self.near_minimum_overlap_factor
            ilc = min(self.index_capacity, self.leaf_capacity)
            if nmof >= ilc:
                self.near_minimum_overlap_factor = ilc // 3 + 1

    def __getstate__(self) -> dict[Any, Any]:
        return self.as_dict()

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.handle = _core.PropertyHandle()
        self.initialize_from_dict(state)

    #: Keys that hold process-local pointers and are not meaningful to
    #: serialize to JSON.
    _json_exclude = ("custom_storage_callbacks", "custom_storage_callbacks_size")

    def to_json(self) -> str:
        """Serialize the properties to a JSON string.

        Custom storage callbacks are process-local pointers and are omitted.

        :raises ValueError: if the encoded JSON is larger than
            ``INDEX_JSON_SERIALIZATION_LIMIT_SIZE`` bytes.

        >>> from rtree import index
        >>> p = index.Property(dimension=3)
        >>> index.Property.from_json(p.to_json()).dimension
        3
        """
        state = {k: v for k, v in self.as_dict().items() if k not in self._json_exclude}
        data = json.dumps(state)
        size = len(data.encode("utf-8"))
        if size > INDEX_JSON_SERIALIZATION_LIMIT_SIZE:
            raise ValueError(
                f"Serialized properties are {size} bytes, above the "
                f"serialization limit of {INDEX_JSON_SERIALIZATION_LIMIT_SIZE}"
            )
        return data

    @classmethod
    def from_json(cls, data: str | bytes) -> Property:
        """Create a new :class:`Property` from a JSON string produced by
        :meth:`to_json`.

        Only known property keys are accepted; anything else raises
        :class:`ValueError`.

        :raises ValueError: if ``data`` is larger than
            ``INDEX_JSON_SERIALIZATION_LIMIT_SIZE`` bytes. The size is checked
            before parsing.
        """
        size = len(data.encode("utf-8") if isinstance(data, str) else data)
        if size > INDEX_JSON_SERIALIZATION_LIMIT_SIZE:
            raise ValueError(
                f"Serialized properties are {size} bytes, above the "
                f"serialization limit of {INDEX_JSON_SERIALIZATION_LIMIT_SIZE}"
            )
        state = json.loads(data)
        if not isinstance(state, dict):
            raise TypeError(f"Expected a JSON object, got {type(state).__name__}")
        allowed = set(cls.pkeys) - set(cls._json_exclude)
        unknown = set(state) - allowed
        if unknown:
            raise ValueError(f"Unknown property keys: {sorted(unknown)}")
        return cls(**state)

    def as_dict(self) -> dict[str, Any]:
        d = {}
        for k in self.pkeys:
            try:
                v = getattr(self, k)
            except RTreeError:
                v = None
            d[k] = v
        return d

    def __repr__(self) -> str:
        return repr(self.as_dict())

    def __str__(self) -> str:
        return pprint.pformat(self.as_dict())

    def get_index_type(self) -> int:
        try:
            return self._type
        except AttributeError:
            type = self.handle.index_type
            self._type: int = type
            return type

    def set_index_type(self, value: int) -> None:
        self._type = value
        self.handle.index_type = value

    type = property(get_index_type, set_index_type)
    """Index type. Valid index type values are
    :data:`RT_RTree`, :data:`RT_MVTree`, or :data:`RT_TPRTree`.  Only
    RT_RTree (the default) is practically supported at this time."""

    def get_variant(self) -> int:
        return self.handle.index_variant

    def set_variant(self, value: int) -> None:
        self.handle.index_variant = value

    variant = property(get_variant, set_variant)
    """Index variant.  Valid index variant values are
    :data:`RT_Linear`, :data:`RT_Quadratic`, and :data:`RT_Star`"""

    def get_dimension(self) -> int:
        try:
            return self._dimension
        except AttributeError:
            dim = self.handle.dimension
            self._dimension: int = dim
            return dim

    def set_dimension(self, value: int) -> None:
        if value <= 0:
            raise RTreeError("Negative or 0 dimensional indexes are not allowed")
        self._dimension = value
        self.handle.dimension = value

    dimension = property(get_dimension, set_dimension)
    """Index dimension.  Must be greater than 0, though a dimension of 1 might
    have undefined behavior."""

    def get_storage(self) -> int:
        return self.handle.index_storage

    def set_storage(self, value: int) -> None:
        self.handle.index_storage = value

    storage = property(get_storage, set_storage)
    """Index storage.

    One of :data:`RT_Disk`, :data:`RT_Memory` or :data:`RT_Custom`.

    If a filename is passed as the first parameter to :class:index.Index,
    :data:`RT_Disk` is assumed. If a CustomStorage instance is passed,
    :data:`RT_Custom` is assumed. Otherwise, :data:`RT_Memory` is the default.
    """

    def get_pagesize(self) -> int:
        return self.handle.pagesize

    def set_pagesize(self, value: int) -> None:
        if value <= 0:
            raise RTreeError("Pagesize must be > 0")
        self.handle.pagesize = value

    pagesize = property(get_pagesize, set_pagesize)
    """The pagesize when disk storage is used.  It is ideal to ensure that your
    index entries fit within a single page for best performance."""

    def get_index_capacity(self) -> int:
        return self.handle.index_capacity

    def set_index_capacity(self, value: int) -> None:
        if value <= 0:
            raise RTreeError("index_capacity must be > 0")
        self.handle.index_capacity = value

    index_capacity = property(get_index_capacity, set_index_capacity)
    """Index capacity"""

    def get_leaf_capacity(self) -> int:
        return self.handle.leaf_capacity

    def set_leaf_capacity(self, value: int) -> None:
        if value <= 0:
            raise RTreeError("leaf_capacity must be > 0")
        self.handle.leaf_capacity = value

    leaf_capacity = property(get_leaf_capacity, set_leaf_capacity)
    """Leaf capacity"""

    def get_index_pool_capacity(self) -> int:
        return self.handle.index_pool_capacity

    def set_index_pool_capacity(self, value: int) -> None:
        if value <= 0:
            raise RTreeError("index_pool_capacity must be > 0")
        self.handle.index_pool_capacity = value

    index_pool_capacity = property(get_index_pool_capacity, set_index_pool_capacity)
    """Index pool capacity"""

    def get_point_pool_capacity(self) -> int:
        return self.handle.point_pool_capacity

    def set_point_pool_capacity(self, value: int) -> None:
        if value <= 0:
            raise RTreeError("point_pool_capacity must be > 0")
        self.handle.point_pool_capacity = value

    point_pool_capacity = property(get_point_pool_capacity, set_point_pool_capacity)
    """Point pool capacity"""

    def get_region_pool_capacity(self) -> int:
        return self.handle.region_pool_capacity

    def set_region_pool_capacity(self, value: int) -> None:
        if value <= 0:
            raise RTreeError("region_pool_capacity must be > 0")
        self.handle.region_pool_capacity = value

    region_pool_capacity = property(get_region_pool_capacity, set_region_pool_capacity)
    """Region pool capacity"""

    def get_buffering_capacity(self) -> int:
        return self.handle.buffering_capacity

    def set_buffering_capacity(self, value: int) -> None:
        if value <= 0:
            raise RTreeError("buffering_capacity must be > 0")
        self.handle.buffering_capacity = value

    buffering_capacity = property(get_buffering_capacity, set_buffering_capacity)
    """Buffering capacity"""

    def get_tight_mbr(self) -> bool:
        return bool(self.handle.ensure_tight_mbrs)

    def set_tight_mbr(self, value: bool) -> None:
        self.handle.ensure_tight_mbrs = int(bool(value))

    tight_mbr = property(get_tight_mbr, set_tight_mbr)
    """Uses tight bounding rectangles"""

    def get_overwrite(self) -> bool:
        return bool(self.handle.overwrite)

    def set_overwrite(self, value: bool) -> None:
        self.handle.overwrite = int(bool(value))

    overwrite = property(get_overwrite, set_overwrite)
    """Overwrite existing index files"""

    def get_near_minimum_overlap_factor(self) -> int:
        return self.handle.near_minimum_overlap_factor

    def set_near_minimum_overlap_factor(self, value: int) -> None:
        if value <= 0:
            raise RTreeError("near_minimum_overlap_factor must be > 0")
        self.handle.near_minimum_overlap_factor = value

    near_minimum_overlap_factor = property(
        get_near_minimum_overlap_factor, set_near_minimum_overlap_factor
    )
    """Overlap factor for MVRTrees"""

    def get_writethrough(self) -> bool:
        return bool(self.handle.write_through)

    def set_writethrough(self, value: bool) -> None:
        self.handle.write_through = int(bool(value))

    writethrough = property(get_writethrough, set_writethrough)
    """Write through caching"""

    def get_fill_factor(self) -> float:
        return self.handle.fill_factor

    def set_fill_factor(self, value: float) -> None:
        self.handle.fill_factor = value

    fill_factor = property(get_fill_factor, set_fill_factor)
    """Index node fill factor before branching"""

    def get_split_distribution_factor(self) -> float:
        return self.handle.split_distribution_factor

    def set_split_distribution_factor(self, value: float) -> None:
        self.handle.split_distribution_factor = value

    split_distribution_factor = property(
        get_split_distribution_factor, set_split_distribution_factor
    )
    """Split distribution factor"""

    def get_tpr_horizon(self) -> float:
        return self.handle.tpr_horizon

    def set_tpr_horizon(self, value: float) -> None:
        self.handle.tpr_horizon = value

    tpr_horizon = property(get_tpr_horizon, set_tpr_horizon)
    """TPR horizon"""

    def get_reinsert_factor(self) -> float:
        return self.handle.reinsert_factor

    def set_reinsert_factor(self, value: float) -> None:
        self.handle.reinsert_factor = value

    reinsert_factor = property(get_reinsert_factor, set_reinsert_factor)
    """Reinsert factor"""

    def get_filename(self) -> str:
        return self.handle.filename

    def set_filename(self, value: str | bytes) -> None:
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        self.handle.filename = value

    filename = property(get_filename, set_filename)
    """Index filename for disk storage"""

    def get_dat_extension(self) -> str:
        return self.handle.dat_extension

    def set_dat_extension(self, value: str | bytes) -> None:
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        self.handle.dat_extension = value

    dat_extension = property(get_dat_extension, set_dat_extension)
    """Extension for .dat file"""

    def get_idx_extension(self) -> str:
        return self.handle.idx_extension

    def set_idx_extension(self, value: str | bytes) -> None:
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        self.handle.idx_extension = value

    idx_extension = property(get_idx_extension, set_idx_extension)
    """Extension for .idx file"""

    def get_custom_storage_callbacks_size(self) -> int:
        return self.handle.custom_storage_callbacks_size

    def set_custom_storage_callbacks_size(self, value: int) -> None:
        self.handle.custom_storage_callbacks_size = value

    custom_storage_callbacks_size = property(
        get_custom_storage_callbacks_size, set_custom_storage_callbacks_size
    )
    """Size of callbacks for custom storage"""

    def get_custom_storage_callbacks(self) -> int | None:
        return self.handle.custom_storage_callbacks

    def set_custom_storage_callbacks(self, value: int | ctypes.c_void_p | None) -> None:
        # Accept the ctypes pointer CustomStorageBase has always passed here.
        if isinstance(value, ctypes.c_void_p):
            value = value.value
        self.handle.custom_storage_callbacks = value or 0

    custom_storage_callbacks = property(
        get_custom_storage_callbacks, set_custom_storage_callbacks
    )
    """Callbacks for custom storage"""

    def get_index_id(self) -> int:
        return self.handle.index_id

    def set_index_id(self, value: int) -> None:
        self.handle.index_id = value

    index_id = property(get_index_id, set_index_id)
    """First node index id"""


# custom storage implementation

id_type = ctypes.c_int64


class CustomStorageCallbacks(ctypes.Structure):
    """ctypes mirror of ``CustomStorageManagerCallbacks``.

    Only used by :class:`CustomStorageBase`, which deliberately exposes the raw
    C buffers.  :class:`CustomStorage` goes through the compiled bridge in
    :mod:`rtree._core` instead.
    """

    # callback types
    createCallbackType = ctypes.CFUNCTYPE(
        None, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)
    )
    destroyCallbackType = ctypes.CFUNCTYPE(
        None, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)
    )
    flushCallbackType = ctypes.CFUNCTYPE(
        None, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)
    )

    loadCallbackType = ctypes.CFUNCTYPE(
        None,
        ctypes.c_void_p,
        id_type,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.POINTER(ctypes.c_uint8)),
        ctypes.POINTER(ctypes.c_int),
    )
    storeCallbackType = ctypes.CFUNCTYPE(
        None,
        ctypes.c_void_p,
        ctypes.POINTER(id_type),
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint8),
        ctypes.POINTER(ctypes.c_int),
    )
    deleteCallbackType = ctypes.CFUNCTYPE(
        None, ctypes.c_void_p, id_type, ctypes.POINTER(ctypes.c_int)
    )

    _fields_ = [
        ("context", ctypes.c_void_p),
        ("createCallback", createCallbackType),
        ("destroyCallback", destroyCallbackType),
        ("flushCallback", flushCallbackType),
        ("loadCallback", loadCallbackType),
        ("storeCallback", storeCallbackType),
        ("deleteCallback", deleteCallbackType),
    ]

    def __init__(
        self,
        context: Any,
        createCallback: Callable[..., None],
        destroyCallback: Callable[..., None],
        flushCallback: Callable[..., None],
        loadCallback: Callable[..., None],
        storeCallback: Callable[..., None],
        deleteCallback: Callable[..., None],
    ) -> None:
        ctypes.Structure.__init__(
            self,
            ctypes.c_void_p(context),
            self.createCallbackType(createCallback),
            self.destroyCallbackType(destroyCallback),
            self.flushCallbackType(flushCallback),
            self.loadCallbackType(loadCallback),
            self.storeCallbackType(storeCallback),
            self.deleteCallbackType(deleteCallback),
        )


class ICustomStorage:
    # error codes
    NoError = 0
    InvalidPageError = 1
    IllegalStateError = 2

    # special pages
    EmptyPage = -0x1
    NewPage = -0x1

    def registerCallbacks(self, properties: Property) -> None:
        raise NotImplementedError()

    def clear(self) -> None:
        raise NotImplementedError()

    hasData = property(lambda self: False)
    """Override this property to allow for reloadable storages"""


class CustomStorageBase(ICustomStorage):
    """Derive from this class to create your own storage manager with access
    to the raw C buffers.

    The callbacks receive :mod:`ctypes` pointers exactly as before.  Buffers
    handed back from ``loadByteArray`` must be allocated by libspatialindex;
    use :meth:`allocateBuffer`.
    """

    def allocateBuffer(self, length: int) -> int:
        return _core.new_buffer(length)

    def registerCallbacks(self, properties: Property) -> None:
        # NOTE: this used to pass ``ctypes.c_void_p()``, which
        # CustomStorageCallbacks wrapped in a second c_void_p and raised
        # TypeError -- CustomStorageBase was unusable and untested on main.
        callbacks = CustomStorageCallbacks(
            None,
            self.create,
            self.destroy,
            self.flush,
            self.loadByteArray,
            self.storeByteArray,
            self.deleteByteArray,
        )
        properties.custom_storage_callbacks_size = ctypes.sizeof(callbacks)
        self.callbacks = callbacks
        properties.custom_storage_callbacks = ctypes.cast(
            ctypes.pointer(callbacks), ctypes.c_void_p
        )

    # the user must override these callback functions
    def create(self, context: Any, returnError: Any) -> None:
        returnError.contents.value = self.IllegalStateError
        raise NotImplementedError("You must override this method.")

    def destroy(self, context: Any, returnError: Any) -> None:
        """please override"""
        returnError.contents.value = self.IllegalStateError
        raise NotImplementedError("You must override this method.")

    def loadByteArray(
        self, context: Any, page: int, resultLen: Any, resultData: Any, returnError: Any
    ) -> None:
        """please override"""
        returnError.contents.value = self.IllegalStateError
        raise NotImplementedError("You must override this method.")

    def storeByteArray(
        self, context: Any, page: Any, len: int, data: Any, returnError: Any
    ) -> None:
        """please override"""
        returnError.contents.value = self.IllegalStateError
        raise NotImplementedError("You must override this method.")

    def deleteByteArray(self, context: Any, page: int, returnError: Any) -> None:
        """please override"""
        returnError.contents.value = self.IllegalStateError
        raise NotImplementedError("You must override this method.")

    def flush(self, context: Any, returnError: Any) -> None:
        """please override"""
        returnError.contents.value = self.IllegalStateError
        raise NotImplementedError("You must override this method.")


class CustomStorage(ICustomStorage):
    """Provides a useful default custom storage implementation which marshals
    the buffers on the C side from/to python :class:`bytes`.
    Derive from this class and override the necessary methods to provide
    your own custom storage manager.

    Each callback receives a ``returnError`` (:class:`rtree._core.ErrorRef`);
    set ``returnError.value`` (or, for backwards compatibility,
    ``returnError.contents.value``) to one of the error codes to signal a
    failure.
    """

    def registerCallbacks(self, properties: Property) -> None:
        properties.handle.set_python_storage(self)

    # the user must override these callback functions
    def create(self, returnError: _core.ErrorRef) -> None:
        """Must be overridden. No return value."""
        returnError.value = self.IllegalStateError
        raise NotImplementedError("You must override this method.")

    def destroy(self, returnError: _core.ErrorRef) -> None:
        """Must be overridden. No return value."""
        returnError.value = self.IllegalStateError
        raise NotImplementedError("You must override this method.")

    def flush(self, returnError: _core.ErrorRef) -> None:
        """Must be overridden. No return value."""
        returnError.value = self.IllegalStateError
        raise NotImplementedError("You must override this method.")

    def loadByteArray(self, page: int, returnError: _core.ErrorRef) -> bytes:
        """Must be overridden. Must return a string with the loaded data."""
        returnError.value = self.IllegalStateError
        raise NotImplementedError("You must override this method.")

    def storeByteArray(
        self, page: int, data: bytes, returnError: _core.ErrorRef
    ) -> int:
        """Must be overridden. Must return the new 64-bit page ID of the stored
        data if a new page had to be created (i.e. page is not NewPage)."""
        returnError.value = self.IllegalStateError
        raise NotImplementedError("You must override this method.")

    def deleteByteArray(self, page: int, returnError: _core.ErrorRef) -> None:
        """please override"""
        returnError.value = self.IllegalStateError
        raise NotImplementedError("You must override this method.")


class RtreeContainer(Rtree):
    """An R-Tree, MVR-Tree, or TPR-Tree indexed container for python objects"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Creates a new index

        :param stream:
            If the first argument in the constructor is not of type basestring,
            it is assumed to be an iterable stream of data that will raise a
            StopIteration.  It must be in the form defined by the
            :attr:`interleaved` attribute of the index. The following example
            would assume :attr:`interleaved` is False::

                (obj,
                 (minx, maxx, miny, maxy, minz, maxz, ..., ..., mink, maxk))

            For a TPR-Tree, this would be in the form::

                (id,
                 ((minx, maxx, miny, maxy, ..., ..., mink, maxk),
                  (minvx, maxvx, minvy, maxvy, ..., ..., minvk, maxvk),
                  time),
                 object)

        :param interleaved: True or False, defaults to True.
            This parameter determines the coordinate order for all methods that
            take in coordinates.

        :param properties: This object sets both the creation and instantiation
            properties for the object and they are passed down into libspatialindex.
            A few properties are curried from instantiation parameters
            for you like ``pagesize`` to ensure compatibility with previous
            versions of the library.  All other properties must be set on the
            object.

        .. warning::
            The coordinate ordering for all functions are sensitive the
            index's :attr:`interleaved` data member.  If :attr:`interleaved`
            is False, the coordinates must be in the form
            [xmin, xmax, ymin, ymax, ..., ..., kmin, kmax]. If
            :attr:`interleaved` is True, the coordinates must be in the form
            [xmin, ymin, ..., kmin, xmax, ymax, ..., kmax]. This also applies
            to velocities when using a TPR-Tree.

        A basic example
        ::

            >>> from rtree import index
            >>> p = index.Property()

            >>> idx = index.RtreeContainer(properties=p)
            >>> idx  # doctest: +NORMALIZE_WHITESPACE
            rtree.index.RtreeContainer(bounds=[1.7976931348623157e+308,
                                     1.7976931348623157e+308,
                                     -1.7976931348623157e+308,
                                     -1.7976931348623157e+308],
                                     size=0)

        Insert an item into the index::

            >>> idx.insert(object(),
            ...            (34.3776829412, 26.7375853734, 49.3776829412,
            ...             41.7375853734))

        Query::

            >>> hits = idx.intersection((0, 0, 60, 60), bbox=True)
            >>> for obj in hits:
            ...     obj.object
            ...     obj.bbox  # doctest: +ELLIPSIS
            <object object at 0x...>
            [34.37768294..., 26.73758537..., 49.37768294..., 41.73758537...]
        """
        if args:
            if (
                isinstance(args[0], str)
                or isinstance(args[0], bytes)
                or isinstance(args[0], ICustomStorage)
            ):
                raise ValueError(f"{self.__class__} supports only in-memory indexes")
        self._objects: dict[int, tuple[int, object]] = {}
        return super().__init__(*args, **kwargs)

    def get_size(self) -> int:
        try:
            return self.count(self.bounds)
        except RTreeError:
            return 0

    def __repr__(self) -> str:
        m = "rtree.index.RtreeContainer(bounds={}, size={})"
        return m.format(self.bounds, self.get_size())

    def __contains__(self, obj: object) -> bool:
        return id(obj) in self._objects

    def __len__(self) -> int:
        return sum(count for count, obj in self._objects.values())

    def __iter__(self) -> Iterator[object]:
        return iter(obj for count, obj in self._objects.values())

    def insert(self, obj: object, coordinates: Any) -> None:  # type: ignore[override]
        """Inserts an item into the index with the given coordinates.

        :param obj: Any object.

        :param coordinates: This may be an object that satisfies the numpy array
            protocol, providing the index's dimension * 2 coordinate
            pairs representing the `mink` and `maxk` coordinates in
            each dimension defining the bounds of the query window.
            For a TPR-Tree, this must be a 3-element sequence including
            not only the positional coordinate pairs but also the
            velocity pairs `minvk` and `maxvk` and a time value as a float.

        The following example inserts a simple object into the container.
        The coordinate ordering in this instance is the default
        (interleaved=True) ordering::

            >>> from rtree import index
            >>> idx = index.RtreeContainer()
            >>> idx.insert(object(),
            ...            (34.3776829412, 26.7375853734, 49.3776829412,
            ...             41.7375853734))

        Similar for TPR-Tree::

            >>> p = index.Property(type=index.RT_TPRTree)  # doctest: +SKIP
            >>> idx = index.RtreeContainer(properties=p)  # doctest: +SKIP
            >>> idx.insert(object(),
            ...            ((34.3776829412, 26.7375853734, 49.3776829412,
            ...             41.7375853734),
            ...             (0.5, 2, 1.5, 2.5),
            ...            3.0))  # doctest: +SKIP

        """
        try:
            count = self._objects[id(obj)][0] + 1
        except KeyError:
            count = 1
        self._objects[id(obj)] = (count, obj)
        return super().insert(id(obj), coordinates, None)

    add = insert  # type: ignore[assignment]

    @overload  # type: ignore[override]
    def intersection(self, coordinates: Any, bbox: Literal[True]) -> Iterator[Item]: ...

    @overload
    def intersection(
        self, coordinates: Any, bbox: Literal[False] = False
    ) -> Iterator[object]: ...

    def intersection(
        self, coordinates: Any, bbox: bool = False
    ) -> Iterator[Item | object]:
        """Return ids or objects in the index that intersect the given
        coordinates.

        :param coordinates: This may be an object that satisfies the numpy array
            protocol, providing the index's dimension * 2 coordinate
            pairs representing the `mink` and `maxk` coordinates in
            each dimension defining the bounds of the query window.
            For a TPR-Tree, this must be a 3-element sequence including
            not only the positional coordinate pairs but also the
            velocity pairs `minvk` and `maxvk` and a time pair for the
            time range as a float.

        :param bbox: If True, the intersection method will return the stored objects,
            as well as the bounds of the entry.

        The following example queries the container for any stored objects that
        intersect the bounds given in the coordinates::

            >>> from rtree import index
            >>> idx = index.RtreeContainer()
            >>> idx.insert(object(),
            ...            (34.3776829412, 26.7375853734, 49.3776829412,
            ...             41.7375853734))

            >>> hits = list(idx.intersection((0, 0, 60, 60), bbox=True))
            >>> [(item.object, item.bbox) for item in hits]
            ... # doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
            [(<object object at 0x...>, [34.3776829412, 26.7375853734,
            49.3776829412, 41.7375853734])]

        If the :class:`rtree.index.Item` wrapper is not used, it is faster to
        request only the stored objects::

            >>> list(idx.intersection((0, 0, 60, 60)))   # doctest: +ELLIPSIS
            [<object object at 0x...>]

        Similar for the TPR-Tree::

            >>> p = index.Property(type=index.RT_TPRTree)  # doctest: +SKIP
            >>> idx = index.RtreeContainer(properties=p)  # doctest: +SKIP
            >>> idx.insert(object(),
            ...            ((34.3776829412, 26.7375853734, 49.3776829412,
            ...             41.7375853734),
            ...             (0.5, 2, 1.5, 2.5),
            ...             3.0))  # doctest: +SKIP

            >>> hits = list(idx.intersection(
            ...     ((0, 0, 60, 60), (0, 0, 0, 0), (3, 5)), bbox=True))
            ... # doctest: +SKIP
            >>> [(item.object, item.bbox) for item in hits]
            ... # doctest: +SKIP
            [(<object object at 0x...>, [34.3776829412, 26.7375853734,
            49.3776829412, 41.7375853734])]

        """
        if bbox is False:
            for id in super().intersection(coordinates, bbox).tolist():
                yield self._objects[id][1]
        elif bbox is True:
            for value in super().intersection(coordinates, bbox):
                value.object = self._objects[value.id][1]
                value.id = None  # type: ignore[assignment]
                yield value
        else:
            raise ValueError("valid values for the bbox argument are True and False")

    @overload  # type: ignore[override]
    def nearest(
        self, coordinates: Any, num_results: int = 1, bbox: Literal[True] = True
    ) -> Iterator[Item]: ...

    @overload
    def nearest(
        self, coordinates: Any, num_results: int = 1, bbox: Literal[False] = False
    ) -> Iterator[object]: ...

    def nearest(
        self, coordinates: Any, num_results: int = 1, bbox: bool = False
    ) -> Iterator[Item | object]:
        """Returns the ``k``-nearest objects to the given coordinates
        in increasing distance order.

        :param coordinates: This may be an object that satisfies the numpy array
            protocol, providing the index's dimension * 2 coordinate
            pairs representing the `mink` and `maxk` coordinates in
            each dimension defining the bounds of the query window.
            For a TPR-Tree, this must be a 3-element sequence including
            not only the positional coordinate pairs but also the
            velocity pairs `minvk` and `maxvk` and a time pair for the
            time range as a float.

        :param num_results: The number of results to return nearest to the given
            coordinates. If two entries are equidistant, *both* are returned.
            This property means that :attr:`num_results` may return more
            items than specified.

        :param bbox: If True, the nearest method will return the stored objects, as
            well as the bounds of the entry.

        .. warning::
            This is currently not implemented for the TPR-Tree.

        Example of finding the three items nearest to this one::

            >>> from rtree import index
            >>> idx = index.RtreeContainer()
            >>> idx.insert(object(), (34.37, 26.73, 49.37, 41.73))
            >>> hits = idx.nearest((0, 0, 10, 10), 3, bbox=True)
        """
        if bbox is False:
            for id in super().nearest(coordinates, num_results, bbox).tolist():
                yield self._objects[id][1]
        elif bbox is True:
            for value in super().nearest(coordinates, num_results, bbox):
                value.object = self._objects[value.id][1]
                value.id = None  # type: ignore[assignment]
                yield value
        else:
            raise ValueError("valid values for the bbox argument are True and False")

    def delete(self, obj: object, coordinates: Any) -> None:
        """Deletes the item from the container within the specified
        coordinates.

        :param obj: Any object.

        :param coordinates: Dimension * 2 coordinate pairs, representing the min
            and max coordinates in each dimension of the item to be
            deleted from the index. Their ordering will depend on the
            index's :attr:`interleaved` data member.
            These are not the coordinates of a space containing the
            item, but those of the item itself. Together with the
            id parameter, they determine which item will be deleted.
            This may be an object that satisfies the numpy array protocol.
            For a TPR-Tree, this must be a 3-element sequence including
            not only the positional coordinate pairs but also the
            velocity pairs `minvk` and `maxvk` and a time pair for the
            original time the object was inserted and the current time
            as a float.

        Example::

            >>> from rtree import index
            >>> idx = index.RtreeContainer()
            >>> idx.delete(object(),
            ...            (34.3776829412, 26.7375853734, 49.3776829412,
            ...             41.7375853734))
            Traceback (most recent call last):
             ...
            IndexError: object is not in the index

        For the TPR-Tree::

            >>> p = index.Property(type=index.RT_TPRTree)  # doctest: +SKIP
            >>> idx = index.RtreeContainer(properties=p)  # doctest: +SKIP
            >>> idx.delete(object(),
            ...            ((34.3776829412, 26.7375853734, 49.3776829412,
            ...             41.7375853734),
            ...             (0.5, 2, 1.5, 2.5),
            ...             (3.0, 5.0)))  # doctest: +SKIP
            Traceback (most recent call last):
             ...
            IndexError: object is not in the index

        """
        try:
            count = self._objects[id(obj)][0] - 1
        except KeyError:
            raise IndexError("object is not in the index")
        if count == 0:
            del self._objects[id(obj)]
        else:
            self._objects[id(obj)] = (count, obj)
        return super().delete(id(obj), coordinates)

    def leaves(self) -> list[tuple[object, list[object], list[float]]]:  # type: ignore[override]
        return [
            (
                self._objects[id][1],
                [self._objects[child_id][1] for child_id in child_ids],
                bounds,
            )
            for id, child_ids, bounds in super().leaves()
        ]
