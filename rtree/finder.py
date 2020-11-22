"""
finder.py
------------

Locate `libspatialindex` shared library by any means necessary.
"""
import os
import sys
import platform
import ctypes

from ctypes.util import find_library

# the current working directory of this file
_cwd = os.path.abspath(os.path.expanduser(
    os.path.dirname(__file__)))


def load():
    """
    Load the `libspatialindex` shared library.

    Returns
    -----------
    rt : ctypes object
      Loaded shared library
    """
    if os.name == 'nt':
        def _load_library(dllname, loadfunction, dllpaths):
            """
            Load a DLL via ctypes load function. Return None on failure.
            Try loading the DLL from the current package directory first,
            then from the Windows DLL search path.
            """
            for path in dllpaths:
                if not path or not os.path.exists(path):
                    continue
                # temporarily add the path to the PATH environment variable
                # so Windows can find additional DLL dependencies.
                try:
                    oldenv = os.environ['PATH']
                    os.environ['PATH'] = path + ';' + oldenv
                except KeyError:
                    oldenv = None
                try:
                    return loadfunction(os.path.join(
                        path, dllname))
                except (WindowsError, OSError) as E:
                    pass
                except BaseException as E:
                    print('rtree.finder unexpected error: {}'.format(str(E)))
                finally:
                    if path and oldenv is not None:
                        os.environ['PATH'] = oldenv
            return None

        if '64' in platform.architecture()[0]:
            arch = '64'
        else:
            arch = '32'

        lib_name = 'spatialindex_c-{}.dll'.format(arch)
        # generate a bunch of candidate locations where the
        # libspatialindex DLL *might* be hanging out
        candidates = [os.environ.get('SPATIALINDEX_C_LIBRARY', None),
                      _cwd,
                      os.path.join(_cwd, 'lib'),
                      os.path.join(sys.prefix, "Library", "bin"),
                      '']
        # run through our list of candidate locations
        rt = _load_library(
            lib_name, ctypes.cdll.LoadLibrary, candidates)

        if not rt:
            raise OSError("could not find or load {}".format(lib_name))

    elif os.name == 'posix':
        # generate a bunch of candidate locations where the
        # libspatialindex_c.so *might* be hanging out
        candidates = [os.environ.get('SPATIALINDEX_C_LIBRARY', None),
                      find_library('spatialindex_c'),
                      _cwd,
                      os.path.join(_cwd, 'lib'),
                      '']
        cwd = os.getcwd()
        for c in candidates:
            if c is None:
                continue
            elif os.path.isdir(c):
                # if our candidate is a directory use best gurss
                path = c
                target = os.path.join(c, "libspatialindex_c.so")
            elif os.path.isfile(c):
                # if it's a straight file use that
                path = os.path.split(c)[0]
                target = c
            else:
                continue

            # chage the working directory to our shared library candidate
            # location
            os.chdir(path)
            try:
                # try loading the target file candidate
                rt = ctypes.cdll.LoadLibrary(target)
            except BaseException as E:
                print(c, E)
                rt = None
            finally:
                os.chdir(cwd)
            if rt:
                return rt

        if not rt:
            raise OSError("Could not load libspatialindex_c library")
    else:
        raise OSError("Could not load libspatialindex_c library")

    return rt
