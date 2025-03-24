"""Common test functions."""

from rtree.core import rt

sidx_version_string = rt.SIDX_Version().decode()
sidx_version = tuple(map(int, sidx_version_string.split(".", maxsplit=3)[:3]))
