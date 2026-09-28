import importlib.util
import os
from pathlib import Path

import pytest

from xgtest.adapter.xugu import XuguConnectionConfig
from xgtest.design.model import load_test_model
from xgtest.generator.candidate import generate_candidates, static_validate_candidate
from xgtest.generator.lifecycle import trial_candidate
from xgtest.query.loader import load_query_directory
from xgtest.runtime.profile import load_profile


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_ENV = ("XGTEST_DB_HOST", "XGTEST_DB_PORT", "XGTEST_DB_NAME", "XGTEST_DB_USER", "XGTEST_DB_PASSWORD")
PROFILE_PATH = os.environ.get("XGTEST_RUNTIME_PROFILE")
HAS_TARGET = importlib.util.find_spec("xgcondb") is not None and all(os.environ.get(name) for name in REQUIRED_ENV) and bool(PROFILE_PATH)


@pytest.mark.xugu_integration
@pytest.mark.skipif(not HAS_TARGET, reason="requires xgcondb, XGTEST_DB_* settings, and XGTEST_RUNTIME_PROFILE")
def test_generated_join_candidates_pass_real_xugu_trial_twice(tmp_path: Path) -> None:
    model = load_test_model(ROOT / "models" / "query" / "join.yaml")
    active = load_query_directory(ROOT / "cases" / "query")
    candidates = generate_candidates(model, "pairwise", active, tmp_path / "candidates", limit=5)
    profile = load_profile(Path(PROFILE_PATH))
    config = XuguConnectionConfig.from_environment()
    for candidate in candidates:
        static_validate_candidate(candidate, model)
        result = trial_candidate(candidate, model, config, tmp_path / "trial-runs", runtime_profile=profile)
        assert result["status"] == "review"
