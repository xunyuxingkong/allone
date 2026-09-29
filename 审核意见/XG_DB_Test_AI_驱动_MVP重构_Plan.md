# XG DB Test：基于现有 MVP 重构为 AI 驱动测试平台的完整实施计划

> 基线分支：`codex/join-model-v2`  
> 基线提交：`350659ab6ccd9f3525557342612fc9835bd57c61`  
> 当前能力：Query Execution、Runtime Profile、Coverage、Generator、Trial Evidence、Promotion Gate、Run History、FastAPI、Vue Coverage/Candidate 页面已具备。JOIN v2 当前仍为 HOLD，`less_equal` 等值边界、最终人工评审与晋级尚未收口。  
> 本计划目标：**不推翻现有确定性测试内核**，逐步增加 AI Control Plane，使用户未来只需提出“执行查询模块全量测试”等目标，由 AI 完成检查、规划、编排、执行、恢复和汇报。

---

# 1. 重构后的核心定位

当前：

```text
人工理解目标
→ 人工决定命令顺序
→ CLI
→ Coverage / Generator / Runner / Evidence
```

目标：

```text
用户自然语言
→ AI Intent Resolver
→ Test Planner
→ Policy Engine
→ Orchestrator
→ Application Services
→ Deterministic Test Core
→ Runtime / Evidence
→ Completion Evaluator
```

核心边界：

```text
AI 负责：
目标理解、规划、编排、诊断、恢复、解释

Core 负责：
PASS/FAIL、Coverage、Constraint、Hash、Runtime Contract、
Evidence Validity、Promotion Gate、Completion Truth
```

AI 可以决定“下一步做什么”，但不能决定“测试事实是什么”。

---

# 2. 现有代码中应直接保留的能力

当前以下代码不应重写：

```text
src/xgtest/query/
  loader.py
  runner.py
  timeout.py
  history.py

src/xgtest/design/
  model.py
  constraint.py
  coverage.py
  signature.py

src/xgtest/generator/
  candidate.py
  dedup.py
  lifecycle.py
  review.py
  template.py

src/xgtest/runtime/
src/xgtest/adapter/
src/xgtest/web/
```

现有能力继续作为 Deterministic Test Core：

```text
Query Loader
Read-only Validation
Xugu Adapter
Runtime Profile
Process Timeout
Comparator
Run History
Test Model
Constraint
Pairwise
Coverage Gap
Candidate Generator
Static Validate
Trial ×2
Review Evidence
Promotion Gate
Acceptance Evidence
```

---

# 3. 当前真正缺失的层

为了让 AI 成为“操纵者”，当前缺少：

```text
Application Service Layer
Module Test Specification
TestIntent
TestPlan
TestJob
Action Contract
Policy Engine
Orchestrator
Recovery Engine
Completion Evaluator
Agent Semantic API
```

也就是说，系统已经具备大量“原子动作”，但还没有：

```text
Goal
→ Plan
→ Execute
→ Observe
→ Recover
→ Complete
```

这条上层控制链。

---

# 4. 目标架构

```text
┌─────────────────────────────────────┐
│          AI Control Plane           │
│ Intent / Planner / Policy           │
│ Orchestrator / Recovery / Completion│
└──────────────────┬──────────────────┘
                   │ Semantic Action
┌──────────────────▼──────────────────┐
│       Application Service Layer     │
│ Project / Module / Preflight        │
│ Regression / Coverage / Candidate   │
│ Runtime / Acceptance                │
└──────────────────┬──────────────────┘
                   │
┌──────────────────▼──────────────────┐
│       Deterministic Test Core       │
│ Model / Constraint / Coverage       │
│ Generator / Trial / Review / Gate   │
│ Query Runner / Comparator           │
└──────────────────┬──────────────────┘
                   │
┌──────────────────▼──────────────────┐
│            Runtime Plane            │
│ Xugu / Runtime Profile / Worker     │
└──────────────────┬──────────────────┘
                   │
┌──────────────────▼──────────────────┐
│           Evidence Plane            │
│ Run / Trial / Job / Coverage / Audit│
└─────────────────────────────────────┘
```

---

# 5. Phase 0：先收口 JOIN v2

AI Control Plane 开发前，先完成当前 JOIN Feature 的 P0。

## 5.1 修复 `less_equal`

当前 `<=` 没有 `a = b` 边界，无法区分 `<` 与 `<=`。

建议：

```text
Model Version      保持 v2
Template Version   v2 → v3
Generator Version  同步升级
```

Template v3 必须构造：

```text
a < b
a = b
a > b
```

中的必要场景，特别保证 `a = b` 对 `less_equal` 有判别力。

## 5.2 增加 Mutation Validation

加入：

```text
<= → <
```

Mutation。

如果替换后结果仍等于 Expected：

```text
CANDIDATE_MUTATION_WEAK
```

候选不得晋级。

## 5.3 修正 `QUERY.JOIN_02_LEFT`

建议将：

```sql
SELECT a.n, b.label
```

改为：

```sql
SELECT a.n, b.n, b.label
```

Expected：

```text
[1, NULL, NULL]
```

让 `null_side=right` 与 JOIN v2 文档严格一致。

## 5.4 重新验收

执行：

```text
Contract Rebuild
Runtime Profile Rebuild
Coverage Recalculate
Candidate Regenerate
Static Validate
Mutation Validate
Real Xugu Trial ×2
AI Technical Review
Human Review
Promotion
Full Regression
Final Coverage Snapshot
```

完成后把 JOIN 作为第一个稳定 Feature Plugin。

---

# 6. Phase 1：抽取 Application Service Layer

这是 AI 重构的第一步，先不改变行为。

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

## 6.1 ProjectService

职责：

```text
Git 状态
Contract 状态
Runtime 状态
模块列表
项目总体可执行状态
```

建议接口：

```python
class ProjectService:
    def inspect(self) -> ProjectState: ...
    def current_contract(self) -> ContractState: ...
    def runtime_state(self) -> RuntimeState: ...
```

## 6.2 CoverageService

把当前 CLI/Web 中的：

```text
load model
load cases
coverage_gap
```

全部统一到：

```python
CoverageService.inspect(...)
CoverageService.gap(...)
```

## 6.3 CandidateService

统一：

```text
generate
validate
mutation_validate
trial
inspect
review
promote
```

内部继续调用现有 `generator/*`。

## 6.4 RegressionService

统一：

```text
query active regression
history persist
post-promotion regression
```

## 6.5 Phase 1 DoD

```text
现有 CLI 输出不变
现有 Web API 行为不变
CLI/Web 均通过 Application Service 调用 Core
现有 Framework Tests 全 PASS
```

---

# 7. Phase 2：定义 Module Test Specification

AI 收到“查询模块全量测试”时，必须知道“全量”是什么。

新增：

```text
modules/query.yaml
```

示例：

```yaml
module_id: query
version: "1"

features:
  - id: basic
    required: true
    execution:
      active_regression: true

  - id: join
    required: true
    model: models/query/join.yaml
    plugin: query.join
    coverage:
      strategies: [pairwise]
      completion:
        gap: 0

  - id: filter
    required: true
    status: not_modeled

  - id: aggregate
    required: true
    status: not_modeled

  - id: subquery
    required: true
    status: not_modeled

  - id: window
    required: true
    status: not_modeled

completion:
  active_regression: PASS
  required_features_modeled: true
  required_coverage_gap: 0
  unresolved_candidates: 0
  acceptance_status: PASS
```

新增：

```text
src/xgtest/control/module_spec.py
```

定义：

```python
ModuleTestSpec
ModuleFeatureSpec
CompletionSpec
```

---

# 8. Phase 3：实现 ModuleService

接口：

```python
ModuleService.inspect("query")
```

返回机器可读状态：

```json
{
  "module": "query",
  "required_features": 6,
  "modeled_features": 1,
  "features": [
    {
      "id": "join",
      "modeled": true,
      "pairwise_gap": 0
    },
    {
      "id": "filter",
      "modeled": false
    }
  ]
}
```

这样 AI 不会因为 JOIN 完成就误判“Query 全量完成”。

---

# 9. Phase 4：统一 Preflight

新增：

```text
src/xgtest/application/preflight_service.py
```

统一检查：

```text
Git branch
Git dirty state
Contract current
Runtime Profile exists
Runtime Profile Contract matches
Driver version matches
Xugu reachable
DB target matches
Artifact directory writable
Cases directory valid
ModuleSpec valid
Feature Plugin availability
```

返回：

```json
{
  "ready": false,
  "checks": [
    {
      "code": "RUNTIME_PROFILE_CURRENT",
      "status": "FAIL",
      "recoverable": true,
      "suggested_action": "runtime.profile.rebuild"
    }
  ]
}
```

---

# 10. Phase 5：引入 TestIntent

新增：

```text
src/xgtest/control/intent.py
```

第一版只支持：

```text
module_full_test
regression_only
coverage_close
acceptance
```

用户说：

```text
“对查询模块执行全量测试”
```

AI 转换成：

```yaml
intent_version: "1"
goal: module_full_test
module: query

execution:
  mode: regression
  run_active_cases: true

coverage:
  inspect: true
  close_gap: true

generation:
  enabled: true

trial:
  enabled: true
  repetitions: 2

review:
  policy: managed

promotion:
  requested: true

acceptance:
  required: true
```

TestIntent 只表达：

```text
用户想要什么
```

不表达执行顺序。

---

# 11. Phase 6：实现确定性 Planner

新增：

```text
src/xgtest/control/planner.py
```

输入：

```text
TestIntent
ProjectState
ModuleState
Policy
```

输出：

```text
TestPlan
```

建议数据结构：

```python
class PlanStep:
    id
    action
    depends_on
    params
    condition

class TestPlan:
    plan_id
    intent_id
    steps
    plan_hash
```

`module_full_test` 默认计划：

```text
project.inspect
→ module.inspect
→ runtime.preflight
→ contract.verify
→ regression.run_active
→ coverage.inspect
→ candidate.generate
→ candidate.validate
→ candidate.mutation_validate
→ candidate.trial
→ technical_review
→ approval_gate
→ candidate.promote
→ regression.run_post_promotion
→ coverage.snapshot
→ acceptance.build
→ completion.evaluate
```

同样输入必须得到稳定 `plan_hash`。

---

# 12. Phase 7：统一 Action Contract

新增：

```text
src/xgtest/control/actions.py
src/xgtest/control/errors.py
```

标准动作：

```text
project.inspect
module.inspect
runtime.preflight
contract.verify
regression.run
coverage.inspect
candidate.generate
candidate.validate
candidate.mutation_validate
candidate.trial
candidate.technical_review
candidate.promote
coverage.snapshot
acceptance.build
completion.evaluate
```

标准返回：

```python
class ActionResult:
    action
    status       # PASS / FAIL / BLOCKED / WAITING_APPROVAL
    outputs
    evidence_refs
    error
```

标准错误：

```python
class ActionError:
    code
    severity
    recoverable
    retryable
    message
    suggested_actions
```

示例：

```json
{
  "code": "RUNTIME_PROFILE_STALE",
  "severity": "BLOCKER",
  "recoverable": true,
  "retryable": false,
  "suggested_actions": [
    "runtime.profile.rebuild",
    "candidate.retrial"
  ]
}
```

---

# 13. Phase 8：实现 TestJob

新增：

```text
src/xgtest/control/job.py
```

Job 状态：

```text
PLANNED
RUNNING
WAITING_APPROVAL
BLOCKED
FAILED
COMPLETED
CANCELLED
```

Step 状态：

```text
PENDING
RUNNING
PASS
FAIL
BLOCKED
SKIPPED
WAITING_APPROVAL
```

TestJob：

```python
class TestJob:
    job_id
    intent
    plan
    state
    current_step
    steps
    blockers
    created_at
    updated_at
```

---

# 14. Phase 9：Job 持久化与 Event Log

新增：

```text
src/xgtest/evidence/jobs.py
```

目录：

```text
artifacts/jobs/
└── QUERY-FULL-20260929-001/
    ├── intent.json
    ├── plan.json
    ├── state.json
    ├── events.jsonl
    └── final-report.json
```

事件：

```json
{"seq":1,"event":"JOB_CREATED"}
{"seq":2,"event":"STEP_STARTED","step":"preflight"}
{"seq":3,"event":"STEP_PASSED","step":"preflight"}
{"seq":4,"event":"STEP_BLOCKED","step":"trial","code":"RUNTIME_PROFILE_STALE"}
```

要求进程重启后可恢复当前 Job。

---

# 15. Phase 10：实现 Orchestrator

新增：

```text
src/xgtest/control/orchestrator.py
```

第一版只支持：

```text
顺序 DAG
depends_on
condition
WAITING_APPROVAL
FAIL STOP
resume
```

不做复杂分布式调度。

核心流程：

```text
读取下一可执行 Step
→ Policy 校验
→ 执行 Action
→ Persist Result
→ 更新 Job State

PASS
→ 下一步

WAITING_APPROVAL
→ 暂停

BLOCKED
→ Recovery

FAIL
→ Job FAILED
```

---

# 16. Phase 11：Policy Engine

新增：

```text
src/xgtest/control/policy.py
policies/default.yaml
```

建议默认使用：

```text
Managed Mode
```

示例：

```yaml
mode: managed

actions:
  project.inspect:
    ai_allowed: true

  regression.run:
    ai_allowed: true

  coverage.inspect:
    ai_allowed: true

  candidate.generate:
    ai_allowed: true

  candidate.validate:
    ai_allowed: true

  candidate.mutation_validate:
    ai_allowed: true

  candidate.trial:
    ai_allowed: true

  candidate.technical_review:
    ai_allowed: true

  candidate.record_human_review:
    ai_allowed: false

  candidate.promote:
    ai_allowed: false

  git.push_main:
    ai_allowed: false
```

---

# 17. Phase 12：定义自治等级

## Level 1 Assisted

```text
AI:
Inspect / Plan / Analyze

Human:
执行 Trial / Review / Promote
```

## Level 2 Managed

```text
AI:
Inspect / Plan / Regression / Coverage / Generate /
Validate / Mutation / Trial / Technical Review

Human:
Promotion Approval
```

## Level 3 Autonomous

```text
AI:
完整推进

但必须满足：
Policy
Deterministic Gate
Independent Review
Mutation Validation
```

当前 MVP 先实现 Level 2。

---

# 18. Phase 13：拆分 Technical Review 与 Promotion Approval

当前 `record_review()` 偏向“正式评审已完成”。

应拆：

```text
TechnicalReview
PromotionApproval
```

TechnicalReview 可以来自：

```text
AI
Human
Static Analyzer
Mutation Validator
```

例如：

```yaml
review_type: ai_technical
reviewer: codex
decision: hold
findings:
  - LESS_EQUAL_BOUNDARY_WEAK
```

PromotionApproval 第一版只允许：

```text
human
```

防止：

```text
AI 出题
→ AI 自评
→ AI 自批
```

---

# 19. Phase 14：正式加入 Mutation Validation

新增：

```text
src/xgtest/generator/mutation.py
```

或后续迁入 Feature Plugin。

JOIN 示例：

```yaml
mutations:
  less_equal:
    - id: replace_le_with_lt
      replacement: "<"
      expectation: result_must_change

  equality:
    - id: replace_eq_with_ne
      replacement: "<>"
      expectation: result_must_change
```

Mutation 结果：

```json
{
  "case_id": "QUERY.JOIN.xxx",
  "mutation_id": "replace_le_with_lt",
  "status": "PASS",
  "original_hash": "...",
  "mutated_hash": "..."
}
```

如果 Mutation 没被杀死：

```text
Candidate HOLD
```

---

# 20. Phase 15：Feature Plugin 化

当前仍有 JOIN-specific 代码，例如：

```text
if model.model_id != "query.join"
```

长期必须去掉。

新增：

```text
src/xgtest/features/
└── query/
    ├── join/
    │   ├── plugin.py
    │   ├── template.py
    │   ├── mutations.py
    │   └── validator.py
    ├── filter/
    └── aggregate/
```

接口：

```python
class FeaturePlugin:
    feature_id
    load_model()
    render()
    validate_candidate()
    mutation_checks()
    supported_strategies()
```

FeatureRegistry：

```text
query.join
query.filter
query.aggregate
...
```

Planner 只读取 Registry，不写 Feature-specific `if/else`。

---

# 21. Phase 16：Completion Evaluator

新增：

```text
src/xgtest/control/completion.py
```

AI 不允许把：

```text
“所有命令执行完”
```

等价成：

```text
“全量测试完成”
```

返回：

```json
{
  "complete": false,
  "checks": {
    "runtime_ready": "PASS",
    "active_regression": "PASS",
    "required_features_modeled": "FAIL",
    "coverage_gap": "PASS",
    "unresolved_candidates": "PASS"
  },
  "blockers": [
    {
      "code": "FEATURE_NOT_MODELED",
      "feature": "window"
    }
  ]
}
```

---

# 22. Phase 17：Recovery Engine

新增：

```text
src/xgtest/control/recovery.py
```

规则示例：

```text
RUNTIME_PROFILE_STALE
→ rebuild profile
→ retrial

CONTRACT_SET_STALE
→ rebuild contract
→ rebuild profile
→ retrial

CANDIDATE_SEMANTIC_HASH_STALE
→ static validate
→ trial
→ review again

HUMAN_APPROVAL_REQUIRED
→ WAITING_APPROVAL
```

每种错误必须分：

```text
auto_recoverable
human_required
fatal
```

---

# 23. Phase 18：AI Semantic Tool API

不要让 AI 直接调用几十个低层函数。

第一版只提供 6 个工具：

```text
inspect_project()
inspect_module(module_id)
create_test_plan(intent)
start_test_job(plan_id)
get_test_job(job_id)
resume_test_job(job_id, approval=None)
```

内部：

```text
Agent API
→ Control/Application Layer
→ Core
```

不允许直接：

```text
shell.exec
filesystem.write
yaml.edit
candidate SQL edit
manual hash rewrite
```

---

# 24. Phase 19：CLI 重构

CLI 最终只是 Adapter：

```text
CLI
→ Application / Control
```

保留旧命令兼容：

```text
xgtest query
xgtest coverage
xgtest candidate
```

新增：

```bash
xgtest project inspect
xgtest module inspect query
xgtest test plan --intent intent.json
xgtest job start plan.json
xgtest job status JOB_ID
xgtest job resume JOB_ID
```

先不删除旧 CLI。

---

# 25. Phase 20：Web Control API

在当前只读 API 上增加：

```text
GET  /api/project
GET  /api/modules/{module}
POST /api/plans
POST /api/jobs
GET  /api/jobs/{job_id}
POST /api/jobs/{job_id}/resume
POST /api/jobs/{job_id}/approval
```

必须：

```text
FastAPI
→ Control/Application
→ Core
```

Web 不实现业务规则。

---

# 26. Phase 21：Web Job 页面

新增：

```text
JobListView.vue
JobDetailView.vue
PlanView.vue
ApprovalView.vue
```

JobDetail 展示：

```text
Intent
Plan
Current Step
Step Status
Blockers
Recovery
Evidence
Approval
Completion
```

---

# 27. Phase 22：第一条 AI Workflow —— query.full_test

这是 AI Control MVP 的核心验收流程。

流程：

```text
User:
“对查询模块执行当前定义范围内的全量测试”

↓
AI: inspect_project

↓
AI: inspect_module(query)

↓
TestIntent

↓
Planner

↓
Preflight

↓
Active Regression

↓
逐个 modeled Feature：
  Coverage
  Gap
  Generate
  Validate
  Mutation Validate
  Trial
  Technical Review

↓
Policy
→ WAITING_APPROVAL

↓
Human Approval

↓
Promote

↓
Post-promotion Full Regression

↓
Coverage Snapshot

↓
Acceptance

↓
Completion Evaluate
```

如果：

```text
JOIN complete
Filter not_modeled
Aggregate not_modeled
```

最终必须返回：

```text
DEFINED_SCOPE_COMPLETE
MODULE_FULL_INCOMPLETE
```

不能说“Query 全量测试已经完成”。

---

# 28. Phase 23：再扩 Filter Plugin

AI Control MVP 跑通后，再实现第二个 Feature：

```text
query.filter
```

建议维度：

```text
operator
datatype
nullability
predicate_position
expression_shape
boundary
```

目的不是一次做完 Query，而是验证 Plugin 架构是否真的通用。

---

# 29. Phase 24：Aggregate Plugin

再实现：

```text
query.aggregate
```

建议维度：

```text
function:
COUNT / SUM / AVG / MIN / MAX

input_shape:
empty / single / multi

null_pattern:
none / partial / all

grouping:
none / group_by

interaction:
having / distinct / expression
```

---

# 30. 后续扩展顺序

建议：

```text
Filter
→ Aggregate
→ Set Operation
→ Subquery
→ CTE
→ Window
→ Complex Query
```

每个 Feature 必须具备：

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

# 31. 推荐最终目录

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
│
├── evidence/
│   ├── jobs.py
│   └── artifacts.py
│
└── interfaces/
    ├── cli.py
    ├── http.py
    └── agent.py

modules/
└── query.yaml

policies/
└── default.yaml

artifacts/
└── jobs/
```

---

# 32. 新增测试结构

```text
framework_tests/control/
├── test_intent.py
├── test_module_spec.py
├── test_planner.py
├── test_actions.py
├── test_job.py
├── test_orchestrator.py
├── test_policy.py
├── test_recovery.py
└── test_completion.py

framework_tests/application/
├── test_project_service.py
├── test_module_service.py
├── test_preflight_service.py
├── test_coverage_service.py
├── test_candidate_service.py
└── test_regression_service.py

framework_tests/features/query/join/
├── test_plugin.py
├── test_mutations.py
└── test_validator.py
```

---

# 33. 必须具备的 Golden / E2E Tests

## Planner Golden

固定：

```text
Intent
ProjectState
ModuleSpec
Policy
```

必须得到固定：

```text
Plan Steps
Plan Hash
```

## Recovery

模拟：

```text
Runtime Profile stale
```

必须：

```text
BLOCK
→ rebuild
→ resume
```

## Approval

Candidate：

```text
Validate PASS
Mutation PASS
Trial PASS
Technical Review PASS
```

但 Policy 要求人工批准时：

```text
Job = WAITING_APPROVAL
```

AI 不能自动 Promote。

## Completion

```text
JOIN gap=0
Filter not_modelled
```

必须：

```text
complete=false
```

## Resume

执行到：

```text
Trial 已完成
Review 等待批准
```

重启进程后，Job 能从 `state.json/events.jsonl` 恢复，不重复执行已确认有效 Step。

---

# 34. AI Control MVP DoD

- [ ] Application Service Layer
- [ ] ModuleTestSpec
- [ ] Query Module Spec
- [ ] Project Inspect
- [ ] Module Inspect
- [ ] Unified Preflight
- [ ] TestIntent
- [ ] Deterministic Planner
- [ ] TestPlan Hash
- [ ] ActionResult
- [ ] Structured ActionError
- [ ] TestJob
- [ ] Event Log
- [ ] Job Resume
- [ ] Sequential Orchestrator
- [ ] Managed Policy
- [ ] WAITING_APPROVAL
- [ ] TechnicalReview / PromotionApproval 分离
- [ ] Mutation Validation
- [ ] Recovery Engine
- [ ] Completion Evaluator
- [ ] Agent Semantic API
- [ ] query.full_test E2E
- [ ] Web Job View
- [ ] Control Layer Framework Tests

---

# 35. AI Control MVP 明确不做

第一版不做：

```text
Multi-Agent
LLM 直接写 SQL
AI 自己判 PASS
AI 自动 Merge main
AI 自动最终 Promotion
跨节点 Scheduler
Lease/Fencing
长期 24h Autonomous Agent
复杂 Workflow DSL
通用 BPM
大型 RAG 平台
```

这些都不应该阻塞 AI Control MVP。

---

# 36. 推荐 Commit 顺序

```text
01 fix: strengthen less_equal join boundary evidence

02 refactor: extract application services from cli and web

03 feat: add module test specification contract

04 feat: add project and module inspection services

05 feat: add unified preflight service

06 feat: add structured test intent contract

07 feat: add deterministic test planner

08 feat: add machine-readable action results and errors

09 feat: add persistent test job and event log

10 feat: add sequential test orchestrator

11 feat: add managed autonomy policy

12 feat: separate technical review and promotion approval

13 feat: add mutation validation

14 feat: add recovery engine

15 feat: add completion evaluator

16 feat: expose semantic agent control API

17 feat: add query full-test workflow

18 refactor: migrate join generator to feature plugin

19 test: add ai control end-to-end workflow tests

20 feat: add job and approval web api

21 feat: add job and approval web views

22 docs: document ai-driven test platform architecture
```

---

# 37. 每个 Commit 的要求

```text
一个主要问题
一个清晰目标
一组对应测试
现有 Query 行为不得退化
Schema/Contract 变化必须同步
```

不要再次出现一个 Commit 同时塞：

```text
Control Plane
Plugin
UI
Feature
大量 Case
```

---

# 38. 实际开发执行顺序

```text
STEP 0
JOIN v3 边界修复并完成最终验收

STEP 1
Application Service 抽层

STEP 2
确认旧 CLI/Web 全部回归 PASS

STEP 3
modules/query.yaml

STEP 4
Project Inspect / Module Inspect

STEP 5
Preflight

STEP 6
TestIntent

STEP 7
Planner / TestPlan

STEP 8
ActionResult / ActionError

STEP 9
TestJob / Event Log

STEP 10
Orchestrator

STEP 11
Policy

STEP 12
WAITING_APPROVAL

STEP 13
TechnicalReview / PromotionApproval

STEP 14
Mutation Validation

STEP 15
Recovery

STEP 16
Completion Evaluator

STEP 17
Agent Semantic API

STEP 18
query.full_test

STEP 19
完整 E2E

STEP 20
JOIN Plugin 化

STEP 21
Filter Plugin

STEP 22
Aggregate Plugin
```

---

# 39. 第一条真正的 AI E2E 验收

用户：

```text
对查询模块执行当前定义范围内的全量测试
```

系统必须自动：

```text
Inspect Project
Inspect Query Module
Preflight
Plan
Run Active Regression
Inspect JOIN Coverage
Close Gap
Generate Candidate
Static Validate
Mutation Validate
Real Xugu Trial
AI Technical Review
WAITING_APPROVAL
```

用户批准后：

```text
Promote
Full Regression
Coverage Snapshot
Acceptance
Completion
```

最终输出必须区分：

```text
当前定义范围测试完成
```

与：

```text
整个 Query Module 完整覆盖
```

如果有 Required Feature 未模型化，后一项必须是 false。

---

# 40. 最终产品形态

重构完成后，用户不再需要知道：

```text
xgtest coverage
xgtest generate
xgtest candidate validate
xgtest candidate trial
xgtest candidate promote
```

用户只表达目标：

```text
“查询模块全量测试”
“重新验证 JOIN”
“关闭 Aggregate 覆盖缺口”
“做一次发布前验收”
```

AI 负责：

```text
理解
计划
执行
恢复
等待必要审批
继续
最终汇报
```

Core 负责：

```text
事实
证据
门禁
```

---

# 41. 最终原则

这个重构的关键不是“把 LLM 接进来”，而是把现有测试框架改造成：

```text
可被 AI 稳定操纵的确定性测试系统
```

必须始终保持：

```text
AI 可以决定下一步
但不能决定测试真相
```

这样最终才能同时获得：

```text
AI 的灵活性
+
数据库测试平台的确定性
+
可重复
+
可追溯
+
可恢复
+
可审计
```
