.. _installation:

Installation
------------------------------------------------------------------------------

\*nix
..............................................................................

First, download and install version 1.8.5+ of the `libspatialindex`_ library from:

https://libspatialindex.org/

The library is a GNU-style build, so it is a matter of::

  $ ./configure; make; make install

You may need to run the ``ldconfig`` command after installing the library to
ensure that applications can find it at startup time.

At this point you can get Rtree 0.7.0 via easy_install::

  $ easy_install Rtree

or by running the local setup.py::

  $ python setup.py install

You can build and test in place like::

  $ python setup.py test

Windows
..............................................................................

The Windows DLLs of `libspatialindex`_ are pre-compiled in
windows installers that are available from `PyPI`_.  Installation on Windows
is as easy as::

  c:\python2x\scripts\easy_install.exe Rtree


.. _`PyPI`: http://pypi.python.org/pypi/Rtree/
.. _`Rtree`: http://pypi.python.org/pypi/Rtree/

.. _`libspatialindex`: https://libspatialindex.org/
