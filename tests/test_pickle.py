import pickle
import unittest
import rtree.index


class TestPickling(unittest.TestCase):

    def test_index(self):
        idx = rtree.index.Index()
        unpickled = pickle.loads(pickle.dumps(idx))
        self.assertNotEqual(idx.handle, unpickled.handle)
        self.assertEqual(idx.properties.as_dict(),
                          unpickled.properties.as_dict())
        self.assertEqual(idx.interleaved, unpickled.interleaved)

    def test_property(self):
        p = rtree.index.Property()
        unpickled = pickle.loads(pickle.dumps(p))
        self.assertNotEqual(p.handle, unpickled.handle)
        self.assertEqual(p.as_dict(), unpickled.as_dict())
