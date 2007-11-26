Rtree
=====

Whether for in-memory feature stores, Plone content, or whatever -- we need an
index to speed up the search for objects that intersect with a spatial bounding
box.


Index Protocol
--------------

In a nutshell::

  >>> from rtree import Rtree
  >>> index = Rtree()
  >>> index.add(id=id, bounds=(left, bottom, right, top))
  >>> [n for n in index.intersection((left, bottom, right, top))]
  [id]

This resembles a subset of the set protocol. *add* indexes a new object by id,
*intersection* returns an iterator over ids where the node containing the id
intersects with the specified bounding box.  The *intersection* method is
exact, with no false positives and no missed data. Ids can be ints or long
ints; index queries return long ints.


Installation
------------

First, obtain and install a copy of both spatialindex and tools libraries from:

http://research.att.com/~marioh/tools/index.html

http://research.att.com/~marioh/spatialindex/index.html  

Rtree version 0.3 depends upon spatialindex version 1.1.1. Each library is a
GNU-style build, so it should just be a matter of::

  $ CPPFLAGS=-DNDEBUG ./configure; make; make install

for each. Debugging is on by default in 1.1.1, you'll want to turn it off for
use in production. The spatialindex library depends on the tools library, so
make sure to build and install that first.

The command::

  $ python setup.py install

installs an egg. You can build and test in place like so::

  $ python setup.py test


Usage
-----

See `tests/R-Tree.txt`_.

.. _tests/R-Tree.txt: http://trac.gispython.org/projects/PCL/browser/Rtree/trunk/tests/R-Tree.txt

Performance
-----------

See the tests/benchmarks.py file for a comparison.

Support
-------

For current information about this project, see the wiki_.

.. _wiki: http://trac.gispython.org/projects/PCL/wiki/RTree

If you have questions, please consider joining our community list:

http://trac.gispython.org/projects/PCL/wiki/CommunityList

