import pickle
import unittest
import rtree.index


class TestPickling(unittest.TestCase):

    def test_index(self):
        idx = rtree.index.Index()
        unpickled = pickle.loads(pickle.dumps(idx))
        self.assertNotEquals(idx.handle, unpickled.handle)
        self.assertEquals(idx.properties.as_dict(),
                          unpickled.properties.as_dict())
        self.assertEquals(idx.interleaved, unpickled.interleaved)

    def test_property(self):
        p = rtree.index.Property()
        unpickled = pickle.loads(pickle.dumps(p))
        self.assertNotEquals(p.handle, unpickled.handle)
        self.assertEquals(p.as_dict(), unpickled.as_dict())
