import ast
import os
import json
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
import logging

logger = logging.getLogger("ArchAI.Analysis")

class ModuleNode:
    def __init__(self, file_path: Path, module_name: str):
        self.file_path = file_path
        self.module_name = module_name
        self.classes: List[str] = []
        self.functions: List[str] = []
        self.imports: List[str] = [] # Absolute module names after resolution
        self.calls: List[str] = []   # External/Internal calls detected
        self.docstring: Optional[str] = None
        self.ownership: str = "Unknown"

class GraphEngine:
    """
    Deterministic Architecture Graph Engine.
    Uses AST analysis to build a dependency graph and call hierarchy.
    """
    
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.nodes: Dict[str, ModuleNode] = {} # module_name -> ModuleNode
        self.ignore_dirs = {'.git', '__pycache__', '.venv', 'venv', 'env', 'node_modules', 'dist', 'build'}

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
        for path in self.root_path.rglob('*.py'):
            if any(part in self.ignore_dirs for part in path.parts):
                continue
            module_name = self.resolve_module_name(path)
            self.nodes[module_name] = ModuleNode(path, module_name)

        # 2. Second pass: Detailed AST analysis per file
        for name, node in self.nodes.items():
            self._analyze_file(node)
        
        # 3. Third pass: Resolve ownership and additional metadata
        self._resolve_dependencies()

    def _analyze_file(self, node: ModuleNode):
        try:
            with open(node.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                tree = ast.parse(f.read(), filename=str(node.file_path))
                
            node.docstring = ast.get_docstring(tree)
            
            for item in tree.body:
                if isinstance(item, ast.ClassDef):
                    node.classes.append(item.name)
                elif isinstance(item, ast.FunctionDef):
                    node.functions.append(item.name)
                elif isinstance(item, (ast.Import, ast.ImportFrom)):
                    self._extract_imports(item, node)
            
            # Extract calls
            for sub_node in ast.walk(tree):
                if isinstance(sub_node, ast.Call):
                    if isinstance(sub_node.func, ast.Name):
                        node.calls.append(sub_node.func.id)
                    elif isinstance(sub_node.func, ast.Attribute):
                        if isinstance(sub_node.func.value, ast.Name):
                            node.calls.append(f"{sub_node.func.value.id}.{sub_node.func.attr}")
        except Exception as e:
            logger.warning(f"AST Analysis failed for {node.file_path}: {e}")

    def _extract_imports(self, item, node: ModuleNode):
        if isinstance(item, ast.Import):
            for alias in item.names:
                node.imports.append(alias.name)
        elif isinstance(item, ast.ImportFrom):
            base_module = item.module or ""
            if item.level > 0:
                # Resolve relative import
                parts = node.module_name.split('.')
                # item.level 1 means current dir, 2 means parent etc.
                # but 'from . import x' level is 1.
                # parts[:-level] gives the base.
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
        
        if any("Base" in c for c in node.classes):
            return "Abstractions"
        
        return "Internal"

    def get_graph_summary(self) -> Dict[str, Any]:
        """Returns a structured summary of the architecture graph."""
        summary = {
            "modules": {},
            "relationships": [],
            "layer_stats": {}
        }
        
        for name, node in self.nodes.items():
            summary["modules"][name] = {
                "classes": node.classes,
                "functions": node.functions,
                "ownership": node.ownership,
                "summary": node.docstring[:150] if node.docstring else None
            }
            
            summary["layer_stats"][node.ownership] = summary["layer_stats"].get(node.ownership, 0) + 1
            
            for imp in node.imports:
                # Find if the import matches any of our internal modules
                matched_internal = None
                for internal_name in self.nodes.keys():
                    if imp == internal_name or imp.startswith(internal_name + "."):
                        matched_internal = internal_name
                        break
                
                if matched_internal:
                    summary["relationships"].append({
                        "from": name,
                        "to": matched_internal,
                        "type": "import"
                    })
        
        # Deduplicate relationships
        unique_rels = []
        seen = set()
        for rel in summary["relationships"]:
            key = (rel["from"], rel["to"], rel["type"])
            if key not in seen:
                unique_rels.append(rel)
                seen.add(key)
        summary["relationships"] = unique_rels
        
        return summary
