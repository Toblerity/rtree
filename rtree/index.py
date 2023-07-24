from __future__ import annotations

import ctypes
import os
import os.path
import pickle
import pprint
import warnings
from typing import Any, Iterator, Literal, Sequence, overload

from . import core
from .exceptions import RTreeError

RT_Memory = 0
RT_Disk = 1
RT_Custom = 2

RT_Linear = 0
RT_Quadratic = 1
RT_Star = 2

RT_RTree = 0
RT_MVRTree = 1
RT_TPRTree = 2

__c_api_version__ = core.rt.SIDX_Version()

major_version, minor_version, patch_version = (
    int(t) for t in __c_api_version__.decode("utf-8").split(".")
)

if (major_version, minor_version, patch_version) < (1, 8, 5):
    raise Exception("Rtree requires libspatialindex 1.8.5 or greater")

__all__ = ["Rtree", "Index", "Property"]


def _get_bounds(handle, bounds_fn, interleaved):
    pp_mins = ctypes.pointer(ctypes.c_double())
    pp_maxs = ctypes.pointer(ctypes.c_double())
    dimension = ctypes.c_uint32(0)

    bounds_fn(
        handle, ctypes.byref(pp_mins), ctypes.byref(pp_maxs), ctypes.byref(dimension)
    )
    if dimension.value == 0:
        return None

    mins = ctypes.cast(pp_mins, ctypes.POINTER(ctypes.c_double * dimension.value))
    maxs = ctypes.cast(pp_maxs, ctypes.POINTER(ctypes.c_double * dimension.value))

    results = [mins.contents[i] for i in range(dimension.value)]
    results += [maxs.contents[i] for i in range(dimension.value)]

    p_mins = ctypes.cast(mins, ctypes.POINTER(ctypes.c_double))
    p_maxs = ctypes.cast(maxs, ctypes.POINTER(ctypes.c_double))
    core.rt.Index_Free(ctypes.cast(p_mins, ctypes.POINTER(ctypes.c_void_p)))
    core.rt.Index_Free(ctypes.cast(p_maxs, ctypes.POINTER(ctypes.c_void_p)))
    if interleaved:  # they want bbox order.
        return results
    return Index.deinterleave(results)


def _get_data(handle):
    length = ctypes.c_uint64(0)
    d = ctypes.pointer(ctypes.c_uint8(0))
    core.rt.IndexItem_GetData(handle, ctypes.byref(d), ctypes.byref(length))
    c = ctypes.cast(d, ctypes.POINTER(ctypes.c_void_p))
    if length.value == 0:
        core.rt.Index_Free(c)
        return None
    s = ctypes.string_at(d, length.value)
    core.rt.Index_Free(c)
    return s


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
        self.properties = kwargs.get("properties", Property())

        if self.properties.type == RT_TPRTree and not hasattr(
            core.rt, "Index_InsertTPData"
        ):
            raise RuntimeError(
                "TPR-Tree type not supported with version of libspatialindex"
            )

        # interleaved True gives 'bbox' order.
        self.interleaved = bool(kwargs.get("interleaved", True))

        stream = None
        basename = None
        storage = None
        if args:
            if isinstance(args[0], str) or isinstance(args[0], bytes):
                # they sent in a filename
                basename = args[0]
                # they sent in a filename, stream
                if len(args) > 1:
                    stream = args[1]
            elif isinstance(args[0], ICustomStorage):
                storage = args[0]
                # they sent in a storage, stream
                if len(args) > 1:
                    stream = args[1]
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
                message = "Unable to open file '%s' for index storage" % f
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
        else:
            self.handle = IndexHandle(self.properties.handle)
            if stream:  # Bulk insert not supported, so add one by one
                for item in stream:
                    self.insert(*item)

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
        return "rtree.index.Index(bounds={}, size={})".format(
            self.bounds, self.get_size()
        )

    def __getstate__(self) -> dict[str, Any]:
        state = self.__dict__.copy()
        del state["handle"]
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)
        self.handle = IndexHandle(self.properties.handle)

    def dumps(self, obj: object) -> bytes:
        return pickle.dumps(obj)

    def loads(self, string: bytes) -> object:
        return pickle.loads(string)

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
        self, coordinates: Sequence[float]
    ) -> tuple[float, float]:
        try:
            iter(coordinates)
        except TypeError:
            raise TypeError("Bounds must be a sequence")
        dimension = self.properties.dimension

        mins = ctypes.c_double * dimension
        maxs = ctypes.c_double * dimension

        if not self.interleaved:
            coordinates = Index.interleave(coordinates)

        # it's a point make it into a bbox. [x, y] => [x, y, x, y]
        if len(coordinates) == dimension:
            coordinates = *coordinates, *coordinates

        if len(coordinates) != dimension * 2:
            raise RTreeError(
                "Coordinates must be in the form "
                "(minx, miny, maxx, maxy) or (x, y) for 2D indexes"
            )

        # so here all coords are in the form:
        # [xmin, ymin, zmin, xmax, ymax, zmax]
        for i in range(dimension):
            if not coordinates[i] <= coordinates[i + dimension]:
                raise RTreeError(
                    "Coordinates must not have minimums more than maximums"
                )

        p_mins = mins(*[ctypes.c_double(coordinates[i]) for i in range(dimension)])
        p_maxs = maxs(
            *[ctypes.c_double(coordinates[i + dimension]) for i in range(dimension)]
        )

        return (p_mins, p_maxs)

    @staticmethod
    def _get_time_doubles(times):
        if times[0] > times[1]:
            raise RTreeError("Start time must be less than end time")
        t_start = ctypes.c_double(times[0])
        t_end = ctypes.c_double(times[1])
        return t_start, t_end

    def _serialize(self, obj):
        serialized = self.dumps(obj)
        size = len(serialized)

        d = ctypes.create_string_buffer(serialized)
        # d.value = serialized
        p = ctypes.pointer(d)

        # return serialized to keep it alive for the pointer.
        return size, ctypes.cast(p, ctypes.POINTER(ctypes.c_uint8)), serialized

    def set_result_limit(self, value):
        return core.rt.Index_SetResultSetOffset(self.handle, value)

    def get_result_limit(self):
        return core.rt.Index_GetResultSetOffset(self.handle)

    result_limit = property(get_result_limit, set_result_limit)

    def set_result_offset(self, value):
        return core.rt.Index_SetResultSetLimit(self.handle, value)

    def get_result_offset(self):
        return core.rt.Index_GetResultSetLimit(self.handle)

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

        :param obj: a pickleable object.  If not None, this object will be
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

        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)
        data = ctypes.c_ubyte(0)
        size = 0
        pyserialized = None
        if obj is not None:
            size, data, pyserialized = self._serialize(obj)
        core.rt.Index_InsertData(
            self.handle, id, p_mins, p_maxs, self.properties.dimension, data, size
        )

    add = insert

    def _insertTP(
        self,
        id: int,
        coordinates: Sequence[float],
        velocities: Sequence[float],
        time: float,
        obj: object = None,
    ) -> None:
        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)
        pv_mins, pv_maxs = self.get_coordinate_pointers(velocities)
        # End time isn't used
        t_start, t_end = self._get_time_doubles((time, time + 1))
        data = ctypes.c_ubyte(0)
        size = 0
        if obj is not None:
            size, data, _ = self._serialize(obj)
        core.rt.Index_InsertTPData(
            self.handle,
            id,
            p_mins,
            p_maxs,
            pv_mins,
            pv_maxs,
            t_start,
            t_end,
            self.properties.dimension,
            data,
            size,
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
        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)

        p_num_results = ctypes.c_uint64(0)

        core.rt.Index_Intersects_count(
            self.handle,
            p_mins,
            p_maxs,
            self.properties.dimension,
            ctypes.byref(p_num_results),
        )

        return p_num_results.value

    def _countTP(
        self, coordinates: Sequence[float], velocities: Sequence[float], times: float
    ) -> int:
        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)
        pv_mins, pv_maxs = self.get_coordinate_pointers(velocities)
        t_start, t_end = self._get_time_doubles(times)

        p_num_results = ctypes.c_uint64(0)

        core.rt.Index_TPIntersects_count(
            self.handle,
            p_mins,
            p_maxs,
            pv_mins,
            pv_maxs,
            t_start,
            t_end,
            self.properties.dimension,
            ctypes.byref(p_num_results),
        )

        return p_num_results.value

    @overload
    def contains(self, coordinates: Any, objects: Literal[True]) -> Iterator[Item]:
        ...

    @overload
    def contains(
        self, coordinates: Any, objects: Literal[False] = False
    ) -> Iterator[int] | None:
        ...

    @overload
    def contains(self, coordinates: Any, objects: Literal["raw"]) -> Iterator[object]:
        ...

    def contains(
        self, coordinates: Any, objects: bool | Literal["raw"] = False
    ) -> Iterator[Item | int | object] | None:
        """Return ids or objects in the index that contains within the given
        coordinates.

        :param coordinates: This may be an object that satisfies the numpy array
            protocol, providing the index's dimension * 2 coordinate
            pairs representing the `mink` and `maxk` coordinates in
            each dimension defining the bounds of the query window.

        :param objects: If True, the intersection method will return index objects that
            were pickled when they were stored with each index entry, as well
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

        if objects:
            return self._contains_obj(coordinates, objects)

        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)

        p_num_results = ctypes.c_uint64(0)

        it = ctypes.pointer(ctypes.c_int64())

        try:
            core.rt.Index_Contains_id
        except AttributeError:
            return None

        core.rt.Index_Contains_id(
            self.handle,
            p_mins,
            p_maxs,
            self.properties.dimension,
            ctypes.byref(it),
            ctypes.byref(p_num_results),
        )
        return self._get_ids(it, p_num_results.value)

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
    def intersection(self, coordinates: Any, objects: Literal[True]) -> Iterator[Item]:
        ...

    @overload
    def intersection(
        self, coordinates: Any, objects: Literal[False] = False
    ) -> Iterator[int]:
        ...

    @overload
    def intersection(
        self, coordinates: Any, objects: Literal["raw"]
    ) -> Iterator[object]:
        ...

    def intersection(
        self, coordinates: Any, objects: bool | Literal["raw"] = False
    ) -> Iterator[Item | int | object]:
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
            were pickled when they were stored with each index entry, as well
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

        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)

        p_num_results = ctypes.c_uint64(0)

        it = ctypes.pointer(ctypes.c_int64())

        core.rt.Index_Intersects_id(
            self.handle,
            p_mins,
            p_maxs,
            self.properties.dimension,
            ctypes.byref(it),
            ctypes.byref(p_num_results),
        )
        return self._get_ids(it, p_num_results.value)

    def _intersectionTP(self, coordinates, velocities, times, objects=False):
        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)
        pv_mins, pv_maxs = self.get_coordinate_pointers(velocities)
        t_start, t_end = self._get_time_doubles(times)

        p_num_results = ctypes.c_uint64(0)

        if objects:
            call = core.rt.Index_TPIntersects_obj
            it = ctypes.pointer(ctypes.c_void_p())
        else:
            call = core.rt.Index_TPIntersects_id
            it = ctypes.pointer(ctypes.c_int64())

        call(
            self.handle,
            p_mins,
            p_maxs,
            pv_mins,
            pv_maxs,
            t_start,
            t_end,
            self.properties.dimension,
            ctypes.byref(it),
            ctypes.byref(p_num_results),
        )

        if objects:
            return self._get_objects(it, p_num_results.value, objects)
        else:
            return self._get_ids(it, p_num_results.value)

    def _intersection_obj(self, coordinates, objects):
        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)

        p_num_results = ctypes.c_uint64(0)

        it = ctypes.pointer(ctypes.c_void_p())

        core.rt.Index_Intersects_obj(
            self.handle,
            p_mins,
            p_maxs,
            self.properties.dimension,
            ctypes.byref(it),
            ctypes.byref(p_num_results),
        )
        return self._get_objects(it, p_num_results.value, objects)

    def _contains_obj(self, coordinates: Any, objects):
        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)

        p_num_results = ctypes.c_uint64(0)

        it = ctypes.pointer(ctypes.c_void_p())

        try:
            core.rt.Index_Contains_obj
        except AttributeError:
            return None

        core.rt.Index_Contains_obj(
            self.handle,
            p_mins,
            p_maxs,
            self.properties.dimension,
            ctypes.byref(it),
            ctypes.byref(p_num_results),
        )
        return self._get_objects(it, p_num_results.value, objects)

    def _get_objects(self, it, num_results, objects):
        # take the pointer, yield the result objects and free
        items = ctypes.cast(
            it, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p * num_results))
        )
        its = ctypes.cast(items, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))

        try:
            if objects != "raw":
                for i in range(num_results):
                    yield Item(self.loads, items[i])
            else:
                for i in range(num_results):
                    data = _get_data(items[i])
                    if data is None:
                        yield data
                    else:
                        yield self.loads(data)

        finally:
            core.rt.Index_DestroyObjResults(its, num_results)

    def _get_ids(self, it, num_results):
        # take the pointer, yield the results  and free
        items = ctypes.cast(it, ctypes.POINTER(ctypes.c_int64 * num_results))
        its = ctypes.cast(items, ctypes.POINTER(ctypes.c_void_p))

        try:
            for i in range(num_results):
                yield items.contents[i]

        finally:
            core.rt.Index_Free(its)

    def _nearest_obj(self, coordinates, num_results, objects):
        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)

        p_num_results = ctypes.pointer(ctypes.c_uint64(num_results))

        it = ctypes.pointer(ctypes.c_void_p())

        core.rt.Index_NearestNeighbors_obj(
            self.handle,
            p_mins,
            p_maxs,
            self.properties.dimension,
            ctypes.byref(it),
            p_num_results,
        )

        return self._get_objects(it, p_num_results.contents.value, objects)

    @overload
    def nearest(
        self, coordinates: Any, num_results: int, objects: Literal[True]
    ) -> Iterator[Item]:
        ...

    @overload
    def nearest(
        self, coordinates: Any, num_results: int, objects: Literal[False] = False
    ) -> Iterator[int]:
        ...

    @overload
    def nearest(
        self, coordinates: Any, num_results: int, objects: Literal["raw"]
    ) -> Iterator[object]:
        ...

    def nearest(
        self,
        coordinates: Any,
        num_results: int = 1,
        objects: bool | Literal["raw"] = False,
    ) -> Iterator[Item | int | object]:
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
            were pickled when they were stored with each index entry, as
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
        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)

        # p_num_results is an input and output for C++ lib
        # as an input it says "get n closest neighbors"
        # but if multiple neighbors are at the same distance, both
        # will be returned
        # so the number of returned neighbors may be > p_num_results
        # thus p_num_results.contents.value gets set as an output by the
        # C++ lib to indicate the actual number of results for
        # _get_ids to use
        p_num_results = ctypes.pointer(ctypes.c_uint64(num_results))

        it = ctypes.pointer(ctypes.c_int64())

        core.rt.Index_NearestNeighbors_id(
            self.handle,
            p_mins,
            p_maxs,
            self.properties.dimension,
            ctypes.byref(it),
            p_num_results,
        )

        return self._get_ids(it, p_num_results.contents.value)

    def _nearestTP(self, coordinates, velocities, times, num_results=1, objects=False):
        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)
        pv_mins, pv_maxs = self.get_coordinate_pointers(velocities)
        t_start, t_end = self._get_time_doubles(times)

        p_num_results = ctypes.pointer(ctypes.c_uint64(num_results))

        if objects:
            it = ctypes.pointer(ctypes.c_void_p())
            call = core.rt.Index_TPNearestNeighbors_obj
        else:
            it = ctypes.pointer(ctypes.c_int64())
            call = core.rt.Index_TPNearestNeighbors_id

        call(
            self.handle,
            p_mins,
            p_maxs,
            pv_mins,
            pv_maxs,
            t_start,
            t_end,
            self.properties.dimension,
            ctypes.byref(it),
            p_num_results,
        )

        if objects:
            return self._get_objects(it, p_num_results.contents.value, objects)
        else:
            return self._get_ids(it, p_num_results.contents.value)

    def get_bounds(self, coordinate_interleaved=None):
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
        return _get_bounds(self.handle, core.rt.Index_GetBounds, coordinate_interleaved)

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
        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)
        core.rt.Index_DeleteData(
            self.handle, id, p_mins, p_maxs, self.properties.dimension
        )

    def _deleteTP(
        self,
        id: int,
        coordinates: Sequence[float],
        velocities: Sequence[float],
        times: float,
    ) -> None:
        p_mins, p_maxs = self.get_coordinate_pointers(coordinates)
        pv_mins, pv_maxs = self.get_coordinate_pointers(velocities)
        t_start, t_end = self._get_time_doubles(times)
        core.rt.Index_DeleteTPData(
            self.handle,
            id,
            p_mins,
            p_maxs,
            pv_mins,
            pv_maxs,
            t_start,
            t_end,
            self.properties.dimension,
        )

    def valid(self) -> bool:
        return bool(core.rt.Index_IsValid(self.handle))

    def clearBuffer(self):
        return core.rt.Index_ClearBuffer(self.handle)

    @classmethod
    def deinterleave(self, interleaved: Sequence[object]) -> list[object]:
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
    def interleave(self, deinterleaved: Sequence[float]) -> list[float]:
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

    def _create_idx_from_stream(self, stream):
        """This function is used to instantiate the index given an
        iterable stream of data."""

        stream_iter = iter(stream)
        dimension = self.properties.dimension
        darray = ctypes.c_double * dimension
        mins = darray()
        maxs = darray()
        no_data = ctypes.cast(
            ctypes.pointer(ctypes.c_ubyte(0)), ctypes.POINTER(ctypes.c_ubyte)
        )

        def py_next_item(p_id, p_mins, p_maxs, p_dimension, p_data, p_length):
            """This function must fill pointers to individual entries that will
            be added to the index.  The C API will actually call this function
            to fill out the pointers.  If this function returns anything other
            than 0, it is assumed that the stream of data is done."""

            try:
                p_id[0], coordinates, obj = next(stream_iter)
            except StopIteration:
                # we're done
                return -1
            except Exception as exc:
                self._exception = exc
                return -1

            if self.interleaved:
                coordinates = Index.deinterleave(coordinates)

            # this code assumes the coords are not interleaved.
            # xmin, xmax, ymin, ymax, zmin, zmax
            for i in range(dimension):
                mins[i] = coordinates[i * 2]
                maxs[i] = coordinates[(i * 2) + 1]

            p_mins[0] = ctypes.cast(mins, ctypes.POINTER(ctypes.c_double))
            p_maxs[0] = ctypes.cast(maxs, ctypes.POINTER(ctypes.c_double))

            # set the dimension
            p_dimension[0] = dimension
            if obj is None:
                p_data[0] = no_data
                p_length[0] = 0
            else:
                p_length[0], data, _ = self._serialize(obj)
                p_data[0] = ctypes.cast(data, ctypes.POINTER(ctypes.c_ubyte))

            return 0

        stream = core.NEXTFUNC(py_next_item)
        return IndexStreamHandle(self.properties.handle, stream)

    def leaves(self):
        leaf_node_count = ctypes.c_uint32()
        p_leafsizes = ctypes.pointer(ctypes.c_uint32())
        p_leafids = ctypes.pointer(ctypes.c_int64())
        pp_childids = ctypes.pointer(ctypes.pointer(ctypes.c_int64()))

        pp_mins = ctypes.pointer(ctypes.pointer(ctypes.c_double()))
        pp_maxs = ctypes.pointer(ctypes.pointer(ctypes.c_double()))
        dimension = ctypes.c_uint32(0)

        core.rt.Index_GetLeaves(
            self.handle,
            ctypes.byref(leaf_node_count),
            ctypes.byref(p_leafsizes),
            ctypes.byref(p_leafids),
            ctypes.byref(pp_childids),
            ctypes.byref(pp_mins),
            ctypes.byref(pp_maxs),
            ctypes.byref(dimension),
        )

        output = []

        count = leaf_node_count.value
        sizes = ctypes.cast(p_leafsizes, ctypes.POINTER(ctypes.c_uint32 * count))
        ids = ctypes.cast(p_leafids, ctypes.POINTER(ctypes.c_int64 * count))
        child = ctypes.cast(
            pp_childids, ctypes.POINTER(ctypes.POINTER(ctypes.c_int64) * count)
        )
        mins = ctypes.cast(
            pp_mins, ctypes.POINTER(ctypes.POINTER(ctypes.c_double) * count)
        )
        maxs = ctypes.cast(
            pp_maxs, ctypes.POINTER(ctypes.POINTER(ctypes.c_double) * count)
        )
        for i in range(count):
            p_child_ids = child.contents[i]

            id = ids.contents[i]
            size = sizes.contents[i]
            child_ids_array = ctypes.cast(
                p_child_ids, ctypes.POINTER(ctypes.c_int64 * size)
            )

            child_ids = []
            for j in range(size):
                child_ids.append(child_ids_array.contents[j])

            # free the child ids list
            core.rt.Index_Free(
                ctypes.cast(p_child_ids, ctypes.POINTER(ctypes.c_void_p))
            )

            p_mins = mins.contents[i]
            p_maxs = maxs.contents[i]

            p_mins = ctypes.cast(
                p_mins, ctypes.POINTER(ctypes.c_double * dimension.value)
            )
            p_maxs = ctypes.cast(
                p_maxs, ctypes.POINTER(ctypes.c_double * dimension.value)
            )

            bounds = []
            bounds = [p_mins.contents[i] for i in range(dimension.value)]
            bounds += [p_maxs.contents[i] for i in range(dimension.value)]

            # free the bounds
            p_mins = ctypes.cast(p_mins, ctypes.POINTER(ctypes.c_double))
            p_maxs = ctypes.cast(p_maxs, ctypes.POINTER(ctypes.c_double))
            core.rt.Index_Free(ctypes.cast(p_mins, ctypes.POINTER(ctypes.c_void_p)))
            core.rt.Index_Free(ctypes.cast(p_maxs, ctypes.POINTER(ctypes.c_void_p)))

            output.append((id, child_ids, bounds))

        return output


# An alias to preserve backward compatibility
Rtree = Index


class Item:
    """A container for index entries"""

    __slots__ = ("handle", "owned", "id", "object", "bounds")

    def __init__(self, loads, handle, owned=False) -> None:
        """There should be no reason to instantiate these yourself. Items are
        created automatically when you call
        :meth:`rtree.index.Index.intersection` (or other index querying
        methods) with objects=True given the parameters of the function."""

        if handle:
            self.handle = handle

        self.owned = owned

        self.id = core.rt.IndexItem_GetID(self.handle)

        self.object = None
        self.object = self.get_object(loads)
        self.bounds = _get_bounds(self.handle, core.rt.IndexItem_GetBounds, False)

    def __lt__(self, other: Item) -> bool:
        return self.id < other.id

    def __gt__(self, other: Item) -> bool:
        return self.id > other.id

    @property
    def bbox(self) -> list[float]:
        """Returns the bounding box of the index entry"""
        return Index.interleave(self.bounds)

    def get_object(self, loads):
        # short circuit this so we only do it at construction time
        if self.object is not None:
            return self.object
        data = _get_data(self.handle)
        if data is None:
            return None
        return loads(data)


class InvalidHandleException(Exception):
    """Handle has been destroyed and can no longer be used"""


class Handle:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._ptr = self._create(*args, **kwargs)

    def _create(self, *args: Any, **kwargs: Any):
        raise NotImplementedError

    def _destroy(self, ptr):
        raise NotImplementedError

    def destroy(self) -> None:
        try:
            if self._ptr is not None:
                self._destroy(self._ptr)
                self._ptr = None
        except AttributeError:
            pass

    @property
    def _as_parameter_(self):
        if self._ptr is None:
            raise InvalidHandleException
        return self._ptr

    def __del__(self) -> None:
        try:
            self.destroy()
        except NameError:
            # The core.py model doesn't have
            # core.rt available anymore and it was tore
            # down. We don't want to try to do anything
            # in that instance
            return


class IndexHandle(Handle):
    _create = core.rt.Index_Create
    _destroy = core.rt.Index_Destroy

    def flush(self) -> None:
        try:
            core.rt.Index_Flush
            if self._ptr is not None:
                core.rt.Index_Flush(self._ptr)
        except AttributeError:
            pass


class IndexStreamHandle(IndexHandle):
    _create = core.rt.Index_CreateWithStream


class PropertyHandle(Handle):
    _create = core.rt.IndexProperty_Create
    _destroy = core.rt.IndexProperty_Destroy


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

    def __init__(self, handle=None, owned: bool = True, **kwargs: Any) -> None:
        if handle is None:
            handle = PropertyHandle()
        self.handle = handle
        self.initialize_from_dict(kwargs)

    def initialize_from_dict(self, state: dict[str, Any]) -> None:
        for k, v in state.items():
            if v is not None:
                setattr(self, k, v)

    def __getstate__(self) -> dict[Any, Any]:
        return self.as_dict()

    def __setstate__(self, state):
        self.handle = PropertyHandle()
        self.initialize_from_dict(state)

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
        return core.rt.IndexProperty_GetIndexType(self.handle)

    def set_index_type(self, value: int) -> None:
        return core.rt.IndexProperty_SetIndexType(self.handle, value)

    type = property(get_index_type, set_index_type)
    """Index type. Valid index type values are
    :data:`RT_RTree`, :data:`RT_MVTree`, or :data:`RT_TPRTree`.  Only
    RT_RTree (the default) is practically supported at this time."""

    def get_variant(self) -> int:
        return core.rt.IndexProperty_GetIndexVariant(self.handle)

    def set_variant(self, value: int) -> None:
        return core.rt.IndexProperty_SetIndexVariant(self.handle, value)

    variant = property(get_variant, set_variant)
    """Index variant.  Valid index variant values are
    :data:`RT_Linear`, :data:`RT_Quadratic`, and :data:`RT_Star`"""

    def get_dimension(self) -> int:
        return core.rt.IndexProperty_GetDimension(self.handle)

    def set_dimension(self, value: int) -> None:
        if value <= 0:
            raise RTreeError("Negative or 0 dimensional indexes are not allowed")
        return core.rt.IndexProperty_SetDimension(self.handle, value)

    dimension = property(get_dimension, set_dimension)
    """Index dimension.  Must be greater than 0, though a dimension of 1 might
    have undefined behavior."""

    def get_storage(self) -> int:
        return core.rt.IndexProperty_GetIndexStorage(self.handle)

    def set_storage(self, value: int) -> None:
        return core.rt.IndexProperty_SetIndexStorage(self.handle, value)

    storage = property(get_storage, set_storage)
    """Index storage.

    One of :data:`RT_Disk`, :data:`RT_Memory` or :data:`RT_Custom`.

    If a filename is passed as the first parameter to :class:index.Index,
    :data:`RT_Disk` is assumed. If a CustomStorage instance is passed,
    :data:`RT_Custom` is assumed. Otherwise, :data:`RT_Memory` is the default.
    """

    def get_pagesize(self) -> int:
        return core.rt.IndexProperty_GetPagesize(self.handle)

    def set_pagesize(self, value: int) -> None:
        if value <= 0:
            raise RTreeError("Pagesize must be > 0")
        return core.rt.IndexProperty_SetPagesize(self.handle, value)

    pagesize = property(get_pagesize, set_pagesize)
    """The pagesize when disk storage is used.  It is ideal to ensure that your
    index entries fit within a single page for best performance."""

    def get_index_capacity(self) -> int:
        return core.rt.IndexProperty_GetIndexCapacity(self.handle)

    def set_index_capacity(self, value: int) -> None:
        if value <= 0:
            raise RTreeError("index_capacity must be > 0")
        return core.rt.IndexProperty_SetIndexCapacity(self.handle, value)

    index_capacity = property(get_index_capacity, set_index_capacity)
    """Index capacity"""

    def get_leaf_capacity(self) -> int:
        return core.rt.IndexProperty_GetLeafCapacity(self.handle)

    def set_leaf_capacity(self, value: int) -> None:
        if value <= 0:
            raise RTreeError("leaf_capacity must be > 0")
        return core.rt.IndexProperty_SetLeafCapacity(self.handle, value)

    leaf_capacity = property(get_leaf_capacity, set_leaf_capacity)
    """Leaf capacity"""

    def get_index_pool_capacity(self) -> int:
        return core.rt.IndexProperty_GetIndexPoolCapacity(self.handle)

    def set_index_pool_capacity(self, value: int) -> None:
        if value <= 0:
            raise RTreeError("index_pool_capacity must be > 0")
        return core.rt.IndexProperty_SetIndexPoolCapacity(self.handle, value)

    index_pool_capacity = property(get_index_pool_capacity, set_index_pool_capacity)
    """Index pool capacity"""

    def get_point_pool_capacity(self) -> int:
        return core.rt.IndexProperty_GetPointPoolCapacity(self.handle)

    def set_point_pool_capacity(self, value: int) -> None:
        if value <= 0:
            raise RTreeError("point_pool_capacity must be > 0")
        return core.rt.IndexProperty_SetPointPoolCapacity(self.handle, value)

    point_pool_capacity = property(get_point_pool_capacity, set_point_pool_capacity)
    """Point pool capacity"""

    def get_region_pool_capacity(self) -> int:
        return core.rt.IndexProperty_GetRegionPoolCapacity(self.handle)

    def set_region_pool_capacity(self, value: int) -> None:
        if value <= 0:
            raise RTreeError("region_pool_capacity must be > 0")
        return core.rt.IndexProperty_SetRegionPoolCapacity(self.handle, value)

    region_pool_capacity = property(get_region_pool_capacity, set_region_pool_capacity)
    """Region pool capacity"""

    def get_buffering_capacity(self) -> int:
        return core.rt.IndexProperty_GetBufferingCapacity(self.handle)

    def set_buffering_capacity(self, value: int) -> None:
        if value <= 0:
            raise RTreeError("buffering_capacity must be > 0")
        return core.rt.IndexProperty_SetBufferingCapacity(self.handle, value)

    buffering_capacity = property(get_buffering_capacity, set_buffering_capacity)
    """Buffering capacity"""

    def get_tight_mbr(self):
        return bool(core.rt.IndexProperty_GetEnsureTightMBRs(self.handle))

    def set_tight_mbr(self, value):
        value = bool(value)
        return bool(core.rt.IndexProperty_SetEnsureTightMBRs(self.handle, value))

    tight_mbr = property(get_tight_mbr, set_tight_mbr)
    """Uses tight bounding rectangles"""

    def get_overwrite(self):
        return bool(core.rt.IndexProperty_GetOverwrite(self.handle))

    def set_overwrite(self, value):
        value = bool(value)
        return bool(core.rt.IndexProperty_SetOverwrite(self.handle, value))

    overwrite = property(get_overwrite, set_overwrite)
    """Overwrite existing index files"""

    def get_near_minimum_overlap_factor(self) -> int:
        return core.rt.IndexProperty_GetNearMinimumOverlapFactor(self.handle)

    def set_near_minimum_overlap_factor(self, value: int) -> None:
        if value <= 0:
            raise RTreeError("near_minimum_overlap_factor must be > 0")
        return core.rt.IndexProperty_SetNearMinimumOverlapFactor(self.handle, value)

    near_minimum_overlap_factor = property(
        get_near_minimum_overlap_factor, set_near_minimum_overlap_factor
    )
    """Overlap factor for MVRTrees"""

    def get_writethrough(self):
        return bool(core.rt.IndexProperty_GetWriteThrough(self.handle))

    def set_writethrough(self, value):
        value = bool(value)
        return bool(core.rt.IndexProperty_SetWriteThrough(self.handle, value))

    writethrough = property(get_writethrough, set_writethrough)
    """Write through caching"""

    def get_fill_factor(self) -> int:
        return core.rt.IndexProperty_GetFillFactor(self.handle)

    def set_fill_factor(self, value: int) -> None:
        return core.rt.IndexProperty_SetFillFactor(self.handle, value)

    fill_factor = property(get_fill_factor, set_fill_factor)
    """Index node fill factor before branching"""

    def get_split_distribution_factor(self) -> int:
        return core.rt.IndexProperty_GetSplitDistributionFactor(self.handle)

    def set_split_distribution_factor(self, value: int) -> None:
        return core.rt.IndexProperty_SetSplitDistributionFactor(self.handle, value)

    split_distribution_factor = property(
        get_split_distribution_factor, set_split_distribution_factor
    )
    """Split distribution factor"""

    def get_tpr_horizon(self):
        return core.rt.IndexProperty_GetTPRHorizon(self.handle)

    def set_tpr_horizon(self, value):
        return core.rt.IndexProperty_SetTPRHorizon(self.handle, value)

    tpr_horizon = property(get_tpr_horizon, set_tpr_horizon)
    """TPR horizon"""

    def get_reinsert_factor(self):
        return core.rt.IndexProperty_GetReinsertFactor(self.handle)

    def set_reinsert_factor(self, value):
        return core.rt.IndexProperty_SetReinsertFactor(self.handle, value)

    reinsert_factor = property(get_reinsert_factor, set_reinsert_factor)
    """Reinsert factor"""

    def get_filename(self):
        return core.rt.IndexProperty_GetFileName(self.handle).decode()

    def set_filename(self, value):
        if isinstance(value, str):
            value = value.encode("utf-8")
        return core.rt.IndexProperty_SetFileName(self.handle, value)

    filename = property(get_filename, set_filename)
    """Index filename for disk storage"""

    def get_dat_extension(self):
        ext = core.rt.IndexProperty_GetFileNameExtensionDat(self.handle)
        return ext.decode()

    def set_dat_extension(self, value):
        if isinstance(value, str):
            value = value.encode("utf-8")
        return core.rt.IndexProperty_SetFileNameExtensionDat(self.handle, value)

    dat_extension = property(get_dat_extension, set_dat_extension)
    """Extension for .dat file"""

    def get_idx_extension(self):
        ext = core.rt.IndexProperty_GetFileNameExtensionIdx(self.handle)
        return ext.decode()

    def set_idx_extension(self, value):
        if isinstance(value, str):
            value = value.encode("utf-8")
        return core.rt.IndexProperty_SetFileNameExtensionIdx(self.handle, value)

    idx_extension = property(get_idx_extension, set_idx_extension)
    """Extension for .idx file"""

    def get_custom_storage_callbacks_size(self) -> int:
        return core.rt.IndexProperty_GetCustomStorageCallbacksSize(self.handle)

    def set_custom_storage_callbacks_size(self, value: int) -> None:
        return core.rt.IndexProperty_SetCustomStorageCallbacksSize(self.handle, value)

    custom_storage_callbacks_size = property(
        get_custom_storage_callbacks_size, set_custom_storage_callbacks_size
    )
    """Size of callbacks for custom storage"""

    def get_custom_storage_callbacks(self):
        return core.rt.IndexProperty_GetCustomStorageCallbacks(self.handle)

    def set_custom_storage_callbacks(self, value):
        return core.rt.IndexProperty_SetCustomStorageCallbacks(self.handle, value)

    custom_storage_callbacks = property(
        get_custom_storage_callbacks, set_custom_storage_callbacks
    )
    """Callbacks for custom storage"""

    def get_index_id(self):
        return core.rt.IndexProperty_GetIndexID(self.handle)

    def set_index_id(self, value):
        return core.rt.IndexProperty_SetIndexID(self.handle, value)

    index_id = property(get_index_id, set_index_id)
    """First node index id"""


# custom storage implementation

id_type = ctypes.c_int64


class CustomStorageCallbacks(ctypes.Structure):
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
        context,
        createCallback,
        destroyCallback,
        flushCallback,
        loadCallback,
        storeCallback,
        deleteCallback,
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

    def allocateBuffer(self, length):
        return core.rt.SIDX_NewBuffer(length)

    def registerCallbacks(self, properties):
        raise NotImplementedError()

    def clear(self):
        raise NotImplementedError()

    hasData = property(lambda self: False)
    """Override this property to allow for reloadable storages"""


class CustomStorageBase(ICustomStorage):
    """Derive from this class to create your own storage manager with access
    to the raw C buffers."""

    def registerCallbacks(self, properties):
        callbacks = CustomStorageCallbacks(
            ctypes.c_void_p(),
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
    def create(self, context, returnError):
        returnError.contents.value = self.IllegalStateError
        raise NotImplementedError("You must override this method.")

    def destroy(self, context, returnError):
        """please override"""
        returnError.contents.value = self.IllegalStateError
        raise NotImplementedError("You must override this method.")

    def loadByteArray(self, context, page, resultLen, resultData, returnError):
        """please override"""
        returnError.contents.value = self.IllegalStateError
        raise NotImplementedError("You must override this method.")

    def storeByteArray(self, context, page, len, data, returnError):
        """please override"""
        returnError.contents.value = self.IllegalStateError
        raise NotImplementedError("You must override this method.")

    def deleteByteArray(self, context, page, returnError):
        """please override"""
        returnError.contents.value = self.IllegalStateError
        raise NotImplementedError("You must override this method.")

    def flush(self, context, returnError):
        """please override"""
        returnError.contents.value = self.IllegalStateError
        raise NotImplementedError("You must override this method.")


class CustomStorage(ICustomStorage):
    """Provides a useful default custom storage implementation which marshals
    the buffers on the C side from/to python strings.
    Derive from this class and override the necessary methods to provide
    your own custom storage manager."""

    def registerCallbacks(self, properties):
        callbacks = CustomStorageCallbacks(
            0,
            self._create,
            self._destroy,
            self._flush,
            self._loadByteArray,
            self._storeByteArray,
            self._deleteByteArray,
        )
        properties.custom_storage_callbacks_size = ctypes.sizeof(callbacks)
        self.callbacks = callbacks
        properties.custom_storage_callbacks = ctypes.cast(
            ctypes.pointer(callbacks), ctypes.c_void_p
        )

    # these functions handle the C callbacks and massage the data, then
    # delegate to the function without underscore below
    def _create(self, context, returnError):
        self.create(returnError)

    def _destroy(self, context, returnError):
        self.destroy(returnError)

    def _flush(self, context, returnError):
        self.flush(returnError)

    def _loadByteArray(self, context, page, resultLen, resultData, returnError):
        resultString = self.loadByteArray(page, returnError)
        if returnError.contents.value != self.NoError:
            return
        # Copy python string over into a buffer allocated on the C side.
        #  The buffer will later be freed by the C side. This prevents
        #  possible heap corruption issues as buffers allocated by ctypes
        #  and the c library might be allocated on different heaps.
        # Freeing a buffer allocated on another heap might make the application
        #  crash.
        count = len(resultString)
        resultLen.contents.value = count
        buffer = self.allocateBuffer(count)
        ctypes.memmove(buffer, ctypes.c_char_p(resultString), count)
        resultData[0] = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_uint8))

    def _storeByteArray(self, context, page, len, data, returnError):
        str = ctypes.string_at(data, len)
        newPageId = self.storeByteArray(page.contents.value, str, returnError)
        page.contents.value = newPageId

    def _deleteByteArray(self, context, page, returnError):
        self.deleteByteArray(page, returnError)

    # the user must override these callback functions
    def create(self, returnError):
        """Must be overridden. No return value."""
        returnError.contents.value = self.IllegalStateError
        raise NotImplementedError("You must override this method.")

    def destroy(self, returnError):
        """Must be overridden. No return value."""
        returnError.contents.value = self.IllegalStateError
        raise NotImplementedError("You must override this method.")

    def flush(self, returnError):
        """Must be overridden. No return value."""
        returnError.contents.value = self.IllegalStateError
        raise NotImplementedError("You must override this method.")

    def loadByteArray(self, page, returnError):
        """Must be overridden. Must return a string with the loaded data."""
        returnError.contents.value = self.IllegalStateError
        raise NotImplementedError("You must override this method.")
        return ""

    def storeByteArray(self, page, data, returnError):
        """Must be overridden. Must return the new 64-bit page ID of the stored
        data if a new page had to be created (i.e. page is not NewPage)."""
        returnError.contents.value = self.IllegalStateError
        raise NotImplementedError("You must override this method.")
        return 0

    def deleteByteArray(self, page, returnError):
        """please override"""
        returnError.contents.value = self.IllegalStateError
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
                raise ValueError("%s supports only in-memory indexes" % self.__class__)
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
    def intersection(self, coordinates: Any, bbox: Literal[True]) -> Iterator[Item]:
        ...

    @overload
    def intersection(
        self, coordinates: Any, bbox: Literal[False] = False
    ) -> Iterator[object]:
        ...

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
            for id in super().intersection(coordinates, bbox):
                yield self._objects[id][1]
        elif bbox is True:
            for value in super().intersection(coordinates, bbox):
                value.object = self._objects[value.id][1]
                value.id = None
                yield value
        else:
            raise ValueError("valid values for the bbox argument are True and False")

    @overload  # type: ignore[override]
    def nearest(
        self, coordinates: Any, num_results: int = 1, bbox: Literal[True] = True
    ) -> Iterator[Item]:
        ...

    @overload
    def nearest(
        self, coordinates: Any, num_results: int = 1, bbox: Literal[False] = False
    ) -> Iterator[object]:
        ...

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
            for id in super().nearest(coordinates, num_results, bbox):
                yield self._objects[id][1]
        elif bbox is True:
            for value in super().nearest(coordinates, num_results, bbox):
                value.object = self._objects[value.id][1]
                value.id = None
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

    def leaves(self):
        return [
            (
                self._objects[id][1],
                [self._objects[child_id][1] for child_id in child_ids],
                bounds,
            )
            for id, child_ids, bounds in super(RtreeContainer, self).leaves()
        ]
