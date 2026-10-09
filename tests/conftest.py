import os

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

