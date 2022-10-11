# Rtree: Spatial indexing for Python

![Build](https://github.com/Toblerity/rtree/workflows/Build/badge.svg)
[![PyPI version](https://badge.fury.io/py/Rtree.svg)](https://badge.fury.io/py/Rtree)


Rtree is a [ctypes](http://docs.python.org/library/ctypes.html) Python wrapper of [libspatialindex](https://libspatialindex.org/) that provides a
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

# Changes

## 1.0.1

* Fix up type hints #243 (thanks @oderby)
* Python 3.11 wheels #250 (thanks @ewouth)

## 1.0.0


* Python 3.7+ is now required (#212) (thanks @adamjstewart!)
* Type hints (#215 and others) (thanks @adamjstewart!)
* Python 3.10 wheels, including osx-arm64 #224
* Clean up libspatialindex C API mismatches #222 (thanks @musicinmybrain!)
* Many doc updates, fixes, and type hints (thanks @adamjstewart!) #212 #221 #217 #215
* __len__ method for index #194
* Prevent get_coordinate_pointers from mutating inputs #205 (thanks @sjones94549!)
* linux-aarch64 wheels #183 (thanks @odidev!)
* black (#218) and flake8 (#145) linting

https://github.com/Toblerity/rtree/releases/1.0.0
