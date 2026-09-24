"""Common test functions."""

import pytest

from rtree.core import sidx_version as _sidx_version

sidx_version_string = _sidx_version()
sidx_version = tuple(map(int, sidx_version_string.split(".", maxsplit=3)[:3]))

skip_sidx_lt_210 = pytest.mark.skipif(sidx_version < (2, 1, 0), reason="SIDX < 2.1.0")
