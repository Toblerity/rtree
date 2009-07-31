Rtree
=====

Whether for in-memory feature stores, Plone content, or whatever -- we need an
index to speed up the search for objects that intersect with a spatial bounding
box.  `R-trees`_ provide excellent query performance and good incremental 
insert performance.  

.. _`R-trees`: http://en.wikipedia.org/wiki/R-tree
.. _`ctypes`: http://docs.python.org/library/ctypes.html

`Rtree`_ is a Python library that uses `ctypes`_ and an internally built C API
to wrap `libspatialindex`_ and provide very flexible spatial indexing.
`Rtree`_ has gone through a number of iterations, and at 0.5.0, it was
completely refactored to use a new internal architecture (ctypes + a C API
over `libspatialindex`_). This refactoring has resulted in a number of new
features and much more flexibility. See CHANGES.txt_ for more detail.

.. _CHANGES.txt: http://trac.gispython.org/lab/browser/Rtree/trunk/CHANGES.txt


Index Protocol
--------------

In a nutshell::

  >>> from rtree import Rtree
  >>> idx = Rtree()
  >>> idx.add(id=id, bounds=(left, bottom, right, top))
  >>> [n for n in idx.intersection((left, bottom, right, top))]
  [id]

The following finds the 1 nearest item to the given bounds. If multiple items
are of equal distance to the bounds, both are returned::
  
  >>> sorted(idx.nearest((left, bottom, right, top), 1))
  [0L, 1L]  

This resembles a subset of the set protocol. *add* indexes a new object by id,
*intersection* returns an iterator over ids (or objects) where the node
containing the id intersects with the specified bounding box. The
*intersection* method is exact, with no false positives and no missed data.
Ids can be ints or long ints; index queries return long ints.


Pickles
**********

Rtree also supports inserting pickleable objects into the index (called a clustered 
index in `libspatialindex`_ parlance).  The following inserts the 
pickleable object ``42`` into the index with the given id::

  >>> index.add(id=id, bounds=(left, bottom, right, top), obj=42)

You can then return a list of objects by giving the ``objects=True`` flag
to intersection::

  >>> [n.object for n in index.intersection((left, bottom, right, top), objects=True)]
  42


3D indexes
**********

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
------------

\*nix 
********************

First, download and install version 1.4.0 of the `libspatialindex`_ library from:

http://trac.gispython.org/spatialindex/wiki/Releases

The library is a GNU-style build, so it is a matter of::

  $ ./configure; make; make install

You may need to run the ``ldconfig`` command after installing the library to 
ensure that applications can find it at startup time.  

At this point you can get Rtree 0.5.0 via easy_install::

  $ easy_install Rtree

or by running the local setup.py::

  $ python setup.py install

You can build and test in place like::

  $ python setup.py test

Windows 
********************

The Windows DLLs of both libsidx and `libspatialindex`_ are pre-compiled in 
windows installers that are available from `PyPI`_.  Installation on Windows 
is as easy as::

  c:\python2x\scripts\easy_install.exe Rtree


Usage
-----

See `tests/index.txt`_ for more detail on index usage and `tests/properties.txt`_ 
for index properties that can be set and manipulated.  Refer to `libspatialindex`_ 
documentation or code for more detail on their meanings and usage.

.. _tests/index.txt: http://trac.gispython.org/lab/browser/Rtree/trunk/tests/index.txt
.. _tests/properties.txt: http://trac.gispython.org/lab/browser/Rtree/trunk/tests/properties.txt

Performance
------------

See the tests/benchmarks.py file for a comparison.

Support
-------

For current information about this project, see the wiki_.

.. _wiki: http://trac.gispython.org/lab/wiki/Rtree

If you have questions, please consider joining our community list:

http://lists.gispython.org/mailman/listinfo/community

.. _`libspatialindex`: http://research.att.com/~marioh/spatialindex/index.html  
.. _`PyPI`: http://pypi.python.org/pypi/Rtree/
