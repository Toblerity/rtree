import os
import shutil

import pytest


data_files = [
    'boxes_15x15.data',
]


@pytest.yield_fixture(autouse=True)
def temporary_working_directory(tmpdir):
    for filename in data_files:
        filename = os.path.join(os.path.dirname(__file__), filename)
        shutil.copy(filename, str(tmpdir))
    with tmpdir.as_cwd():
        yield
