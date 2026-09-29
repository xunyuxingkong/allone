import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "xgtest", *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_model_coverage_generate_and_validate_cli(tmp_path: Path) -> None:
    model = cli("model", "validate")
    assert model.returncode == 0
    assert json.loads(model.stdout)["model_id"] == "query.join"

    gap = cli("coverage", "gap", "query.join", "--strategy", "pairwise")
    assert gap.returncode == 0
    assert json.loads(gap.stdout)["missing"] > 0

    output_dir = tmp_path / "candidates"
    generated = cli("generate", "query.join", "--strategy", "pairwise", "--limit", "1", "--output", str(output_dir))
    assert generated.returncode == 0, generated.stderr
    report = json.loads(generated.stdout)
    assert report["generated"] == 1
    candidate = Path(report["candidates"][0])

    validated = cli("candidate", "validate", str(candidate))
    assert validated.returncode == 0, validated.stderr
    assert json.loads(validated.stdout)["candidates"][0]["status"] == "draft"

    repeated = cli("generate", "query.join", "--strategy", "pairwise", "--limit", "1", "--output", str(output_dir))
    assert repeated.returncode == 0, repeated.stderr
    assert json.loads(repeated.stdout)["generated"] == 1
    listed = cli("candidate", "list", "--path", str(output_dir))
    assert listed.returncode == 0
    assert json.loads(listed.stdout)[0]["status"] == "draft"
