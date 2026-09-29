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
xgtest candidate mutation-validate candidates/query/join --runtime-profile artifacts/runtime-profile-v9.json --artifacts artifacts/mutations
xgtest candidate trial candidates/query/join/QUERY.JOIN.<signature>.yaml --artifacts artifacts/trial-runs --runtime-profile artifacts/runtime-profile-v9.json
xgtest acceptance verify-trial-index --index acceptance/query-generation-mvp/trial-run-index.json --runtime-profile artifacts/runtime-profile-v9.json
xgtest candidate list --status review
```

Template v4 includes less-than, equality, and greater-than input relationships for `less_equal` and explicitly casts `int` JOIN keys to Xugu `INTEGER`. `candidate mutation-validate` stores a checksummed Mutation Evidence artifact; `less_equal` requires `KILLED`, while other predicates record `NOT_APPLICABLE` as `SKIPPED`. Candidate trials use the isolated Query Runner twice and preserve each Xugu return row, column name, observed type, row count, and result hash in the Trial Artifact. The row values are included in the trial result hash, and the artifact SHA-256 binds the full JSON. Current v9 artifacts are under `artifacts/trial-runs/`; `acceptance verify-trial-index` checks the candidate, trial artifact, index, Contract Set, Runtime Profile, semantic hash, database build, row counts, and result hashes. The generator uses a known-result Oracle declared by its deterministic template; it never adopts Xugu output as Expected.

After Git review has happened, record the external review references and promote:

```powershell
xgtest candidate review QUERY.JOIN.<signature> --reviewer <name> --reference <PR-or-review-reference> --coverage-reference <coverage-review-reference>
xgtest candidate promote QUERY.JOIN.<signature> --artifacts artifacts/trial-runs --mutation-artifacts artifacts/mutations --runtime-profile artifacts/runtime-profile-v9.json
```

Promotion verifies static, trial, Mutation, Oracle, human review, coverage review, semantic hash, artifact SHA-256 values, current Contract Set, and expected Runtime Profile. It writes an active case into `cases/query/` and refreshes a coverage snapshot under `artifacts/coverage/`. The JOIN model v2 and template v4 semantics are defined in [Query_Generation_JOIN_Model_v2.md](Query_Generation_JOIN_Model_v2.md). Current acceptance summaries are under `acceptance/query-generation-mvp/`; v2 and v3 candidates and evidence are archived separately.

The Web UI has read-only `/coverage`, `/candidates`, and `/candidates/:caseId` pages backed by `/api/coverage` and `/api/candidates`. Coverage distinguishes active claims from provisional coverage if the review candidates are promoted, and shows a server-computed dimension matrix, model constraints, and candidate links for each active gap. Candidate detail shows the pairwise requirements it would add relative to the active set. Candidate pages check the local trial artifact hash and its current Contract/Profile before labeling evidence verified. Review evidence and promotion remain CLI-gated after human review.

## Scope and acceptance

Only the JOIN feature and `all_values` / `pairwise` are implemented. Other declared strategies are reserved and rejected as unimplemented. Candidate generation is greedy and deterministic; it chooses assignments that reduce currently missing requirements. Generated SQL uses inline derived rows and is statically checked as read-only. Current v4 candidates use `artifacts/runtime-profile-v9.json`; [the review packet](../acceptance/query-generation-mvp/review-packet.md) records the acceptance boundary. Fake sessions verify the lifecycle contract but are not database acceptance evidence.
