import unittest

import numpy as np

from rtree import index


class IndexTests(unittest.TestCase):

    def test_stream_input(self):
        p = index.Property()
        sindex = index.Index(boxes15_stream(), properties=p)
        bounds = (0, 0, 60, 60)
        hits = sindex.intersection(bounds)
        self.assertEqual(sorted(hits), [0, 4, 16, 27, 35, 40, 47, 50, 76, 80])


def boxes15_stream(interleaved=True):
    boxes15 = np.genfromtxt('boxes_15x15.data')
    for i, (minx, miny, maxx, maxy) in enumerate(boxes15):
        if interleaved:
            yield (i, (minx, miny, maxx, maxy), 42)
        else:
            yield (i, (minx, maxx, miny, maxy), 42)
