# Rtree: Spatial indexing for Python

![Build](https://github.com/Toblerity/rtree/workflows/Build/badge.svg)
[![PyPI version](https://badge.fury.io/py/rtree.svg)](https://badge.fury.io/py/rtree)


Rtree is a [ctypes](https://docs.python.org/3/library/ctypes.html) Python wrapper of [libspatialindex](https://libspatialindex.org/) that provides a
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


Wheels are available for most major platforms, and `rtree` with bundled `libspatialindex` can be installed via pip:

```
pip install rtree
```

See [changes](https://rtree.readthedocs.io/en/latest/changes.html) for all versions.
