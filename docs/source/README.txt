Rtree: Spatial indexing for Python
------------------------------------------------------------------------------

`R-trees`_ possess excellent query performance, good incremental 
insert performance, and great flexibility in the spatial indexing algorithms 
world.  

`Rtree`_ is a `ctypes`_ Python wrapper of `libspatialindex`_ that provides a 
number of advanced spatial indexing features for the spatially curious Python 
user.  These features include:

Features
..............................................................................

* Nearest neighbor search
* Intersection search
* Multi-dimensional indexes
* Clustered indexes (store Python pickles directly with index entries)
* Bulk loading
* Deletion
* Disk serialization
* Custom backend implementation



Requirements
..............................................................................

* `libspatialindex`_ 1.7.0+.

Download
..............................................................................

* PyPI http://pypi.python.org/pypi/Rtree/


.. _`R-trees`: http://en.wikipedia.org/wiki/R-tree
.. _`ctypes`: http://docs.python.org/library/ctypes.html
.. _`libspatialindex`: http://libspatialindex.github.com
.. _`Rtree`: http://rtree.github.com
