import os
import textwrap
from pathlib import Path

import pytest


def pytest_collection_modifyitems(config, items):
    """Tests marked `llm` call a real model provider (possibly a cloud model);
    they only run when explicitly requested."""
    if os.environ.get("ARCHAI_RUN_LLM_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="calls a real LLM; set ARCHAI_RUN_LLM_TESTS=1 to run")
    for item in items:
        if "llm" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def make_repo(tmp_path):
    """Writes a synthetic repository from {relative_path: source} and returns its root."""
    def _make(files, name="repo"):
        root = tmp_path / name
        root.mkdir()
        for rel, content in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")
        return root
    return _make
