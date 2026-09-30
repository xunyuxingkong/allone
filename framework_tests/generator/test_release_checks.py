import json
from pathlib import Path
from types import SimpleNamespace

from xgtest.generator import release_checks as checks


def test_release_checks_verify_bound_sources_logs_and_real_junit_shape(tmp_path, monkeypatch):
    def synthetic_check(command, **kwargs):
        if "pytest" in command:
            destination = Path(next(item.split("=", 1)[1] for item in command if item.startswith("--junitxml=")))
            destination.write_text('<testsuites><testsuite tests="2"><testcase name="passed"/><testcase name="skipped"><skipped/></testcase></testsuite></testsuites>', encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout=b"synthetic check log", stderr=b"")

    monkeypatch.setattr(checks.subprocess, "run", synthetic_check)
    reports = {kind: checks.run_release_check(tmp_path, kind)["report"] for kind in ("framework", "frontend")}
    package = checks.freeze_release_checks(tmp_path, reports)
    path = tmp_path / "release-checks.json"
    path.write_text(json.dumps(package), encoding="utf-8")
    result = checks.verify_release_checks(tmp_path, path)
    assert result == {"status": "PASS", "framework": {"passed": 1, "skipped": 1, "failed": 0}, "errors": []}
    modified = tmp_path / "src/changed.py"
    modified.parent.mkdir(parents=True)
    modified.write_text("changed = True\n")
    assert checks.verify_release_checks(tmp_path, path)["status"] == "FAIL"


def test_failed_build_cannot_be_declared_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(checks.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1, stdout=b"failed", stderr=b""))
    framework = checks.run_release_check(tmp_path, "framework")
    frontend = checks.run_release_check(tmp_path, "frontend")
    assert framework["status"] == frontend["status"] == "FAIL"
    path = tmp_path / "checks.json"
    path.write_text(json.dumps(checks.freeze_release_checks(tmp_path, {"framework": framework["report"], "frontend": frontend["report"]})))
    assert checks.verify_release_checks(tmp_path, path)["status"] == "FAIL"
