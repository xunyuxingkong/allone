# XG DB Test 最新待修复项与后续完整实施计划
## 基于 `codex/join-model-v2@fc50de4934794ef5134d8a10cd91eaefe293acf3`

> 当前分支：`codex/join-model-v2`  
> 当前提交：`fc50de4934794ef5134d8a10cd91eaefe293acf3`  
> 当前状态：JOIN Generation 技术验证基本完成，但仍为 **HOLD**。独立人工评审、正式晋级、晋级后完整回归和最终 Active Coverage Snapshot 尚未完成。  
> 本文目标：列出当前最新代码中仍需修复的问题、优先级、具体修改方式、验收标准，以及 JOIN MVP 收口后进入 AI 驱动测试平台改造的完整步骤。

---

# 1. 当前最新状态

已经完成：

```text
JOIN Model v2
Template v4
Generator v4
null_side 语义修正
predicate=none 修正
range → less_equal
less_equal 等值边界补齐
Mutation Validation
5/5 less_equal Mutation KILLED
datatype=int → 显式 INTEGER
数据库 Version / Build Probe
21 Candidate Static Validate
21 Candidate Real Xugu Double Trial
Raw Trial Rows Capture
AI Technical Review
30 Active Query Regression PASS
Runtime Profile v6
Contract Set Candidate
Acceptance Summary
Coverage / Candidate Web View
```

当前 Coverage：

```text
Required Pairwise Points:          137
Current Active Covered:             17
Current Active Missing:            120
Review Candidates:                  21
Projected Covered After Promotion: 137 / 137
Projected Gap:                       0
```

正式状态仍然是：

```text
candidate_review_status = PENDING_HUMAN_REVIEW
promotion_status = PENDING
post_promotion_regression_status = PENDING
final status = HOLD
```

---

# 2. P0：当前必须先修复的问题

## 2.1 Trial Artifact 与最新 Index / Candidate Evidence 不一致

这是当前最高优先级问题。

最新 `acceptance/query-generation-mvp/trial-run-index.json` 声明：

```text
contract_set_id =
c1fb2d3586a70dd627f8da950dbe900847837f48cb33ece865c0aa0ae85e911a

runtime_profile_id =
5ea8f183395d637fd37366173abe1722b5f6a9744f3ce5c895115dbafd068fd0

database_version =
BETA-11679_11665

raw_result_rows = true
```

但当前 Git 中至少部分：

```text
artifacts/trial-runs/<CASE_ID>/<semantic_hash>.json
```

仍然是旧 Evidence，例如：

```text
contract_set_id =
3541e2217dabc75ec9e32ad42f6d55b63e935d11dd7b759a6c59f1edf7268db8

runtime_profile_id =
45e7e9b320a9bc24503d214a97223018b659f24b1e0fa68e736d979bd8be4b78

database_version = null
```

并且至少部分 Artifact 中没有最新声明的 `result_rows`。

### 风险

其他开发者 clone 当前分支后执行 Promotion Gate，可能得到：

```text
CANDIDATE_TRIAL_ARTIFACT_HASH_MISMATCH
CANDIDATE_CONTRACT_SET_STALE
CANDIDATE_RUNTIME_PROFILE_MISMATCH
```

这说明当前 Git 仓库还不能算完整可复现的 Acceptance Package。

### 修复步骤

```text
1. 固定当前 Contract Set
2. 固定当前 Runtime Profile
3. 对 21 Candidate 重新正式 Trial ×2
4. 强制 capture_result_rows=True
5. 重新写入当前 artifacts/trial-runs/
6. 重算 artifact_sha256
7. 更新 Candidate.validation_evidence
8. 重新生成 trial-run-index.json
9. 校验 case_id / semantic_hash / contract / profile / db version / build / rows / result_hash
10. 重新生成 final-acceptance.json
```

### 必须增加自动一致性检查

新增：

```text
xgtest acceptance verify-trial-index
```

或者 Core：

```python
verify_trial_artifact_index()
```

要求自动验证：

```text
Index Entry
↔ Artifact Path
↔ Artifact SHA256
↔ Candidate Evidence
↔ Contract Set
↔ Runtime Profile
↔ Semantic Hash
```

任何不一致：

```text
ACCEPTANCE_TRIAL_INDEX_INVALID
```

### DoD

```text
21/21 Artifact 与 Index 一致
21/21 Artifact SHA256 一致
21/21 Contract Set 一致
21/21 Runtime Profile 一致
21/21 Semantic Hash 一致
21/21 Raw Rows 存在
21/21 DB Version / Build 一致
```

---

## 2.2 Mutation Evidence 尚未进入 Promotion Gate

当前已有：

```text
validate_candidate_mutation()
```

5 条 `less_equal` 的：

```text
<= → <
```

均为：

```text
KILLED
```

但当前 `promote_candidate()` 没有强制验证 Mutation Evidence。

### 风险

理论上可能出现：

```text
Mutation = WEAK
```

但只要 Trial、Review、Coverage Review 都存在，仍可能进入 Promote。

### 修复方案

新增正式模型：

```text
MutationEvidence
```

建议结构：

```yaml
mutation_evidence:
  policy_version: "1"
  contract_set_id: ...
  runtime_profile_id: ...
  artifact_sha256: ...
  checks:
    - mutation_id: replace_le_with_lt
      status: KILLED
      original_hash: ...
      mutated_hash: ...
```

规则：

```text
predicate = less_equal
→ replace_le_with_lt 必须 KILLED

其它 predicate
→ NOT_APPLICABLE 允许
```

Promotion 新增：

```text
CANDIDATE_MUTATION_EVIDENCE_REQUIRED
CANDIDATE_MUTATION_GATE_FAILED
CANDIDATE_MUTATION_EVIDENCE_STALE
```

`review_input_hash` 也应绑定 Mutation Evidence，使 Mutation 改变后旧 Review 自动失效。

---

## 2.3 Mutation CLI 的 NOT_APPLICABLE 状态需要重构

未来 AI 会按 Candidate 单独调用 Mutation。

统一建议：

```text
KILLED           → PASS
NOT_APPLICABLE   → SKIPPED / PASS
WEAK             → FAIL
BASELINE_NOT_PASS→ FAIL
INCONCLUSIVE     → BLOCKED
NONDETERMINISTIC → BLOCKED
```

不要让 `NOT_APPLICABLE` 被解释成失败。

---

## 2.4 本轮 Framework Tests 尚未重跑

最新 `docs/G0A_ACCEPTANCE.md` 明确写：

```text
Framework Tests = NOT RUN
```

但本轮修改了：

```text
core/models.py
query/runner.py
generator/template.py
generator/candidate.py
generator/lifecycle.py
cli.py
web/service.py
schemas/*
```

因此合并前必须重新跑完整 Framework Regression。

必跑：

```bash
pytest -m "not xugu_integration"

xgtest registry validate
xgtest schema export
xgtest contract verify

cd webui
npm ci
npm run build
```

如果 Schema / Generated Enum 有变化，必须确保：

```text
git diff = clean
```

---

## 2.5 GitHub CI 还没有这次 Commit 的 PASS 证据

当前 `fc50de493...` 没有可见 Workflow Run / Combined Status。

合并 `main` 前必须：

```text
创建 PR
→ GitHub Actions
→ 全部 Required Checks PASS
```

---

## 2.6 独立人工 Review 尚未完成

AI Technical Review 不等于人工正式 Review。

人工至少检查：

```text
Case ID
Coverage Assignment
SQL
Expected
Oracle Provenance
Mutation Result
Trial Raw Rows
Contract/Profile
Coverage Contribution
Duplicate
Readability
Test Purpose
```

---

## 2.7 Review Evidence 尚未正式写入

人工 Review 后必须通过正式流程生成：

```text
review_evidence
coverage_review
```

并绑定：

```text
semantic_hash
trial_artifact_sha256
mutation_evidence
review_input_hash
review_reference
coverage_reference
```

不允许手工改 YAML 伪造 Review。

---

## 2.8 Promotion 尚未完成

完成全部 Gate 后：

```text
review → active
```

必须通过 Core `promote_candidate()`。

禁止：

```text
手工移动文件
+
直接改 status
```

---

## 2.9 Promotion 后必须 Full Regression

Promote 后运行整个：

```text
cases/query/
```

最终 Case Count 以 Loader 实际扫描为准，不硬编码数量。

---

## 2.10 Final Active Coverage 尚未生成

Promotion 后重新计算：

```text
query.join
pairwise
```

目标：

```text
required = 137
active_covered = 137
active_missing = 0
```

此时才能把：

```text
provisional 137/137
```

转成真正：

```text
active 137/137
```

---

## 2.11 Final Acceptance 仍是 HOLD

Promotion + Full Regression + Coverage Snapshot 后，重新生成 `final-acceptance.json`。

目标：

```text
candidate_review_status = PASS
promotion_status = PASS
post_promotion_regression_status = PASS
active_missing = 0
status = PASS
```

这仍不自动等于 G0A Freeze。

---

# 3. P1：应在下一阶段优化的问题

## 3.1 Raw Result Rows 不应长期放通用 QueryStepReport

当前 `QueryStepReport.result_rows` 对 Trial 很方便，但长期可能产生：

```text
真实业务 Query
→ capture_result_rows=True
→ 大量数据进入 Artifact / Web / Git
```

建议后续拆：

```text
QueryStepReport
= 普通执行摘要

TrialEvidence
= 原始行证据
```

并增加：

```text
max_capture_rows
max_capture_bytes
synthetic_only
redaction_policy
allow_sensitive_rows
```

默认：

```text
synthetic_only = true
```

---

## 3.2 Artifact Store 应从 Git 拆出去

本次 Commit 体积很大，主要来自 Trial Artifact、历史 Candidate、Runtime Evidence 和 Acceptance 历史版本。

AI 自动运行后这种模式不可持续。

建议：

```text
Raw Artifact
→ MinIO / S3 / GitHub Artifact / 内部制品库

Git
→ URI / SHA256 / Contract / Profile / Semantic Hash / Summary
```

---

## 3.3 Acceptance 历史版本治理

当前大量：

```text
coverage-summary-v3/v4/v5
final-acceptance-v3/v4/v5
trial-run-index-v2/v3/v4/v5
review-packet-v2/v3/v4/v5
```

建议未来：

```text
acceptance/current/
acceptance/history/manifest.json
```

详细 Raw Evidence 放 Artifact Store。

---

## 3.4 Active Coverage Claim 升级需要 Migration Review

历史 Active Case 从 Model v1 → v2 时，不应仅改：

```text
model_version
assignment
```

就继续贡献 Coverage。

建议：

```text
Active Case + Model Version Change
→ CoverageClaimMigrationReview Required
```

---

## 3.5 Contract Identity 边界过宽

当前 Model、Template、Generator 改动都会影响 `contract_set_id`，进而导致 Runtime Profile 失效。

长期建议拆：

```text
Core Contract ID
Runtime Contract ID
Generator Contract ID
Model Hash
Template Hash
Source Snapshot Hash
```

最好在 G0A 真正 Freeze 前定型。

---

## 3.6 Branch Protection

建议 main 开启：

```text
Require Pull Request
Require CI PASS
Require Review
No Direct Push
```

---

## 3.7 Required Status Checks

至少：

```text
framework-tests
registry-schema-contract
frontend-build
```

后续增加：

```text
candidate-validation
acceptance-consistency
coverage-validation
```

---

## 3.8 Trial Evidence Verifier 进入 CI

CI 自动验证：

```text
Candidate
↔ Trial Artifact
↔ Trial Index
↔ Runtime Profile
↔ Contract
↔ Mutation Index
```

防止再次出现 Artifact / Index 不一致。

---

## 3.9 host_hash 隐私优化

长期：

```text
SHA256(host)
```

改成：

```text
HMAC(host, deployment_secret)
```

或使用匿名 `target_id`。

---

## 3.10 Cancel Server-side Stop Proof

当前 Process Timeout 已保证 Framework 有界退出，但服务端 SQL 是否立即停止仍 UNKNOWN。

后续 Probe：

```text
Long Query
→ cancel / terminate
→ 查询 server session
→ 确认执行停止
```

---

## 3.11 Full Session Reset

当前 one-case-one-process 不阻塞。

但未来 Connection Pool / Worker Reuse 前必须验证：

```text
transaction
role
schema
session variable
temp object
lock
cursor
```

---

# 4. JOIN MVP 收口完整步骤

```text
STEP 1
修 Trial Artifact / Index 一致性

STEP 2
增加 MutationEvidence 正式模型

STEP 3
Mutation Gate 接入 Promotion

STEP 4
统一 Mutation Action 状态

STEP 5
运行完整 Framework Tests

STEP 6
重新生成 Contract Descriptor

STEP 7
重建 Runtime Profile

STEP 8
重新跑 Active Query Regression

STEP 9
重新跑 21 Candidate Mutation

STEP 10
重新跑 21 Candidate Trial ×2

STEP 11
Acceptance Consistency Verify

STEP 12
创建 PR 并拿到 CI PASS

STEP 13
独立人工 Review

STEP 14
记录 Review Evidence / Coverage Review

STEP 15
Promotion Preflight

STEP 16
正式 Promotion

STEP 17
Post-Promotion Full Regression

STEP 18
Active Coverage 137/137

STEP 19
Final Acceptance PASS

STEP 20
重新评估 G0A HOLD / FREEZE
```

---

# 5. JOIN MVP 完成 DoD

- [x] JOIN Model v2
- [x] Template v4
- [x] null_side 语义修正
- [x] predicate=none 修正
- [x] less_equal 命名修正
- [x] less_equal 等值边界
- [x] Mutation Validator
- [x] 5 条 Mutation KILLED
- [x] int → INTEGER
- [x] DB Version / Build
- [x] 21 Candidate 双跑
- [x] 30 Active Regression
- [x] AI Technical Review
- [ ] Trial Artifact / Index 完全一致
- [ ] Mutation Evidence 进入 Promotion Gate
- [ ] Framework Tests 最新 PASS
- [ ] GitHub CI PASS
- [ ] Human Review
- [ ] Review Evidence
- [ ] Coverage Review
- [ ] Promotion
- [ ] Post-Promotion Full Regression
- [ ] Active Pairwise 137/137
- [ ] Final Acceptance PASS
- [ ] G0A 最终决定

---

# 6. JOIN 收口后：进入 AI 驱动重构

JOIN 收口后，不建议继续追加 JOIN v5/v6/v7。

应该切换到 AI Control Plane 主线。

---

# 7. AI Phase 1：Application Service Layer

新增：

```text
src/xgtest/application/
├── project_service.py
├── module_service.py
├── preflight_service.py
├── regression_service.py
├── coverage_service.py
├── candidate_service.py
├── runtime_service.py
└── acceptance_service.py
```

目标：

```text
CLI
Web
AI
```

全部走同一层 Service，避免三套业务逻辑。

---

# 8. AI Phase 2：ModuleTestSpec

新增：

```text
modules/query.yaml
```

定义：

```text
Query 有哪些 Required Feature
哪些 Feature 已模型化
各 Feature Coverage Strategy
模块完成条件
```

第一版建议：

```text
basic
join
filter
aggregate
subquery
window
```

---

# 9. AI Phase 3：Project / Module Inspect

实现：

```text
inspect_project()
inspect_module("query")
```

返回：

```text
Git
Contract
Runtime
Feature
Coverage
Blocker
```

---

# 10. AI Phase 4：Unified Preflight

统一检查：

```text
Git
Contract
Runtime Profile
DB Reachability
Artifact Store
Module Spec
Feature Plugin
```

输出：

```text
ready
blockers
recoverable
suggested_actions
```

---

# 11. AI Phase 5：TestIntent

第一版支持：

```text
module_full_test
regression_only
coverage_close
acceptance
```

自然语言先转结构化 TestIntent。

---

# 12. AI Phase 6：Deterministic Planner

输入：

```text
Intent
Project State
Module State
Policy
```

输出：

```text
TestPlan
plan_hash
```

AI 不直接拼执行顺序。

---

# 13. AI Phase 7：ActionResult / ActionError

统一动作状态：

```text
PASS
FAIL
BLOCKED
WAITING_APPROVAL
SKIPPED
```

错误统一：

```text
code
severity
recoverable
retryable
suggested_actions
```

---

# 14. AI Phase 8：TestJob / Event Log

新增：

```text
TestJob
```

状态：

```text
PLANNED
RUNNING
WAITING_APPROVAL
BLOCKED
FAILED
COMPLETED
CANCELLED
```

持久化到：

```text
artifacts/jobs/<job_id>/
```

支持中断恢复。

---

# 15. AI Phase 9：Orchestrator

第一版支持：

```text
顺序 DAG
depends_on
condition
resume
WAITING_APPROVAL
recovery
```

先不做分布式调度。

---

# 16. AI Phase 10：Policy Engine

默认：

```text
Managed Mode
```

AI 可以：

```text
Inspect
Plan
Regression
Coverage
Generate
Validate
Mutation
Trial
Technical Review
```

AI 不可以：

```text
Final Human Review
Promotion Approval
Push main
```

---

# 17. AI Phase 11：TechnicalReview / PromotionApproval 分离

正式定义：

```text
AI Technical Review
≠
Human Promotion Approval
```

防止：

```text
AI 出题
→ AI 自评
→ AI 自批
```

---

# 18. AI Phase 12：Recovery Engine

自动恢复：

```text
Runtime Profile stale
Contract stale
Trial stale
```

人工处理：

```text
Human Review Missing
Promotion Approval
```

---

# 19. AI Phase 13：Completion Evaluator

AI 不允许因为流程跑完就宣布：

```text
Query Full Complete
```

必须根据：

```text
Required Feature
Coverage
Regression
Candidate
Acceptance
```

计算完成状态。

---

# 20. AI Phase 14：Agent Semantic API

第一版只暴露：

```text
inspect_project()
inspect_module()
create_test_plan()
start_test_job()
get_test_job()
resume_test_job()
```

不让 AI 直接：

```text
shell
编辑 YAML
编辑 SQL
重写 Hash
```

---

# 21. AI Phase 15：第一条目标工作流

实现：

```text
query.full_test
```

完整流程：

```text
Inspect
→ Plan
→ Preflight
→ Regression
→ Coverage
→ Generate
→ Validate
→ Mutation
→ Trial
→ Technical Review
→ WAITING_APPROVAL
→ Human Approval
→ Promote
→ Full Regression
→ Coverage Snapshot
→ Acceptance
→ Completion
```

---

# 22. AI Phase 16：Feature Plugin 化

把 `query.join` 迁入：

```text
src/xgtest/features/query/join/
```

标准接口：

```text
load_model
render
validate
mutations
coverage_strategies
```

Planner 只认 Feature Registry，不写 JOIN-specific if/else。

---

# 23. AI Phase 17：扩第二个 Feature

优先：

```text
query.filter
```

然后：

```text
aggregate
set
subquery
cte
window
complex
```

每个 Feature 必须有：

```text
Model
Constraint
Plugin
Template
Mutation
Coverage
Candidate Lifecycle
```

---

# 24. AI 驱动阶段目标目录

```text
src/xgtest/

├── control/
│   ├── intent.py
│   ├── module_spec.py
│   ├── planner.py
│   ├── actions.py
│   ├── errors.py
│   ├── job.py
│   ├── orchestrator.py
│   ├── policy.py
│   ├── recovery.py
│   └── completion.py
│
├── application/
│   ├── project_service.py
│   ├── module_service.py
│   ├── preflight_service.py
│   ├── regression_service.py
│   ├── coverage_service.py
│   ├── candidate_service.py
│   ├── runtime_service.py
│   └── acceptance_service.py
│
├── features/
│   └── query/
│       ├── join/
│       ├── filter/
│       └── aggregate/
│
├── design/
├── generator/
├── query/
├── runtime/
├── adapter/
├── evidence/
└── interfaces/
    ├── cli.py
    ├── http.py
    └── agent.py

modules/
└── query.yaml

policies/
└── default.yaml
```

---

# 25. 推荐 Commit 顺序

JOIN 收口：

```text
01 fix: republish current join trial artifacts
02 feat: verify trial artifact index consistency
03 feat: persist mutation evidence on candidates
04 fix: enforce mutation evidence during promotion
05 fix: normalize mutation action statuses
06 test: rerun framework and schema contract gates
07 test: record current xugu candidate acceptance
08 review: record independent join candidate review
09 feat: promote reviewed join candidates
10 test: record post-promotion query regression
11 feat: publish final join coverage snapshot
12 docs: finalize query generation mvp acceptance
```

AI 重构：

```text
13 refactor: extract application services
14 feat: add module test specification
15 feat: add project and module inspection
16 feat: add unified preflight
17 feat: add test intent contract
18 feat: add deterministic planner
19 feat: add action result and structured errors
20 feat: add persistent test jobs
21 feat: add sequential orchestrator
22 feat: add managed policy engine
23 feat: split technical review and promotion approval
24 feat: add recovery engine
25 feat: add completion evaluator
26 feat: expose agent semantic api
27 feat: add query full-test workflow
28 refactor: migrate join to feature plugin
29 test: add ai-driven e2e workflow
30 feat: add job control web api and views
```

---

# 26. 推荐实际执行顺序

```text
STEP 1   修 Trial Artifact / Index 不一致
STEP 2   Mutation Evidence 正式化
STEP 3   Mutation Gate 接 Promotion
STEP 4   完整 Framework Tests
STEP 5   CI PASS
STEP 6   重新 Real Xugu Acceptance
STEP 7   人工 Review
STEP 8   记录 Review Evidence
STEP 9   Promotion Preflight
STEP 10  Promotion
STEP 11  Post-Promotion Full Regression
STEP 12  Active Coverage 137/137
STEP 13  Final Acceptance
STEP 14  G0A 重新判断
STEP 15  停止继续打磨 JOIN
STEP 16  Application Service
STEP 17  ModuleSpec
STEP 18  Inspect / Preflight
STEP 19  Intent / Planner
STEP 20  Job / Orchestrator
STEP 21  Policy / Recovery / Completion
STEP 22  Agent Semantic API
STEP 23  query.full_test
STEP 24  Feature Plugin 化
STEP 25  Filter / Aggregate 扩展
```

---

# 27. 最终完成标准

JOIN Generation MVP 真正 DONE：

```text
Artifact Chain Consistent
Mutation Gate Enforced
Framework Tests PASS
CI PASS
Human Review PASS
Promotion PASS
Post-Promotion Regression PASS
Active Pairwise 137/137
Final Acceptance PASS
```

AI Control MVP 真正 DONE：

```text
用户只说：
“执行查询模块当前定义范围内全量测试”

系统能够：
Inspect
Plan
Preflight
Run
Recover
Generate
Validate
Mutation
Trial
Review
Wait Approval
Promote
Regression
Coverage
Acceptance
Completion

所有 PASS / Coverage / Promotion Truth
均由 Deterministic Core 决定。
```

---

# 28. 当前最重要的原则

现在不应继续堆：

```text
JOIN v5
JOIN v6
JOIN v7
```

JOIN 已经足够作为第一个 Feature Reference Implementation。

当前优先级应切换为：

```text
证据链收口
→ 正式晋级
→ AI Control Plane
```

即：

```text
先把 JOIN 做成可信、可晋级、可复现的标准样板，
再让 AI 学会操纵这套标准样板。
```
