from __future__ import annotations

import os
import shutil
from collections.abc import Iterator

import numpy
import py
import pytest

import rtree

data_files = ["boxes_15x15.data"]


@pytest.fixture(autouse=True)
def temporary_working_directory(tmpdir: py.path.local) -> Iterator[None]:
    for filename in data_files:
        filename = os.path.join(os.path.dirname(__file__), filename)
        shutil.copy(filename, str(tmpdir))
    with tmpdir.as_cwd():
        yield


def pytest_report_header(config):
    """Header for pytest."""
    vers = [
        f"SIDX version: {rtree.core.rt.SIDX_Version().decode()}",
        f"NumPy version: {numpy.__version__}",
    ]
    return "\n".join(vers)
