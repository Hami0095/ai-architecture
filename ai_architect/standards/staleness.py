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
"""
from __future__ import annotations

import ast
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..analysis.graph_engine import GraphEngine, ModuleNode
from .extract import _Resolver, index_modules, resolve_import_targets
from .model import SCOPE_DYNAMIC, ImportEdge, RepoGraph

VERIFIED = "VERIFIED"
STALE = "STALE"
UNVERIFIABLE = "UNVERIFIABLE"
DEFAULT_WINDOW = 5


@dataclass
class FactVerdict:
    kind: str                 # "module" | "edge"
    fact: Dict[str, Any]      # the stored fact
    label: str                # VERIFIED | STALE | UNVERIFIABLE
    reason: str
    found_line: Optional[int] = None


@dataclass
class VerificationResult:
    window: Optional[int]
    verdicts: List[FactVerdict] = field(default_factory=list)
    seconds: float = 0.0
    files_read: int = 0

    def counts(self, kind: Optional[str] = None) -> Dict[str, int]:
        out = {VERIFIED: 0, STALE: 0, UNVERIFIABLE: 0}
        for v in self.verdicts:
            if kind is None or v.kind == kind:
                out[v.label] += 1
        return out

    def to_dict(self) -> Dict[str, Any]:
        return {"window": self.window, "seconds": self.seconds, "files_read": self.files_read,
                "counts": {"module": self.counts("module"), "edge": self.counts("edge")},
                "verdicts": [asdict(v) for v in self.verdicts]}


class _SourceCache:
    """Reads and parses each cited file at most once per verification run."""

    def __init__(self, root: Path):
        self.root = root
        self.engine = GraphEngine(root, compute_churn=False)
        self.cache: Dict[str, Tuple[Optional[ModuleNode], Optional[str]]] = {}

    def load(self, rel: str, module: str) -> Tuple[Optional[ModuleNode], Optional[str]]:
        """(records node, None) if parsed; (None, 'missing') or (None, '<error>') otherwise."""
        if rel not in self.cache:
            path = self.root / rel
            if not path.is_file():
                self.cache[rel] = (None, "missing")
            else:
                try:
                    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                    node = ModuleNode(path, module)
                    self.engine._collect_import_records(tree, node)
                    self.cache[rel] = (node, None)
                except (SyntaxError, ValueError, UnicodeDecodeError, OSError) as e:
                    self.cache[rel] = (None, f"{type(e).__name__}: {e}")
        return self.cache[rel]


def _within(line: int, cited: int, window: Optional[int]) -> bool:
    return window is None or abs(line - cited) <= window


def verify_graph(old: RepoGraph, new_root: Path, source_roots: Optional[List[str]] = None,
                 exclude: Optional[List[str]] = None, window: Optional[int] = DEFAULT_WINDOW,
                 edge_scopes: Optional[List[str]] = None) -> VerificationResult:
    """Labels every module fact and edge fact of ``old`` against the checkout at ``new_root``.

    window=None searches the whole file (used only for sensitivity analysis).
    edge_scopes limits which edge facts are verified (default: all).
    """
    started = time.perf_counter()
    new_root = Path(new_root).resolve()
    index = index_modules(new_root, source_roots, exclude)
    resolver = _Resolver(index)
    files = _SourceCache(new_root)
    result = VerificationResult(window=window)

    for name, fact in sorted(old.modules.items()):
        node, problem = files.load(fact.path, name)
        stored = {"module": name, "path": fact.path}
        if problem == "missing":
            result.verdicts.append(FactVerdict("module", stored, STALE, "file no longer exists at this path"))
        elif problem:
            result.verdicts.append(FactVerdict("module", stored, UNVERIFIABLE, f"file exists but cannot be parsed: {problem}"))
        elif index.get(name, (None,))[0] != fact.path:
            result.verdicts.append(FactVerdict("module", stored, STALE, "path no longer maps to this module name"))
        else:
            result.verdicts.append(FactVerdict("module", stored, VERIFIED, "file exists and parses"))

    for edge in old.edges:
        if edge_scopes and edge.scope not in edge_scopes:
            continue
        result.verdicts.append(_verify_edge(old, edge, files, index, resolver, window))

    result.seconds = round(time.perf_counter() - started, 4)
    result.files_read = len(files.cache)
    return result


def _verify_edge(old: RepoGraph, edge: ImportEdge, files: _SourceCache, index: Dict[str, Tuple[str, bool]],
                 resolver: _Resolver, window: Optional[int]) -> FactVerdict:
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
    if not candidates:
        same_text = [r for r in records if r["statement"] == edge.statement]
        nearby = [r for r in same_text if _within(r["line"], edge.line, window)]
        if nearby:
            reason = f"statement present but now in {nearby[0]['scope']} scope, not {edge.scope}"
        elif same_text:
            reason = (f"statement no longer within {window} lines of line {edge.line} "
                      f"(now at line(s) {', '.join(str(r['line']) for r in same_text[:3])})")
        else:
            reason = "import statement no longer present"
        return FactVerdict("edge", stored, STALE, reason)

    for rec in sorted(candidates, key=lambda r: abs(r["line"] - edge.line)):
        if edge.scope == SCOPE_DYNAMIC:
            targets = [t for t in [resolver.resolve(rec["target"] or "")] if t]
        else:
            targets, _ = resolve_import_targets(edge.source, is_package, rec, resolver)
        if edge.target in targets:
            return FactVerdict("edge", stored, VERIFIED, "statement re-read and resolves to the same target",
                               found_line=rec["line"])
    return FactVerdict("edge", stored, STALE,
                       f"statement still present but no longer resolves to {edge.target}")
