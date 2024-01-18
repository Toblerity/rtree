.. _changes:

Changes
..............................................................................

0.9.3: 2019-12-10
=================

- find_library and libspatialindex library loading https://github.com/Toblerity/rtree/pull/131

0.9.2: 2019-12-09
=================

- Refactored tests to be based on unittest https://github.com/Toblerity/rtree/pull/129
- Update libspatialindex library loading code to adapt previous behavior https://github.com/Toblerity/rtree/pull/128
- Empty data streams throw exceptions and do not partially construct indexes https://github.com/Toblerity/rtree/pull/127

0.9.0: 2019-11-24
=================

- Add Index.GetResultSetOffset()
- Add Index.contains() method for object and id (requires libspatialindex 1.9.3+) #116
- Add Index.Flush() #107
- Add TPRTree index support (thanks @sdhiscocks #117 )
- Return container sizes without returning objects #90
- Add set_result_limit and set_result_offset for Index paging  44ad21aecd3f7b49314b9be12f3334d8bae7e827

Bug fixes:

- Better exceptions in cases where stream functions throw #80
- Migrated CI platform to Azure Pipelines  https://dev.azure.com/hobuinc/rtree/_build?definitionId=5
- Minor test enhancements and fixups. Both libspatialindex 1.8.5 and libspatialindex 1.9.3 are tested with CI



0.8: 2014-07-17
===============

- Support for Python 3 added.

0.7.0: 2011-12-29
=================

- 0.7.0 relies on libspatialindex 1.7.1+.
- int64_t's should be used for IDs instead of uint64_t (requires libspatialindex 1.7.1 C API changes)
- Fix __version__
- More documentation at http://toblerity.github.com/rtree/
- Class documentation at http://toblerity.github.com/rtree/class.html
- Tweaks for PyPy compatibility. Still not compatible yet, however.
- Custom storage support by Mattias (requires libspatialindex 1.7.1)

0.6.0: 2010-04-13
=================

- 0.6.0 relies on libspatialindex 1.5.0+.
- :py:meth:`~rtree.index.Index.intersection` and :py:meth:`~rtree.index.Index.nearest` methods return iterators over results instead of
  lists.
- Number of results for :py:meth:`~rtree.index.Index.nearest` defaults to 1.
- libsidx C library of 0.5.0 removed and included in libspatialindex
- objects="raw" in :py:meth:`~rtree.index.Index.intersection` to return the object sent in (for speed).
- :py:meth:`~rtree.index.Index.count` method to return the intersection count without the overhead
  of returning a list (thanks Leonard Norrgård).
- Improved bulk loading performance
- Supposedly no memory leaks :)
- Many other performance tweaks (see docs).
- Bulk loader supports interleaved coordinates
- Leaf queries.  You can return the box and ids of the leaf nodes of the index.
  Useful for visualization, etc.
- Many more docstrings, sphinx docs, etc


0.5.0: 2009-08-XX
=================

0.5.0 was a complete refactoring to use libsidx - a C API for libspatialindex.
The code is now ctypes over libsidx, and a number of new features are now
available as a result of this refactoring.

* ability to store pickles within the index (clustered index)
* ability to use custom extension names for disk-based indexes
* ability to modify many index parameters at instantiation time
* storage of point data reduced by a factor of 4
* bulk loading of indexes at instantiation time
* ability to quickly return the bounds of the entire index
* ability to return the bounds of index entries
* much better windows support
* libspatialindex 1.4.0 required.

0.4.3: 2009-06-05
=================
- Fix reference counting leak #181

0.4.2: 2009-05-25
=================
- Windows support

0.4.1: 2008-03-24
=================

- Eliminate uncounted references in add, delete, nearestNeighbor (#157).

0.4: 2008-01-24
===============

- Testing improvements.
- Switch dependency to the single consolidated spatialindex library (1.3).

0.3: 26 November 2007
=====================
- Change to Python long integer identifiers (#126).
- Allow deletion of objects from indexes.
- Reraise index query errors as Python exceptions.
- Improved persistence.

0.2:
==================
- Link spatialindex system library.

0.1: 13 April 2007
==================
- Add disk storage option for indexes (#320).
- Change license to LGPL.
- Moved from Pleiades to GIS-Python repo.
- Initial release.
