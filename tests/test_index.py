import unittest
from rtree import index, core
import numpy as np
import pytest

def boxes15_stream(interleaved=True):
    boxes15 = np.genfromtxt('boxes_15x15.data')
    for i, (minx, miny, maxx, maxy) in enumerate(boxes15):
        
        if interleaved:
            yield (i, (minx, miny, maxx, maxy), 42)
        else:
            yield (i, (minx, maxx, miny, maxy), 42)


class IndexTests(unittest.TestCase):

    def test_stream_input(self):
        p = index.Property()
        sindex = index.Index(boxes15_stream(), properties=p)
        bounds = (0, 0, 60, 60)
        hits = sindex.intersection(bounds)
        self.assertEqual(sorted(hits), [0, 4, 16, 27, 35, 40, 47, 50, 76, 80])
    
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


class ExceptionTests(unittest.TestCase):
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