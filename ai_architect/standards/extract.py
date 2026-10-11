"""Builds a RepoGraph (deterministic repository facts) from source via GraphEngine."""
from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from ..analysis.graph_engine import GraphEngine
from .model import ImportEdge, ModuleFact, RepoGraph, SCOPE_DYNAMIC

# Source files ArchAI recognises but cannot analyze yet. They are counted and
# reported as a limitation instead of being silently treated as clean.
UNSUPPORTED_SOURCE_EXTENSIONS = {
    ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".java", ".kt", ".kts", ".scala",
    ".go", ".rs", ".rb", ".php", ".cs", ".fs", ".vb", ".c", ".h", ".cc", ".cpp",
    ".hpp", ".m", ".mm", ".swift", ".dart", ".lua", ".pl", ".r", ".jl", ".ex",
    ".exs", ".erl", ".clj", ".groovy", ".pyx", ".pyi",
}


def _posix(path: Path) -> str:
    return path.as_posix()


def _matches_any(rel_path: str, globs: Iterable[str]) -> bool:
    return any(fnmatch.fnmatchcase(rel_path, g) for g in globs)


def _canonical_name(rel_path: str, source_roots: List[str]) -> Tuple[str, bool]:
    """Maps a repo-relative .py path to its importable dotted module name."""
    stripped = rel_path
    for root in sorted(source_roots, key=len, reverse=True):
        prefix = root.strip("/") + "/"
        if root not in ("", ".") and rel_path.startswith(prefix):
            stripped = rel_path[len(prefix):]
            break
    parts = stripped[:-3].split("/")
    is_package = parts[-1] == "__init__"
    if is_package:
        parts = parts[:-1]
    return ".".join(parts), is_package


def _absolute_base(module: str, is_package: bool, level: int, name: Optional[str]) -> Optional[str]:
    """Resolves the module part of a (possibly relative) `from` import."""
    if level == 0:
        return name or None
    parts = module.split(".") if is_package else module.split(".")[:-1]
    drop = level - 1
    if drop > len(parts):
        return None
    parts = parts[: len(parts) - drop]
    if name:
        parts.append(name)
    return ".".join(p for p in parts if p) or None


class _Resolver:
    def __init__(self, module_names: Iterable[str]):
        self.modules = set(module_names)
        self.top_levels = {m.split(".")[0] for m in self.modules if m}
        # Directories that contain modules but have no __init__.py of their own.
        self.namespaces = {
            ".".join(m.split(".")[:i]) for m in self.modules for i in range(1, m.count(".") + 1)
        } - self.modules

    def resolve(self, dotted: str) -> Optional[str]:
        """Exact internal module, or None."""
        return dotted if dotted in self.modules else None

    def resolve_prefix(self, dotted: str) -> Optional[str]:
        """Longest internal module that `dotted` names or lives inside."""
        parts = dotted.split(".")
        for i in range(len(parts), 0, -1):
            candidate = ".".join(parts[:i])
            if candidate in self.modules:
                return candidate
        return None

    def looks_internal(self, dotted: str) -> bool:
        return dotted.split(".")[0] in self.top_levels


def _inventory(root: Path, engine: GraphEngine) -> Tuple[List[str], Dict[str, int]]:
    files: List[str] = []
    unsupported: Dict[str, int] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in engine.ignore_dirs)
        for filename in sorted(filenames):
            if engine.is_ignored(Path(dirpath, filename)):
                continue
            rel = _posix(Path(dirpath, filename).relative_to(root))
            files.append(rel)
            ext = Path(filename).suffix.lower()
            if ext in UNSUPPORTED_SOURCE_EXTENSIONS:
                unsupported[ext] = unsupported.get(ext, 0) + 1
    files.sort()
    return files, unsupported


def build_repo_graph(root: Path, source_roots: Optional[List[str]] = None,
                     exclude: Optional[List[str]] = None) -> RepoGraph:
    root = Path(root).resolve()
    graph = RepoGraph()
    source_roots = list(source_roots or [])
    exclude = list(exclude or [])

    src_dir = root / "src"
    if not source_roots and src_dir.is_dir() and not (src_dir / "__init__.py").exists():
        source_roots = ["src"]
        graph.diagnostics.append(
            "Detected a 'src/' layout; module names are computed relative to 'src/'. "
            "Set source_roots in the standards config to override.")

    engine = GraphEngine(root, compute_churn=False)
    engine.analyze_project()
    graph.files, graph.unsupported_files = _inventory(root, engine)

    # 1. Modules (canonical, importable names)
    raw_by_name: Dict[str, object] = {}
    for node in sorted(engine.nodes.values(), key=lambda n: _posix(n.file_path.relative_to(root))):
        rel = _posix(node.file_path.relative_to(root))
        name, is_package = _canonical_name(rel, source_roots)
        if not name:
            graph.diagnostics.append(f"Skipped '{rel}': it maps to no importable module name.")
            continue
        if _matches_any(rel, exclude):
            graph.excluded_modules.append(name)
            continue
        if name in graph.modules:
            graph.diagnostics.append(
                f"Module name collision: '{rel}' and '{graph.modules[name].path}' both map to "
                f"'{name}'. Only '{graph.modules[name].path}' was analyzed.")
            continue
        graph.modules[name] = ModuleFact(name=name, path=rel, is_package=is_package,
                                         parse_error=node.parse_error)
        raw_by_name[name] = node
    graph.excluded_modules.sort()

    # 2. Edges. Excluded modules are outside the analyzed system: edges into
    # them are dropped rather than reported as unresolved.
    resolver = _Resolver(graph.modules)
    excluded = _Resolver(graph.excluded_modules)
    edges = set()

    def unresolved(src: str, rec: dict, target: Optional[str]) -> None:
        graph.unresolved_internal.append({
            "source": src, "file": graph.modules[src].path, "line": rec["line"],
            "statement": rec["statement"], "target": target})

    def add_edge(src: str, target: Optional[str], rec: dict, scope: str) -> None:
        if target and target != src:
            edges.add(ImportEdge(src, target, rec["line"], scope, rec["statement"]))

    def is_known_elsewhere(dotted: str) -> bool:
        # Excluded by config, or a namespace package (no code of its own).
        return excluded.resolve_prefix(dotted) is not None or dotted in resolver.namespaces

    for name, node in raw_by_name.items():
        fact = graph.modules[name]
        for rec in node.import_records:
            if rec["kind"] == "import":
                # `import a.b.c` must name a module; it also imports a and a.b.
                for imported in rec["names"]:
                    target = resolver.resolve(imported)
                    if target:
                        add_edge(name, target, rec, rec["scope"])
                    elif resolver.looks_internal(imported) and not is_known_elsewhere(imported):
                        unresolved(name, rec, imported)
                continue
            base = _absolute_base(name, fact.is_package, rec["level"], rec["module"])
            if base is None:
                unresolved(name, rec, None)
                continue
            if rec["level"] == 0 and not resolver.looks_internal(base):
                continue  # third-party or standard library
            base_module = resolver.resolve(base)
            for imported in rec["names"]:
                submodule = f"{base}.{imported}"
                if imported != "*" and submodule in resolver.modules:
                    add_edge(name, submodule, rec, rec["scope"])
                elif base_module:
                    add_edge(name, base_module, rec, rec["scope"])
                elif not (is_known_elsewhere(base) or is_known_elsewhere(submodule)):
                    unresolved(name, rec, submodule if imported != "*" else base)
        for dyn in node.dynamic_imports:
            target = dyn["target"]
            if target and not target.startswith("."):
                resolved = resolver.resolve(target)
                if resolved:
                    add_edge(name, resolved, dyn, SCOPE_DYNAMIC)
                elif resolver.looks_internal(target) and not is_known_elsewhere(target):
                    unresolved(name, dyn, target)
            else:
                graph.opaque_dynamic_imports.append({
                    "source": name, "file": fact.path, "line": dyn["line"],
                    "statement": dyn["statement"]})

    graph.edges = sorted(edges, key=lambda e: (e.source, e.line, e.target, e.scope, e.statement))
    unique = {(u["source"], u["line"], str(u["target"]), u["statement"]): u for u in graph.unresolved_internal}
    graph.unresolved_internal = [unique[k] for k in sorted(unique)]
    graph.opaque_dynamic_imports.sort(key=lambda u: (u["source"], u["line"]))
    return graph
