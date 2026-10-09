"""CHECK-STANDARDS through the existing console command dispatcher."""
import json

import yaml

from ai_architect.cli import process_command

FILES = {
    "app/__init__.py": "",
    "app/a.py": "from app import b\n",
    "app/b.py": "from app import a\n",
}


def test_json_report_and_exit_code(make_repo, tmp_path, capsys):
    root = make_repo(FILES)
    out = tmp_path / "report.json"
    md = tmp_path / "report.md"
    bundle = tmp_path / "bundle"
    code = process_command(["CHECK-STANDARDS", str(root), "--json", str(out), "--markdown", str(md),
                            "--okf-out", str(bundle)])
    assert code == 1  # a verified violation exists
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["schema_version"] == "archai.standards/1"
    assert report["summary"]["findings"]["VERIFIED_VIOLATION"] == 1
    text = md.read_text(encoding="utf-8")
    for heading in ("## 1. What was checked", "## 2. What was found", "## 3. Evidence for each finding",
                    "## 4. What could not be verified", "## 5. What to investigate next"):
        assert heading in text
    assert "`app/a.py:1`" in text
    assert (bundle / "index.md").exists()
    assert "conformant with OKF v0.2" in capsys.readouterr().err


def test_from_okf_reproduces_source_result(make_repo, tmp_path, capsys):
    root = make_repo(FILES)
    bundle = tmp_path / "bundle"
    process_command(["CHECK-STANDARDS", str(root), "--okf-out", str(bundle), "--json"])
    first = json.loads(capsys.readouterr().out)
    process_command(["CHECK-STANDARDS", "--from-okf", str(bundle), "--json"])
    second = json.loads(capsys.readouterr().out)
    assert second["provenance"]["fact_source"] == "okf-bundle"
    assert second["rule_results"] == first["rule_results"]


def test_clean_repo_exits_zero_and_bad_config_exits_two(make_repo, tmp_path, capsys):
    root = make_repo({"app/__init__.py": "", "app/a.py": "import os\n"})
    assert process_command(["CHECK-STANDARDS", str(root)]) == 0
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump({"rules": [{"id": "x", "kind": "nope"}]}), encoding="utf-8")
    assert process_command(["CHECK-STANDARDS", str(root), "--config", str(bad)]) == 2
    assert "unknown kind" in capsys.readouterr().out
    assert process_command(["CHECK-STANDARDS", str(tmp_path / "missing")]) == 2
