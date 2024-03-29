.. _home:

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

Documentation
..............................................................................

.. toctree::
   :maxdepth: 2

   install
   tutorial
   class
   misc
   changes
   performance
   history

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _`R-trees`: https://en.wikipedia.org/wiki/R-tree
.. _`ctypes`: https://docs.python.org/3/library/ctypes.html
.. _`libspatialindex`: https://libspatialindex.org
.. _`Rtree`: https://rtree.readthedocs.io
