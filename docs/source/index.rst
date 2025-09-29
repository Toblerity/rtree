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
* Disk serialization (`currently broken as of Jan 2024`_)
* Custom storage implementation (to implement spatial indexing in ZODB, for example)

These features do not include:

* Multithread safety (for reading or writing)
* Multiprocess safety (for reading or writing)

For either of these, we recommend using:

* A PostGIS database, or
* GeoPandas + spatial joining, or
* Building an rtree from scratch in each thread/process (using [generator syntax](https://rtree.readthedocs.io/en/latest/performance.html#use-stream-loading))

Note that since rtree is written in C, it can be orders of magnitude faster than a
database even if running sequentially.

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

.. _`currently broken as of Jan 2024`: https://github.com/Toblerity/rtree/pull/197
.. _`R-trees`: https://en.wikipedia.org/wiki/R-tree
.. _`ctypes`: https://docs.python.org/3/library/ctypes.html
.. _`libspatialindex`: https://libspatialindex.org
.. _`Rtree`: https://rtree.readthedocs.io
