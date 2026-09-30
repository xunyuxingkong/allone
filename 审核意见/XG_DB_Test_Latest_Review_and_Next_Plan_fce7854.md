# XG DB Test 最新审核意见与后续实施计划
## 基于 `origin/codex/join-model-v2`

> 当前分支 HEAD：`fce78543822423df9bfea9b898088627e7d032ee`  
> HEAD 提交：`docs: add latest fix and AI roadmap`  
> 当前实际代码基线：`6e044b7bbc49d75fa90124997bf0d27e28af08f9`  
> 代码提交：`feat: enforce mutation evidence and verify trial index`  
> 说明：`fce7854` 仅新增审核路线文档，没有代码变化，因此无需因该提交单独重跑测试；后续代码审核应以 `6e044b7` 为真实实现基线。

---

# 1. 本次审核结论

当前 JOIN Query Generation MVP 已从“功能闭环”进入“正式准入收口”阶段。

已完成：

```text
JOIN Model v2
Template v4
Generator v4
less_equal equality boundary
Mutation Validation
Mutation Evidence
Mutation Promotion Gate
Trial Artifact Consistency Verify
Runtime Profile Binding
Contract Set Binding
Raw Trial Rows
DB Version / Build Evidence
172 Framework Tests PASS
Frontend Build PASS
30 Active Query Regression PASS
21 Candidate Real Xugu Double Trial PASS
5 / 5 less_equal Mutation KILLED
16 / 16 Mutation NOT_APPLICABLE → SKIPPED
AI Technical Review
```

当前真正剩余：

```text
Human Review
→ Review Evidence
→ Promotion Preflight
→ Promotion
→ Post-Promotion Full Regression
→ Active Coverage 137 / 137
→ Final Acceptance
→ G0A Freeze Decision
```

因此不建议继续做 JOIN v5 / v6 / v7。JOIN 已经足够作为后续 Feature Plugin 的 Reference Implementation。

---

# 2. 最新代码质量评价

## 2.1 Mutation Evidence 已正式进入模型

当前已经新增：

```text
MutationCheck
MutationEvidence
```

并进入：

```text
QueryCaseInput
```

Candidate 可以正式记录：

```text
mutation_id
status
original_hash
mutated_hash
contract_set_id
runtime_profile_id
artifact_ref
artifact_sha256
```

这已经从“Mutation 旁路报告”升级为正式测试证据。

## 2.2 Promotion Gate 已绑定 Mutation

当前 `promote_candidate()` 已经校验：

```text
MutationEvidence 存在
semantic_hash 一致
contract_set_id 一致
runtime_profile_id 一致
artifact SHA256 一致
mutation artifact 内容一致
required mutation 状态满足 Gate
```

对于：

```text
predicate = less_equal
```

要求：

```text
replace_le_with_lt = KILLED
```

否则拒绝：

```text
CANDIDATE_MUTATION_GATE_FAILED
```

## 2.3 Review Hash 已绑定 Mutation Evidence

当前 `current_review_input_hash()` 已经包含：

```text
trial_run_hash
trial_artifact_sha256
mutation_evidence
coverage
```

Mutation Evidence 变化后，旧 Review 自动 stale，这个设计正确。

## 2.4 Trial Artifact 一致性问题已修复

新增：

```text
verify_trial_artifact_index()
```

会校验：

```text
Index
Candidate
Artifact
Artifact SHA256
Semantic Hash
Contract Set
Runtime Profile
DB Version
DB Build
Raw Rows
Double Run Result
Trial Result Hash
```

此前 Artifact / Index 不一致的 P0 已经关闭。

## 2.5 Mutation CLI 状态语义已改善

当前映射：

```text
KILLED                    → PASS
NOT_APPLICABLE            → SKIPPED
WEAK                      → FAIL
BASELINE_NOT_PASS         → FAIL
BASELINE_NONDETERMINISTIC → BLOCKED
INCONCLUSIVE              → BLOCKED
MUTATED_NONDETERMINISTIC  → BLOCKED
```

已经比较适合后续 `ActionResult` / Orchestrator 使用。

---

# 3. 当前仍存在的问题与可优化空间

## 3.1 最新 Roadmap 文档已经落后于代码

当前 HEAD `fce7854` 新增的：

```text
审核意见/XG_DB_Test_Latest_Fix_Issues_and_AI_Driven_Roadmap.md
```

仍把以下事项写成待修：

```text
Trial Artifact / Index 不一致
Mutation Evidence 尚未进入 Promotion Gate
Framework Tests 尚未重跑
```

但这些实际已在 `6e044b7` 完成。

这意味着：

```text
代码状态 != “最新”文档状态
```

这对未来 AI 驱动平台是重要风险。

### 建议

所有状态类文档以后增加：

```yaml
as_of_commit: 6e044b7...
generated_at: 2026-09-29
status: current
superseded_by: null
```

旧文档标：

```text
status: historical
```

或迁入：

```text
审核意见/history/
```

未来 AI 不能把 Markdown 当作项目状态 Truth Source。

---

## 3.2 Lifecycle 仍然严重 JOIN-specific

当前：

```text
generator/lifecycle.py
```

文件名是通用生命周期，但内部仍然知道：

```text
replace_le_with_lt
predicate == less_equal
QUERY.JOIN.
TEMPLATE_ID
TEMPLATE_VERSION
candidate_signature()
```

这意味着 Lifecycle 本质还是 JOIN-specific。

### 风险

扩：

```text
Filter
Aggregate
Subquery
Window
CTE
```

后很容易变成大量：

```python
if feature == "join":
    ...
elif feature == "filter":
    ...
```

这与 AI 驱动平台所需的通用能力不符。

### 建议

Lifecycle 只负责：

```text
Candidate State
Evidence Validity
Policy
Promotion
```

Feature-specific 逻辑交给：

```text
FeaturePlugin
```

例如：

```python
plugin.compute_candidate_id(...)
plugin.validate_assignment(...)
plugin.required_mutations(...)
plugin.validate_mutation_evidence(...)
plugin.validate_candidate(...)
```

---

## 3.3 Mutation Engine 仍然写死 JOIN

当前 `validate_candidate_mutation()` 核心就是：

```text
a.k <= b.k
→
a.k < b.k
```

MVP 可以接受，但现在 Mutation Evidence / Gate 已经是平台能力，执行逻辑也应该抽象成：

```text
MutationSpec
MutationPolicy
MutationExecutor
```

例如：

```yaml
feature: query.join

mutations:
  - id: replace_le_with_lt
    applicable_when:
      predicate: less_equal
    expectation:
      must_change_result: true
```

以后 Filter 可定义：

```text
= → <>
AND → OR
IS NULL → IS NOT NULL
```

Aggregate 可定义：

```text
SUM → COUNT
remove DISTINCT
HAVING > → >=
```

---

## 3.4 Mutation Gate 对非 Applicable 状态还可以更严格

当前非 `less_equal` 情况允许：

```text
NOT_APPLICABLE
或
KILLED
```

通过。

更严谨的规则应是：

```text
Applicable:
必须 KILLED

Not Applicable:
必须 NOT_APPLICABLE
```

避免错误 Evidence 被接受。

---

## 3.5 Mutation Evidence Authoring 仍过度信任调用方

当前：

```python
record_candidate_mutation_evidence(
    path,
    result: dict,
    ...
)
```

接受任意 dict。

它默认调用方已经正确执行 Validator。

AI Orchestrator 上线后，这种“靠调用顺序约定”的方式不够安全。

### 建议

新增严格模型：

```python
MutationValidationResult
```

并形成：

```text
Validator
→ MutationValidationResult
→ Evidence Writer
```

Evidence Writer 不接受任意 dict，同时验证：

```text
result.case_id == Candidate
mutation_id 属于 Feature Policy
status 与 Applicability 一致
```

---

## 3.6 Acceptance Verifier 还不是完整 Acceptance Gate

目前有：

```text
verify_trial_artifact_index()
```

但完整 Acceptance Package 还包括：

```text
Trial Index
Mutation Index
Runtime Profile
Candidate Evidence
Coverage Summary
Final Acceptance
Contract Descriptor
```

应该增加统一：

```text
verify_acceptance_package()
```

和 CLI：

```bash
xgtest acceptance verify
```

一次性验证全部证据。

未来 AI 只需要：

```text
acceptance.verify()
```

而不是读取多个文件自行判断。

---

## 3.7 Acceptance Verifier 统计可优化

当前任何一条失败时：

```text
verified_count = 0
```

不利于排查。

建议输出：

```text
verified_count
failed_count
failed_cases
```

例如：

```json
{
  "status": "FAIL",
  "verified_count": 20,
  "failed_count": 1
}
```

---

## 3.8 Raw Rows 与 result_sha256 建议再做一层一致性验证

既然保存了：

```text
result_rows
result_sha256
```

Acceptance Verify 应重新：

```text
result_rows
→ canonicalize
→ recompute result_sha256
```

确认 Stored Rows 与 Stored Hash 一致。

---

## 3.9 QueryCaseInput 职责已经过重

当前 `QueryCaseInput` 同时包含：

```text
metadata
steps
coverage
generation
oracle
validation_evidence
mutation_evidence
review_evidence
coverage_review
```

但 Runner 实际主要需要：

```text
metadata
steps
```

说明：

```text
Authoring / Governance Asset
Runtime Execution Input
```

正在混在一起。

### 建议拆分

```text
QueryCaseAsset
```

负责：

```text
Coverage
Generation
Oracle
Mutation
Review
Lifecycle
```

编译为：

```text
QueryCaseInput
```

只用于 Runner：

```text
QueryCaseAsset
↓ Compiler
QueryCaseInput
↓ Runner
```

未来 AI 操纵 Asset，而不是 Runtime DTO。

---

## 3.10 Human Review 目前仍是软门禁

当前：

```python
record_review(
    reviewer="...",
    review_reference="...",
    coverage_reference="..."
)
```

只要传字符串就能生成 Review Evidence。

Core 无法证明：

```text
reviewer 是真人
reference 是真实 PR
PR 确实 APPROVED
```

对于未来 AI 平台，这是重要安全边界。

### 建议拆分

```text
TechnicalReview
PromotionApproval
```

TechnicalReview 可来自：

```text
AI
Human
Static Analyzer
Mutation Validator
```

PromotionApproval 第一版必须：

```text
approval_type = human
```

最好绑定：

```text
GitHub PR Review
Reviewer Identity
Commit SHA
Review Timestamp
Immutable Review Reference
```

---

## 3.11 Contract Set Identity 仍然耦合过重

短时间已经出现：

```text
Runtime Profile v6
v8
v9
```

原因：

```text
Generator / Mutation / Lifecycle 变化
→ Contract Set ID 变化
→ Runtime Profile 失效
→ Profile 重建
→ Trial 重跑
```

这已经实际造成：

```text
Profile Churn
Evidence Churn
Artifact Churn
```

### 建议在 AI Control Plane 前拆分

至少：

```text
Runtime Contract ID
Core Comparison Contract ID
Generator Contract ID
Model Hash
Template Hash
Control Plane Version
```

Runtime Profile 不应因为新增一个 Mutation 就失效。

这项建议从普通 P1 提升为：

```text
AI 重构前置项
```

---

## 3.12 Artifact 全进 Git 已开始不可持续

当前只有 JOIN，就已经产生：

```text
Trial Artifact
Mutation Artifact
Runtime Evidence
Regression Evidence
Acceptance Evidence
Historical Evidence
```

以后 AI 自动跑 Filter / Aggregate / Window 后，Git 会迅速膨胀。

### 建议先抽象 ArtifactStore

```python
class ArtifactStore(Protocol):
    def put(...)
    def get(...)
    def verify(...)
```

第一版：

```text
LocalArtifactStore
```

后续：

```text
MinIOArtifactStore
S3ArtifactStore
```

Candidate 只保存：

```text
artifact_uri
sha256
```

---

## 3.13 Batch Promotion 缺少事务性

当前仍然逐条：

```text
candidate promote CASE_ID
```

如果：

```text
前 13 条成功
第 14 条失败
```

系统会进入部分 Active 状态。

### 当前至少应增加

```text
Promotion Preflight
```

一次验证：

```text
21 / 21 promotable
```

更进一步建议：

```text
PromotionPlan
```

包含：

```text
Candidate Set
Evidence Set
Expected Coverage
Plan Hash
```

Preflight 全 PASS 后再执行。

---

# 4. 与 AI 驱动设计目标的主要偏差

当前最明显的偏差：

```text
目标：
AI 操纵通用测试平台

当前：
未来 AI 会操纵一个高度 JOIN-specific 的测试生命周期
```

具体偏差：

```text
Feature-specific logic 仍在 Lifecycle
Mutation 仍硬编码 JOIN
Review Gate 仍依赖自由字符串
Runtime Contract 与 Generator 强耦合
QueryCaseInput 同时承担 Asset + Runtime DTO
Raw Artifact 仍放 Git
Promotion 仍逐条非事务
Markdown 仍承担过多当前状态描述
```

这些如果不先处理，Planner / Job / Orchestrator 后续会建立在错误边界上。

---

# 5. 最新 HEAD 对 AI 架构的实际提醒

当前 HEAD `fce7854` 新增的“Latest Roadmap”实际上描述了 `fc50de` 时期的一些旧问题，而这些问题在 `6e044b7` 已经修复。

这恰好说明：

> **Markdown 文档不能作为 AI 判断项目当前状态的 Truth Source。**

未来 AI 应读取结构化：

```text
ProjectState
ModuleState
AcceptanceState
CompletionReport
JobState
```

Markdown 只负责：

```text
设计说明
Review 意见
历史背景
```

而不是：

```text
当前事实
```

---

# 6. 当前剩余 JOIN 收口动作

JOIN 技术层已经足够。

现在只做：

```text
1. 更新或标记旧 Roadmap 文档状态
2. Human Review 21 Candidate
3. 记录 Review Evidence
4. Promotion Preflight
5. 正式 Promotion
6. Post-Promotion Full Query Regression
7. Active Pairwise 137 / 137
8. Final Acceptance PASS
9. G0A HOLD / FREEZE 最终决定
```

完成后：

```text
停止继续修改 JOIN Feature
```

---

# 7. 推荐新的后续开发顺序

建议调整为：

```text
STEP 1   完成 JOIN Human Review
STEP 2   Promotion Preflight
STEP 3   Promotion
STEP 4   Post-Promotion Full Regression
STEP 5   Active Coverage 137 / 137
STEP 6   Final Acceptance
STEP 7   G0A Decision

STEP 8   Contract Identity 分层
STEP 9   ArtifactStore 抽象
STEP 10  拆 QueryCaseAsset / QueryCaseInput
STEP 11  FeaturePlugin 化 JOIN
STEP 12  Application Service Layer
STEP 13  ModuleTestSpec
STEP 14  Project / Module Inspect
STEP 15  Unified Preflight
STEP 16  TestIntent
STEP 17  Deterministic Planner
STEP 18  ActionResult / ActionError
STEP 19  TestJob / Event Log
STEP 20  Orchestrator
STEP 21  Policy Engine
STEP 22  TechnicalReview / PromotionApproval 分离
STEP 23  Recovery Engine
STEP 24  Completion Evaluator
STEP 25  Agent Semantic API
STEP 26  query.full_test
STEP 27  Filter Plugin
STEP 28  Aggregate Plugin
```

---

# 8. AI Control Plane 前置重构 DoD

正式做 Planner / Orchestrator 前建议先满足：

```text
[ ] Contract Identity 分层完成
[ ] ArtifactStore Interface 完成
[ ] QueryCaseAsset / Runtime DTO 边界明确
[ ] JOIN 迁移到 FeaturePlugin
[ ] Mutation Policy 不再硬编码 JOIN
[ ] Human Approval Contract 明确
[ ] Acceptance Package 有统一 Verify
```

---

# 9. AI Control MVP 最终目标

第一条真实 AI Workflow：

```text
用户：
“执行查询模块当前定义范围内的全量测试”
```

系统：

```text
Project Inspect
↓
Module Inspect
↓
Preflight
↓
TestIntent
↓
Planner
↓
TestJob
↓
Regression
↓
Coverage
↓
Generate
↓
Mutation
↓
Trial
↓
Technical Review
↓
WAITING_APPROVAL
↓
Human Approval
↓
Promotion
↓
Full Regression
↓
Coverage Snapshot
↓
Acceptance
↓
Completion
```

最终 AI 只能报告 Core 返回的：

```text
DEFINED_SCOPE_COMPLETE
MODULE_FULL_INCOMPLETE
MODULE_FULL_COMPLETE
```

而不能自己判断“差不多完成”。

---

# 10. 本次审核最终结论

`6e044b7` 是一次有效的工程收口提交：

```text
Mutation Evidence
Promotion Gate
Trial Consistency
Framework Regression
```

均明显提升。

但它也暴露出下一阶段真正需要解决的问题：

```text
平台边界还没有真正通用化。
```

因此后续重点应从：

```text
继续增加 JOIN 能力
```

切换到：

```text
Contract Identity
Artifact Store
Asset / Runtime DTO
FeaturePlugin
Application Service
AI Control Plane
```

---

# 11. 长期原则

后续整个项目建议坚持：

```text
Markdown 不是 Truth Source
AI 不是 Truth Source
CLI 不是 Business Logic
Web 不是 Business Logic
```

真正 Truth 应来自：

```text
Deterministic Core
Structured State
Evidence
Contract
Policy
Completion Evaluator
```

最终达到：

```text
AI 可以决定下一步做什么，
但不能决定测试事实是什么。
```
