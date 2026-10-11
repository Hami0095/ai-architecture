"""Staleness verification: does evidence recorded in an old graph still hold?

Given a RepoGraph built at an old revision and a checkout of a newer revision,
every stored fact is labelled:

VERIFIED
    The evidence was re-read in the current code and still holds.
    Module fact: the file exists at the same path and parses.
    Edge fact: the importing file exists at the same path and parses, and an
    import statement with the same text and the same scope sits within
    ``window`` lines of the cited line and still resolves to the same target.
STALE
    The evidence no longer holds: the file is gone, or no matching statement
    is near the cited line, or the statement now resolves elsewhere or nowhere.
UNVERIFIABLE
    The evidence cannot be checked: the file exists but cannot be read or
    parsed with the running Python's grammar.

The verifier never labels a fact VERIFIED without re-reading and re-parsing
the cited file in the current checkout. It does not rebuild the graph: it reads
only the files the old facts cite, plus a file listing to resolve targets.

Search window: the cited line +/- ``window`` lines (default 5). A statement that
moved further than that is STALE, because the receipt as recorded no longer
points at it, even if the dependency still exists elsewhere in the file.

Optional extensions (off by default):

re-anchoring (``reanchor=True``)
    A STALE edge fact becomes VERIFIED (``reanchored=True``) only if the same
    source file, at the same path, still contains an import in the same scope
    class (module, function, type_checking or dynamic) that resolves to the same
    target. The new file:line and statement are recorded as ``new_evidence``.
    UNVERIFIABLE facts and facts whose file is gone are never re-anchored.

coverage (``file_hashes={path: sha256}`` captured when the graph was built)
    Every cited file gets COMPLETE if its content hash is unchanged since the
    graph was built, otherwise POSSIBLY_INCOMPLETE (changed or deleted). A fact
    missing from the graph for a POSSIBLY_INCOMPLETE file is not evidence that
    the import does not exist.

``verify_graph_git_restricted`` is a separate, cheaper variant: facts in files
that git reports unchanged are carried over as VERIFIED *without re-reading*
(``reread=False``). It exists to measure that trade-off and is not the default.
"""
from __future__ import annotations

import ast
import hashlib
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from ..analysis.graph_engine import GraphEngine, ModuleNode
from .extract import _Resolver, index_modules, resolve_import_targets
from .model import SCOPE_DYNAMIC, ImportEdge, RepoGraph

VERIFIED = "VERIFIED"
STALE = "STALE"
UNVERIFIABLE = "UNVERIFIABLE"
COMPLETE = "COMPLETE"
POSSIBLY_INCOMPLETE = "POSSIBLY_INCOMPLETE"
DEFAULT_WINDOW = 5


@dataclass
class FactVerdict:
    kind: str                 # "module" | "edge"
    fact: Dict[str, Any]      # the stored fact
    label: str                # VERIFIED | STALE | UNVERIFIABLE
    reason: str
    found_line: Optional[int] = None
    reanchored: bool = False
    new_evidence: Optional[Dict[str, Any]] = None   # file, line, scope, statement (re-anchored facts)
    coverage: Optional[str] = None                  # COMPLETE | POSSIBLY_INCOMPLETE (when hashes are given)
    reread: bool = True                             # False only in the git-restricted variant


@dataclass
class VerificationResult:
    window: Optional[int]
    reanchor: bool = False
    verdicts: List[FactVerdict] = field(default_factory=list)
    coverage: Dict[str, str] = field(default_factory=dict)   # cited file path -> coverage label
    seconds: float = 0.0
    files_read: int = 0

    def counts(self, kind: Optional[str] = None) -> Dict[str, int]:
        out = {VERIFIED: 0, STALE: 0, UNVERIFIABLE: 0}
        for v in self.verdicts:
            if kind is None or v.kind == kind:
                out[v.label] += 1
        return out

    def reanchored(self) -> int:
        return sum(1 for v in self.verdicts if v.reanchored)

    def to_dict(self) -> Dict[str, Any]:
        return {"window": self.window, "reanchor": self.reanchor, "seconds": self.seconds,
                "files_read": self.files_read, "reanchored": self.reanchored(),
                "counts": {"module": self.counts("module"), "edge": self.counts("edge")},
                "coverage": dict(sorted(self.coverage.items())),
                "verdicts": [asdict(v) for v in self.verdicts]}


def file_hashes(root: Path, graph: RepoGraph) -> Dict[str, str]:
    """SHA-256 of every module file of ``graph`` under ``root`` (call when the graph is built)."""
    out = {}
    for fact in graph.modules.values():
        path = Path(root) / fact.path
        if path.is_file():
            out[fact.path] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


class _SourceCache:
    """Reads and parses each cited file at most once per verification run."""

    def __init__(self, root: Path):
        self.root = root
        self.engine = GraphEngine(root, compute_churn=False)
        self.cache: Dict[str, Tuple[Optional[ModuleNode], Optional[str]]] = {}
        self.raw: Dict[str, Optional[bytes]] = {}

    def load(self, rel: str, module: str) -> Tuple[Optional[ModuleNode], Optional[str]]:
        """(records node, None) if parsed; (None, 'missing') or (None, '<error>') otherwise."""
        if rel not in self.cache:
            path = self.root / rel
            if not path.is_file():
                self.raw[rel] = None
                self.cache[rel] = (None, "missing")
            else:
                try:
                    data = path.read_bytes()
                    self.raw[rel] = data
                    tree = ast.parse(data.decode("utf-8"), filename=str(path))
                    node = ModuleNode(path, module)
                    self.engine._collect_import_records(tree, node)
                    self.cache[rel] = (node, None)
                except (SyntaxError, ValueError, UnicodeDecodeError, OSError) as e:
                    self.cache[rel] = (None, f"{type(e).__name__}: {e}")
        return self.cache[rel]

    def coverage(self, rel: str, hashes: Dict[str, str]) -> str:
        data = self.raw.get(rel)
        if data is None:
            path = self.root / rel
            data = path.read_bytes() if path.is_file() else None
        if data is None or rel not in hashes:
            return POSSIBLY_INCOMPLETE
        return COMPLETE if hashlib.sha256(data).hexdigest() == hashes[rel] else POSSIBLY_INCOMPLETE


def _within(line: int, cited: int, window: Optional[int]) -> bool:
    return window is None or abs(line - cited) <= window


def verify_graph(old: RepoGraph, new_root: Path, source_roots: Optional[List[str]] = None,
                 exclude: Optional[List[str]] = None, window: Optional[int] = DEFAULT_WINDOW,
                 edge_scopes: Optional[List[str]] = None, reanchor: bool = False,
                 file_hashes: Optional[Dict[str, str]] = None,
                 only_files: Optional[Set[str]] = None) -> VerificationResult:
    """Labels every module fact and edge fact of ``old`` against the checkout at ``new_root``.

    window=None searches the whole file (used only for sensitivity analysis).
    edge_scopes limits which edge facts are verified (default: all).
    only_files restricts verification to facts citing those files (others are skipped).
    """
    started = time.perf_counter()
    new_root = Path(new_root).resolve()
    index = index_modules(new_root, source_roots, exclude)
    resolver = _Resolver(index)
    files = _SourceCache(new_root)
    result = VerificationResult(window=window, reanchor=reanchor)

    for name, fact in sorted(old.modules.items()):
        if only_files is not None and fact.path not in only_files:
            continue
        node, problem = files.load(fact.path, name)
        stored = {"module": name, "path": fact.path}
        if problem == "missing":
            v = FactVerdict("module", stored, STALE, "file no longer exists at this path")
        elif problem:
            v = FactVerdict("module", stored, UNVERIFIABLE, f"file exists but cannot be parsed: {problem}")
        elif index.get(name, (None,))[0] != fact.path:
            v = FactVerdict("module", stored, STALE, "path no longer maps to this module name")
        else:
            v = FactVerdict("module", stored, VERIFIED, "file exists and parses")
        result.verdicts.append(v)

    for edge in old.edges:
        if edge_scopes and edge.scope not in edge_scopes:
            continue
        if only_files is not None and old.modules[edge.source].path not in only_files:
            continue
        result.verdicts.append(_verify_edge(old, edge, files, index, resolver, window, reanchor))

    if file_hashes is not None:
        for v in result.verdicts:
            rel = v.fact["path"] if v.kind == "module" else v.fact["file"]
            if rel not in result.coverage:
                result.coverage[rel] = files.coverage(rel, file_hashes)
            v.coverage = result.coverage[rel]

    result.seconds = round(time.perf_counter() - started, 4)
    result.files_read = len(files.cache)
    return result


def verify_graph_git_restricted(old: RepoGraph, new_root: Path, changed_files: Iterable[str],
                                **kwargs) -> VerificationResult:
    """Re-reads only files git reports as changed; facts citing other files are carried over
    as VERIFIED without re-reading (reread=False). A measured variant, not the default:
    an unchanged file can still lose an import target that moved or was deleted elsewhere."""
    started = time.perf_counter()
    changed = set(changed_files)
    result = verify_graph(old, new_root, only_files=changed, **kwargs)
    edge_scopes = kwargs.get("edge_scopes")
    carried = []
    for name, fact in sorted(old.modules.items()):
        if fact.path not in changed:
            carried.append(FactVerdict("module", {"module": name, "path": fact.path}, VERIFIED,
                                       "file unchanged per git diff; not re-read", reread=False))
    for edge in old.edges:
        if (edge_scopes and edge.scope not in edge_scopes) or old.modules[edge.source].path in changed:
            continue
        stored = {"source": edge.source, "target": edge.target, "file": old.modules[edge.source].path,
                  "line": edge.line, "scope": edge.scope, "statement": edge.statement}
        carried.append(FactVerdict("edge", stored, VERIFIED, "file unchanged per git diff; not re-read",
                                   reread=False))
    result.verdicts = carried + result.verdicts
    result.seconds = round(time.perf_counter() - started, 4)
    return result


def _matching_targets(edge: ImportEdge, rec: dict, is_package: bool, resolver: _Resolver) -> List[str]:
    if edge.scope == SCOPE_DYNAMIC:
        return [t for t in [resolver.resolve(rec.get("target") or "")] if t]
    targets, _ = resolve_import_targets(edge.source, is_package, rec, resolver)
    return targets


def _verify_edge(old: RepoGraph, edge: ImportEdge, files: _SourceCache, index: Dict[str, Tuple[str, bool]],
                 resolver: _Resolver, window: Optional[int], reanchor: bool) -> FactVerdict:
    source = old.modules[edge.source]
    stored = {"source": edge.source, "target": edge.target, "file": source.path, "line": edge.line,
              "scope": edge.scope, "statement": edge.statement}
    node, problem = files.load(source.path, edge.source)
    if problem == "missing":
        return FactVerdict("edge", stored, STALE, "importing file no longer exists at this path")
    if problem:
        return FactVerdict("edge", stored, UNVERIFIABLE, f"importing file cannot be parsed: {problem}")
    if index.get(edge.source, (None,))[0] != source.path:
        return FactVerdict("edge", stored, STALE, "importing file no longer maps to this module name")
    is_package = index[edge.source][1]

    records = node.dynamic_imports if edge.scope == SCOPE_DYNAMIC else node.import_records
    candidates = [r for r in records
                  if r["statement"] == edge.statement and _within(r["line"], edge.line, window)
                  and (edge.scope == SCOPE_DYNAMIC or r["scope"] == edge.scope)]
    verdict = None
    for rec in sorted(candidates, key=lambda r: abs(r["line"] - edge.line)):
        if edge.target in _matching_targets(edge, rec, is_package, resolver):
            return FactVerdict("edge", stored, VERIFIED, "statement re-read and resolves to the same target",
                               found_line=rec["line"])
    if candidates:
        verdict = FactVerdict("edge", stored, STALE, f"statement still present but no longer resolves to {edge.target}")
    else:
        same_text = [r for r in records if r["statement"] == edge.statement]
        nearby = [r for r in same_text if _within(r["line"], edge.line, window)]
        if nearby:
            reason = f"statement present but now in {nearby[0]['scope']} scope, not {edge.scope}"
        elif same_text:
            reason = (f"statement no longer within {window} lines of line {edge.line} "
                      f"(now at line(s) {', '.join(str(r['line']) for r in same_text[:3])})")
        else:
            reason = "import statement no longer present"
        verdict = FactVerdict("edge", stored, STALE, reason)

    if reanchor:
        same_scope = [r for r in records if edge.scope == SCOPE_DYNAMIC or r["scope"] == edge.scope]
        for rec in sorted(same_scope, key=lambda r: (abs(r["line"] - edge.line), r["line"])):
            if edge.target in _matching_targets(edge, rec, is_package, resolver):
                return FactVerdict(
                    "edge", stored, VERIFIED, f"re-anchored: {verdict.reason}; the same file still imports "
                    f"{edge.target} in {edge.scope} scope", found_line=rec["line"], reanchored=True,
                    new_evidence={"file": source.path, "line": rec["line"], "scope": edge.scope,
                                  "statement": rec["statement"]})
    return verdict
