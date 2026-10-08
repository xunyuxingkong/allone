# XG DB Test：面向“可用 AI 驱动测试 MVP”的下一步实施计划

## 0. 本文基线

- 仓库：`xunyuxingkong/allone`
- 分支：`codex/join-model-v2`
- 当前远端 HEAD：`969f8be6e9698d5b6cbb97ee870ac6963ac9d1b4`
- 当前提交：`feat: implement audit model separation and refresh v14 evidence`
- 文档目标：**尽快做出一个真正可使用的 AI 驱动测试 MVP，而不是继续无限完善底层治理。**

当前项目已经具备：

```text
Query Runner
Runtime Profile
Contract Identity v3
FeaturePlugin
AcceptanceScope
Coverage
Candidate Generator
Static Validation
Real Xugu Trial
Mutation Validation
Artifact Evidence
Human Review Gate
Signed Promotion Approval
Promotion Preflight
Recoverable Batch Promotion
Post Acceptance
Release Check Evidence
FastAPI / Vue Read UI
```

这些能力已经足够支撑第一版 AI Control Plane。

从本版本开始，开发原则调整为：

> **除非存在阻塞 AI MVP E2E 的真实缺陷，否则停止继续单独做 Evidence / Contract / Governance 的大规模增强。**

---

# 1. 重新定义 MVP

最开始的项目目标不是做一个“测试资产治理平台”。

真正目标应保持为：

```text
用户给目标
        ↓
AI 理解当前项目状态
        ↓
AI 决定下一步测试动作
        ↓
确定性测试内核执行
        ↓
Evidence 决定事实
        ↓
AI 分析结果 / 规划后续动作
        ↓
必要时等待人工批准
        ↓
继续执行
        ↓
给出最终测试结论
```

因此新的 MVP 定义为：

> **用户不需要理解 xgtest 的底层命令，只需要描述测试目标，AI 能够自主检查、规划、执行、分析、恢复并汇报；所有 PASS/FAIL、Coverage、Evidence、Promotion 事实仍由 Deterministic Core 决定。**

核心原则：

```text
AI 决定“下一步做什么”
Core 决定“事实是什么”
Human 决定“高风险动作是否批准”
```

---

# 2. 可用 MVP 的最小用户体验

第一版只要求真正跑通一个用户入口：

```text
“对查询模块执行当前定义范围内的全量测试”
```

用户不再手工执行：

```text
xgtest coverage ...
xgtest generate ...
xgtest candidate validate ...
xgtest candidate mutation-validate ...
xgtest candidate trial ...
xgtest acceptance ...
```

系统自动完成：

```text
Inspect Project
↓
Inspect Query Module
↓
检查 Contract / Runtime / DB
↓
生成 Test Plan
↓
执行 Active Regression
↓
分析 JOIN Coverage
↓
发现 Gap
↓
生成 Candidate
↓
Static Validate
↓
Mutation Validate
↓
Real Xugu Trial
↓
AI Technical Review
↓
WAITING_APPROVAL
```

人工批准之后：

```text
Resume Job
↓
Promotion Preflight
↓
Promote
↓
Full Query Regression
↓
Post Acceptance
↓
Completion Evaluate
↓
Final Report
```

这条链真正跑通，就是第一版 **AI Driven Test MVP**。

---

# 3. MVP 的验收标准

只有同时满足下面条件，才叫“可用 MVP”。

## 3.1 用户入口

支持：

```text
自然语言目标
```

至少：

```text
查询模块全量测试
重新验证 JOIN
查看当前 Query 测试完成度
```

不要求用户知道底层命令。

---

## 3.2 AI 必须真正参与决策

AI 不能只是：

```text
自然语言 → 固定脚本
```

AI 至少负责：

```text
理解用户目标
读取 Project / Module State
根据当前状态选择下一 Semantic Action
解释 Failure / Blocker
决定是否重试、补覆盖、继续还是等待审批
生成 Technical Review
生成最终自然语言报告
```

但 AI 不能决定：

```text
PASS / FAIL
Coverage 数值
Mutation 是否 KILLED
Evidence 是否有效
Promotion 是否满足 Gate
Final Acceptance Truth
```

这些继续由 Core 计算。

---

## 3.3 Job 可恢复

执行到：

```text
WAITING_APPROVAL
```

关闭程序后重新启动，必须能够：

```text
继续原 Job
```

而不是从头重新跑。

---

## 3.4 有真实 Xugu 执行

MVP 必须继续使用：

```text
真实 Xugu
真实 Trial
真实 Regression
真实 Mutation Evidence
```

Fake Runner 只能用于 Framework Test。

---

## 3.5 AI 不能自批

AI 可以：

```text
Technical Review
```

但不能写入：

```text
Human ReviewEvidence
CoverageReview
Signed Promotion Approval
```

正式 Promotion 必须保留人工 Gate。

---

# 4. MVP 当前范围

为了防止继续失控，第一版范围固定为：

```text
Module:
query

Feature:
join

Intent:
query.full_test
query.join.verify
query.status
```

允许：

```text
JOIN Active Regression
JOIN Coverage
JOIN Candidate Generation
JOIN Mutation
JOIN Trial
JOIN Acceptance
```

第一版不要求：

```text
Filter
Aggregate
Subquery
Window
CTE
Set Operation
```

真正 E2E 跑通之后，再用 Filter 验证 Plugin 扩展能力。

---

# 5. 现在立即停止扩大的内容

以下能力 **不再作为 MVP 前置条件**：

```text
ActiveManifest
ActiveCaseRepository
Remote ArtifactStore
MinIO / S3
CiEvidence
GitHub Required Checks
Branch Protection
GovernanceExceptionApproval
Multi-Agent
Distributed Scheduler
Lease / Fencing
复杂 Workflow DSL
完整 Source Repair Engine
更多 JOIN Coverage
更多 Mutation Framework 抽象
大型 Web Control Center
RAG / Knowledge Graph
```

这些不是“不做”，而是：

```text
MVP 后再做
```

当前已有：

```text
Cross-process Lock
Recoverable Batch
Local ArtifactStore
Portable Bundle
Signed Approval
Post Acceptance
```

已经足够支撑本机单用户 MVP。

---

# 6. 从现在开始禁止“无目的 Evidence 刷版本”

过去：

```text
v12
v13
v14
```

每轮都明显提高了底层质量。

但从现在开始：

> **只有 Execution Contract、Runtime、Candidate 语义或真实 Test Result 改变时，才重建对应 Evidence。**

禁止：

```text
仅因为重构 UI
仅因为改文档
仅因为新增 AI Control 代码
```

就机械产生：

```text
v15
v16
v17
```

Trial / Mutation 全量刷新。

AI Control Plane 不应不断制造测试证据版本。

---

# 7. 当前先完成一个最小前置动作

在进入 AI Control Plane 之前，只完成一个业务收口：

```text
JOIN Formal Acceptance
```

但不再继续重构 JOIN。

当前必须完成：

```text
1. 将运行中的 API 切到 v14
2. 确认：
   Git Commit
   Execution Contract ID
   Runtime Profile ID
   Manifest ID
3. Human Review 21 Candidate
4. Re-Freeze Package
5. Verify
6. 生成新的 PromotionPlan
7. Signed Approval
8. Preflight
9. Promote
10. Full Regression
11. Post Acceptance
```

如果 CI 仍然 Deferred：

```text
Final = HOLD
```

可以接受。

这里的目的不是追求正式 Release，而是：

> **证明完整 Human Gate / Resume / Post Acceptance 这条链真实跑过一次。**

完成后立即停止继续打磨 JOIN。

---

# 8. MVP 目标架构

```text
┌────────────────────────────────────────┐
│             User / Web / CLI           │
│ “执行 Query 当前定义范围的全量测试”      │
└───────────────────┬────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────┐
│            AI Control Plane            │
│ Intent Resolver                        │
│ AI Planner                             │
│ Failure Analyzer                       │
│ Technical Reviewer                     │
│ Job Controller                         │
└───────────────────┬────────────────────┘
                    │ Semantic Actions
                    ▼
┌────────────────────────────────────────┐
│       Minimal Application Services     │
│ ProjectService                         │
│ ModuleService                          │
│ CandidateService                       │
│ AcceptanceService                      │
└───────────────────┬────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────┐
│        Deterministic Test Core         │
│ Runner / Comparator / Coverage         │
│ Generator / Mutation / Evidence        │
│ Promotion / Post Acceptance            │
└───────────────────┬────────────────────┘
                    │
             ┌──────┴──────┐
             ▼             ▼
         Real Xugu      Evidence
```

原则：

```text
LLM 永远不直接修改 Truth
```

---

# 9. Application Service 不再做“大而全”

旧计划准备一次抽：

```text
ProjectService
ModuleService
PreflightService
RegressionService
CoverageService
CandidateService
RuntimeService
AcceptanceService
...
```

MVP 不需要一次做完。

只做 4 个：

```text
ProjectService
ModuleService
CandidateService
AcceptanceService
```

---

# 10. ProjectService

职责：

```text
读取当前 Project State
Contract State
Runtime State
DB Reachability
当前 Git / Source Identity
```

建议：

```python
class ProjectService:
    def inspect(self) -> ProjectState: ...
    def preflight(self) -> PreflightResult: ...
```

返回机器可读：

```json
{
  "ready": true,
  "execution_contract_id": "...",
  "runtime_profile_id": "...",
  "database": "Xugu",
  "blockers": []
}
```

它只调用现有 Core，不重新实现规则。

---

# 11. ModuleService

MVP 只支持：

```text
query
```

职责：

```text
读取 Feature
读取 Active Regression 状态
读取 Coverage
读取 Candidate
计算当前定义范围完成度
```

接口：

```python
class ModuleService:
    def inspect(self, module_id: str) -> ModuleState: ...
    def run_regression(self, module_id: str) -> ActionResult: ...
    def inspect_coverage(self, feature_id: str) -> ActionResult: ...
```

第一版 ModuleState：

```json
{
  "module": "query",
  "features": {
    "join": {
      "modeled": true,
      "active_coverage": "17/137",
      "candidate_coverage": "137/137"
    }
  },
  "module_completion": "MODULE_FULL_INCOMPLETE"
}
```

---

# 12. CandidateService

直接封装现有：

```text
generate
static validate
mutation validate
trial
technical review
```

建议：

```python
class CandidateService:
    def generate(...): ...
    def validate(...): ...
    def mutation_validate(...): ...
    def trial(...): ...
    def technical_review(...): ...
```

AI 不允许：

```text
直接改 YAML
直接写 Hash
直接写 MutationEvidence
```

只能调用 Service。

---

# 13. AcceptanceService

封装：

```text
freeze package
verify package
promotion preflight
promotion
post acceptance
final
```

接口：

```python
class AcceptanceService:
    def inspect(...): ...
    def preflight(...): ...
    def promote(...): ...
    def post_verify(...): ...
```

正式 Promotion 仍要求：

```text
Human Review
Signed Approval
```

---

# 14. MVP 只新增 5 个控制模型

不要继续造大量 Model。

第一版只需要：

```text
TestIntent
TestPlan
TestJob
ActionResult
JobEvent
```

---

# 15. TestIntent

表达：

```text
用户到底想干什么
```

第一版只允许：

```text
query.full_test
query.join.verify
query.status
```

示例：

```json
{
  "intent": "query.full_test",
  "module": "query",
  "requested_by": "user",
  "allow_candidate_generation": true,
  "allow_trial": true,
  "allow_promotion": true
}
```

---

# 16. AI Planner，而不是纯固定 Planner

为了不偏离“AI 驱动”的本心：

> **Planner 应允许 AI 根据当前 ProjectState / ModuleState 选择下一步 Semantic Action。**

但 AI 不能随便生成命令。

结构：

```text
AI
↓
提出 Action Plan
↓
PlanValidator
↓
Policy
↓
允许的 Semantic Actions
```

例如 AI 可以判断：

```text
Runtime stale
→ 先 rebuild / stop

Coverage 有 Gap
→ generate

Candidate 已有有效 Trial
→ 不重复 Trial

Candidate 等待人工批准
→ WAITING_APPROVAL
```

AI 负责：

```text
选择动作
```

Deterministic Validator 负责：

```text
这个动作是否允许
前置条件是否满足
参数是否合法
```

---

# 17. Semantic Action 白名单

AI 只能调用：

```text
project.inspect
project.preflight

module.inspect
module.regression
feature.coverage

candidate.generate
candidate.validate
candidate.mutation
candidate.trial
candidate.technical_review

acceptance.inspect
acceptance.preflight
acceptance.promote
acceptance.post_verify
```

禁止 AI 直接：

```text
shell command
filesystem.write
yaml edit
SQL rewrite
hash edit
git main merge
human approval
```

---

# 18. ActionResult

所有 Service 返回统一结构：

```json
{
  "action": "candidate.trial",
  "status": "PASS",
  "outputs": {},
  "evidence_refs": [],
  "blockers": [],
  "next_allowed_actions": []
}
```

状态第一版只需要：

```text
PASS
FAIL
BLOCKED
WAITING_APPROVAL
SKIPPED
```

---

# 19. TestJob

Job 是 MVP 真正的中心。

```python
class TestJob:
    job_id
    intent
    plan
    state
    current_action
    action_results
    blockers
```

状态：

```text
PLANNED
RUNNING
WAITING_APPROVAL
BLOCKED
FAILED
COMPLETED
```

---

# 20. Job 持久化直接用文件，不引入数据库

MVP 不上 SQLite / PostgreSQL Job Store。

继续遵守当前项目 Evidence 风格：

```text
artifacts/jobs/<job_id>/
```

目录：

```text
intent.json
plan.json
state.json
events.jsonl
final-report.json
```

写入：

```text
atomic state replace
+
events append lock
```

已经够用。

未来真正需要并发 Agent 时再迁数据库。

---

# 21. Minimal Orchestrator

第一版 Orchestrator 只支持：

```text
一个 Job
顺序执行
一个 Action 一个 Action 地推进
WAITING_APPROVAL
BLOCKED
Resume
```

不做：

```text
DAG Scheduler
Parallel Worker
Distributed Lease
Queue
Retry Storm
```

核心：

```python
while job.running:
    state = inspect_state()
    action = ai.choose_next_action(state)
    validate(action)
    result = service.execute(action)
    persist(result)

    if result.status == "WAITING_APPROVAL":
        pause()
```

---

# 22. AI Control Loop

真正的 MVP 应是一个循环，而不是一次 Plan 后机械跑完：

```text
Inspect
↓
AI Decide
↓
Validate Action
↓
Execute
↓
Observe
↓
AI Decide
↓
...
```

即：

```text
Observe → Think → Act → Observe
```

但“Think”只能影响：

```text
Next Action
```

不能影响：

```text
PASS / FAIL Truth
```

---

# 23. AI Technical Review

新增独立结构：

```text
TechnicalReview
```

AI 根据：

```text
SQL
Expected
Coverage Claim
Trial run1/run2
Mutation
Runtime Identity
```

输出：

```json
{
  "review_type": "ai_technical",
  "decision": "PASS",
  "findings": [],
  "recommendation": "READY_FOR_HUMAN_REVIEW"
}
```

这个结果：

```text
可以帮助人评审
不能满足 Human Review Gate
```

---

# 24. Failure Analyzer 必须进入 MVP

这是保持“AI 驱动测试”而不是“AI 点按钮”的关键。

Regression / Trial 失败后：

```text
Core:
FAIL

AI:
读取结构化失败信息
↓
分类
↓
解释
↓
决定下一动作
```

MVP 分类只需要：

```text
TEST_ASSERTION
DATABASE_ERROR
RUNTIME_ENVIRONMENT
EVIDENCE_STALE
COVERAGE_GAP
UNKNOWN
```

AI 输出：

```text
failure_summary
likely_area
recommended_action
confidence
```

但不覆盖 Core FailureType。

---

# 25. MVP 暂时不做自动源码修复，但必须预留 Repair Action

为了尽快可用：

第一版不要求：

```text
AI 自动改数据库源码
自动 commit
自动 merge
```

否则 MVP 会再次膨胀。

但 Action Contract 中预留：

```text
repair.propose
repair.validate
```

MVP 中：

```text
Failure Analyzer
→ RepairSuggestion
```

即可。

下一阶段再升级成：

```text
Patch Candidate
→ Targeted Test
→ Regression
→ Human Merge
```

这样没有偏离最开始的自动修复方向，但不会阻塞当前 AI Test MVP。

---

# 26. 第一个 AI E2E Workflow

用户：

```text
执行 Query 当前定义范围全量测试
```

执行：

```text
1. AI resolve intent

2. project.inspect

3. project.preflight

4. module.inspect(query)

5. AI 决定执行 module.regression

6. Core Regression

7. 如果 FAIL：
      AI Failure Analyze
      Job BLOCKED / Recommend

8. 如果 PASS：
      feature.coverage(join)

9. 如果 Gap > 0：
      AI → candidate.generate

10. static validate

11. mutation validate

12. real trial

13. AI technical review

14. acceptance.inspect

15. WAITING_APPROVAL
```

人工完成 Review + Signed Approval 后：

```text
16. resume job

17. acceptance.preflight

18. promote

19. module.regression

20. post verify

21. completion evaluate

22. final report
```

---

# 27. MVP 最终报告

用户最终看到的不是几十个 JSON。

报告至少包含：

```text
Goal
Result
Current Module State
Regression Result
Coverage Result
Generated Candidate
Trial Result
Mutation Result
AI Findings
Human Approval State
Post Acceptance
Remaining Blockers
Recommended Next Action
```

例如：

```text
Query 当前定义范围：
PASS

JOIN Feature：
DEFINED_SCOPE_COMPLETE

Query Module：
MODULE_FULL_INCOMPLETE

原因：
Filter / Aggregate / Subquery 等尚未建模

数据库执行：
PASS

Evidence：
VALID

下一步：
可开始 Filter Feature 建模
```

---

# 28. MVP CLI

新增一个真正面向用户的入口：

```bash
xgtest ai run "执行查询模块当前定义范围内的全量测试"
```

查看：

```bash
xgtest ai status JOB_ID
```

恢复：

```bash
xgtest ai resume JOB_ID
```

底层旧 CLI：

```text
全部保留
```

作为：

```text
Debug / Expert Interface
```

AI CLI 才是新 MVP 的产品入口。

---

# 29. MVP Web

不要再开发大型页面。

只增加一个：

```text
/jobs
```

以及一个：

```text
/jobs/:id
```

显示：

```text
Goal
Current Action
Action History
AI Explanation
Evidence
Blocker
WAITING_APPROVAL
Final Report
```

已有 Coverage / Candidate 页面继续复用。

---

# 30. LLM 接口

第一版只需要一个很小的 AI 接口：

```python
class AITestAgent:
    def resolve_intent(text, project_state) -> TestIntent
    def choose_next_action(job_state) -> SemanticAction
    def analyze_failure(action_result, context) -> FailureAnalysis
    def technical_review(candidate_context) -> TechnicalReview
    def summarize(job_state) -> str
```

不要先做：

```text
Agent Team
Memory Agent
Reviewer Agent
Recovery Agent
Planner Agent
```

单 Agent 足够。

---

# 31. AI 输出必须 Schema Validate

任何 LLM 输出：

```text
Intent
Action
FailureAnalysis
TechnicalReview
```

都必须：

```text
Pydantic validate
```

失败：

```text
AI_OUTPUT_INVALID
```

不得直接执行自由文本。

---

# 32. Policy 第一版保持简单

AI 自动允许：

```text
inspect
regression
coverage
generate
static validate
mutation validate
trial
technical review
```

AI 禁止：

```text
human review
sign approval
promotion without approval
git merge
delete evidence
modify active cases directly
```

Promotion 本身可以由 AI 在：

```text
已有有效 Signed Approval
```

后调用。

也就是说：

```text
AI 可以执行 Promotion
但不能批准 Promotion
```

这个边界最合理。

---

# 33. Recovery 第一版只支持 4 类

不要一次做复杂 Recovery Engine。

只支持：

```text
RUNTIME_PROFILE_STALE
→ BLOCKED + 建议重建

CONTRACT_STALE
→ BLOCKED + 建议重建

EVIDENCE_STALE
→ 自动重跑对应 Trial / Mutation

WAITING_APPROVAL
→ Pause / Resume
```

其他：

```text
FAIL
```

交给 AI Failure Analyzer 解释。

---

# 34. 不要在 MVP 前实现 Filter

Filter 应作为：

```text
MVP 完成后的第一项架构验证
```

原因：

如果现在同时开发：

```text
AI Control
+
Filter
+
ActiveManifest
+
Remote Store
```

又会回到“大重构没有产品入口”的状态。

正确顺序：

```text
JOIN AI E2E
↓
可用 MVP
↓
Filter
```

---

# 35. MVP 后用 Filter 验证平台是否真的通用

MVP 完成后添加：

```text
query.filter
```

如果只需要新增：

```text
Model
Template
Plugin
MutationSpecs
```

而不需要修改：

```text
Orchestrator
Application Services
Acceptance Core
Job Model
AI Semantic API
```

说明 MVP 架构成功。

如果大量通用代码都要改：

```text
再修平台抽象
```

---

# 36. 推荐 Commit 顺序

从当前 `969f8be` 开始：

```text
01 chore: align running v14 api and review identities

02 acceptance: complete join human review and formal acceptance

03 refactor: add minimal application services for ai control

04 feat: add ai test intent and semantic action contracts

05 feat: add file-backed test job and event log

06 feat: add ai action planner and plan validator

07 feat: add sequential resumable orchestrator

08 feat: add ai failure analysis and technical review

09 feat: expose ai semantic control service

10 feat: add query full-test ai workflow

11 feat: add ai cli run status resume

12 feat: add minimal job web views

13 test: add ai-driven query full-test e2e

14 docs: freeze usable ai test mvp contract
```

MVP 结束。

然后：

```text
15 feat: add filter plugin
```

而不是继续 v15/v16 Evidence 架构重构。

---

# 37. 每个 Commit 的控制规则

每个 Commit：

```text
只解决一个核心问题
必须带 Framework Test
不得顺便重构 Evidence Core
不得顺便扩新 Feature
不得修改 Truth Logic，除非存在真实缺陷
```

如果需要改：

```text
Contract
Mutation
Promotion
```

必须明确回答：

```text
为什么这是 AI MVP 的 blocker？
```

回答不了：

```text
延后
```

---

# 38. MVP E2E Framework Tests

至少补以下测试：

```text
test_ai_intent_query_full_test

test_ai_cannot_execute_unknown_action

test_ai_cannot_write_human_review

test_ai_regression_failure_triggers_analysis

test_ai_coverage_gap_generates_candidate

test_ai_valid_candidate_runs_mutation_and_trial

test_ai_job_waits_for_human_approval

test_ai_job_resume_after_approval

test_ai_job_does_not_repeat_valid_trial_after_resume

test_ai_full_flow_produces_final_report

test_join_complete_does_not_mark_query_module_complete
```

---

# 39. 真实 Xugu MVP 验收场景

必须真正跑一次：

```text
xgtest ai run "执行查询模块当前定义范围内的全量测试"
```

要求：

```text
真实 Xugu
当前 Execution Contract
当前 Runtime Profile
当前 JOIN Active Cases
```

系统自动走到：

```text
WAITING_APPROVAL
```

人工完成 Approval 后：

```text
xgtest ai resume JOB_ID
```

直到：

```text
Post Acceptance
Final Report
```

整个过程中用户不需要手工拼底层命令。

这才算 MVP 真正可用。

---

# 40. MVP DoD

## 产品行为

- [ ] 自然语言启动 Test Job
- [ ] AI 自动 Inspect
- [ ] AI 自动选择 Semantic Action
- [ ] Active Regression 自动执行
- [ ] Coverage 自动分析
- [ ] Candidate 自动生成
- [ ] Static Validate 自动执行
- [ ] Mutation 自动执行
- [ ] Trial 自动执行
- [ ] AI Technical Review
- [ ] Failure Analyzer
- [ ] WAITING_APPROVAL
- [ ] Job Resume
- [ ] Promotion / Post Verify
- [ ] Final AI Report

## 确定性边界

- [ ] AI 不能修改 PASS/FAIL
- [ ] AI 不能修改 Coverage 数值
- [ ] AI 不能伪造 Evidence
- [ ] AI 不能伪造 Human Review
- [ ] AI 不能生成 Signed Approval
- [ ] 所有 Semantic Action Schema Validate

## 可用性

- [ ] 用户无需了解底层 xgtest 命令
- [ ] Job 中断后可继续
- [ ] Web 能看当前 Job
- [ ] CLI 能 run / status / resume
- [ ] 真实 Xugu E2E 跑通

达到以上标准：

```text
XG DB Test AI-Driven MVP = DONE
```

---

# 41. MVP 明确不要求

MVP 完成时允许以下仍未完成：

```text
GitHub CI
Branch Protection
Remote ArtifactStore
ActiveManifest
Multi-Agent
Distributed Scheduler
Full Query Features
Automatic Source Patch
Automatic Git Merge
24h Scheduler
MinIO
Filter / Aggregate
```

不要因为这些未完成，就继续把 MVP 判定为“不够好”。

---

# 42. MVP 后的第一阶段

MVP 一旦完成，下一阶段只做两件：

```text
1. Filter Plugin
2. Repair Candidate Loop
```

Filter 用来验证：

```text
平台是不是通用
```

Repair Loop 用来回到最初更长远的目标：

```text
Test Failure
↓
AI Diagnosis
↓
Patch Candidate
↓
Targeted Test
↓
Regression
↓
Human Merge
```

这时再扩：

```text
Aggregate
Subquery
Window
```

---

# 43. 最终产品方向不能改变

这个项目最终不是：

```text
Test Case Management System
```

也不是：

```text
Evidence Management System
```

而应该是：

> **AI 驱动的数据库测试执行与演进系统。**

Evidence、Contract、Promotion 都只是为了保证：

```text
AI 自动化仍然可信
```

不是产品本身。

未来所有新增架构都应该问一句：

> **它有没有让 AI 更可靠地完成测试目标？**

如果没有：

```text
不应该成为 MVP 前置任务
```

---

# 44. 最终路线

```text
当前 v14
│
├─ 对齐运行 API
├─ 完成 JOIN Formal Acceptance
│
▼
Minimal Application Service
│
▼
TestIntent + Semantic Actions
│
▼
File-backed TestJob
│
▼
AI Planner + Plan Validator
│
▼
Sequential Orchestrator
│
▼
Failure Analyzer
│
▼
AI Technical Review
│
▼
query.full_test
│
▼
CLI /jobs Minimal UI
│
▼
真实 Xugu E2E
│
▼
===========================
   AI-Driven Usable MVP
===========================
│
├─ Filter Plugin
├─ Repair Candidate Loop
├─ ActiveManifest
├─ Remote ArtifactStore
├─ CiEvidence
└─ 24h Autonomous Runner
```

---

# 45. 最重要的执行原则

从现在开始：

```text
不要继续为了“架构更完美”
延迟 AI E2E。
```

当前 Deterministic Core 已经足够强。

下一阶段评价每项工作的标准应该从：

```text
“底层是否还能更严？”
```

切换成：

```text
“它是否让用户更接近只说一句话，
AI 就能完成一次可信数据库测试？”
```

只有这个目标不变，项目才不会偏离最开始的 AI 驱动测试本心。
