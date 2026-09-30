"""Run and verify source-bound local release checks; these are not GitHub CI."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import platform
import shutil
from importlib import metadata
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
    paths.update(path for path in (root / "webui").glob("*") if path.is_file() and path.suffix in suffixes)
    paths.update(path for path in (root / "webui/public").rglob("*") if path.is_file())
    paths.update(root / name for name in ("pyproject.toml", "uv.lock") if (root / name).is_file())
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
        environment = {"os": platform.system(), "arch": platform.machine()}
        commands = []
        if kind == "framework":
            environment.update(python_version=platform.python_version(), python_executable=sys.executable)
            dependencies = sorted({(item.metadata["Name"].lower(), item.version) for item in metadata.distributions()})
            environment["dependencies"] = _store(root, json.dumps(dependencies, sort_keys=True).encode(), "application/json")
            command = [sys.executable, "-m", "pytest", "framework_tests", "-o", "addopts=", "-q", f"--junitxml={junit}"]
            cwd = root
        else:
            cwd = Path(temporary) / "webui"
            shutil.copytree(root / "webui", cwd, ignore=shutil.ignore_patterns("node_modules", "dist", ".vite"))
            environment["package_lock_sha256"] = hashlib.sha256((cwd / "package-lock.json").read_bytes()).hexdigest()
            for name, command in (("node", ["node", "--version"]), ("npm", _npm_command("--version"))):
                version = subprocess.run(command, cwd=cwd, capture_output=True, timeout=60, check=False)
                if version.returncode:
                    raise ValueError(f"RELEASE_TOOL_VERSION_UNAVAILABLE:{name}")
                environment[f"{name}_version"] = version.stdout.decode("utf-8").strip()
            install_command = _npm_command("ci")
            installed = subprocess.run(install_command, cwd=cwd, capture_output=True, timeout=600, check=False)
            commands.append({"command": install_command, "cwd": str(cwd), "exit_code": installed.returncode,
                             "log": _store(root, installed.stdout + installed.stderr, "text/plain")})
            command = _npm_command("run build")
        completed = subprocess.run(command, cwd=cwd, capture_output=True, timeout=600, check=False) if not commands or commands[0]["exit_code"] == 0 else installed
        commands.append({"command": command, "cwd": str(cwd), "exit_code": completed.returncode,
                         "log": _store(root, completed.stdout + completed.stderr, "text/plain")})
        dependency_ok = True
        if kind == "frontend":
            tree = subprocess.run(_npm_command("ls --all --json"), cwd=cwd, capture_output=True, timeout=60, check=False)
            dependency_ok = tree.returncode == 0
            environment["dependencies"] = _store(root, tree.stdout, "application/json")
            environment["dependency_tree_exit_code"] = tree.returncode
        environment_id = xgmj1_sha256(environment)
        after = release_source_id(root)
        payload = {
            "schema_version": "2", "kind": kind, "source_snapshot_id": before,
            "environment": environment, "environment_id": environment_id, "commands": commands,
            "source_unchanged": before == after, "exit_code": completed.returncode,
            "status": "PASS" if completed.returncode == 0 and dependency_ok and before == after else "FAIL",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "log": _store(root, completed.stdout + completed.stderr, "text/plain"),
        }
        if kind == "framework" and junit.is_file():
            payload["junit"] = _store(root, junit.read_bytes(), "application/xml")
        raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        return {"status": payload["status"], "kind": kind, "report": _store(root, raw, "application/json")}


def _npm_command(arguments: str) -> list[str]:
    return ["cmd.exe", "/d", "/c", f"npm {arguments}"] if os.name == "nt" else ["npm", *arguments.split()]


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
            if not isinstance(report, dict) or report.get("kind") != kind or report.get("schema_version") != "2" or report.get("source_snapshot_id") != source_id or report.get("source_unchanged") is not True or type(report.get("exit_code")) is not int or report["exit_code"] != 0 or report.get("status") != "PASS":
                raise ValueError(f"RELEASE_CHECK_FAILED_OR_STALE:{kind}")
            _read_ref(root, report["log"])
            environment = report["environment"]
            if report["environment_id"] != xgmj1_sha256(environment) or not all(isinstance(environment.get(key), str) and environment[key] for key in ("os", "arch")):
                raise ValueError("RELEASE_ENVIRONMENT_INVALID")
            dependencies = json.loads(_read_ref(root, environment["dependencies"]))
            commands = report["commands"]
            if not isinstance(commands, list) or len(commands) != (1 if kind == "framework" else 2):
                raise ValueError("RELEASE_COMMANDS_INVALID")
            for item in commands:
                if type(item["exit_code"]) is not int or item["exit_code"] != 0 or not isinstance(item["cwd"], str) or not item["cwd"]:
                    raise ValueError("RELEASE_COMMAND_FAILED")
                _read_ref(root, item["log"])
            if kind == "frontend":
                if (environment.get("package_lock_sha256") != hashlib.sha256((root / "webui/package-lock.json").read_bytes()).hexdigest()
                    or environment.get("dependency_tree_exit_code") != 0 or not isinstance(dependencies, dict)
                    or any(not isinstance(environment.get(key), str) or not environment[key] for key in ("node_version", "npm_version"))
                    or [item["command"] for item in commands] != [_npm_command("ci"), _npm_command("run build")]):
                    raise ValueError("RELEASE_CLEAN_BUILD_ENVIRONMENT_INVALID")
            if kind == "framework":
                if not isinstance(dependencies, list) or not dependencies or not environment.get("python_version") or commands[0]["command"][:4] != [environment.get("python_executable"), "-m", "pytest", "framework_tests"]:
                    raise ValueError("RELEASE_PYTHON_ENVIRONMENT_INVALID")
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
