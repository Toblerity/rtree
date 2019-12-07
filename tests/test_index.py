import unittest
from rtree import index, core
import numpy as np
import pytest
import tempfile


class IndexTestCase(unittest.TestCase):
    def setUp(self):
        self.boxes15 = np.genfromtxt('boxes_15x15.data')
        self.idx = index.Index()
        for i, coords in enumerate(self.boxes15):
            self.idx.add(i, coords)

    def boxes15_stream(interleaved=True):
        boxes15 = np.genfromtxt('boxes_15x15.data')
        for i, (minx, miny, maxx, maxy) in enumerate(boxes15):

            if interleaved:
                yield (i, (minx, miny, maxx, maxy), 42)
            else:
                yield (i, (minx, maxx, miny, maxy), 42)


class IndexVersion(unittest.TestCase):

    def test_libsidx_version(self):
        self.assertTrue(index.major_version == 1)
        self.assertTrue(index.minor_version >= 7)

class IndexProperties(unittest.TestCase):

    @pytest.mark.skipif(
        not hasattr(core.rt, 'Index_GetResultSetOffset'),
        reason="Index_GetResultsSetOffset required in libspatialindex")
    def test_result_offset(self):
        idx = index.Rtree()
        idx.set_result_offset(3)
        self.assertEqual(idx.result_offset, 3)

    @pytest.mark.skipif(
        not hasattr(core.rt, 'Index_GetResultSetLimit'),
        reason="Index_GetResultsSetOffset required in libspatialindex")
    def test_result_limit(self):
        idx = index.Rtree()
        idx.set_result_limit(44)
        self.assertEqual(idx.result_limit, 44)

class IndexIntersection(IndexTestCase):
    def test_intersection(self):
        """Test basic insertion and retrieval"""

        self.assertTrue(0 in self.idx.intersection((0, 0, 60, 60)))
        hits = list(self.idx.intersection((0, 0, 60, 60)))

        self.assertTrue(len(hits), 10)
        self.assertEqual(hits, [0, 4, 16, 27, 35, 40, 47, 50, 76, 80])

    def test_pickle(self):
        """Test insertion of objects"""

        idx = index.Index()
        for i, coords in enumerate(self.boxes15):
            idx.add(i, coords)
        idx.insert(4321, (34.3776829412, 26.7375853734, 49.3776829412, 41.7375853734), obj=42)
        hits = idx.intersection((0, 0, 60, 60), objects=True)
        hit = [h for h in hits if h.id == 4321][0]
        self.assertEqual(hit.id, 4321)
        self.assertEqual(hit.object, 42)
        box = ['%.10f' % t for t in hit.bbox]
        expected = ['34.3776829412', '26.7375853734', '49.3776829412', '41.7375853734']
        self.assertEqual(box, expected)

class IndexSerialization(unittest.TestCase):

    def setUp(self):
        self.boxes15 = np.genfromtxt('boxes_15x15.data')
        self.tname = tempfile.mktemp()

    def boxes15_stream(interleaved=True):
        boxes15 = np.genfromtxt('boxes_15x15.data')
        for i, (minx, miny, maxx, maxy) in enumerate(boxes15):

            if interleaved:
                yield (i, (minx, miny, maxx, maxy), 42)
            else:
                yield (i, (minx, maxx, miny, maxy), 42)

    def test_custom_filenames(self):
        """Test using custom filenames for index serialization"""
        p = index.Property()
        p.dat_extension = 'data'
        p.idx_extension = 'index'
        tname = tempfile.mktemp()
        idx = index.Index(self.tname, properties = p)
        for i, coords in enumerate(self.boxes15):
            idx.add(i, coords)

        hits = list(idx.intersection((0, 0, 60, 60)))
        self.assertTrue(len(hits), 10)
        self.assertEqual(hits, [0, 4, 16, 27, 35, 40, 47, 50, 76, 80])
        del idx

        # Check we can reopen the index and get the same results
        idx2 = index.Index(self.tname, properties = p)
        hits = list(idx2.intersection((0, 0, 60, 60)))
        self.assertTrue(len(hits), 10)
        self.assertEqual(hits, [0, 4, 16, 27, 35, 40, 47, 50, 76, 80])


class IndexNearest(IndexTestCase):

    def test_nearest_basic(self):
        """Test nearest basic selection of records"""
        hits = list(self.idx.nearest((0,0,10,10), 3))
        self.assertEqual(hits, [76, 48, 19])

        idx = index.Index()
        locs = [(2, 4), (6, 8), (10, 12), (11, 13), (15, 17), (13, 20)]
        for i, (start, stop) in enumerate(locs):
            idx.add(i, (start, 1, stop, 1))
        hits = sorted(idx.nearest((13, 0, 20, 2), 3))
        self.assertEqual(hits, [3, 4, 5])


    def test_nearest_object(self):
        """Test nearest object selection of records"""
        idx = index.Index()
        locs = [(14, 10, 14, 10), (16, 10, 16, 10)]
        for i, (minx, miny, maxx, maxy) in enumerate(locs):
            idx.add(i, (minx, miny, maxx, maxy), obj={'a': 42})

        hits = sorted([(i.id, i.object) for i in idx.nearest((15, 10, 15, 10), 1, objects=True)])
        self.assertEqual(hits, [(0, {'a': 42}), (1, {'a': 42})])

class IndexDelete(IndexTestCase):

    def test_deletion(self):
        """Test we can delete data from the index"""
        idx = index.Index()
        for i, coords in enumerate(self.boxes15):
            idx.add(i, coords)

        for i, coords in enumerate(self.boxes15):
            idx.delete(i, coords)

        hits = list(idx.intersection((0, 0, 60, 60)))
        self.assertEqual(hits, [])


class IndexMoreDimensions(IndexTestCase):
    def test_3d(self):
        """Test we make and query a 3D index"""
        p = index.Property()
        p.dimension = 3
        idx = index.Index(properties = p, interleaved = False)
        idx.insert(1, (0, 0, 60, 60, 22, 22.0))
        hits = idx.intersection((-1, 1, 58, 62, 22, 24))
        self.assertEqual(list(hits), [1])
    def test_4d(self):
        """Test we make and query a 4D index"""
        p = index.Property()
        p.dimension = 4
        idx = index.Index(properties = p, interleaved = False)
        idx.insert(1, (0, 0, 60, 60, 22, 22.0, 128, 142))
        hits = idx.intersection((-1, 1, 58, 62, 22, 24, 120, 150))
        self.assertEqual(list(hits), [1])


class IndexStream(IndexTestCase):

    def test_stream_input(self):
        p = index.Property()
        sindex = index.Index(self.boxes15_stream(), properties=p)
        bounds = (0, 0, 60, 60)
        hits = sindex.intersection(bounds)
        self.assertEqual(sorted(hits), [0, 4, 16, 27, 35, 40, 47, 50, 76, 80])
        objects = list(sindex.intersection((0, 0, 60, 60), objects=True))

        self.assertEqual(len(objects), 10)
        self.assertEqual(objects[0].object, 42)

    def test_empty_stream(self):
        """Assert empty stream raises exception"""
        self.assertRaises(core.RTreeError, index.Index, ((x for x in [])))

    def test_exception_in_generator(self):
        """Assert exceptions raised in callbacks are raised in main thread"""
        class TestException(Exception):
            pass

        def create_index():
            def gen():
                # insert at least 6 or so before the exception
                for i in range(10):
                    yield (i, (1,2,3,4), None)
                raise TestException("raising here")
            return index.Index(gen())

        self.assertRaises(TestException, create_index)

    def test_exception_at_beginning_of_generator(self):
        """Assert exceptions raised in callbacks before generator function are raised in main thread"""
        class TestException(Exception):
            pass

        def create_index():
            def gen():

                raise TestException("raising here")
            return index.Index(gen())

        self.assertRaises(TestException, create_index)
