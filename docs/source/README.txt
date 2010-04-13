.. _home:

Rtree: Spatial indexing for Python
------------------------------------------------------------------------------

`R-trees`_ possess excellent query performance, good incremental 
insert performance, and great flexibility in the spatial indexing algorithms 
world.  

.. _`R-trees`: http://en.wikipedia.org/wiki/R-tree
.. _`ctypes`: http://docs.python.org/library/ctypes.html

`Rtree`_ is a Python library that uses `ctypes`_ 
to wrap `libspatialindex`_.
`Rtree`_ has gone through a number of iterations, and at 0.5.0, it was
completely refactored to use a new internal architecture (ctypes + a C API
over `libspatialindex`_). This refactoring has resulted in a number of new
features and much more flexibility. See CHANGES.txt_ for more detail.

Rtree 0.6.0+ requires `libspatialindex`_ 1.5.0+ to work.  Rtree 0.5.0 included 
a C library that is now the C API for libspatialindex and is part of that 
source tree.  The code bases  are independent from each other and can now 
evolve separately.  Rtree is now pure Python.

.. _Rtree: http://pypi.python.org/pypi/Rtree/
.. _CHANGES.txt: http://trac.gispython.org/lab/browser/Rtree/trunk/CHANGES.txt


Index Protocol
------------------------------------------------------------------------------

In a nutshell::

  >>> from rtree import Rtree
  >>> idx = Rtree()
  >>> minx, miny, maxx, maxy = (0.0, 0.0, 1.0, 1.0)
  >>> idx.add(0, (minx, miny, maxx, maxy))
  >>> list(idx.intersection((1.0, 1.0, 2.0, 2.0)))
  [0L]
  >>> list(idx.intersection((1.0000001, 1.0000001, 2.0, 2.0)))
  []

The following finds the 1 nearest item to the given bounds. If multiple items
are of equal distance to the bounds, both are returned::
  
  >>> idx.add(1, (minx, miny, maxx, maxy))
  >>> list(idx.nearest((1.0000001, 1.0000001, 2.0, 2.0), 1))
  [0L, 1L]

This resembles a subset of the set protocol. *add* indexes a new object by id,
*intersection* returns an iterator over ids (or objects) where the node
containing the id intersects with the specified bounding box. The
*intersection* method is exact, with no false positives and no missed data.
Ids can be ints or long ints; index queries return long ints.


Pickles
..............................................................................

Rtree also supports inserting pickleable objects into the index (called a clustered 
index in `libspatialindex`_ parlance).  The following inserts the 
pickleable object ``42`` into the index with the given id::

  >>> index.add(id=id, bounds=(left, bottom, right, top), obj=42)

You can then return a list of objects by giving the ``objects=True`` flag
to intersection::

  >>> [n.object for n in index.intersection((left, bottom, right, top), objects=True)]
  42


3D indexes
..............................................................................

As of Rtree version 0.5.0, you can create 3D (actually kD) `R-trees`_. The
following is a 3D index that is to be stored on disk. Persisted indexes are
stored on disk using two files -- an index file (.idx) and a data (.dat) file.
You can modify the extensions these files use by altering the properties of
the index at instantiation time. The following creates a 3D index that is
stored on disk as the files ``3d_index.data`` and ``3d_index.index``::

  >>> from rtree import index
  >>> p = index.Property()
  >>> p.dimension = 3
  >>> p.dat_extension = 'data'
  >>> p.idx_extension = 'index'  
  >>> idx3d = index.Index('3d_index',properties=p)
  >>> idx3d.insert(1, (0, 0, 60, 60, 23.0, 42.0))
  >>> idx3d.intersection( (-1, -1, 62, 62, 22, 43))
  [1L]

Installation
------------------------------------------------------------------------------

\*nix 
..............................................................................

First, download and install version 1.5.0 of the `libspatialindex`_ library from:

http://trac.gispython.org/spatialindex/wiki/Releases

The library is a GNU-style build, so it is a matter of::

  $ ./configure; make; make install

You may need to run the ``ldconfig`` command after installing the library to 
ensure that applications can find it at startup time.  

At this point you can get Rtree 0.6.0 via easy_install::

  $ easy_install Rtree

or by running the local setup.py::

  $ python setup.py install

You can build and test in place like::

  $ python setup.py test

Windows 
..............................................................................

The Windows DLLs of both libsidx and `libspatialindex`_ are pre-compiled in 
windows installers that are available from `PyPI`_.  Installation on Windows 
is as easy as::

  c:\python2x\scripts\easy_install.exe Rtree


Usage
------------------------------------------------------------------------------

See `tests/index.txt`_ for more detail on index usage and `tests/properties.txt`_ 
for index properties that can be set and manipulated.  Refer to `libspatialindex`_ 
documentation or code for more detail on their meanings and usage.

.. _tests/index.txt: http://trac.gispython.org/lab/browser/Rtree/trunk/tests/index.txt
.. _tests/properties.txt: http://trac.gispython.org/lab/browser/Rtree/trunk/tests/properties.txt

Performance
------------------------------------------------------------------------------

See the `tests/benchmarks.py`_ file for a comparison.

.. _tests/benchmarks.py: http://trac.gispython.org/lab/browser/Rtree/trunk/tests/benchmarks.py

There are a few simple things that will improve performance.

 - Use stream loading. This will substantially (orders of magnitude in many cases) 
   improve performance over Rtree.insert by allowing the data to be pre-sorted 
   

   .. code-block:: python

       >>> def generator_function():
       ...    for i, obj in enumerate(somedata):
       ...        yield (i, (obj.xmin, obj.ymin, obj.xmax, obj.ymax), obj)
       >>> r = Rtree(generator_function())

   .. note::
        After bulk loading the index, you can then insert additional records into 
        the index using :meth:`rtree.index.insert()`

 - Override Rtree.dumps() to use the highest pickle protocol ::

    >>> import cPickle, rtree
    >>> class FastRtree(rtree.Rtree):
    ...     def dumps(self, obj):
    ...         return cPickle.dumps(obj, -1)
    >>> r = FastRtree()


 - In any query, use objects='raw' keyword argument ::

    >>> objs = r.intersection((xmin, ymin, xmax, ymax), objects="raw")

 - Adjust :class:`rtree.index.Property` appropriate to your index.

   * Set your leaf_capacity to a higher value than the default 100.  1000+ is 
     fine for the default pagesize of 4096 in many cases.

   * Increase the fill_factor to something near 0.9.  Smaller fill factors 
     mean more splitting, which means more nodes.  This may be bad or good 
     depending on your usage.
   
 - Don't use more dimensions than you actually need. If you only need 2,
   only use two. Otherwise, you will waste lots of storage and add that 
   many more floating point comparisons for each query, search, and insert 
   operation of the index.
 
 - Use :meth:`rtree.index.Index.count` if you only need a count and :meth:`rtree.index.Index.intersection` 
   if you only need the ids.  Otherwise, lots of data may potentially be copied.

Support
------------------------------------------------------------------------------

For current information about this project, see the wiki_.

.. _wiki: http://trac.gispython.org/lab/wiki/Rtree

If you have questions, please consider joining our community list:

http://lists.gispython.org/mailman/listinfo/community

.. _`libspatialindex`: http://research.att.com/~marioh/spatialindex/index.html  
.. _`PyPI`: http://pypi.python.org/pypi/Rtree/
