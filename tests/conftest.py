
import pytest


@pytest.yield_fixture(autouse=True)
def temporary_working_directory(tmpdir):
    with tmpdir.as_cwd():
        yield
