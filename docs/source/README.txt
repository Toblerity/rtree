Rtree: Spatial indexing for Python
------------------------------------------------------------------------------

`Rtree`_ is a `ctypes`_ Python wrapper of `libspatialindex`_ that provides a 
number of advanced spatial indexing features for the spatially curious Python 
user.  These features include:

* Nearest neighbor search
* Intersection search
* Multi-dimensional indexes
* Clustered indexes (store Python pickles directly with index entries)
* Bulk loading
* Deletion
* Disk serialization
* Custom storage implementation (to implement spatial indexing in ZODB, for example)

Documentation and Website
..............................................................................

https://rtree.readthedocs.io/en/latest/

Requirements
..............................................................................

* `libspatialindex`_ 1.8.5+.

Download
..............................................................................

* PyPI http://pypi.python.org/pypi/Rtree/
* Windows binaries http://www.lfd.uci.edu/~gohlke/pythonlibs/#rtree

Development
..............................................................................

* https://github.com/Toblerity/Rtree

.. _`R-trees`: http://en.wikipedia.org/wiki/R-tree
.. _`ctypes`: http://docs.python.org/library/ctypes.html
.. _`libspatialindex`: http://libspatialindex.github.com
.. _`Rtree`: http://toblerity.github.com/rtree/
