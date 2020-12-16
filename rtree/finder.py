"""
finder.py
------------

Locate `libspatialindex` shared library by any means necessary.
"""
import os
import sys
import ctypes
import platform
from ctypes.util import find_library

# the current working directory of this file
_cwd = os.path.abspath(os.path.expanduser(
    os.path.dirname(__file__)))

# generate a bunch of candidate locations where the
# libspatialindex shared library *might* be hanging out
_candidates = [
    os.environ.get('SPATIALINDEX_C_LIBRARY', None),
    os.path.join(_cwd, 'lib'),
    _cwd,
    '']


def load():
    """
    Load the `libspatialindex` shared library.

    Returns
    -----------
    rt : ctypes object
      Loaded shared library
    """
    if os.name == 'nt':
        # check the platform architecture
        if '64' in platform.architecture()[0]:
            arch = '64'
        else:
            arch = '32'
        lib_name = 'spatialindex_c-{}.dll'.format(arch)

        # add search paths for conda installs
        if 'conda' in sys.version:
            _candidates.append(
                os.path.join(sys.prefix, "Library", "bin"))

        # get the current PATH
        oldenv = os.environ.get('PATH', '').strip().rstrip(';')
        # run through our list of candidate locations
        for path in _candidates:
            if not path or not os.path.exists(path):
                continue
            # temporarily add the path to the PATH environment variable
            # so Windows can find additional DLL dependencies.
            os.environ['PATH'] = ';'.join([path, oldenv])
            try:
                rt = ctypes.cdll.LoadLibrary(os.path.join(path, lib_name))
                if rt is not None:
                    return rt
            except (WindowsError, OSError):
                pass
            except BaseException as E:
                print('rtree.finder unexpected error: {}'.format(str(E)))
            finally:
                os.environ['PATH'] = oldenv
        raise OSError("could not find or load {}".format(lib_name))

    elif os.name == 'posix':

        # posix includes both mac and linux
        # use the extension for the specific platform
        if platform.system() == 'Darwin':
            # macos shared libraries are `.dylib`
            lib_name = "libspatialindex_c.dylib"
        else:
            # linux shared libraries are `.so`
            lib_name = 'libspatialindex_c.so'

        # get the starting working directory
        cwd = os.getcwd()
        for cand in _candidates:
            if cand is None:
                continue
            elif os.path.isdir(cand):
                # if our candidate is a directory use best guess
                path = cand
                target = os.path.join(cand, lib_name)
            elif os.path.isfile(cand):
                # if candidate is just a file use that
                path = os.path.split(cand)[0]
                target = cand
            else:
                continue

            if not os.path.exists(target):
                continue

            try:
                # move to the location we're checking
                os.chdir(path)
                # try loading the target file candidate
                rt = ctypes.cdll.LoadLibrary(target)
                if rt is not None:
                    return rt
            except BaseException as E:
                print('rtree.finder ({}) unexpected error: {}'.format(
                    target, str(E)))
            finally:
                os.chdir(cwd)

    try:
        # try loading library using LD path search
        rt = ctypes.cdll.LoadLibrary(
            find_library('spatialindex_c'))
        if rt is not None:
            return rt
    except BaseException:
        pass

    raise OSError("Could not load libspatialindex_c library")
