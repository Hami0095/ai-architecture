from typing import Dict, List, Any, Optional
from pathlib import Path
import json
from .graph_engine import GraphEngine
from ..infrastructure.logging_utils import logger

class ArchRule:
    def __init__(self, name: str, description: str, severity: str = "Critical"):
        self.name = name
        self.description = description
        self.severity = severity

    def validate(self, summary: Dict[str, Any]) -> List[str]:
        raise NotImplementedError

class NoCyclicImports(ArchRule):
    def validate(self, summary: Dict[str, Any]) -> List[str]:
        violations = []
        # Basic cycle detection (A -> B -> A)
        rels = summary.get("relationships", [])
        graph = {}
        for r in rels:
            if r["from"] not in graph: graph[r["from"]] = []
            graph[r["from"]].append(r["to"])
        
        def has_cycle(node, visited, path):
            visited.add(node)
            path.add(node)
            for neighbor in graph.get(node, []):
                if neighbor in path:
                    return True, path | {neighbor}
                if neighbor not in visited:
                    res, cycle_path = has_cycle(neighbor, visited, path)
                    if res: return True, cycle_path
            path.remove(node)
            return False, set()

        visited = set()
        for node in graph:
            if node not in visited:
                res, cycle = has_cycle(node, visited, set())
                if res:
                    violations.append(f"Cyclic dependency detected: {cycle}")
        return violations

class LayeredArchitectureViolation(ArchRule):
    """Ensures layers only call 'down' (e.g. API -> Core -> Infrastructure)."""
    
    ALLOWED_DOWNWARD = {
        "Interface": {"Core", "Infrastructure", "Data", "Abstractions", "Internal"},
        "Core": {"Infrastructure", "Data", "Abstractions", "Internal"},
        "Infrastructure": {"Data", "Abstractions", "Internal", "Core"},
        "Data": {"Abstractions", "Internal", "Infrastructure"},
        "Abstractions": {"Internal", "Core", "Infrastructure", "Data", "Interface"},
        "Internal": {"Interface", "Core", "Infrastructure", "Data", "Abstractions", "Internal"},
        "Test": {"Interface", "Core", "Infrastructure", "Data", "Abstractions", "Internal"}
    }

    def validate(self, summary: Dict[str, Any]) -> List[str]:
        violations = []
        modules = summary.get("modules", {})
        rels = summary.get("relationships", [])
        
        for rel in rels:
            from_mod = rel["from"]
            to_mod = rel["to"]
            
            from_layer = modules.get(from_mod, {}).get("ownership")
            to_layer = modules.get(to_mod, {}).get("ownership")
            
            if from_layer and to_layer and from_layer != to_layer:
                allowed = self.ALLOWED_DOWNWARD.get(from_layer, set())
                if to_layer not in allowed:
                    violations.append(f"Layer Violation: {from_mod} ({from_layer}) calls UP to {to_mod} ({to_layer})")
        
        return violations

class ArchValidator:
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.engine = GraphEngine(self.root_path)
        self.rules: List[ArchRule] = [
            NoCyclicImports("No Cycles", "Modules should not have circular dependencies."),
            LayeredArchitectureViolation("Layered Policy", "Layers must only depend on lower levels.")
        ]

    def run_validation(self) -> Dict[str, Any]:
        logger.info(f"Starting deterministic architecture validation for {self.root_path}")
        self.engine.analyze_project()
        summary = self.engine.get_graph_summary()
        
        all_violations = []
        for rule in self.rules:
            logger.info(f"Checking rule: {rule.name}")
            violations = rule.validate(summary)
            for v in violations:
                all_violations.append({
                    "rule": rule.name,
                    "severity": rule.severity,
                    "message": v
                })
        
        return {
            "success": len([v for v in all_violations if v["severity"] == "Critical"]) == 0,
            "violations": all_violations,
            "project_stats": summary.get("layer_stats", {})
        }
