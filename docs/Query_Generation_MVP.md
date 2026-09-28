# Query Generation MVP

This MVP implements a bounded, deterministic JOIN case-generation loop. It uses a versioned model and coverage gaps; it does not infer tests from Xugu kernel source or claim source-code branch coverage.

## Assets

- `models/query/join.yaml` defines JOIN dimensions, values, constraints, and the supported `all_values` / `pairwise` strategies.
- `generators/query/templates/join.yaml` identifies the versioned JOIN template.
- `cases/query/` contains reviewed active cases. JOIN cases declare `coverage` claims that point to query step IDs.
- `candidates/query/join/` receives generated candidates. Candidate files do not enter regression until explicitly promoted.

## Workflow

```powershell
xgtest model validate models/query/join.yaml
xgtest coverage show query.join
xgtest coverage gap query.join --strategy pairwise
xgtest generate query.join --strategy pairwise
xgtest candidate validate candidates/query/join
xgtest candidate trial candidates/query/join/QUERY.JOIN.<signature>.yaml --runtime-profile artifacts/runtime-profile.json
xgtest candidate list --status review
```

Trial runs use the existing isolated Query Runner twice and require a Runtime Profile plus matching PASS status, row count, and result hashes. They write evidence under `artifacts/trial-runs/`. The generator uses a known-result Oracle declared by its deterministic template; it never adopts Xugu output as Expected.

After Git review has happened, record the external review references and promote:

```powershell
xgtest candidate review QUERY.JOIN.<signature> --reviewer <name> --reference <PR-or-review-reference> --coverage-reference <coverage-review-reference>
xgtest candidate promote QUERY.JOIN.<signature> --artifacts artifacts/trial-runs
```

Promotion verifies the static, trial, Oracle, human review, coverage review, and semantic-hash evidence, writes an active case into `cases/query/`, and refreshes a coverage snapshot under `artifacts/coverage/`.

## Scope and acceptance

Only the JOIN feature and `all_values` / `pairwise` are implemented. Other declared strategies are reserved and rejected as unimplemented. Candidate generation is greedy and deterministic; it chooses assignments that reduce currently missing requirements. Generated SQL uses inline derived rows and is statically checked as read-only. Real Xugu trial acceptance still requires a reachable Xugu target and the supported project driver; fake sessions verify the lifecycle contract but are not database acceptance evidence.
