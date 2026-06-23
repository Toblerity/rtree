from ctypes import CDLL
from pathlib import Path
from unittest import mock

from rtree import finder


def test_load():
    lib = finder.load()
    assert isinstance(lib, CDLL)


def test_load_without_importlib_metadata():
    """Test that library loading works when importlib.metadata.files() is unavailable.

    This can happen in sandboxed environments like Bazel where package metadata
    isn't properly exposed.
    """
    # Reload finder module with mocked importlib.metadata.files returning None
    with mock.patch("importlib.metadata.files", return_value=None):
        # Need to reload the module to re-run the load logic
        import importlib

        importlib.reload(finder)
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
