from __future__ import annotations

import ctypes
import pickle
import sys
import tempfile
import unittest
from collections.abc import Iterator

import numpy as np
import pytest

import rtree
from rtree import core, index
from rtree.exceptions import RTreeError


class IndexTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.boxes15 = np.genfromtxt("boxes_15x15.data")
        self.idx = index.Index()
        for i, coords in enumerate(self.boxes15):
            self.idx.add(i, coords)

    def boxes15_stream(
        self, interleaved: bool = True
    ) -> Iterator[tuple[int, tuple[float, float, float, float], int]]:
        boxes15 = np.genfromtxt("boxes_15x15.data")
        for i, (minx, miny, maxx, maxy) in enumerate(boxes15):
            if interleaved:
                yield (i, (minx, miny, maxx, maxy), 42)
            else:
                yield (i, (minx, maxx, miny, maxy), 42)

    def stream_basic(self) -> None:
        # some versions of libspatialindex screw up indexes on stream loading
        # so do a very simple index check
        rtree_test = rtree.index.Index(
            [(1564, [0, 0, 0, 10, 10, 10], None)],
            properties=rtree.index.Property(dimension=3),
        )
        assert next(rtree_test.intersection([1, 1, 1, 2, 2, 2])) == 1564


class IndexCount(unittest.TestCase):
    def setUp(self) -> None:
        self.boxes15 = np.genfromtxt("boxes_15x15.data")
        self.idx = index.Index()
        for i, coords in enumerate(self.boxes15):
            self.idx.add(i, coords)

    def test_len(self) -> None:
        self.assertEqual(len(self.idx), len(self.boxes15))

    def test_get_size(self) -> None:
        with pytest.deprecated_call():
            self.assertEqual(self.idx.get_size(), len(self.boxes15))


class IndexBounds(unittest.TestCase):
    def test_invalid_specifications(self) -> None:
        """Invalid specifications of bounds properly throw"""

        idx = index.Index()
        self.assertRaises(RTreeError, idx.add, None, (0.0, 0.0, -1.0, 1.0))
        self.assertRaises(RTreeError, idx.intersection, (0.0, 0.0, -1.0, 1.0))
        self.assertRaises(ctypes.ArgumentError, idx.add, None, (1, 1))


class IndexProperties(IndexTestCase):
    @pytest.mark.skipif(
        not hasattr(core.rt, "Index_GetResultSetOffset"),
        reason="Index_GetResultsSetOffset required in libspatialindex",
    )
    def test_result_offset(self) -> None:
        idx = index.Rtree()
        idx.set_result_offset(3)
        self.assertEqual(idx.result_offset, 3)

    @pytest.mark.skipif(
        not hasattr(core.rt, "Index_GetResultSetLimit"),
        reason="Index_GetResultsSetOffset required in libspatialindex",
    )
    def test_result_limit(self) -> None:
        idx = index.Rtree()
        idx.set_result_limit(44)
        self.assertEqual(idx.result_limit, 44)

    def test_invalid_properties(self) -> None:
        """Invalid values are guarded"""
        p = index.Property()

        self.assertRaises(RTreeError, p.set_buffering_capacity, -4321)
        self.assertRaises(RTreeError, p.set_region_pool_capacity, -4321)
        self.assertRaises(RTreeError, p.set_point_pool_capacity, -4321)
        self.assertRaises(RTreeError, p.set_index_pool_capacity, -4321)
        self.assertRaises(RTreeError, p.set_pagesize, -4321)
        self.assertRaises(RTreeError, p.set_index_capacity, -4321)
        self.assertRaises(RTreeError, p.set_storage, -4321)
        self.assertRaises(RTreeError, p.set_variant, -4321)
        self.assertRaises(RTreeError, p.set_dimension, -2)
        self.assertRaises(RTreeError, p.set_index_type, 6)
        self.assertRaises(RTreeError, p.get_index_id)

    def test_index_properties(self) -> None:
        """Setting index properties returns expected values"""
        idx = index.Rtree()
        p = index.Property()

        p.leaf_capacity = 100
        p.fill_factor = 0.5
        p.index_capacity = 10
        p.near_minimum_overlap_factor = 7
        p.buffering_capacity = 10
        p.variant = 0
        p.dimension = 3
        p.storage = 0
        p.pagesize = 4096
        p.index_pool_capacity = 1500
        p.point_pool_capacity = 1600
        p.region_pool_capacity = 1700
        p.tight_mbr = True
        p.overwrite = True
        p.writethrough = True
        p.tpr_horizon = 20.0
        p.reinsert_factor = 0.3
        p.idx_extension = "index"
        p.dat_extension = "data"

        idx = index.Index(properties=p)

        props = idx.properties
        self.assertEqual(props.leaf_capacity, 100)
        self.assertEqual(props.fill_factor, 0.5)
        self.assertEqual(props.index_capacity, 10)
        self.assertEqual(props.near_minimum_overlap_factor, 7)
        self.assertEqual(props.buffering_capacity, 10)
        self.assertEqual(props.variant, 0)
        self.assertEqual(props.dimension, 3)
        self.assertEqual(props.storage, 0)
        self.assertEqual(props.pagesize, 4096)
        self.assertEqual(props.index_pool_capacity, 1500)
        self.assertEqual(props.point_pool_capacity, 1600)
        self.assertEqual(props.region_pool_capacity, 1700)
        self.assertEqual(props.tight_mbr, True)
        self.assertEqual(props.overwrite, True)
        self.assertEqual(props.writethrough, True)
        self.assertEqual(props.tpr_horizon, 20.0)
        self.assertEqual(props.reinsert_factor, 0.3)
        self.assertEqual(props.idx_extension, "index")
        self.assertEqual(props.dat_extension, "data")


class TestPickling(unittest.TestCase):
    # https://github.com/Toblerity/rtree/issues/87
    @pytest.mark.xfail
    def test_index(self) -> None:
        idx = rtree.index.Index()
        idx.insert(0, [0, 1, 2, 3], 4)
        unpickled = pickle.loads(pickle.dumps(idx))
        self.assertNotEqual(idx.handle, unpickled.handle)
        self.assertEqual(idx.properties.as_dict(), unpickled.properties.as_dict())
        self.assertEqual(idx.interleaved, unpickled.interleaved)
        self.assertEqual(len(idx), len(unpickled))
        self.assertEqual(idx.bounds, unpickled.bounds)
        a = next(idx.intersection(idx.bounds, objects=True))
        b = next(unpickled.intersection(unpickled.bounds, objects=True))
        self.assertEqual(a.id, b.id)
        self.assertEqual(a.bounds, b.bounds)
        self.assertEqual(a.object, b.object)

    def test_property(self) -> None:
        p = rtree.index.Property()
        unpickled = pickle.loads(pickle.dumps(p))
        self.assertNotEqual(p.handle, unpickled.handle)
        self.assertEqual(p.as_dict(), unpickled.as_dict())


class IndexContainer(IndexTestCase):
    def test_container(self) -> None:
        """rtree.index.RtreeContainer works as expected"""

        container = rtree.index.RtreeContainer()
        objects = list()

        for coordinates in self.boxes15:
            objects.append(object())
            container.insert(objects[-1], coordinates)

        self.assertEqual(len(container), len(self.boxes15))
        assert all(obj in container for obj in objects)

        for obj, coordinates in zip(objects, self.boxes15[:5]):
            container.delete(obj, coordinates)

        assert all(obj in container for obj in objects[5:])
        assert all(obj not in container for obj in objects[:5])
        assert len(container) == len(self.boxes15) - 5

        with pytest.raises(IndexError):
            container.delete(objects[0], self.boxes15[0])

            # Insert duplicate object, at different location
        container.insert(objects[5], self.boxes15[0])
        assert objects[5] in container
        # And then delete it, but check object still present
        container.delete(objects[5], self.boxes15[0])
        assert objects[5] in container

        # Intersection
        obj = objects[10]
        results = container.intersection(self.boxes15[10])
        assert obj in results

        # Intersection with bbox
        obj = objects[10]
        results = container.intersection(self.boxes15[10], bbox=True)
        result = [result for result in results if result.object is obj][0]
        assert np.array_equal(result.bbox, self.boxes15[10])

        # Nearest
        obj = objects[8]
        results = container.intersection(self.boxes15[8])
        assert obj in results

        # Nearest with bbox
        obj = objects[8]
        results = container.nearest(self.boxes15[8], bbox=True)
        result = [result for result in results if result.object is obj][0]
        assert np.array_equal(result.bbox, self.boxes15[8])

        # Test iter method
        assert objects[12] in set(container)


class IndexIntersection(IndexTestCase):
    def test_intersection(self) -> None:
        """Test basic insertion and retrieval"""

        self.assertTrue(0 in self.idx.intersection((0, 0, 60, 60)))
        hits = list(self.idx.intersection((0, 0, 60, 60)))

        self.assertEqual(len(hits), 10)
        self.assertEqual(hits, [0, 4, 16, 27, 35, 40, 47, 50, 76, 80])

    def test_objects(self) -> None:
        """Test insertion of objects"""

        idx = index.Index()
        for i, coords in enumerate(self.boxes15):
            idx.add(i, coords)
        idx.insert(
            4321, (34.3776829412, 26.7375853734, 49.3776829412, 41.7375853734), obj=42
        )
        hits = idx.intersection((0, 0, 60, 60), objects=True)
        hit = [h for h in hits if h.id == 4321][0]
        self.assertEqual(hit.id, 4321)
        self.assertEqual(hit.object, 42)
        box = [f"{t:.10f}" for t in hit.bbox]
        expected = ["34.3776829412", "26.7375853734", "49.3776829412", "41.7375853734"]
        self.assertEqual(box, expected)

    def test_double_insertion(self) -> None:
        """Inserting the same id twice does not overwrite data"""
        idx = index.Index()
        idx.add(1, (2, 2))
        idx.add(1, (3, 3))

        self.assertEqual([1, 1], list(idx.intersection((0, 0, 5, 5))))


class TestIndexIntersectionUnion:
    @pytest.fixture(scope="class")
    def index_a_interleaved(self) -> index.Index:
        idx = index.Index(interleaved=True)
        idx.insert(1, (3, 3, 5, 5), "a_1")
        idx.insert(2, (4, 2, 6, 4), "a_2")
        return idx

    @pytest.fixture(scope="class")
    def index_a_uninterleaved(self) -> index.Index:
        idx = index.Index(interleaved=False)
        idx.insert(1, (3, 5, 3, 5), "a_1")
        idx.insert(2, (4, 6, 2, 4), "a_2")
        return idx

    @pytest.fixture(scope="class")
    def index_b_interleaved(self) -> index.Index:
        idx = index.Index(interleaved=True)
        idx.insert(3, (2, 1, 7, 6), "b_3")
        idx.insert(4, (8, 7, 9, 8), "b_4")
        return idx

    @pytest.fixture(scope="class")
    def index_b_uninterleaved(self) -> index.Index:
        idx = index.Index(interleaved=False)
        idx.insert(3, (2, 7, 1, 6), "b_3")
        idx.insert(4, (8, 9, 7, 8), "b_4")
        return idx

    def test_intersection_interleaved(
        self, index_a_interleaved: index.Index, index_b_interleaved: index.Index
    ) -> None:
        index_c_interleaved = index_a_interleaved & index_b_interleaved
        assert index_c_interleaved.interleaved
        assert len(index_c_interleaved) == 2
        for hit in index_c_interleaved.intersection(
            index_c_interleaved.bounds, objects=True
        ):
            if hit.bbox == [3.0, 3.0, 5.0, 5.0]:
                assert hit.object == ("a_1", "b_3")
            elif hit.bbox == [4.0, 2.0, 6.0, 4.0]:
                assert hit.object == ("a_2", "b_3")
            else:
                assert False

    def test_intersection_uninterleaved(
        self, index_a_uninterleaved: index.Index, index_b_uninterleaved: index.Index
    ) -> None:
        index_c_uninterleaved = index_a_uninterleaved & index_b_uninterleaved
        assert not index_c_uninterleaved.interleaved
        assert len(index_c_uninterleaved) == 2
        for hit in index_c_uninterleaved.intersection(
            index_c_uninterleaved.bounds, objects=True
        ):
            if hit.bounds == [3.0, 5.0, 3.0, 5.0]:
                assert hit.object == ("a_1", "b_3")
            elif hit.bounds == [4.0, 6.0, 2.0, 4.0]:
                assert hit.object == ("a_2", "b_3")
            else:
                assert False

    def test_intersection_mismatch(
        self, index_a_interleaved: index.Index, index_b_uninterleaved: index.Index
    ) -> None:
        with pytest.raises(AssertionError):
            index_a_interleaved & index_b_uninterleaved

    def test_union_interleaved(
        self, index_a_interleaved: index.Index, index_b_interleaved: index.Index
    ) -> None:
        index_c_interleaved = index_a_interleaved | index_b_interleaved
        assert index_c_interleaved.interleaved
        assert len(index_c_interleaved) == 4
        for hit in index_c_interleaved.intersection(
            index_c_interleaved.bounds, objects=True
        ):
            if hit.bbox == [3.0, 3.0, 5.0, 5.0]:
                assert hit.object == "a_1"
            elif hit.bbox == [4.0, 2.0, 6.0, 4.0]:
                assert hit.object == "a_2"
            elif hit.bbox == [2.0, 1.0, 7.0, 6.0]:
                assert hit.object == "b_3"
            elif hit.bbox == [8.0, 7.0, 9.0, 8.0]:
                assert hit.object == "b_4"
            else:
                assert False

    def test_union_uninterleaved(
        self, index_a_uninterleaved: index.Index, index_b_uninterleaved: index.Index
    ) -> None:
        index_c_uninterleaved = index_a_uninterleaved | index_b_uninterleaved
        assert not index_c_uninterleaved.interleaved
        assert len(index_c_uninterleaved) == 4
        for hit in index_c_uninterleaved.intersection(
            index_c_uninterleaved.bounds, objects=True
        ):
            if hit.bounds == [3.0, 5.0, 3.0, 5.0]:
                assert hit.object == "a_1"
            elif hit.bounds == [4.0, 6.0, 2.0, 4.0]:
                assert hit.object == "a_2"
            elif hit.bounds == [2.0, 7.0, 1.0, 6.0]:
                assert hit.object == "b_3"
            elif hit.bounds == [8.0, 9.0, 7.0, 8.0]:
                assert hit.object == "b_4"
            else:
                assert False

    def test_union_mismatch(
        self, index_a_interleaved: index.Index, index_b_uninterleaved: index.Index
    ) -> None:
        with pytest.raises(AssertionError):
            index_a_interleaved | index_b_uninterleaved


class IndexSerialization(unittest.TestCase):
    def setUp(self) -> None:
        self.boxes15 = np.genfromtxt("boxes_15x15.data")

    def boxes15_stream(
        self, interleaved: bool = True
    ) -> Iterator[tuple[int, tuple[float, float, float, float], int]]:
        for i, (minx, miny, maxx, maxy) in enumerate(self.boxes15):
            if interleaved:
                yield (i, (minx, miny, maxx, maxy), 42)
            else:
                yield (i, (minx, maxx, miny, maxy), 42)

    def test_unicode_filenames(self) -> None:
        """Unicode filenames work as expected"""
        tname = tempfile.mktemp()
        filename = tname + "gilename\u4500abc"
        idx = index.Index(filename)
        idx.insert(
            4321, (34.3776829412, 26.7375853734, 49.3776829412, 41.7375853734), obj=42
        )

    def test_pickling(self) -> None:
        """Pickling works as expected"""

        idx = index.Index()
        import json

        some_data = {"a": 22, "b": [1, "ccc"]}

        # https://github.com/python/mypy/issues/2427
        idx.dumps = lambda obj: json.dumps(obj).encode(  # type: ignore[assignment]
            "utf-8"
        )
        idx.loads = lambda string: json.loads(  # type: ignore[assignment]
            string.decode("utf-8")
        )

        idx.add(0, (0, 0, 1, 1), some_data)

        self.assertEqual(list(idx.nearest((0, 0), 1, objects="raw"))[0], some_data)

    def test_custom_filenames(self) -> None:
        """Test using custom filenames for index serialization"""
        p = index.Property()
        p.dat_extension = "data"
        p.idx_extension = "index"
        tname = tempfile.mktemp()
        idx = index.Index(tname, properties=p)
        for i, coords in enumerate(self.boxes15):
            idx.add(i, coords)

        hits = list(idx.intersection((0, 0, 60, 60)))
        self.assertEqual(len(hits), 10)
        self.assertEqual(hits, [0, 4, 16, 27, 35, 40, 47, 50, 76, 80])
        del idx

        # Check we can reopen the index and get the same results
        idx2 = index.Index(tname, properties=p)
        hits = list(idx2.intersection((0, 0, 60, 60)))
        self.assertEqual(len(hits), 10)
        self.assertEqual(hits, [0, 4, 16, 27, 35, 40, 47, 50, 76, 80])

    @pytest.mark.skipif(not sys.maxsize > 2**32, reason="Fails on 32bit systems")
    def test_interleaving(self) -> None:
        """Streaming against a persisted index without interleaving"""

        def data_gen(
            interleaved: bool = True,
        ) -> Iterator[tuple[int, tuple[float, float, float, float], int]]:
            for i, (minx, miny, maxx, maxy) in enumerate(self.boxes15):
                if interleaved:
                    yield (i, (minx, miny, maxx, maxy), 42)
                else:
                    yield (i, (minx, maxx, miny, maxy), 42)

        p = index.Property()
        tname = tempfile.mktemp()
        idx = index.Index(
            tname, data_gen(interleaved=False), properties=p, interleaved=False
        )
        hits1 = sorted(list(idx.intersection((0, 60, 0, 60))))
        self.assertEqual(len(hits1), 10)
        self.assertEqual(hits1, [0, 4, 16, 27, 35, 40, 47, 50, 76, 80])

        leaves = idx.leaves()
        expected = [
            (
                0,
                [
                    2,
                    92,
                    51,
                    55,
                    26,
                    95,
                    7,
                    81,
                    38,
                    22,
                    58,
                    89,
                    91,
                    83,
                    98,
                    37,
                    70,
                    31,
                    49,
                    34,
                    11,
                    6,
                    13,
                    3,
                    23,
                    57,
                    9,
                    96,
                    84,
                    36,
                    5,
                    45,
                    77,
                    78,
                    44,
                    12,
                    42,
                    73,
                    93,
                    41,
                    71,
                    17,
                    39,
                    54,
                    88,
                    72,
                    97,
                    60,
                    62,
                    48,
                    19,
                    25,
                    76,
                    59,
                    66,
                    64,
                    79,
                    94,
                    40,
                    32,
                    46,
                    47,
                    15,
                    68,
                    10,
                    0,
                    80,
                    56,
                    50,
                    30,
                ],
                [-186.673789279, -96.7177218184, 172.392784956, 45.4856075292],
            ),
            (
                2,
                [
                    61,
                    74,
                    29,
                    99,
                    16,
                    43,
                    35,
                    33,
                    27,
                    63,
                    18,
                    90,
                    8,
                    53,
                    82,
                    21,
                    65,
                    24,
                    4,
                    1,
                    75,
                    67,
                    86,
                    52,
                    28,
                    85,
                    87,
                    14,
                    69,
                    20,
                ],
                [-174.739939684, 32.6596016791, 184.761387556, 96.6043699778],
            ),
        ]

        # go through the traversal and see if everything is close
        assert all(
            all(np.allclose(a, b) for a, b in zip(L, E))  # type: ignore
            for L, E in zip(leaves, expected)
        )

        hits2 = sorted(list(idx.intersection((0, 60, 0, 60), objects=True)))
        self.assertEqual(len(hits2), 10)
        self.assertEqual(hits2[0].object, 42)

    def test_overwrite(self) -> None:
        """Index overwrite works as expected"""
        tname = tempfile.mktemp()

        idx = index.Index(tname)
        del idx
        idx = index.Index(tname, overwrite=True)
        assert isinstance(idx, index.Index)


class IndexNearest(IndexTestCase):
    def test_nearest_basic(self) -> None:
        """Test nearest basic selection of records"""
        hits = list(self.idx.nearest((0, 0, 10, 10), 3))
        self.assertEqual(hits, [76, 48, 19])

        idx = index.Index()
        locs = [(2, 4), (6, 8), (10, 12), (11, 13), (15, 17), (13, 20)]
        for i, (start, stop) in enumerate(locs):
            idx.add(i, (start, 1, stop, 1))
        hits = sorted(idx.nearest((13, 0, 20, 2), 3))
        self.assertEqual(hits, [3, 4, 5])

    def test_nearest_equidistant(self) -> None:
        """Test that if records are equidistant, both are returned."""
        point = (0, 0)
        small_box = (-10, -10, 10, 10)
        large_box = (-50, -50, 50, 50)

        idx = index.Index()
        idx.insert(0, small_box)
        idx.insert(1, large_box)
        self.assertEqual(list(idx.nearest(point, 2)), [0, 1])
        self.assertEqual(list(idx.nearest(point, 1)), [0, 1])

        idx.insert(2, (0, 0))
        self.assertEqual(list(idx.nearest(point, 2)), [0, 1, 2])
        self.assertEqual(list(idx.nearest(point, 1)), [0, 1, 2])

        idx = index.Index()
        idx.insert(0, small_box)
        idx.insert(1, large_box)
        idx.insert(2, (50, 50))  # point on top right vertex of large_box
        point = (51, 51)  # right outside of large_box
        self.assertEqual(list(idx.nearest(point, 2)), [1, 2])
        self.assertEqual(list(idx.nearest(point, 1)), [1, 2])

        idx = index.Index()
        idx.insert(0, small_box)
        idx.insert(1, large_box)
        # point right outside on top right vertex of large_box
        idx.insert(2, (51, 51))
        point = (51, 52)  # shifted 1 unit up from the point above
        self.assertEqual(list(idx.nearest(point, 2)), [2, 1])
        self.assertEqual(list(idx.nearest(point, 1)), [2])

    def test_nearest_object(self) -> None:
        """Test nearest object selection of records"""
        idx = index.Index()
        locs = [(14, 10, 14, 10), (16, 10, 16, 10)]
        for i, (minx, miny, maxx, maxy) in enumerate(locs):
            idx.add(i, (minx, miny, maxx, maxy), obj={"a": 42})

        hits = sorted(
            (i.id, i.object) for i in idx.nearest((15, 10, 15, 10), 1, objects=True)
        )
        self.assertEqual(hits, [(0, {"a": 42}), (1, {"a": 42})])


class IndexDelete(IndexTestCase):
    def test_deletion(self) -> None:
        """Test we can delete data from the index"""
        idx = index.Index()
        for i, coords in enumerate(self.boxes15):
            idx.add(i, coords)

        for i, coords in enumerate(self.boxes15):
            idx.delete(i, coords)

        hits = list(idx.intersection((0, 0, 60, 60)))
        self.assertEqual(hits, [])


class IndexMoreDimensions(IndexTestCase):
    def test_3d(self) -> None:
        """Test we make and query a 3D index"""
        p = index.Property()
        p.dimension = 3
        idx = index.Index(properties=p, interleaved=False)
        idx.insert(1, (0, 0, 60, 60, 22, 22.0))
        hits = idx.intersection((-1, 1, 58, 62, 22, 24))
        self.assertEqual(list(hits), [1])

    def test_4d(self) -> None:
        """Test we make and query a 4D index"""
        p = index.Property()
        p.dimension = 4
        idx = index.Index(properties=p, interleaved=False)
        idx.insert(1, (0, 0, 60, 60, 22, 22.0, 128, 142))
        hits = idx.intersection((-1, 1, 58, 62, 22, 24, 120, 150))
        self.assertEqual(list(hits), [1])


class IndexStream(IndexTestCase):
    def test_stream_input(self) -> None:
        p = index.Property()
        sindex = index.Index(self.boxes15_stream(), properties=p)
        bounds = (0, 0, 60, 60)
        hits = sindex.intersection(bounds)
        self.assertEqual(sorted(hits), [0, 4, 16, 27, 35, 40, 47, 50, 76, 80])
        objects = list(sindex.intersection((0, 0, 60, 60), objects=True))

        self.assertEqual(len(objects), 10)
        self.assertEqual(objects[0].object, 42)

    def test_empty_stream(self) -> None:
        """Assert empty stream raises exception"""
        self.assertRaises(RTreeError, index.Index, iter(()))

    def test_exception_in_generator(self) -> None:
        """Assert exceptions raised in callbacks are raised in main thread"""

        class TestException(Exception):
            pass

        def create_index() -> index.Index:
            def gen() -> Iterator[tuple[int, tuple[int, int, int, int], None]]:
                # insert at least 6 or so before the exception
                for i in range(10):
                    yield (i, (1, 2, 3, 4), None)
                raise TestException("raising here")

            return index.Index(gen())

        self.assertRaises(TestException, create_index)

    def test_exception_at_beginning_of_generator(self) -> None:
        """
        Assert exceptions raised in callbacks before generator
        function are raised in main thread.
        """

        class TestException(Exception):
            pass

        def create_index() -> index.Index:
            def gen() -> None:
                raise TestException("raising here")

            return index.Index(gen())  # type: ignore[func-returns-value]

        self.assertRaises(TestException, create_index)


class DictStorage(index.CustomStorage):
    """A simple storage which saves the pages in a python dictionary"""

    def __init__(self) -> None:
        index.CustomStorage.__init__(self)
        self.clear()

    def create(self, returnError):
        """Called when the storage is created on the C side"""

    def destroy(self, returnError):
        """Called when the storage is destroyed on the C side"""

    def clear(self) -> None:
        """Clear all our data"""
        self.dict: dict = {}

    def loadByteArray(self, page, returnError):
        """Returns the data for page or returns an error"""
        try:
            return self.dict[page]
        except KeyError:
            returnError.contents.value = self.InvalidPageError

    def storeByteArray(self, page, data, returnError):
        """Stores the data for page"""
        if page == self.NewPage:
            newPageId = len(self.dict)
            self.dict[newPageId] = data
            return newPageId
        else:
            if page not in self.dict:
                returnError.value = self.InvalidPageError
                return 0
            self.dict[page] = data
            return page

    def deleteByteArray(self, page, returnError):
        """Deletes a page"""
        try:
            del self.dict[page]
        except KeyError:
            returnError.contents.value = self.InvalidPageError

    hasData = property(lambda self: bool(self.dict))
    """ Returns true if we contains some data """


class IndexCustomStorage(unittest.TestCase):
    def test_custom_storage(self) -> None:
        """Custom index storage works as expected"""
        settings = index.Property()
        settings.writethrough = True
        settings.buffering_capacity = 1

        # Notice that there is a small in-memory buffer by default.
        # We effectively disable it here so our storage directly receives
        # any load/store/delete calls.
        # This is not necessary in general and can hamper performance;
        # we just use it here for illustrative and testing purposes.

        storage = DictStorage()
        r = index.Index(storage, properties=settings)

        # Interestingly enough, if we take a look at the contents of our
        # storage now, we can see the Rtree has already written two pages
        # to it. This is for header and index.

        state1 = storage.dict.copy()
        self.assertEqual(list(state1.keys()), [0, 1])

        r.add(123, (0, 0, 1, 1))

        state2 = storage.dict.copy()
        self.assertNotEqual(state1, state2)

        item = list(r.nearest((0, 0), 1, objects=True))[0]
        self.assertEqual(item.id, 123)
        self.assertTrue(r.valid())
        self.assertTrue(isinstance(list(storage.dict.values())[0], bytes))

        r.delete(123, (0, 0, 1, 1))
        self.assertTrue(r.valid())

        r.clearBuffer()
        self.assertTrue(r.valid())

        del r

        storage.clear()
        self.assertFalse(storage.hasData)

        del storage

    def test_custom_storage_reopening(self) -> None:
        """Reopening custom index storage works as expected"""

        storage = DictStorage()
        r1 = index.Index(storage, overwrite=True)
        r1.add(555, (2, 2))
        del r1
        self.assertTrue(storage.hasData)

        r2 = index.Index(storage, overwrite=False)
        count = r2.count((0, 0, 10, 10))
        self.assertEqual(count, 1)
