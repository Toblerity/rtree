import doctest
import unittest
import glob
import os

#from zope.testing import doctest
from rtree.index import __c_api_version__
from .data import boxes15, boxes3, points

optionflags = (doctest.REPORT_ONLY_FIRST_FAILURE |
               doctest.NORMALIZE_WHITESPACE |
               doctest.ELLIPSIS)

sindex_version = tuple(map(int, 
    __c_api_version__.decode('utf-8').split('.')))

def list_doctests():
    # Skip the custom storage test unless we have libspatialindex 1.8+.
    return [filename
            for filename
            in glob.glob(os.path.join(os.path.dirname(__file__), '*.txt'))
            if not (
                filename.endswith('customStorage.txt') 
                and sindex_version < (1,8,0))]

def open_file(filename, mode='r'):
    """Helper function to open files from within the tests package."""
    return open(os.path.join(os.path.dirname(__file__), filename), mode)

def setUp(test):
    test.globs.update(dict(
            open_file = open_file,
            boxes15=boxes15,
            boxes3=boxes3,
            points=points
            ))

def test_suite():
    return unittest.TestSuite(
        [doctest.DocFileSuite(os.path.basename(filename),
                              optionflags=optionflags,
                              setUp=setUp)
         for filename
         in sorted(list_doctests())])

print(list_doctests())

if __name__ == "__main__":
    runner = unittest.TextTestRunner()
    runner.run(test_suite())
