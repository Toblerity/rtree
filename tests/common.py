"""Common test functions."""

import pytest

from rtree.core import rt

sidx_version_string = rt.SIDX_Version().decode()
sidx_version = tuple(map(int, sidx_version_string.split(".", maxsplit=3)[:3]))

skip_sidx_lt_210 = pytest.mark.skipif(sidx_version < (2, 1, 0), reason="SIDX < 2.1.0")
