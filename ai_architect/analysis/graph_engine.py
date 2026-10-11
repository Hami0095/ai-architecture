import ast
import functools
import os
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Set, Any, Optional, Tuple
import logging

logger = logging.getLogger("ArchAI.Analysis")

class FunctionNode:
    def __init__(self, name: str, lineno: int):
        self.name = name
        self.lineno = lineno
        self.calls: List[str] = [] # Names of functions/methods called
        self.docstring: Optional[str] = None

class ModuleNode:
    def __init__(self, file_path: Path, module_name: str):
        self.file_path = file_path
        self.module_name = module_name
        self.classes: Dict[str, List[str]] = {} # class_name -> [method_names]
        self.functions: Dict[str, FunctionNode] = {} # func_name -> FunctionNode (includes class.method)
        self.imports: List[str] = [] # Absolute module names after resolution
        self.docstring: Optional[str] = None
        # Every import statement in the file (any nesting), with line numbers and
        # execution scope. Used by the standards checker; `imports` is kept as-is.
        self.import_records: List[Dict[str, Any]] = []
        # importlib.import_module / __import__ calls (literal target or None).
        self.dynamic_imports: List[Dict[str, Any]] = []
        self.parse_error: Optional[str] = None
        self.ownership: str = "Unknown"
        self.metrics: Dict[str, Any] = {
            "dependency_depth": 0,
            "callers_count": 0,
            "churn": 0, # commit count
            "fan_in": 0,
            "fan_out": 0
        }

def git_visible_files(root: Path) -> Optional[Set[str]]:
    """Files git considers part of the repository at `root`: tracked files plus untracked
    files that no .gitignore (nested, global or info/exclude) excludes. Paths are relative
    to `root`, with forward slashes.

    Returns None, meaning "do not filter", when `root` is not inside a git work tree, git
    is unavailable, or `root` is itself ignored by an enclosing repository (a vendored or
    extracted tree is then analyzed as a standalone folder).
    """
    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=30, check=False)

    try:
        if git("rev-parse", "--is-inside-work-tree").returncode != 0:
            return None
        if git("check-ignore", "-q", ".").returncode == 0:
            return None
        listed = git("ls-files", "-z", "--cached", "--others", "--exclude-standard")
    except (OSError, subprocess.SubprocessError):
        return None
    if listed.returncode != 0:
        return None
    return {p for p in listed.stdout.decode("utf-8", errors="replace").split("\0") if p}


class GraphEngine:
    """
    Deterministic Architecture Graph Engine with Function-Level Call Tracing.
    Uses AST analysis to build a granular dependency graph and execution paths.
    """
    
    def __init__(self, root_path: Path, compute_churn: bool = True, respect_gitignore: bool = True):
        self.root_path = root_path
        self.compute_churn = compute_churn
        self.respect_gitignore = respect_gitignore
        self.nodes: Dict[str, ModuleNode] = {} # module_name -> ModuleNode
        self.ignore_dirs = {'.git', '__pycache__', '.venv', 'venv', 'env', 'node_modules', 'dist', 'build',
                            '.tox', '.nox', '.mypy_cache', '.pytest_cache', 'site-packages'}

    @functools.cached_property
    def git_files(self) -> Optional[Set[str]]:
        return git_visible_files(Path(self.root_path)) if self.respect_gitignore else None

    def is_ignored(self, path: Path) -> bool:
        """True for files under ignored directory names (checked relative to the root, so a
        repository that itself lives under e.g. a 'build' folder is still analyzed) and for
        files the repository's .gitignore excludes."""
        try:
            rel = path.relative_to(self.root_path)
        except ValueError:
            return any(part in self.ignore_dirs for part in path.parts)
        if any(part in self.ignore_dirs for part in rel.parts):
            return True
        files = self.git_files
        return files is not None and path.is_file() and rel.as_posix() not in files

    def resolve_module_name(self, file_path: Path) -> str:
        """Converts file path to dot-notation module name."""
        try:
            rel_path = file_path.relative_to(self.root_path)
            parts = rel_path.with_suffix('').parts
            return '.'.join(parts)
        except Exception:
            return file_path.stem

    def analyze_project(self):
        """Walks the project and analyzes all Python files."""
        # 1. First pass: Identify all internal modules
        for path in sorted(self.root_path.rglob('*.py')):
            if self.is_ignored(path):
                continue
            module_name = self.resolve_module_name(path)
            self.nodes[module_name] = ModuleNode(path, module_name)

        # 2. Second pass: Detailed AST analysis per file
        for name, node in self.nodes.items():
            self._analyze_file(node)
        
        # 3. Third pass: Resolve ownership and additional metadata
        self._resolve_dependencies()
        
        # 4. Fourth pass: Calculate metrics
        self._calculate_metrics()

    def _analyze_file(self, node: ModuleNode):
        try:
            with open(node.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                tree = ast.parse(content, filename=str(node.file_path))
                
            node.docstring = ast.get_docstring(tree)
            
            for item in tree.body:
                if isinstance(item, ast.ClassDef):
                    methods = []
                    for sub in item.body:
                        if isinstance(sub, ast.FunctionDef):
                            methods.append(sub.name)
                            func_node = FunctionNode(sub.name, sub.lineno)
                            func_node.docstring = ast.get_docstring(sub)
                            self._extract_calls_from_scope(sub, func_node)
                            node.functions[f"{item.name}.{sub.name}"] = func_node
                    node.classes[item.name] = methods
                elif isinstance(item, ast.FunctionDef):
                    func_node = FunctionNode(item.name, item.lineno)
                    func_node.docstring = ast.get_docstring(item)
                    self._extract_calls_from_scope(item, func_node)
                    node.functions[item.name] = func_node
                elif isinstance(item, (ast.Import, ast.ImportFrom)):
                    self._extract_imports(item, node)

            self._collect_import_records(tree, node)

        except Exception as e:
            node.parse_error = f"{type(e).__name__}: {e}"
            logger.warning(f"AST Analysis failed for {node.file_path}: {e}")

    def _collect_import_records(self, tree: ast.AST, node: ModuleNode):
        """Records every import with its line and execution scope.

        scope is "module" (runs at import time), "function" (deferred until
        called) or "type_checking" (inside `if TYPE_CHECKING:`, never at runtime).
        """
        def is_type_checking_test(test: ast.AST) -> bool:
            if isinstance(test, ast.Name):
                return test.id == "TYPE_CHECKING"
            if isinstance(test, ast.Attribute):
                return test.attr == "TYPE_CHECKING"
            return False

        def visit(item: ast.AST, scope: str):
            if isinstance(item, ast.Import):
                node.import_records.append({
                    "kind": "import", "module": None, "level": 0,
                    "names": [a.name for a in item.names],
                    "line": item.lineno, "scope": scope,
                    "statement": ast.unparse(item),
                })
            elif isinstance(item, ast.ImportFrom):
                node.import_records.append({
                    "kind": "from", "module": item.module, "level": item.level,
                    "names": [a.name for a in item.names],
                    "line": item.lineno, "scope": scope,
                    "statement": ast.unparse(item),
                })
            elif isinstance(item, ast.Call):
                func = item.func
                name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
                if name in ("import_module", "__import__"):
                    arg = item.args[0] if item.args else None
                    literal = arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else None
                    node.dynamic_imports.append({
                        "target": literal, "line": item.lineno, "scope": scope,
                        "statement": ast.unparse(item),
                    })

            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                child_scope = "type_checking" if scope == "type_checking" else "function"
                for child in ast.iter_child_nodes(item):
                    visit(child, child_scope)
            elif isinstance(item, ast.If) and is_type_checking_test(item.test):
                visit(item.test, scope)
                for child in item.body:
                    visit(child, "type_checking")
                for child in item.orelse:
                    visit(child, scope)
            else:
                for child in ast.iter_child_nodes(item):
                    visit(child, scope)

        visit(tree, "module")
        node.import_records.sort(key=lambda r: (r["line"], r["statement"]))
        node.dynamic_imports.sort(key=lambda r: (r["line"], r["statement"]))

    def _extract_calls_from_scope(self, scope: ast.AST, func_node: FunctionNode):
        """Recursively finds all calls within a function scope."""
        for sub_node in ast.walk(scope):
            if isinstance(sub_node, ast.Call):
                if isinstance(sub_node.func, ast.Name):
                    func_node.calls.append(sub_node.func.id)
                elif isinstance(sub_node.func, ast.Attribute):
                    if isinstance(sub_node.func.value, ast.Name):
                        func_node.calls.append(f"{sub_node.func.value.id}.{sub_node.func.attr}")

    def _extract_imports(self, item, node: ModuleNode):
        if isinstance(item, ast.Import):
            for alias in item.names:
                node.imports.append(alias.name)
        elif isinstance(item, ast.ImportFrom):
            base_module = item.module or ""
            if item.level > 0:
                parts = node.module_name.split('.')
                prefix_parts = parts[:-item.level]
                if base_module:
                    prefix_parts.append(base_module)
                resolved = '.'.join(prefix_parts)
                node.imports.append(resolved)
            else:
                node.imports.append(base_module)

    def _resolve_dependencies(self):
        """Infers ownership and cross-file relationships."""
        for name, node in self.nodes.items():
            node.ownership = self._infer_ownership(node)

    def _infer_ownership(self, node: ModuleNode) -> str:
        path_str = str(node.file_path).replace("\\", "/").lower()
        if "infrastructure" in path_str or "persistence" in path_str or "caching" in path_str:
            return "Infrastructure"
        if "core" in path_str or "orchestrator" in path_str:
            return "Core"
        if "api" in path_str or "interface" in path_str:
            return "Interface"
        if "model" in path_str or "data" in path_str:
            return "Data"
        if "test" in path_str:
            return "Test"
        
        if any("Base" in c for c in node.classes.keys()):
            return "Abstractions"
        
        return "Internal"

    def _calculate_metrics(self):
        """Calculates advanced metrics like dependency depth, fan-in/out, and churn."""
        for name, node in self.nodes.items():
            # 1. Fan-out (Imports of internal modules)
            internal_imports = [imp for imp in node.imports if any(imp == n or imp.startswith(n + ".") for n in self.nodes.keys())]
            node.metrics["fan_out"] = len(internal_imports)
            
            # 2. Fan-in (How many modules import this one)
            fan_in = 0
            for other_name, other_node in self.nodes.items():
                if other_name == name: continue
                if any(imp == name or imp.startswith(name + ".") for imp in other_node.imports):
                    fan_in += 1
            node.metrics["fan_in"] = fan_in
            node.metrics["callers_count"] = fan_in # Approximation

            # 3. Churn
            node.metrics["churn"] = self._get_git_churn(node.file_path) if self.compute_churn else 0

            # 4. Dependency Depth (recursive)
            node.metrics["dependency_depth"] = self._get_depth(name, set())

    def _get_depth(self, module_name: str, visited: Set[str]) -> int:
        if module_name in visited: return 0
        visited.add(module_name)
        
        node = self.nodes.get(module_name)
        if not node or not node.imports: return 0
        
        max_child_depth = 0
        for imp in node.imports:
            matched_internal = next((n for n in self.nodes.keys() if imp == n or imp.startswith(n + ".")), None)
            if matched_internal:
                max_child_depth = max(max_child_depth, self._get_depth(matched_internal, visited))
        
        return 1 + max_child_depth

    def _get_git_churn(self, file_path: Path) -> int:
        """Returns commit count for file using git CLI."""
        try:
            result = subprocess.run(
                ["git", "rev-list", "--count", "HEAD", str(file_path)],
                capture_output=True, text=True, cwd=self.root_path, check=False
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        except Exception:
            pass
        return 1

    def get_graph_summary(self) -> Dict[str, Any]:
        """Returns a structured summary of the architecture graph including call hierarchy and metrics."""
        summary = {
            "modules": {},
            "relationships": [],
            "call_graph": [],
            "layer_stats": {}
        }
        
        for name, node in self.nodes.items():
            summary["modules"][name] = {
                "classes": node.classes,
                "functions": list(node.functions.keys()),
                "ownership": node.ownership,
                "complexity_metrics": node.metrics,
                "summary": node.docstring[:150] if node.docstring else None
            }
            
            summary["layer_stats"][node.ownership] = summary["layer_stats"].get(node.ownership, 0) + 1
            
            for imp in node.imports:
                matched_internal = next((n for n in self.nodes.keys() if imp == n or imp.startswith(n + ".")), None)
                if matched_internal:
                    summary["relationships"].append({"from": name, "to": matched_internal, "type": "import"})

            for func_name, func_node in node.functions.items():
                for call_target in func_node.calls:
                    summary["call_graph"].append({
                        "from": f"{name}.{func_name}",
                        "to_symbol": call_target
                    })
        
        return summary

    def get_impact_scope(self, target_symbol: str, max_depth: int = 3) -> List[Dict[str, Any]]:
        """
        Finds all components that depend on or call the target symbol (upward/backward trace).
        """
        impacted = []
        visited = set()
        
        # Normalize symbol name (remove module prefix if present)
        target_name = target_symbol.split('.')[-1]
        
        def trace_up(current_symbol: str, depth: int):
            if depth > max_depth or current_symbol in visited:
                return
            visited.add(current_symbol)
            
            # Search all functions in all modules for calls to current_symbol
            for mod_name, node in self.nodes.items():
                for func_name, func_node in node.functions.items():
                    full_func_name = f"{mod_name}.{func_name}"
                    for call in func_node.calls:
                        # Match logic: if the call contains the symbol name or matches full name
                        if current_symbol == call or current_symbol.endswith('.' + call) or call.endswith('.' + current_symbol):
                            if full_func_name not in [i['name'] for i in impacted]:
                                impacted.append({
                                    "name": full_func_name,
                                    "depth": depth,
                                    "file": str(node.file_path.relative_to(self.root_path))
                                })
                            trace_up(full_func_name, depth + 1)

        trace_up(target_symbol, 1)
        # Also check module-level imports
        for mod_name, node in self.nodes.items():
            for imp in node.imports:
                if target_symbol == imp or target_symbol.startswith(imp + "."):
                    impacted.append({
                        "name": f"Module Import: {mod_name}",
                        "depth": 1,
                        "file": str(node.file_path.relative_to(self.root_path))
                    })
                    
        return impacted

    def get_symbol_metrics(self, symbol: str) -> Dict[str, Any]:
        """Gathers metrics for a specific symbol by searching modules."""
        # 1. Try direct module match
        if symbol in self.nodes:
            node = self.nodes[symbol]
            return {
                "module": symbol,
                "churn": node.metrics["churn"],
                "complexity": len(node.functions),
                "fan_in": node.metrics["fan_in"],
                "fan_out": node.metrics["fan_out"],
                "depth": node.metrics["dependency_depth"]
            }
            
        # 2. Try class/function match within modules
        for mod_name, node in self.nodes.items():
            if symbol in node.classes or symbol in node.functions or any(symbol in f for f in node.functions):
                return {
                    "module": mod_name,
                    "churn": node.metrics["churn"],
                    "complexity": len(node.functions.get(symbol, node.functions).calls if hasattr(node.functions.get(symbol), "calls") else []),
                    "fan_in": node.metrics["fan_in"],
                    "fan_out": node.metrics["fan_out"],
                    "depth": node.metrics["dependency_depth"]
                }
        
        # 3. Fuzzy match
        for mod_name, node in self.nodes.items():
            if symbol.lower() in mod_name.lower():
                 return self.get_symbol_metrics(mod_name)
                    
        return {"error": "Symbol not found in graph"}
