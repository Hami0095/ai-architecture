"""ArchAI respects .gitignore when walking a repository."""
import subprocess

import pytest

from ai_architect.analysis.graph_engine import GraphEngine, git_visible_files
from ai_architect.standards import extract
from ai_architect.standards.extract import build_repo_graph

FILES = {
    ".gitignore": "generated/\n*_tmp.py\n",
    "app/__init__.py": "",
    "app/a.py": "from app import new\n",
    "app/new.py": "x = 1\n",
    "app/scratch_tmp.py": "import app.a\n",
    "generated/__init__.py": "",
    "generated/models.py": "from app import a\n",
    "notes.txt": "hello\n",
}


def git(root, *args):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=root, check=True,
                   capture_output=True)


@pytest.fixture
def repo(make_repo):
    root = make_repo(FILES)
    git(root, "init", "-q")
    git(root, "add", ".gitignore", "app/__init__.py", "app/a.py")
    git(root, "commit", "-q", "-m", "init")       # app/new.py stays untracked but not ignored
    return root


def test_ignored_files_are_not_analyzed(repo):
    graph = build_repo_graph(repo)
    assert sorted(graph.modules) == ["app", "app.a", "app.new"]
    assert "generated/models.py" not in graph.files and "app/scratch_tmp.py" not in graph.files
    assert "notes.txt" in graph.files                     # untracked, not ignored
    if hasattr(extract, "index_modules"):              # module index used by the staleness verifier
        assert sorted(extract.index_modules(repo)) == ["app", "app.a", "app.new"]


def test_tracked_file_matching_gitignore_is_still_analyzed(repo):
    git(repo, "add", "-f", "generated/models.py")         # git treats tracked files as not ignored
    assert "generated.models" in build_repo_graph(repo).modules


def test_folder_ignored_by_an_enclosing_repo_is_analyzed_standalone(repo, tmp_path):
    vendored = repo / "generated"                          # ignored by the outer repo
    assert git_visible_files(vendored) is None
    assert sorted(build_repo_graph(vendored).modules) == ["models"]


def test_non_git_folder_and_opt_out(make_repo, repo):
    plain = make_repo(FILES, name="plain")
    assert git_visible_files(plain) is None
    assert "generated.models" in build_repo_graph(plain).modules
    engine = GraphEngine(repo, respect_gitignore=False)
    assert not engine.is_ignored(repo / "generated" / "models.py")
    assert GraphEngine(repo).is_ignored(repo / "generated" / "models.py")
