"""Deterministic evaluation of standards rules over a RepoGraph.

Every evaluator is a pure function of (RuleSpec, layers, RepoGraph). No LLM,
no network, no filesystem access: the same graph always yields the same result.
"""
from __future__ import annotations

import fnmatch
from collections import defaultdict, deque
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

from .config import RuleSpec
from .model import (
    INSUFFICIENT_GRAPH_EVIDENCE, PASS, POTENTIAL_RISK, RUNTIME_SCOPES, SCOPE_MODULE,
    VERIFIED_VIOLATION, EvidenceRef, Finding, ImportEdge, RepoGraph, RuleResult,
    deterministic_verification, stable_finding_id, worst_status,
)

_WILDCARDS = set("*?[")


def module_matches(module: str, pattern: str) -> bool:
    """A plain dotted name matches that module and everything beneath it; a
    pattern containing * ? or [ is matched with fnmatch against the full name."""
    if pattern in ("*", "**"):
        return True
    if _WILDCARDS & set(pattern):
        return fnmatch.fnmatchcase(module, pattern)
    return module == pattern or module.startswith(pattern + ".")


def matches_any(module: str, patterns: Iterable[str]) -> bool:
    return any(module_matches(module, p) for p in patterns)


def _scope(graph: RepoGraph, patterns: Iterable[str]) -> List[str]:
    patterns = list(patterns)
    return sorted(m for m in graph.modules if matches_any(m, patterns))


def _edge_evidence(graph: RepoGraph, edge: ImportEdge) -> EvidenceRef:
    return EvidenceRef(kind="import_statement", file=graph.modules[edge.source].path,
                       line=edge.line, detail=f"{edge.statement}  [scope: {edge.scope}]")


def _finding(rule: RuleSpec, status: str, key: Tuple, summary: str, modules: List[str],
             graph: RepoGraph, evidence: List[EvidenceRef], observed: Dict, expected: str,
             evaluation: str, complete: bool = True, limitations: Optional[List[str]] = None,
             next_steps: Optional[List[str]] = None) -> Finding:
    files = sorted({graph.modules[m].path for m in modules if m in graph.modules})
    return Finding(
        id=stable_finding_id(rule.id, status, *key), rule_id=rule.id,
        rule_description=rule.description, category=rule.kind, status=status,
        summary=summary, modules=sorted(set(modules)), files=files, evidence=evidence,
        observed=observed, expected=expected, evaluation=evaluation,
        verification=deterministic_verification(complete),
        limitations=limitations or [], next_steps=next_steps or [])


# --- Shared evidence-gap checks -------------------------------------------------

def _evidence_gaps(rule: RuleSpec, graph: RepoGraph, scope: List[str], scope_label: str,
                   dependency_rule: bool = True) -> List[Finding]:
    """Findings for the parts of a rule's scope that could not be evaluated."""
    gaps: List[Finding] = []
    if not graph.modules:
        unsupported = ", ".join(f"{n} {ext}" for ext, n in sorted(graph.unsupported_files.items()))
        gaps.append(_finding(
            rule, INSUFFICIENT_GRAPH_EVIDENCE, ("no-python-modules",),
            "No analyzable Python modules were found, so this rule could not be evaluated.",
            [], graph, [], {"unsupported_files": graph.unsupported_files},
            "At least one Python module in scope.",
            "Not evaluated: the repository graph is empty." +
            (f" Unsupported source files present: {unsupported}." if unsupported else ""),
            complete=False,
            next_steps=["Check the repository path, or note that only Python is supported."]))
        return gaps
    if not scope:
        gaps.append(_finding(
            rule, INSUFFICIENT_GRAPH_EVIDENCE, ("empty-scope", scope_label),
            f"The rule's scope ({scope_label}) matched no modules, so nothing was checked.",
            [], graph, [], {"scope": scope_label, "modules_in_graph": len(graph.modules)},
            "Scope patterns should match at least one module.",
            "Not evaluated: empty scope. A typo in a pattern would look exactly like this.",
            complete=False,
            next_steps=["Compare the scope patterns against module names in the JSON report."]))

    broken = [m for m in scope if graph.modules[m].parse_error]
    if broken:
        gaps.append(_finding(
            rule, INSUFFICIENT_GRAPH_EVIDENCE, ("parse-errors", tuple(broken)),
            f"{len(broken)} module(s) in scope could not be parsed; their dependencies are unknown.",
            broken, graph,
            [EvidenceRef("parse_error", graph.modules[m].path, None, graph.modules[m].parse_error or "")
             for m in broken],
            {"unparsed_modules": broken}, "Every module in scope parses with the running Python's grammar.",
            "These modules were not evaluated; absence of findings for them is not evidence of compliance.",
            complete=False,
            next_steps=["Fix the syntax errors, or run ArchAI under the Python version the code targets."]))

    if dependency_rule:
        scope_set = set(scope)
        unresolved = [u for u in graph.unresolved_internal if u["source"] in scope_set]
        opaque = [u for u in graph.opaque_dynamic_imports if u["source"] in scope_set]
        if unresolved or opaque:
            mods = sorted({u["source"] for u in unresolved + opaque})
            evidence = [EvidenceRef("import_statement", u["file"], u["line"],
                                    f"{u['statement']}  [unresolved internal import]") for u in unresolved]
            evidence += [EvidenceRef("import_statement", u["file"], u["line"],
                                     f"{u['statement']}  [dynamic import with non-literal target]") for u in opaque]
            gaps.append(_finding(
                rule, INSUFFICIENT_GRAPH_EVIDENCE,
                ("incomplete-dependencies", tuple((e.file, e.line) for e in evidence)),
                f"{len(evidence)} import(s) in scope could not be resolved to a module, so the "
                f"dependency facts for {len(mods)} module(s) are incomplete.",
                mods, graph, evidence,
                {"unresolved_internal_imports": len(unresolved), "opaque_dynamic_imports": len(opaque)},
                "Every internal import in scope resolves to a module in the repository.",
                "Dependencies these imports might create were not evaluated.",
                complete=False,
                next_steps=["Check source_roots in the config, missing files, or dynamic imports."]))
    return gaps


# --- Rule 1: forbidden dependencies ---------------------------------------------

def _dependency_findings(rule: RuleSpec, graph: RepoGraph, pairs: Dict[Tuple[str, str], List[ImportEdge]],
                         expected: Callable[[str, str], str], describe: Callable[[str, str], str]) -> List[Finding]:
    findings = []
    for (src, dst), edges in sorted(pairs.items()):
        runtime = [e for e in edges if e.scope in RUNTIME_SCOPES]
        status = VERIFIED_VIOLATION if runtime else POTENTIAL_RISK
        limitations = []
        if not runtime:
            scopes = sorted({e.scope for e in edges})
            limitations.append(
                f"The dependency exists only as {', '.join(scopes)} import(s). Type-checking imports never "
                "run, and dynamic imports run only if that code path executes; whether this breaches the "
                "rule depends on how the standard treats such dependencies.")
        findings.append(_finding(
            rule, status, (src, dst), f"{describe(src, dst)}",
            [src, dst], graph, [_edge_evidence(graph, e) for e in edges],
            {"source_module": src, "target_module": dst,
             "import_lines": [e.line for e in edges], "scopes": sorted({e.scope for e in edges})},
            expected(src, dst),
            f"{len(edges)} import statement(s) in {graph.modules[src].path} resolve to '{dst}'.",
            limitations=limitations,
            next_steps=[f"Inspect {graph.modules[src].path} line(s) {', '.join(str(e.line) for e in edges)}; "
                        f"route the dependency through an allowed module or invert it."]))
    return findings


def evaluate_forbidden_dependency(rule: RuleSpec, layers, graph: RepoGraph) -> RuleResult:
    src_patterns, dst_patterns = rule.params["from"], rule.params["to"]
    scope = _scope(graph, src_patterns)
    findings = _evidence_gaps(rule, graph, scope, f"from: {', '.join(src_patterns)}")
    targets = _scope(graph, dst_patterns)
    if graph.modules and not targets:
        findings.append(_finding(
            rule, INSUFFICIENT_GRAPH_EVIDENCE, ("empty-target", tuple(dst_patterns)),
            "The forbidden targets matched no modules, so the rule cannot fail as written.",
            [], graph, [], {"to": dst_patterns}, "Target patterns should name existing modules.",
            "Not meaningfully evaluated: a typo in a pattern would look exactly like this.",
            complete=False, next_steps=["Check the 'to' patterns against module names."]))
    scope_set = set(scope)
    pairs: Dict[Tuple[str, str], List[ImportEdge]] = defaultdict(list)
    examined = 0
    for e in graph.edges:
        if e.source in scope_set:
            examined += 1
            if matches_any(e.target, dst_patterns) and not matches_any(e.target, src_patterns):
                pairs[(e.source, e.target)].append(e)
    findings += _dependency_findings(
        rule, graph, pairs,
        lambda s, d: f"Modules matching {src_patterns} must not import modules matching {dst_patterns}.",
        lambda s, d: f"'{s}' imports '{d}', which this rule forbids.")
    return _result(rule, findings, {"modules_in_scope": len(scope), "target_modules": len(targets),
                                    "edges_examined": examined})


# --- Rule 2: layer boundaries ---------------------------------------------------

def evaluate_layer_boundary(rule: RuleSpec, layers: Dict[str, List[str]], graph: RepoGraph) -> RuleResult:
    layer = rule.params["layer"]
    membership: Dict[str, List[str]] = {
        m: [name for name, pats in layers.items() if matches_any(m, pats)] for m in graph.modules}
    ambiguous = sorted(m for m, ls in membership.items() if len(ls) > 1)
    scope = sorted(m for m, ls in membership.items() if ls == [layer])
    findings = _evidence_gaps(rule, graph, scope, f"layer '{layer}'")
    if ambiguous:
        findings.append(_finding(
            rule, INSUFFICIENT_GRAPH_EVIDENCE, ("ambiguous-layers", tuple(ambiguous)),
            f"{len(ambiguous)} module(s) match more than one layer and were left out of this check.",
            ambiguous, graph,
            [EvidenceRef("module_file", graph.modules[m].path, None, f"layers: {', '.join(membership[m])}")
             for m in ambiguous],
            {m: membership[m] for m in ambiguous}, "Each module belongs to at most one layer.",
            "Edges to or from these modules were not evaluated.", complete=False,
            next_steps=["Make the layer patterns in the config non-overlapping."]))

    if "forbidden_layers" in rule.params:
        forbidden = set(rule.params["forbidden_layers"])
        is_breach = lambda target_layer: target_layer in forbidden
        expected = f"Layer '{layer}' must not depend on layer(s): {', '.join(sorted(forbidden))}."
    else:
        allowed = set(rule.params["allowed_layers"]) | {layer}
        is_breach = lambda target_layer: target_layer not in allowed
        expected = f"Layer '{layer}' may depend only on layer(s): {', '.join(sorted(allowed))}."

    scope_set = set(scope)
    pairs: Dict[Tuple[str, str], List[ImportEdge]] = defaultdict(list)
    examined = to_unlayered = 0
    for e in graph.edges:
        if e.source not in scope_set:
            continue
        examined += 1
        target_layers = membership.get(e.target, [])
        if not target_layers:
            to_unlayered += 1
        elif len(target_layers) == 1 and target_layers[0] != layer and is_breach(target_layers[0]):
            pairs[(e.source, e.target)].append(e)
    findings += _dependency_findings(
        rule, graph, pairs, lambda s, d: expected,
        lambda s, d: f"'{s}' (layer '{layer}') imports '{d}' (layer '{membership[d][0]}').")
    limitations = []
    if to_unlayered:
        limitations.append(f"{to_unlayered} import edge(s) from this layer point at modules assigned to no "
                           "layer; those edges are outside this rule's scope.")
    return _result(rule, findings, {"modules_in_scope": len(scope), "edges_examined": examined,
                                    "edges_to_unlayered_modules": to_unlayered}, limitations)


# --- Rule 3: circular dependencies ----------------------------------------------

def _sccs(nodes: List[str], adj: Dict[str, Set[str]]) -> List[List[str]]:
    """Tarjan's algorithm, iterative, with deterministic ordering."""
    index: Dict[str, int] = {}
    low: Dict[str, int] = {}
    on_stack: Set[str] = set()
    stack: List[str] = []
    result: List[List[str]] = []
    counter = 0
    for root in nodes:
        if root in index:
            continue
        work = [(root, iter(sorted(adj.get(root, ()))))]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        while work:
            node, children = work[-1]
            advanced = False
            for child in children:
                if child not in index:
                    index[child] = low[child] = counter
                    counter += 1
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, iter(sorted(adj.get(child, ())))))
                    advanced = True
                    break
                if child in on_stack:
                    low[node] = min(low[node], index[child])
            if advanced:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[node])
            if low[node] == index[node]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                result.append(sorted(component))
    return sorted(result)


def _shortest_path(start: str, goal: str, adj: Dict[str, Set[str]], allowed: Set[str]) -> Optional[List[str]]:
    previous: Dict[str, Optional[str]] = {start: None}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if node == goal:
            path = []
            while node is not None:
                path.append(node)
                node = previous[node]
            return path[::-1]
        for nxt in sorted(adj.get(node, ())):
            if nxt in allowed and nxt not in previous:
                previous[nxt] = node
                queue.append(nxt)
    return None


def _cycle_finding(rule: RuleSpec, graph: RepoGraph, status: str, component: List[str], cycle: List[str],
                   edge_index: Dict[Tuple[str, str], List[ImportEdge]], limitations: List[str]) -> Finding:
    evidence = []
    for a, b in zip(cycle, cycle[1:]):
        evidence.append(_edge_evidence(graph, sorted(edge_index[(a, b)], key=lambda e: e.line)[0]))
    path_text = " -> ".join(cycle)
    return _finding(
        rule, status, (tuple(component),),
        f"Import cycle among {len(component)} module(s): {path_text}",
        component, graph, evidence,
        {"cycle_path": cycle, "strongly_connected_modules": component},
        "No import cycles among modules in scope.",
        f"Each step of the cycle path is an import statement cited in the evidence "
        f"({len(component)} module(s) are mutually reachable).",
        limitations=limitations,
        next_steps=["Break the cycle by moving the shared code into a lower-level module, "
                    "or by inverting one dependency."])


def evaluate_circular_dependency(rule: RuleSpec, layers, graph: RepoGraph) -> RuleResult:
    scope = _scope(graph, rule.params["scope"])
    findings = _evidence_gaps(rule, graph, scope, f"scope: {', '.join(rule.params['scope'])}")
    scope_set = set(scope)
    in_scope = [e for e in graph.edges if e.source in scope_set and e.target in scope_set]

    def index(edges: List[ImportEdge]):
        adj: Dict[str, Set[str]] = defaultdict(set)
        by_pair: Dict[Tuple[str, str], List[ImportEdge]] = defaultdict(list)
        for e in edges:
            adj[e.source].add(e.target)
            by_pair[(e.source, e.target)].append(e)
        return adj, by_pair

    strict_adj, strict_pairs = index([e for e in in_scope if e.scope == SCOPE_MODULE])
    full_adj, full_pairs = index(in_scope)

    verified_components = [c for c in _sccs(scope, strict_adj) if len(c) > 1]
    for comp in verified_components:
        cycle = [comp[0]] + _shortest_path(next(iter(sorted(strict_adj[comp[0]] & set(comp)))),
                                           comp[0], strict_adj, set(comp))
        findings.append(_cycle_finding(rule, graph, VERIFIED_VIOLATION, comp, cycle, strict_pairs, []))

    verified_sets = [set(c) for c in verified_components]
    for comp in [c for c in _sccs(scope, full_adj) if len(c) > 1]:
        if set(comp) in verified_sets:
            continue
        members = set(comp)
        cycle = None
        for (u, v) in sorted(full_pairs):
            if u in members and v in members and (u, v) not in strict_pairs:
                back = _shortest_path(v, u, full_adj, members)
                if back:
                    cycle = [u] + back
                    break
        if cycle is None:
            continue
        findings.append(_cycle_finding(
            rule, graph, POTENTIAL_RISK, comp, cycle, full_pairs,
            ["This cycle is closed only through function-level, type-checking or dynamic imports. "
             "Those do not run at module import time, so the cycle may be deliberate and harmless; "
             "it still couples these modules."]))

    return _result(rule, findings, {"modules_in_scope": len(scope), "edges_examined": len(in_scope),
                                    "module_scope_edges": sum(len(v) for v in strict_pairs.values())})


# --- Rule 4: excessive coupling -------------------------------------------------

def evaluate_coupling_threshold(rule: RuleSpec, layers, graph: RepoGraph) -> RuleResult:
    metric, maximum = rule.params["metric"], rule.params["max"]
    scope = _scope(graph, rule.params["scope"])
    findings = _evidence_gaps(rule, graph, scope, f"scope: {', '.join(rule.params['scope'])}")

    counted: Dict[str, Dict[str, List[ImportEdge]]] = defaultdict(lambda: defaultdict(list))
    other: Dict[str, Dict[str, List[ImportEdge]]] = defaultdict(lambda: defaultdict(list))
    for e in graph.edges:
        subject, peer = (e.source, e.target) if metric == "fan_out" else (e.target, e.source)
        (counted if e.scope in RUNTIME_SCOPES else other)[subject][peer].append(e)

    measured = {}
    for module in scope:
        peers = counted.get(module, {})
        value = len(peers)
        measured[module] = value
        extra = {p: es for p, es in other.get(module, {}).items() if p not in peers}
        direction = "imports" if metric == "fan_out" else "is imported by"
        if value > maximum:
            status, summary = VERIFIED_VIOLATION, f"'{module}' {direction} {value} internal modules; the threshold is {maximum}."
            evidence_peers, limitations = peers, []
        elif value + len(extra) > maximum:
            status = POTENTIAL_RISK
            summary = (f"'{module}' {direction} {value} internal modules at runtime (threshold {maximum}); "
                       f"counting {len(extra)} type-checking/dynamic dependencies gives {value + len(extra)}.")
            evidence_peers = {**peers, **extra}
            limitations = ["Type-checking and dynamic imports are not counted toward the measured value."]
        else:
            continue
        evidence = [_edge_evidence(graph, sorted(es, key=lambda e: e.line)[0])
                    for _, es in sorted(evidence_peers.items())]
        findings.append(_finding(
            rule, status, (module, metric, value, maximum), summary, [module], graph, evidence,
            {"metric": metric, "measured_value": value, "threshold": maximum,
             "counted_modules": sorted(peers), "uncounted_modules": sorted(extra)},
            f"{metric} <= {maximum} (configured threshold).",
            f"{metric} counts distinct internal modules linked by runtime imports "
            f"(module- and function-level); measured {value}.",
            limitations=limitations + ["Imports of third-party and standard-library modules are not counted."],
            next_steps=["Review whether the dependencies cluster into a responsibility that could be split out."]))

    values = sorted(measured.values())
    return _result(rule, findings, {
        "modules_in_scope": len(scope), "metric": metric, "threshold": maximum,
        "max_measured": values[-1] if values else None,
        "median_measured": values[len(values) // 2] if values else None})


# --- Rule 5: required tests -----------------------------------------------------

def _is_test_module(name: str, path: str) -> bool:
    leaf = name.split(".")[-1]
    return leaf.startswith("test_") or leaf.endswith("_test") or "tests" in path.split("/")[:-1] \
        or "test" in path.split("/")[:-1]


def evaluate_required_tests(rule: RuleSpec, layers, graph: RepoGraph) -> RuleResult:
    templates = rule.params["test_paths"]
    scope = [m for m in _scope(graph, rule.params["scope"])
             if rule.params["include_packages"] or not graph.modules[m].is_package]
    scope = [m for m in scope if not _is_test_module(m, graph.modules[m].path)]
    findings = _evidence_gaps(rule, graph, scope, f"scope: {', '.join(rule.params['scope'])}",
                              dependency_rule=False)
    files = set(graph.files)
    test_importers: Dict[str, List[ImportEdge]] = defaultdict(list)
    for e in graph.edges:
        if _is_test_module(e.source, graph.modules[e.source].path):
            test_importers[e.target].append(e)

    satisfied = 0
    for module in scope:
        parts = module.split(".")
        mapping = {"leaf": parts[-1], "module": module, "module_path": "/".join(parts),
                   "parent_path": "/".join(parts[:-1])}
        candidates = sorted({"/".join(p for p in t.format(**mapping).split("/") if p) for t in templates})
        if any(c in files for c in candidates):
            satisfied += 1
            continue
        importers = test_importers.get(module, [])
        evidence = [EvidenceRef("module_file", graph.modules[module].path, None, "module requiring a test")]
        evidence += [EvidenceRef("missing_file", c, None, "expected test file not present in the repository")
                     for c in candidates]
        limitations = ["Checks file existence by naming convention only; it does not measure test coverage."]
        if graph.excluded_modules:
            limitations.append("Modules excluded by config were not searched for imports of this module.")
        if importers:
            status = POTENTIAL_RISK
            summary = (f"No test file at the conventional path for '{module}', but "
                       f"{len({e.source for e in importers})} test module(s) import it.")
            evidence += [_edge_evidence(graph, e) for e in importers]
        else:
            status = VERIFIED_VIOLATION
            summary = f"No test file at the conventional path for '{module}', and no test module imports it."
        findings.append(_finding(
            rule, status, (module, tuple(candidates)), summary,
            [module] + sorted({e.source for e in importers}), graph, evidence,
            {"module": module, "checked_paths": candidates,
             "test_modules_importing": sorted({e.source for e in importers})},
            f"One of: {', '.join(candidates)} exists.",
            "None of the configured test paths exist in the analyzed file inventory.",
            limitations=limitations,
            next_steps=[f"Add {candidates[0]}, or adjust the test_paths convention if tests live elsewhere."]))
    return _result(rule, findings, {"modules_in_scope": len(scope), "modules_with_test_file": satisfied})


# --- Dispatch -------------------------------------------------------------------

EVALUATORS = {
    "forbidden_dependency": evaluate_forbidden_dependency,
    "layer_boundary": evaluate_layer_boundary,
    "circular_dependency": evaluate_circular_dependency,
    "coupling_threshold": evaluate_coupling_threshold,
    "required_tests": evaluate_required_tests,
}


def _result(rule: RuleSpec, findings: List[Finding], stats: Dict, limitations: Optional[List[str]] = None) -> RuleResult:
    findings = sorted(findings, key=lambda f: (STATUS_RANK[f.status], f.modules, f.id))
    return RuleResult(
        rule_id=rule.id, kind=rule.kind, description=rule.description, rationale=rule.rationale,
        origin=rule.origin, params=rule.params,
        outcome=worst_status([f.status for f in findings]) if findings else PASS,
        scope_stats=stats, findings=findings, limitations=limitations or [])


STATUS_RANK = {VERIFIED_VIOLATION: 0, POTENTIAL_RISK: 1, INSUFFICIENT_GRAPH_EVIDENCE: 2, PASS: 3}


def evaluate_rule(rule: RuleSpec, layers: Dict[str, List[str]], graph: RepoGraph) -> RuleResult:
    return EVALUATORS[rule.kind](rule, layers, graph)
