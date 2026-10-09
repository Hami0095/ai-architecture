"""Standards checker against synthetic repositories with known outcomes.

Each test asserts the exact status, the modules involved, and the cited
evidence (file and line), not merely that a finding exists.
"""
import json
from pathlib import Path

import pytest
import yaml

from ai_architect.standards import StandardsConfigError, deterministic_view, run_check
from ai_architect.standards.config import parse_config
from ai_architect.standards.model import (
    INSUFFICIENT_GRAPH_EVIDENCE, PASS, POTENTIAL_RISK, VERIFIED_VIOLATION,
)

PKG = {
    "app/__init__.py": "",
    "app/domain/__init__.py": "",
    "app/infra/__init__.py": "",
    "app/api/__init__.py": "",
}

LAYERS = {"domain": ["app.domain"], "infrastructure": ["app.infra"], "api": ["app.api"]}

ALL_RULES = {
    "version": 1,
    "layers": LAYERS,
    "rules": [
        {"id": "api-no-infra", "kind": "forbidden_dependency", "from": ["app.api"], "to": ["app.infra"]},
        {"id": "domain-pure", "kind": "layer_boundary", "layer": "domain", "forbidden_layers": ["infrastructure"]},
        {"id": "no-cycles", "kind": "circular_dependency", "scope": ["app"]},
        {"id": "fan-out", "kind": "coupling_threshold", "metric": "fan_out", "max": 2, "scope": ["app"]},
        {"id": "tests", "kind": "required_tests", "scope": ["app.domain"], "test_paths": ["tests/test_{leaf}.py"]},
    ],
}

CLEAN = {
    **PKG,
    "app/domain/order.py": "from dataclasses import dataclass\n\n@dataclass\nclass Order:\n    id: int\n",
    "app/infra/repo.py": "from app.domain.order import Order\n\ndef load():\n    return Order(1)\n",
    "app/api/routes.py": "from app.domain.order import Order\n",
    "tests/test_order.py": "from app.domain.order import Order\n",
}


def check(root, config, **kw):
    cfg = root / "archai_standards.yaml"
    cfg.write_text(yaml.safe_dump(config), encoding="utf-8")
    return run_check(str(root), str(cfg), **kw)


def rule(report, rule_id):
    return next(r for r in report["rule_results"] if r["rule_id"] == rule_id)


def findings(report, rule_id, status=None):
    return [f for f in rule(report, rule_id)["findings"] if status is None or f["status"] == status]


def evidence_lines(finding):
    return [(e["file"], e["line"]) for e in finding["evidence"] if e["kind"] == "import_statement"]


# --- Clean repository -----------------------------------------------------------

def test_clean_repository_passes_every_rule(make_repo):
    report = check(make_repo(CLEAN), ALL_RULES)
    assert [r["outcome"] for r in report["rule_results"]] == [PASS] * 5
    assert report["summary"]["findings_total"] == 0
    assert report["provenance"]["llm_used"] is False
    assert report["analysis"]["python_modules"] == 8  # 4 packages + 3 modules + tests.test_order


# --- Rule 1: forbidden dependency -----------------------------------------------

def test_forbidden_import_is_verified_with_exact_line(make_repo):
    root = make_repo({**CLEAN, "app/api/routes.py": "import json\n\nfrom app.infra.repo import load\n"})
    report = check(root, ALL_RULES)
    [f] = findings(report, "api-no-infra")
    assert f["status"] == VERIFIED_VIOLATION
    assert f["modules"] == ["app.api.routes", "app.infra.repo"]
    assert evidence_lines(f) == [("app/api/routes.py", 3)]
    assert "from app.infra.repo import load" in f["evidence"][0]["detail"]
    assert f["verification"] == {"method": "deterministic-static-analysis", "llm_assisted": False,
                                 "evidence_completeness": "complete"}


def test_function_level_import_still_counts_as_dependency(make_repo):
    root = make_repo({**CLEAN, "app/api/routes.py": "def handler():\n    from app.infra import repo\n"})
    [f] = findings(check(root, ALL_RULES), "api-no-infra")
    assert f["status"] == VERIFIED_VIOLATION
    assert f["observed"]["scopes"] == ["function"]
    assert evidence_lines(f) == [("app/api/routes.py", 2)]


def test_type_checking_only_import_is_potential_risk_not_violation(make_repo):
    root = make_repo({**CLEAN, "app/api/routes.py": (
        "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from app.infra.repo import load\n")})
    [f] = findings(check(root, ALL_RULES), "api-no-infra")
    assert f["status"] == POTENTIAL_RISK
    assert f["limitations"]


def test_similar_names_and_text_do_not_trigger_false_positives(make_repo):
    root = make_repo({
        **CLEAN,
        "app/infra_helpers.py": "",
        "app/api/routes.py": (
            '"""Docs: never write `import app.infra` here."""\n'
            "# from app.infra import repo\n"
            "from app import infra_helpers\n"
            "import infra  # third-party package of the same leaf name\n"
            "s = 'from app.infra import repo'\n"),
    })
    report = check(root, ALL_RULES)
    assert findings(report, "api-no-infra") == []
    assert rule(report, "api-no-infra")["outcome"] == PASS


def test_dynamic_import_with_literal_target_is_potential_risk(make_repo):
    root = make_repo({**CLEAN, "app/api/routes.py": (
        "import importlib\n\ndef get():\n    return importlib.import_module('app.infra.repo')\n")})
    [f] = findings(check(root, ALL_RULES), "api-no-infra")
    assert f["status"] == POTENTIAL_RISK
    assert evidence_lines(f) == [("app/api/routes.py", 4)]


# --- Rule 2: layer boundaries ---------------------------------------------------

def test_layer_violation_reports_both_layers(make_repo):
    root = make_repo({**CLEAN, "app/domain/order.py": "from app.infra.repo import load\n"})
    report = check(root, ALL_RULES)
    [f] = findings(report, "domain-pure")
    assert f["status"] == VERIFIED_VIOLATION
    assert "(layer 'domain')" in f["summary"] and "(layer 'infrastructure')" in f["summary"]
    assert evidence_lines(f) == [("app/domain/order.py", 1)]


def test_allowed_layers_mode_and_unlayered_edges(make_repo):
    root = make_repo({**CLEAN, "app/shared.py": "",
                      "app/domain/order.py": "from app import shared\nfrom app.api import routes\n"})
    config = {"layers": LAYERS, "rules": [
        {"id": "domain-allow", "kind": "layer_boundary", "layer": "domain", "allowed_layers": []}]}
    report = check(root, config)
    [f] = findings(report, "domain-allow")
    assert f["modules"] == ["app.api.routes", "app.domain.order"]
    result = rule(report, "domain-allow")
    assert result["scope_stats"]["edges_to_unlayered_modules"] == 1  # app.shared
    assert result["limitations"]


def test_overlapping_layers_are_reported_not_guessed(make_repo):
    root = make_repo({**CLEAN, "app/domain/order.py": "from app.infra.repo import load\n"})
    config = {"layers": {"domain": ["app.domain"], "infrastructure": ["app.infra", "app.domain.order"]},
              "rules": [{"id": "d", "kind": "layer_boundary", "layer": "domain",
                         "forbidden_layers": ["infrastructure"]}]}
    report = check(root, config)
    statuses = [f["status"] for f in findings(report, "d")]
    assert statuses == [INSUFFICIENT_GRAPH_EVIDENCE]
    assert rule(report, "d")["outcome"] == INSUFFICIENT_GRAPH_EVIDENCE


# --- Rule 3: cycles -------------------------------------------------------------

def test_cycle_reports_concrete_path_with_each_edge_cited(make_repo):
    root = make_repo({**PKG,
                      "app/a.py": "from app import b\n",
                      "app/b.py": "import os\nfrom app.c import thing\n",
                      "app/c.py": "thing = 1\nimport app.a\n"})
    [f] = findings(check(root, ALL_RULES), "no-cycles")
    assert f["status"] == VERIFIED_VIOLATION
    assert f["observed"]["cycle_path"] == ["app.a", "app.b", "app.c", "app.a"]
    assert evidence_lines(f) == [("app/a.py", 1), ("app/b.py", 2), ("app/c.py", 2)]


def test_cycle_closed_only_by_deferred_import_is_potential_risk(make_repo):
    root = make_repo({**PKG,
                      "app/a.py": "from app import b\n",
                      "app/b.py": "def f():\n    from app import a\n"})
    [f] = findings(check(root, ALL_RULES), "no-cycles")
    assert f["status"] == POTENTIAL_RISK
    assert f["observed"]["cycle_path"] == ["app.b", "app.a", "app.b"]


def test_acyclic_chain_is_not_a_cycle(make_repo):
    root = make_repo({**PKG, "app/a.py": "from app import b\n", "app/b.py": "from app import c\n",
                      "app/c.py": "x = 1\n"})
    assert rule(check(root, ALL_RULES), "no-cycles")["outcome"] == PASS


# --- Rule 4: coupling -----------------------------------------------------------

def _fan_out_repo(make_repo, n):
    files = {**PKG, **{f"app/m{i}.py": "" for i in range(n)}}
    files["app/hub.py"] = "".join(f"from app import m{i}\n" for i in range(n)) + "import json\nimport os\n"
    return make_repo(files)


def test_coupling_reports_measured_value_and_threshold(make_repo):
    report = check(_fan_out_repo(make_repo, 3), ALL_RULES)
    [f] = findings(report, "fan-out")
    assert f["status"] == VERIFIED_VIOLATION
    assert f["observed"]["measured_value"] == 3 and f["observed"]["threshold"] == 2
    assert f["observed"]["counted_modules"] == ["app.m0", "app.m1", "app.m2"]
    assert evidence_lines(f) == [("app/hub.py", 1), ("app/hub.py", 2), ("app/hub.py", 3)]


def test_coupling_at_threshold_passes_and_ignores_stdlib(make_repo):
    report = check(_fan_out_repo(make_repo, 2), ALL_RULES)
    assert findings(report, "fan-out") == []
    assert rule(report, "fan-out")["scope_stats"]["max_measured"] == 2


def test_fan_in_metric(make_repo):
    root = make_repo({**PKG, "app/core.py": "", **{f"app/u{i}.py": "from app import core\n" for i in range(3)}})
    config = {"rules": [{"id": "fan-in", "kind": "coupling_threshold", "metric": "fan_in", "max": 2}]}
    [f] = findings(check(root, config), "fan-in")
    assert f["modules"] == ["app.core"] and f["observed"]["measured_value"] == 3


# --- Rule 5: required tests -----------------------------------------------------

def test_missing_required_test_is_verified(make_repo):
    root = make_repo({**CLEAN, "app/domain/invoice.py": "x = 1\n"})
    [f] = findings(check(root, ALL_RULES), "tests")
    assert f["status"] == VERIFIED_VIOLATION
    assert f["modules"] == ["app.domain.invoice"]
    assert f["observed"]["checked_paths"] == ["tests/test_invoice.py"]
    assert {(e["kind"], e["file"]) for e in f["evidence"]} == {
        ("module_file", "app/domain/invoice.py"), ("missing_file", "tests/test_invoice.py")}
    assert any("coverage" in note for note in f["limitations"])


def test_test_elsewhere_that_imports_module_is_potential_risk(make_repo):
    root = make_repo({**CLEAN, "app/domain/invoice.py": "x = 1\n",
                      "tests/test_billing.py": "from app.domain import invoice\n"})
    [f] = findings(check(root, ALL_RULES), "tests")
    assert f["status"] == POTENTIAL_RISK
    assert f["observed"]["test_modules_importing"] == ["tests.test_billing"]


def test_required_tests_template_placeholders(make_repo):
    root = make_repo({**CLEAN, "tests/app/domain/test_order.py": ""})
    config = {"rules": [{"id": "mirror", "kind": "required_tests", "scope": ["app.domain"],
                         "test_paths": ["tests/{parent_path}/test_{leaf}.py"]}]}
    assert rule(check(root, config), "mirror")["outcome"] == PASS


# --- Insufficient evidence ------------------------------------------------------

def test_syntax_error_is_insufficient_evidence_not_clean(make_repo):
    root = make_repo({**CLEAN, "app/api/broken.py": "def oops(:\n    from app.infra import repo\n"})
    report = check(root, ALL_RULES)
    result = rule(report, "api-no-infra")
    assert result["outcome"] == INSUFFICIENT_GRAPH_EVIDENCE
    [f] = result["findings"]
    assert f["modules"] == ["app.api.broken"]
    assert f["evidence"][0]["kind"] == "parse_error" and f["evidence"][0]["line"] is None
    assert f["verification"]["evidence_completeness"] == "partial"
    assert report["analysis"]["parse_failures"] == ["app.api.broken"]


def test_scope_matching_nothing_is_insufficient(make_repo):
    config = {"rules": [{"id": "typo", "kind": "forbidden_dependency", "from": ["app.apii"], "to": ["app.infra"]}]}
    report = check(make_repo(CLEAN), config)
    assert rule(report, "typo")["outcome"] == INSUFFICIENT_GRAPH_EVIDENCE
    assert "matched no modules" in findings(report, "typo")[0]["summary"]


def test_unresolved_internal_import_is_insufficient(make_repo):
    root = make_repo({**CLEAN, "app/api/routes.py": "from app.infrastructure import db\n"})
    result = rule(check(root, ALL_RULES), "api-no-infra")
    assert result["outcome"] == INSUFFICIENT_GRAPH_EVIDENCE
    assert evidence_lines(result["findings"][0]) == [("app/api/routes.py", 1)]


def test_unsupported_language_is_reported_not_treated_as_clean(make_repo):
    root = make_repo({"src/index.ts": "import { db } from './infra';\n", "src/infra.ts": "export const db = 1;\n"})
    report = check(root, {"rules": [{"id": "no-cycles", "kind": "circular_dependency"}]})
    assert rule(report, "no-cycles")["outcome"] == INSUFFICIENT_GRAPH_EVIDENCE
    assert report["analysis"]["unsupported_files"] == {".ts": 2}
    assert any("Unsupported source files" in note for note in report["limitations"])


# --- Resolution details ---------------------------------------------------------

def test_relative_imports_and_src_layout(make_repo):
    root = make_repo({"src/pkg/__init__.py": "from . import a\n", "src/pkg/a.py": "from .b import x\n",
                      "src/pkg/b.py": "from ..pkg import a\nx = 1\n"})
    report = check(root, {"rules": [{"id": "c", "kind": "circular_dependency"}]})
    edges = {(e.source, e.target) for e in report["_graph"].edges}
    assert edges == {("pkg", "pkg.a"), ("pkg.a", "pkg.b"), ("pkg.b", "pkg.a")}
    [f] = findings(report, "c")
    assert f["status"] == VERIFIED_VIOLATION and f["files"] == ["src/pkg/a.py", "src/pkg/b.py"]


def test_excluded_paths_leave_the_analyzed_system(make_repo):
    root = make_repo({**CLEAN, "app/api/routes.py": "from app.infra.repo import load\n"})
    config = {**ALL_RULES, "exclude": ["app/infra/*"]}
    report = check(root, config)
    assert findings(report, "api-no-infra")[0]["status"] == INSUFFICIENT_GRAPH_EVIDENCE  # target now empty
    assert "app.infra.repo" in report["analysis"]["excluded_modules"]


# --- Determinism, configuration, defaults ---------------------------------------

def test_repeated_runs_are_identical(make_repo):
    root = make_repo({**CLEAN, "app/a.py": "from app import b\n", "app/b.py": "from app import a\n",
                      "app/domain/order.py": "from app.infra.repo import load\n"})
    first, second = check(root, ALL_RULES), check(root, ALL_RULES)
    assert json.dumps(deterministic_view(first), sort_keys=True, default=str) == \
        json.dumps(deterministic_view(second), sort_keys=True, default=str)
    assert first["summary"]["findings_total"] > 0


def test_defaults_are_labelled_and_only_used_without_rules(make_repo):
    report = run_check(str(make_repo(CLEAN)))
    [r] = report["rule_results"]
    assert r["rule_id"] == "archai.default.no-import-cycles" and r["origin"] == "archai-default"
    assert "not your organization's standards" in report["limitations"][0]
    configured = parse_config({"rules": [{"id": "x", "kind": "coupling_threshold", "max": 3}]})
    assert [r.origin for r in configured.rules] == ["user-config"]


@pytest.mark.parametrize("bad, message", [
    ({"rules": [{"id": "x", "kind": "magic"}]}, "unknown kind"),
    ({"rules": [{"kind": "circular_dependency"}]}, "missing required key 'id'"),
    ({"rules": [{"id": "x", "kind": "layer_boundary", "layer": "nope", "forbidden_layers": []}]}, "not declared"),
    ({"rules": [{"id": "x", "kind": "coupling_threshold", "max": -1}]}, "non-negative"),
    ({"rules": [{"id": "x", "kind": "coupling_threshold", "max": "5"}]}, "non-negative"),
    ({"rules": [{"id": "x", "kind": "required_tests", "scope": "a", "test_paths": "tests/x.py"}]}, "uses none of"),
    ({"rules": [{"id": "x", "kind": "circular_dependency"}, {"id": "x", "kind": "circular_dependency"}]}, "Duplicate"),
    ({"rulez": []}, "Unknown top-level"),
    ({"version": 2}, "Unsupported config version"),
    (["not", "a", "mapping"], "must be a YAML mapping"),
])
def test_malformed_config_is_rejected(bad, message):
    with pytest.raises(StandardsConfigError, match=message):
        parse_config(bad)


def test_missing_and_unparseable_config_files(make_repo, tmp_path):
    root = make_repo(CLEAN)
    with pytest.raises(StandardsConfigError, match="not found"):
        run_check(str(root), str(tmp_path / "missing.yaml"))
    bad = tmp_path / "bad.yaml"
    bad.write_text("rules: [unclosed", encoding="utf-8")
    with pytest.raises(StandardsConfigError, match="Could not parse"):
        run_check(str(root), str(bad))


# --- No fabricated evidence -----------------------------------------------------

def test_every_cited_line_exists_and_holds_the_cited_statement(make_repo):
    root = make_repo({**CLEAN,
                      "app/a.py": "from app import b\n", "app/b.py": "\n\nfrom app import a\n",
                      "app/domain/order.py": "x = 1\n\nfrom app.infra.repo import load\n",
                      "app/domain/invoice.py": "", "app/api/routes.py": "def f():\n    import app.infra.repo\n"})
    report = check(root, ALL_RULES)
    cited = 0
    for r in report["rule_results"]:
        for f in r["findings"]:
            for ev in f["evidence"]:
                if ev["kind"] == "missing_file":
                    assert not (root / ev["file"]).exists()
                    continue
                assert (root / ev["file"]).is_file()
                if ev["line"] is not None:
                    line = (root / ev["file"]).read_text(encoding="utf-8").splitlines()[ev["line"] - 1]
                    assert line.strip() == ev["detail"].split("  [scope")[0]
                    cited += 1
    assert cited >= 5


def test_shipped_example_config_is_valid():
    from ai_architect.standards.config import load_config
    root = Path(__file__).resolve().parent.parent
    config = load_config(root, root / "examples" / "archai_standards.example.yaml")
    assert sorted({r.kind for r in config.rules}) == sorted(
        ["forbidden_dependency", "layer_boundary", "circular_dependency", "coupling_threshold", "required_tests"])
