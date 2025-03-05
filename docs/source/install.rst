.. _installation:

Installation
------------------------------------------------------------------------------

\*nix
..............................................................................

First, download and install version 1.8.5+ of the `libspatialindex`_ library from:

https://libspatialindex.org

The library supports CMake builds, so it is a matter of::

  $ mkdir build && cd build
  $ cmake ..
  $ cmake --build . -j
  $ cmake --install .

You may need to run the ``ldconfig`` command after installing the library to
ensure that applications can find it at startup time.

Rtree can be easily installed via pip::

  $ pip install rtree

or by running in a local source directory::

  $ pip install -e .

You can build and test in place like::

  $ pytest

Windows
..............................................................................

The Windows DLLs of `libspatialindex`_ are pre-compiled in
windows installers that are available from `PyPI`_.  Installation on Windows
is as easy as::

  pip install rtree


.. _`PyPI`: https://pypi.org/project/rtree/
.. _`libspatialindex`: https://libspatialindex.org
