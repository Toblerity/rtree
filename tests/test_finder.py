from ctypes import CDLL
from pathlib import Path

from rtree import finder


def test_load():
    lib = finder.load()
    assert isinstance(lib, CDLL)


def test_get_include():
    incl = finder.get_include()
    assert isinstance(incl, str)
    if incl:
        path = Path(incl)
        assert path.is_dir()
        assert (path / "spatialindex").is_dir()
        assert (path / "spatialindex" / "SpatialIndex.h").is_file()
