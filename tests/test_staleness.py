"""Staleness verifier: labels on small synthetic repos with known changes."""
import pytest

from ai_architect.standards.extract import build_repo_graph
from ai_architect.standards.staleness import (DEFAULT_WINDOW, STALE, UNVERIFIABLE, VERIFIED,
                                              verify_graph)

OLD = {
    "app/__init__.py": "",
    "app/a.py": "import os\nfrom app import b\n\nx = 1\n",
    "app/b.py": "from app.c import helper\n",
    "app/c.py": "def helper():\n    return 1\n",
}


@pytest.fixture
def old_graph(make_repo):
    return build_repo_graph(make_repo(OLD, name="old"))


def check(make_repo, old_graph, changes, name="new", **kw):
    files = dict(OLD)
    for path, content in changes.items():
        if content is None:
            files.pop(path)
        else:
            files[path] = content
    return verify_graph(old_graph, make_repo(files, name=name), **kw)


def label(result, kind, **match):
    hits = [v for v in result.verdicts if v.kind == kind and all(v.fact.get(k) == val for k, val in match.items())]
    assert len(hits) == 1, (match, hits)
    return hits[0]


def test_unchanged_code_is_verified(make_repo, old_graph):
    r = check(make_repo, old_graph, {})
    assert {v.label for v in r.verdicts} == {VERIFIED}
    assert r.counts("edge") == {VERIFIED: 2, STALE: 0, UNVERIFIABLE: 0}


def test_moved_module(make_repo, old_graph):
    r = check(make_repo, old_graph, {"app/a.py": None, "app/core/__init__.py": "",
                                     "app/core/a.py": "import os\nfrom app import b\n"})
    assert label(r, "module", module="app.a").label == STALE
    edge = label(r, "edge", source="app.a", target="app.b")
    assert edge.label == STALE and "no longer exists" in edge.reason
    assert label(r, "edge", source="app.b", target="app.c").label == VERIFIED


def test_deleted_import(make_repo, old_graph):
    r = check(make_repo, old_graph, {"app/a.py": "import os\n\nx = 1\n"})
    assert label(r, "module", module="app.a").label == VERIFIED   # the file itself is still there
    edge = label(r, "edge", source="app.a", target="app.b")
    assert edge.label == STALE and edge.reason == "import statement no longer present"


def test_import_moved_within_window_is_verified(make_repo, old_graph):
    padding = "\n" * DEFAULT_WINDOW  # exactly at the edge of the window
    r = check(make_repo, old_graph, {"app/a.py": "import os\n" + padding + "from app import b\n"})
    edge = label(r, "edge", source="app.a", target="app.b")
    assert edge.label == VERIFIED and edge.found_line == 2 + DEFAULT_WINDOW


def test_import_moved_beyond_window_is_stale(make_repo, old_graph):
    padding = "\n" * (DEFAULT_WINDOW + 1)
    r = check(make_repo, old_graph, {"app/a.py": "import os\n" + padding + "from app import b\n"})
    edge = label(r, "edge", source="app.a", target="app.b")
    assert edge.label == STALE and "no longer within" in edge.reason
    # whole-file search (sensitivity analysis only) still finds it
    r_any = check(make_repo, old_graph, {"app/a.py": "import os\n" + padding + "from app import b\n"},
                  name="new2", window=None)
    assert label(r_any, "edge", source="app.a", target="app.b").label == VERIFIED


def test_renamed_target(make_repo, old_graph):
    # c.py renamed to helpers.py, and b.py updated accordingly
    r = check(make_repo, old_graph, {"app/c.py": None, "app/helpers.py": "def helper():\n    return 1\n",
                                     "app/b.py": "from app.helpers import helper\n"})
    assert label(r, "module", module="app.c").label == STALE
    edge = label(r, "edge", source="app.b", target="app.c")
    assert edge.label == STALE and edge.reason == "import statement no longer present"


def test_unchanged_statement_whose_target_disappeared(make_repo, old_graph):
    # b.py still says `from app.c import helper`, but app/c.py is gone: a dangling import
    r = check(make_repo, old_graph, {"app/c.py": None})
    edge = label(r, "edge", source="app.b", target="app.c")
    assert edge.label == STALE and "no longer resolves" in edge.reason


def test_import_moved_into_a_function_is_stale(make_repo, old_graph):
    r = check(make_repo, old_graph, {"app/a.py": "import os\ndef f():\n    from app import b\n"})
    edge = label(r, "edge", source="app.a", target="app.b")
    assert edge.label == STALE and edge.reason == "statement present but now in function scope, not module"


def test_syntax_error_is_unverifiable(make_repo, old_graph):
    r = check(make_repo, old_graph, {"app/a.py": "from app import b\ndef broken(:\n"})
    assert label(r, "module", module="app.a").label == UNVERIFIABLE
    edge = label(r, "edge", source="app.a", target="app.b")
    assert edge.label == UNVERIFIABLE and "cannot be parsed" in edge.reason


def test_never_verifies_without_rereading(make_repo, old_graph):
    """Every VERIFIED edge corresponds to an edge in a fresh build of the new code."""
    new_root = make_repo({**OLD, "app/b.py": "\n\nfrom app.c import helper\n", "app/d.py": "from app import a\n"},
                         name="fresh")
    r = verify_graph(old_graph, new_root)
    fresh = {(e.source, e.target, e.scope) for e in build_repo_graph(new_root).edges}
    for v in r.verdicts:
        if v.kind == "edge" and v.label == VERIFIED:
            assert (v.fact["source"], v.fact["target"], v.fact["scope"]) in fresh
    assert r.files_read == 4  # only the cited files (plus the listing), not a rebuild


def test_deterministic(make_repo, old_graph):
    new_root = make_repo({**OLD, "app/a.py": "import os\n"}, name="det")
    first = verify_graph(old_graph, new_root).to_dict()
    second = verify_graph(old_graph, new_root).to_dict()
    first.pop("seconds"); second.pop("seconds")
    assert first == second
