"""Data model for the standards checker: repository facts, findings and results.

Status semantics (used for both findings and rule outcomes):

VERIFIED_VIOLATION
    The rule's condition is violated, and every fact needed to establish that
    was extracted deterministically from source and is cited with a file (and
    a line, where the fact is a statement). Re-running on the same input
    yields the same finding.
POTENTIAL_RISK
    Deterministic facts match the rule's pattern, but whether they violate the
    rule depends on something static analysis cannot settle: a type-checking
    only import, a dynamic import by string, a cycle closed only by a deferred
    (function-level) import, or a test convention met by some other test file.
INSUFFICIENT_GRAPH_EVIDENCE
    Part of the rule's scope could not be evaluated: files that failed to
    parse, scope patterns that match nothing, imports that look internal but
    do not resolve, or no supported source files at all. Absence of a
    violation in that part of the scope is NOT evidence of compliance.
PASS
    Rule-level outcome only. The rule was evaluated over its whole declared
    scope and produced no findings. It says nothing about anything outside
    that scope or outside what the rule checks.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

VERIFIED_VIOLATION = "VERIFIED_VIOLATION"
POTENTIAL_RISK = "POTENTIAL_RISK"
INSUFFICIENT_GRAPH_EVIDENCE = "INSUFFICIENT_GRAPH_EVIDENCE"
PASS = "PASS"

# Most severe first; a rule's outcome is the most severe status among its findings.
STATUS_ORDER = [VERIFIED_VIOLATION, POTENTIAL_RISK, INSUFFICIENT_GRAPH_EVIDENCE, PASS]

# Import scopes recorded by GraphEngine._collect_import_records.
SCOPE_MODULE = "module"
SCOPE_FUNCTION = "function"
SCOPE_TYPE_CHECKING = "type_checking"
SCOPE_DYNAMIC = "dynamic"
RUNTIME_SCOPES = (SCOPE_MODULE, SCOPE_FUNCTION)

REPORT_SCHEMA_VERSION = "archai.standards/1"


@dataclass(frozen=True)
class ImportEdge:
    """A resolved dependency from one internal module to another."""
    source: str
    target: str
    line: int
    scope: str  # module | function | type_checking | dynamic
    statement: str


@dataclass
class ModuleFact:
    name: str
    path: str  # repo-relative, POSIX separators
    is_package: bool
    parse_error: Optional[str] = None


@dataclass
class RepoGraph:
    """Deterministic repository facts. Built from source or loaded from an OKF bundle."""
    modules: Dict[str, ModuleFact] = field(default_factory=dict)
    edges: List[ImportEdge] = field(default_factory=list)
    # Imports that name an internal top-level package but resolve to no module.
    unresolved_internal: List[Dict[str, Any]] = field(default_factory=list)
    # Dynamic imports whose target is not a string literal.
    opaque_dynamic_imports: List[Dict[str, Any]] = field(default_factory=list)
    # Every non-ignored file path in the repository (repo-relative, POSIX).
    files: List[str] = field(default_factory=list)
    unsupported_files: Dict[str, int] = field(default_factory=dict)  # extension -> count
    excluded_modules: List[str] = field(default_factory=list)
    diagnostics: List[str] = field(default_factory=list)

    def edges_from(self, module: str) -> List[ImportEdge]:
        return [e for e in self.edges if e.source == module]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "modules": {k: asdict(v) for k, v in sorted(self.modules.items())},
            "edges": [asdict(e) for e in self.edges],
            "unresolved_internal": self.unresolved_internal,
            "opaque_dynamic_imports": self.opaque_dynamic_imports,
            "files": self.files,
            "unsupported_files": dict(sorted(self.unsupported_files.items())),
            "excluded_modules": self.excluded_modules,
            "diagnostics": self.diagnostics,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RepoGraph":
        return cls(
            modules={k: ModuleFact(**v) for k, v in data.get("modules", {}).items()},
            edges=[ImportEdge(**e) for e in data.get("edges", [])],
            unresolved_internal=list(data.get("unresolved_internal", [])),
            opaque_dynamic_imports=list(data.get("opaque_dynamic_imports", [])),
            files=list(data.get("files", [])),
            unsupported_files=dict(data.get("unsupported_files", {})),
            excluded_modules=list(data.get("excluded_modules", [])),
            diagnostics=list(data.get("diagnostics", [])),
        )


@dataclass
class EvidenceRef:
    """A pointer to the source fact behind a finding. `line` is None when the
    fact is about a whole file (or a file's absence), never guessed."""
    kind: str  # import_statement | module_file | missing_file | parse_error | metric
    file: Optional[str]
    line: Optional[int] = None
    detail: str = ""


@dataclass
class Finding:
    id: str
    rule_id: str
    rule_description: str
    category: str
    status: str
    summary: str
    modules: List[str]
    files: List[str]
    evidence: List[EvidenceRef]
    observed: Dict[str, Any]
    expected: str
    evaluation: str
    verification: Dict[str, Any]
    limitations: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)


@dataclass
class RuleResult:
    rule_id: str
    kind: str
    description: str
    rationale: str
    origin: str  # "user-config" | "archai-default"
    params: Dict[str, Any]
    outcome: str
    scope_stats: Dict[str, Any]
    findings: List[Finding]
    limitations: List[str] = field(default_factory=list)


def stable_finding_id(rule_id: str, *key_parts: Any) -> str:
    """Finding IDs depend only on the rule and the facts that identify the finding."""
    payload = json.dumps([rule_id, *key_parts], sort_keys=True, default=str)
    return "F-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def worst_status(statuses: List[str]) -> str:
    for status in STATUS_ORDER:
        if status in statuses:
            return status
    return PASS


def deterministic_verification(complete: bool) -> Dict[str, Any]:
    return {
        "method": "deterministic-static-analysis",
        "llm_assisted": False,
        "evidence_completeness": "complete" if complete else "partial",
    }
