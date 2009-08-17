import doctest
import unittest
import glob
import os

#from zope.testing import doctest
from data import boxes15, boxes3, points

optionflags = (doctest.REPORT_ONLY_FIRST_FAILURE |
               doctest.NORMALIZE_WHITESPACE |
               doctest.ELLIPSIS)

def list_doctests():
    return [filename
            for filename
            in glob.glob(os.path.join(os.path.dirname(__file__), '*.txt'))]

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

if __name__ == "__main__":
    runner = unittest.TextTestRunner()
    runner.run(test_suite())
