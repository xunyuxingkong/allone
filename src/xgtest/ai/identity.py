"""Freeze the control logic used by a durable job, separately from SQL execution."""
import subprocess
import tempfile
from pathlib import Path
from xgtest.core.contract_set import build_contract_descriptor


def job_source_identity(root: Path) -> dict:
    descriptor = build_contract_descriptor(root)
    git_commit = git_output(root, ["rev-parse", "HEAD"]).decode("ascii", errors="ignore").strip() or None
    return {"control_plane_layer_id": descriptor["layers"]["control_plane"]["id"], "git_commit": git_commit}


def git_output(root: Path, arguments: list[str]) -> bytes:
    # stdio MCP owns stdin; Git must neither inherit it nor retain capture pipes.
    try:
        with tempfile.TemporaryFile() as output:
            result = subprocess.run(["git", *arguments], cwd=root, stdin=subprocess.DEVNULL,
                stdout=output, stderr=subprocess.DEVNULL, check=False, timeout=10)
            output.seek(0)
            return output.read() if result.returncode == 0 else b""
    except (OSError, subprocess.TimeoutExpired):
        return b""
