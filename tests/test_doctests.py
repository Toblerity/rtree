import doctest
import unittest
import glob
import os

doctest.IGNORE_EXCEPTION_DETAIL

# from zope.testing import doctest
from rtree.index import major_version, minor_version  # , patch_version

from .data import boxes15, boxes3, points

optionflags = (doctest.REPORT_ONLY_FIRST_FAILURE |
               doctest.NORMALIZE_WHITESPACE |
               doctest.ELLIPSIS)


def list_doctests():
    # Skip the custom storage test unless we have libspatialindex 1.8+.
    return [filename
            for filename
            in glob.glob(os.path.join(os.path.dirname(__file__), '*.txt'))
            if not (
                filename.endswith('customStorage.txt')
                and major_version < 2 and minor_version < 8)]


def open_file(filename, mode='r'):
    """Helper function to open files from within the tests package."""
    return open(os.path.join(os.path.dirname(__file__), filename), mode)


def setUp(test):
    test.globs.update(dict(
        open_file=open_file,
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

if __name__ == "__main__":
    runner = unittest.TextTestRunner()
    runner.run(test_suite())
