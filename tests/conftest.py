from __future__ import annotations

import os
import shutil
from typing import Iterator

import py
import pytest

data_files = ["boxes_15x15.data"]


@pytest.fixture(autouse=True)
def temporary_working_directory(tmpdir: py.path.local) -> Iterator[None]:
    for filename in data_files:
        filename = os.path.join(os.path.dirname(__file__), filename)
        shutil.copy(filename, str(tmpdir))
    with tmpdir.as_cwd():
        yield
