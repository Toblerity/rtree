# Rtree: Spatial indexing for Python

![Build](https://github.com/Toblerity/rtree/workflows/Build/badge.svg)
[![PyPI version](https://badge.fury.io/py/Rtree.svg)](https://badge.fury.io/py/Rtree)


Rtree is a [ctypes](https://docs.python.org/3/library/ctypes.html) Python wrapper of [libspatialindex](https://libspatialindex.org/) that provides a
number of advanced spatial indexing features for the spatially curious Python
user.  These features include:

* Nearest neighbor search
* Intersection search
* Multi-dimensional indexes
* Clustered indexes (store Python pickles directly with index entries)
* Bulk loading
* Deletion
* ~~Disk serialization~~ [currently broken as of Jan 2024](https://github.com/Toblerity/rtree/pull/197)
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

Wheels are available for most major platforms, and `rtree` with bundled `libspatialindex` can be installed via pip:

```
pip install rtree
```

See [changes](https://rtree.readthedocs.io/en/latest/changes.html) for all versions.
