import os
import tempfile

# Isolate test data before the app module is imported.
_tmp = tempfile.mkdtemp(prefix="aurelia-test-")
os.environ["AURELIA_DATA_DIR"] = _tmp
os.environ["AURELIA_ENABLE_SHELL_TOOL"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from aurelia_api.main import app  # noqa: E402


@pytest.fixture()
def client():
    return TestClient(app)
