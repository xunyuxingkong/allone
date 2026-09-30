"""Run and verify source-bound local release checks; these are not GitHub CI."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from xgtest.core.canonical import xgmj1_sha256
from xgtest.generator.artifact_store import LocalArtifactStore


def release_source_id(root: Path) -> str:
    suffixes = {".py", ".yaml", ".yml", ".json", ".toml", ".vue", ".ts", ".css", ".html"}
    paths = set()
    for directory in ("src", "framework_tests", "registry", "models", "generators", "schemas", "webui/src"):
        paths.update(path for path in (root / directory).rglob("*") if path.is_file() and path.suffix in suffixes)
    paths.update(root / name for name in ("pyproject.toml", "webui/package.json", "webui/package-lock.json", "webui/vite.config.ts", "webui/tsconfig.json", "webui/index.html") if (root / name).is_file())
    return xgmj1_sha256({path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest() for path in sorted(paths)})


def _store(root: Path, content: bytes, media_type: str) -> dict[str, Any]:
    store_root = root / "artifacts/release-checks"
    ref = LocalArtifactStore(store_root).put(content, media_type=media_type)
    return {"path": (store_root / ref.uri).relative_to(root).as_posix(), "sha256": ref.sha256}


def run_release_check(root: Path, kind: str) -> dict[str, Any]:
    root = root.resolve()
    if kind not in {"framework", "frontend"}:
        raise ValueError("RELEASE_CHECK_KIND_INVALID")
    before = release_source_id(root)
    temporary_root = root / "artifacts/release-checks"
    temporary_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".check-", dir=temporary_root) as temporary:
        junit = Path(temporary) / "junit.xml"
        command = [sys.executable, "-m", "pytest", "framework_tests", "-o", "addopts=", "-q", f"--junitxml={junit}"] if kind == "framework" else (["cmd.exe", "/d", "/c", "npm run build"] if os.name == "nt" else ["npm", "run", "build"])
        completed = subprocess.run(command, cwd=root if kind == "framework" else root / "webui", capture_output=True, timeout=600, check=False)
        after = release_source_id(root)
        payload = {
            "schema_version": "1", "kind": kind, "source_snapshot_id": before,
            "source_unchanged": before == after, "exit_code": completed.returncode,
            "status": "PASS" if completed.returncode == 0 and before == after else "FAIL",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "log": _store(root, completed.stdout + completed.stderr, "text/plain"),
        }
        if kind == "framework" and junit.is_file():
            payload["junit"] = _store(root, junit.read_bytes(), "application/xml")
        raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        return {"status": payload["status"], "kind": kind, "report": _store(root, raw, "application/json")}


def _read_ref(root: Path, ref: Any) -> bytes:
    if not isinstance(ref, dict) or set(ref) != {"path", "sha256"} or not isinstance(ref["path"], str):
        raise ValueError("RELEASE_REFERENCE_INVALID")
    path = (root / ref["path"]).resolve()
    if not path.is_relative_to((root / "artifacts/release-checks").resolve()):
        raise ValueError("RELEASE_REFERENCE_OUTSIDE_STORE")
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != ref["sha256"]:
        raise ValueError("RELEASE_REFERENCE_HASH_MISMATCH")
    return content


def freeze_release_checks(root: Path, reports: dict[str, dict[str, str]]) -> dict[str, Any]:
    if set(reports) != {"framework", "frontend"}:
        raise ValueError("RELEASE_CHECKS_REQUIRED")
    for reference in reports.values():
        _read_ref(root, reference)
    payload = {"schema_version": "1", "checks": reports, "source_snapshot_id": release_source_id(root)}
    return {**payload, "checks_id": xgmj1_sha256(payload)}


def verify_release_checks(root: Path, path: Path) -> dict[str, Any]:
    errors = []
    counts = {}
    try:
        package = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(package, dict) or package.get("schema_version") != "1" or package.get("checks_id") != xgmj1_sha256({k: v for k, v in package.items() if k != "checks_id"}):
            raise ValueError("RELEASE_CHECKS_SCHEMA_OR_ID_INVALID")
        source_id = release_source_id(root)
        if package.get("source_snapshot_id") != source_id or set(package["checks"]) != {"framework", "frontend"}:
            raise ValueError("RELEASE_CHECKS_SOURCE_OR_SCOPE_INVALID")
        for kind, reference in package["checks"].items():
            report = json.loads(_read_ref(root, reference))
            if not isinstance(report, dict) or report.get("kind") != kind or report.get("schema_version") != "1" or report.get("source_snapshot_id") != source_id or report.get("source_unchanged") is not True or type(report.get("exit_code")) is not int or report["exit_code"] != 0 or report.get("status") != "PASS":
                raise ValueError(f"RELEASE_CHECK_FAILED_OR_STALE:{kind}")
            _read_ref(root, report["log"])
            if kind == "framework":
                document = ET.fromstring(_read_ref(root, report["junit"]))
                cases = list(document.iter("testcase"))
                failed = sum(case.find("failure") is not None or case.find("error") is not None for case in cases)
                skipped = sum(case.find("skipped") is not None for case in cases)
                declared = sum(int(suite.attrib["tests"]) for suite in document.iter("testsuite"))
                if not cases or failed or declared != len(cases):
                    raise ValueError("RELEASE_FRAMEWORK_JUNIT_INVALID")
                counts = {"passed": len(cases) - skipped, "skipped": skipped, "failed": failed}
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError) as error:
        errors.append(str(error))
    return {"status": "FAIL" if errors else "PASS", "framework": counts, "errors": errors}
