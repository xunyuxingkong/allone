import json
from pathlib import Path
from types import SimpleNamespace

from xgtest.generator import release_checks as checks


def _frontend_fixture(root):
    (root / "webui").mkdir()
    (root / "webui/package-lock.json").write_text('{}', encoding='utf-8')


def test_release_checks_verify_bound_sources_logs_and_real_junit_shape(tmp_path, monkeypatch):
    _frontend_fixture(tmp_path)
    def synthetic_check(command, **kwargs):
        if "pytest" in command:
            destination = Path(next(item.split("=", 1)[1] for item in command if item.startswith("--junitxml=")))
            destination.write_text('<testsuites><testsuite tests="2"><testcase name="passed"/><testcase name="skipped"><skipped/></testcase></testsuite></testsuites>', encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout=b'{}' if any('ls' in part for part in command) else b"synthetic check log", stderr=b"")

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
    _frontend_fixture(tmp_path)
    monkeypatch.setattr(checks.subprocess, "run", lambda command, **kw: SimpleNamespace(returncode=0 if any('--version' in part for part in command) else 1, stdout=b"failed", stderr=b""))
    framework = checks.run_release_check(tmp_path, "framework")
    frontend = checks.run_release_check(tmp_path, "frontend")
    assert framework["status"] == frontend["status"] == "FAIL"
    path = tmp_path / "checks.json"
    path.write_text(json.dumps(checks.freeze_release_checks(tmp_path, {"framework": framework["report"], "frontend": frontend["report"]})))
    assert checks.verify_release_checks(tmp_path, path)["status"] == "FAIL"


def test_environment_identity_and_clean_install_are_required(tmp_path, monkeypatch):
    _frontend_fixture(tmp_path)
    def run(command, **kwargs):
        if 'pytest' in command:
            Path(next(item.split('=', 1)[1] for item in command if item.startswith('--junitxml='))).write_text('<testsuites><testsuite tests="1"><testcase name="synthetic"/></testsuite></testsuites>')
        return SimpleNamespace(returncode=0, stdout=b'{}' if any('ls' in part for part in command) else b'v1', stderr=b'')
    monkeypatch.setattr(checks.subprocess, 'run', run)
    reports = {kind: checks.run_release_check(tmp_path, kind)['report'] for kind in ('framework', 'frontend')}
    frontend = json.loads(checks._read_ref(tmp_path, reports['frontend']))
    frontend['environment']['node_version'] = 'tampered'
    reports['frontend'] = checks._store(tmp_path, json.dumps(frontend).encode(), 'application/json')
    path = tmp_path/'checks.json'
    path.write_text(json.dumps(checks.freeze_release_checks(tmp_path, reports)))
    assert 'RELEASE_ENVIRONMENT_INVALID' in checks.verify_release_checks(tmp_path, path)['errors']
