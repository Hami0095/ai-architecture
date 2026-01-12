import hashlib
import os

ARCHAI_VERSION = "0.2.1-pilot"

def get_graph_core_hash():
    """Generates a hash of the deterministic graph engine logic to ensure audit integrity."""
    # We hash the core files involved in deterministic reasoning
    core_files = [
        "ai_architect/core_ai/auditor.py",
        "ai_architect/core_ai/prompts.py",
        "ai_architect/improvement_engine/planner.py"
    ]
    hasher = hashlib.sha256()
    for f_path in core_files:
        full_path = os.path.join(os.getcwd(), f_path)
        if os.path.exists(full_path):
            with open(full_path, "rb") as f:
                hasher.update(f.read())
    return hasher.hexdigest()[:12]
