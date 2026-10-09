"""OKF-VIEW: terminal previewer for ArchAI and generic OKF bundles."""
import textwrap

import pytest
import yaml

from ai_architect.cli import process_command
from ai_architect.okf import export_bundle
from ai_architect.okf.viewer import BundleView, render
from ai_architect.standards import run_check

FILES = {
    "app/__init__.py": "",
    "app/a.py": "from app import b\n",
    "app/b.py": "from app import a\n",
    "app/domain/__init__.py": "",
    "app/domain/order.py": "x = 1\n",
}
CONFIG = {"rules": [
    {"id": "no-cycles", "kind": "circular_dependency"},
    {"id": "tests", "kind": "required_tests", "scope": ["app.domain"], "test_paths": ["tests/test_{leaf}.py"]},
]}


@pytest.fixture
def bundle(make_repo, tmp_path):
    root = make_repo(FILES)
    cfg = root / "archai_standards.yaml"
    cfg.write_text(yaml.safe_dump(CONFIG), encoding="utf-8")
    report = run_check(str(root), str(cfg))
    return export_bundle(report, str(tmp_path / "bundle")), report


@pytest.fixture
def generic_bundle(tmp_path):
    """A hand-written, non-ArchAI bundle exercising OKF v0.2 trust, lifecycle and computation fields."""
    root = tmp_path / "generic"
    files = {
        "index.md": "---\nokf_version: '0.2'\n---\n# Metrics\n\n* [Revenue](metrics/revenue.md) - Revenue\n",
        "metrics/revenue.md": """\
            ---
            type: Metric
            title: Revenue
            description: Recognized revenue.
            verified: { by: human:ana, at: 2026-06-25T09:00:00Z }
            ---
            # Definition

            Computed by [the computation](../computations/revenue.md); see [old doc](/missing/doc.md)
            and [the wiki](https://wiki.example/rev).
            """,
        "computations/revenue.md": """\
            ---
            type: Attested Computation
            title: Revenue for fiscal year
            runtime: bigquery
            parameters:
              - { name: year, type: integer, required: true }
            executor: { resource: references/run.md, receipt: [job_id, executed_sql] }
            attester: { resource: references/attest.py }
            verified: [{ by: process:nightly, at: 2026-06-26T02:00:00Z }]
            stale_after: 2020-01-01T00:00:00Z
            ---
            # Computation

                SELECT 1
            """,
    }
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text), encoding="utf-8")
    return root


def view(*args, **kw):
    code, text = render(*args, color=False, **kw)
    return code, text


def test_overview_shows_provenance_rules_and_findings(bundle):
    path, report = bundle
    code, text = view(str(path))
    assert code == 0
    assert "Conformance (OKF v0.2 section 11): PASS" in text
    assert "== ARCHAI STANDARDS CHECK" in text and "LLM used: no" in text
    assert "no-cycles" in text and "user-config" in text
    assert "only ArchAI default rules ran" not in text
    for f in (f for r in report["rule_results"] for f in r["findings"]):
        assert f["id"] in text


def test_findings_view_filters_and_marks_missing_files(bundle):
    path, _ = bundle
    _, text = view(str(path), "findings", status="violation")
    assert "FINDINGS (2) - VERIFIED_VIOLATION" in text
    assert "tests/test_order.py (missing)" in text
    assert "app/a.py:1" in text
    _, none = view(str(path), "findings", status="RISK")
    assert "FINDINGS (0)" in none


def test_concept_view_resolves_links_sources_and_backlinks(bundle):
    path, report = bundle
    cycle = next(f for r in report["rule_results"] for f in r["findings"] if f["rule_id"] == "no-cycles")
    code, text = view(str(path), cycle["id"])
    assert code == 0
    assert "VERIFIED_VIOLATION  rule no-cycles" in text
    assert "LLM-assisted: no" in text
    assert "-> rules/no-cycles" in text
    assert "[ev1] app/a.py:1  -> modules/app.a" in text
    assert "LINKED FROM (1)" in text and "results/no-cycles" in text
    assert "[^ev1]:" not in text  # footnote definitions are folded into SOURCES


def test_module_view_lists_importers(bundle):
    path, _ = bundle
    _, text = view(str(path), "app.a")
    assert "IMPORTED BY (1)" in text and "modules/app.b" in text


def test_lookup_ambiguous_and_missing(bundle):
    path, _ = bundle
    code, text = view(str(path), "domain")  # app.domain and app.domain.order
    assert code == 2 and "be more specific" in text
    assert view(str(path), "app")[1].startswith("== modules/app ")  # exact title wins
    code, text = view(str(path), "does-not-exist")
    assert code == 2 and "No concept matches" in text
    code, _ = view(str(path.parent / "nowhere"))
    assert code == 2


def test_raw_shows_frontmatter(bundle):
    path, _ = bundle
    _, text = view(str(path), "rules/no-cycles", raw=True)
    assert "FRONTMATTER" in text and "archai_rule:" in text


def test_generic_bundle_trust_staleness_links_and_computation(generic_bundle):
    b = BundleView(str(generic_bundle))
    assert not b.is_archai and b.okf_version == "0.2"
    assert b.resolve("metrics/revenue", "../computations/revenue.md") == "computations/revenue"
    assert b.backlinks["computations/revenue"] == ["metrics/revenue"]

    _, overview = view(str(generic_bundle))
    assert "ARCHAI" not in overview
    assert "human-reviewed 1, machine-confirmed 1" in overview and "Stale: 1" in overview

    _, metric = view(str(generic_bundle), "revenue")  # ambiguous by substring, exact by title
    assert "trust: human-reviewed" in metric
    assert "-> computations/revenue" in metric
    assert "-> missing/doc [missing]" in metric
    assert "the wiki <https://wiki.example/rev>" in metric

    _, comp = view(str(generic_bundle), "computations/revenue")
    assert "trust: machine-confirmed" in comp and "STALE since 2020-01-01" in comp
    assert "runtime: bigquery | parameters: year: integer" in comp
    assert "attester: references/attest.py" in comp


def test_color_toggle(bundle):
    path, _ = bundle
    assert "\x1b[" not in render(str(path), color=False)[1]
    assert "\x1b[" in render(str(path), color=True)[1]


def test_cli_okf_view_and_preview(bundle, make_repo, tmp_path, capsys):
    path, _ = bundle
    assert process_command(["OKF-VIEW", str(path), "tree", "--no-color"]) == 0
    assert "modules/" in capsys.readouterr().out
    assert process_command(["OKF-VIEW", str(path), "zzz-missing"]) == 2

    root = make_repo({"app/__init__.py": "", "app/x.py": "import os\n"}, name="clean")
    code = process_command(["CHECK-STANDARDS", str(root), "--okf-out", str(tmp_path / "b2"), "--preview"])
    out = capsys.readouterr().out
    assert code == 0 and "== OKF BUNDLE" in out and "== ARCHAI STANDARDS CHECK" in out
    # No config: the preview must say that only ArchAI defaults were checked.
    assert "archai-default" in out and "only ArchAI default rules ran" in out
    assert "Limitations" in out
    assert "# ArchAI Standards Report" not in out  # preview replaces the Markdown report
    assert process_command(["CHECK-STANDARDS", str(root), "--preview"]) == 2


def test_preview_refuses_to_mix_with_json_on_stdout(make_repo, tmp_path):
    root = make_repo({"app/__init__.py": ""}, name="mix")
    assert process_command(["CHECK-STANDARDS", str(root), "--okf-out", str(tmp_path / "b"), "--preview", "--json"]) == 2
