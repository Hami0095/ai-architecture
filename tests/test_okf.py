"""OKF v0.2 bundle export, round trip, conformance, and adjudication from the bundle."""
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest
import yaml

from ai_architect.okf import OKFDocument, check_conformance, export_bundle, load_bundle
from ai_architect.okf.document import trust_tier
from ai_architect.standards import run_check

FILES = {
    "app/__init__.py": "",
    "app/domain/__init__.py": "",
    "app/infra/__init__.py": "",
    "app/domain/order.py": "from app.infra.repo import load\n",
    "app/infra/repo.py": "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from app.domain import order\n",
    "app/a.py": "from app import b\n",
    "app/b.py": "from app import a\n",
    "app/broken.py": "def oops(:\n",
    "web/app.ts": "export {}\n",
}
CONFIG = {
    "layers": {"domain": ["app.domain"], "infrastructure": ["app.infra"]},
    "rules": [
        {"id": "domain-pure", "kind": "layer_boundary", "layer": "domain", "forbidden_layers": ["infrastructure"],
         "rationale": "Domain logic must stay testable without I/O."},
        {"id": "no-cycles", "kind": "circular_dependency"},
        {"id": "fan-out", "kind": "coupling_threshold", "max": 0, "scope": ["app.domain"]},
        {"id": "tests", "kind": "required_tests", "scope": ["app.domain"], "test_paths": ["tests/test_{leaf}.py"]},
    ],
}


@pytest.fixture
def analyzed(make_repo, tmp_path):
    root = make_repo(FILES)
    cfg = root / "archai_standards.yaml"
    cfg.write_text(yaml.safe_dump(CONFIG), encoding="utf-8")
    report = run_check(str(root), str(cfg))
    bundle = export_bundle(report, str(tmp_path / "bundle"))
    return report, bundle


def all_findings(report):
    return [f for r in report["rule_results"] for f in r["findings"]]


def test_bundle_is_conformant(analyzed):
    _, bundle = analyzed
    result = check_conformance(str(bundle))
    assert result == {"okf_version": "0.2", "conformant": True, "concepts": result["concepts"], "errors": []}
    root_index = OKFDocument.parse((bundle / "index.md").read_text(encoding="utf-8"))
    assert root_index.frontmatter == {"okf_version": "0.2"}


def test_every_concept_has_type_and_actor_and_is_unverified(analyzed):
    _, bundle = analyzed
    for path in bundle.rglob("*.md"):
        if path.name in ("index.md", "log.md"):
            continue
        fm = OKFDocument.parse(path.read_text(encoding="utf-8")).frontmatter
        assert fm["type"]
        assert fm["generated"]["by"].startswith("archai/")
        assert fm["generated"]["at"].endswith("Z")
        # Extraction is not independent confirmation, so nothing claims `verified`.
        assert trust_tier(fm) == "unverified"


def test_round_trip_preserves_graph_rules_and_findings(analyzed):
    report, bundle = analyzed
    loaded = load_bundle(str(bundle))
    assert loaded["graph"].to_dict() == report["_graph"].to_dict()
    assert [r.id for r in loaded["config"].rules] == [r.id for r in report["_config"].rules]
    assert loaded["config"].layers == report["_config"].layers
    assert loaded["findings"] == {f["id"]: f for f in all_findings(report)}


def test_adjudication_from_bundle_matches_adjudication_from_source(analyzed):
    """Condition B (facts via OKF) must reproduce condition A (facts from source)."""
    report, bundle = analyzed
    loaded = load_bundle(str(bundle))
    replay = run_check(None, graph=loaded["graph"], config=loaded["config"], fact_source="okf-bundle")
    assert replay["provenance"]["fact_source"] == "okf-bundle"
    assert replay["rule_results"] == report["rule_results"]
    statuses = {f["status"] for f in all_findings(report)}
    assert {"VERIFIED_VIOLATION", "POTENTIAL_RISK", "INSUFFICIENT_GRAPH_EVIDENCE"} <= statuses


def test_finding_concepts_attribute_evidence_through_sources(analyzed):
    report, bundle = analyzed
    finding = next(f for f in all_findings(report) if f["rule_id"] == "domain-pure"
                   and f["status"] == "VERIFIED_VIOLATION")
    doc = OKFDocument.parse((bundle / "findings" / f"{finding['id']}.md").read_text(encoding="utf-8"))
    assert doc.frontmatter["sources"] == [
        {"id": "ev1", "resource": "/modules/app.domain.order.md", "title": "app/domain/order.py:1"}]
    assert "[^ev1]" in doc.body and "[^ev1]: app/domain/order.py:1" in doc.body
    assert (bundle / "modules" / "app.domain.order.md").exists()


def test_bundle_bytes_are_reproducible(make_repo, tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1790000000")
    root = make_repo(FILES)
    cfg = root / "archai_standards.yaml"
    cfg.write_text(yaml.safe_dump(CONFIG), encoding="utf-8")

    def snapshot(name):
        report = run_check(str(root), str(cfg))
        report["provenance"]["duration_ms"] = 0  # wall-clock; the only run-varying field
        out = export_bundle(report, str(tmp_path / name))
        return {p.relative_to(out).as_posix(): p.read_bytes() for p in sorted(out.rglob("*.md"))}

    assert snapshot("one") == snapshot("two")


def test_bundle_stores_no_source_code_beyond_import_statements(analyzed):
    _, bundle = analyzed
    text = "\n".join(p.read_text(encoding="utf-8") for p in bundle.rglob("*.md"))
    assert "def oops" not in text  # file contents are never copied
    assert "export {}" not in text


def test_export_refuses_to_overwrite_unrelated_directory(analyzed, tmp_path):
    report, _ = analyzed
    target = tmp_path / "precious"
    target.mkdir()
    (target / "notes.txt").write_text("keep me", encoding="utf-8")
    with pytest.raises(FileExistsError):
        export_bundle(report, str(target))
    assert (target / "notes.txt").exists()


def test_conformance_checker_detects_violations(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "no_type.md").write_text("---\ntitle: x\n---\nbody\n", encoding="utf-8")
    (tmp_path / "no_frontmatter.md").write_text("just text\n", encoding="utf-8")
    (tmp_path / "ok.md").write_text("---\ntype: Note\n---\n", encoding="utf-8")
    (tmp_path / "sub" / "index.md").write_text("---\nokf_version: '0.2'\n---\n# X\n", encoding="utf-8")
    (tmp_path / "log.md").write_text("# Log\n\n## May 5th\n", encoding="utf-8")
    result = check_conformance(str(tmp_path))
    assert not result["conformant"]
    joined = "\n".join(result["errors"])
    for expected in ("no_type.md", "no_frontmatter.md", "sub/index.md", "log.md"):
        assert expected in joined
    assert "ok.md" not in joined


def test_frontmatter_timestamps_round_trip_as_written():
    text = "---\ntype: Note\ngenerated:\n  by: human:x\n  at: 2026-06-30T14:00:00Z\n---\n\nBody\n"
    doc = OKFDocument.parse(text)
    assert doc.frontmatter["generated"]["at"] == "2026-06-30T14:00:00Z"
    assert OKFDocument.parse(doc.serialize()).frontmatter == doc.frontmatter
    assert trust_tier(doc.frontmatter) == "unverified"
    assert trust_tier({"verified": {"by": "human:x", "at": "2026-01-01T00:00:00Z"}}) == "human-reviewed"
    assert trust_tier({"verified": [{"by": "process:ci", "at": "2026-01-01T00:00:00Z"}]}) == "machine-confirmed"


@pytest.mark.skipif(not os.environ.get("OKF_REFERENCE_SRC"),
                    reason="set OKF_REFERENCE_SRC to a checkout of GoogleCloudPlatform/open-knowledge-format/src")
def test_reference_implementation_parses_bundle_identically(analyzed):
    """Cross-check with the upstream reference parser (reference_agent.bundle.document)."""
    path = Path(os.environ["OKF_REFERENCE_SRC"]) / "reference_agent" / "bundle" / "document.py"
    spec = importlib.util.spec_from_file_location("okf_reference_document", path)
    ref = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = ref
    spec.loader.exec_module(ref)
    _, bundle = analyzed
    concepts = 0
    for md in sorted(bundle.rglob("*.md")):
        text = md.read_text(encoding="utf-8")
        theirs, ours = ref.OKFDocument.parse(text), OKFDocument.parse(text)
        assert (theirs.frontmatter, theirs.body) == (ours.frontmatter, ours.body), md
        if md.name not in ("index.md", "log.md"):
            theirs.validate()
            concepts += 1
    assert concepts > 10
