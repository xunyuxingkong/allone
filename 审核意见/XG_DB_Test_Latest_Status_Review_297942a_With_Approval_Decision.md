# XG DB Test 最新提交现状 + 未决审批决策综合审核

## 1. 当前远端基线

- 仓库：`xunyuxingkong/allone`
- 分支：`codex/join-model-v2`
- 当前 HEAD：`297942a3d56dce0224de2f1fb719a897d7519767`
- 最新提交：`feat: implement status review MVP follow-ups`
- 父提交：`8f9a6bbcaa7b7fce3dd8cdfd5fce86c2bf15702e`
- 当前提交：unsigned
- Branch Protection：OFF
- GitHub Commit Status：无
- GitHub Workflow Runs：无

本报告合并两部分：

1. `297942a` 最新代码增量审核；
2. 之前尚未完成的 **Signed Approval / Human Gate 决策**。

---

# 2. 总体判断

这一版继续沿着正确方向推进：

```text
Product Layer
+
AI Control
+
Deterministic Core
+
Human Governance Gate
```

相比上一版，产品真实性已经明显改善：

```text
多 Feature 假执行        → 已止血
Strategy 只展示不执行    → 已部分落地
Query Coverage 误导      → 已修
tested_scope 过早宣称    → 已修
```

但是现在仍有三类问题没有收口：

```text
A. 执行语义问题
B. 产品内容规模问题
C. 人工签名审批决策
```

这三类问题都应该在宣布 Product MVP DONE 之前解决。

---

# 3. 最新提交已经解决的问题

## 3.1 多 Feature 假执行问题已经止血

之前 UI 可以同时选择：

```text
JOIN
Filter
Aggregate
Subquery
Sort / Limit
```

但真实 Job 只使用第一个 Feature。

现在已经改为：

```text
一个 Mission 暂时只能选择一个 Feature
一个 Job 只拥有一个 Feature Scope
```

合同层直接限制：

```text
MISSION_FEATURE_SCOPE_MUST_BE_SINGLE_UNTIL_ORCHESTRATION
JOB_FEATURE_SCOPE_MUST_BE_SINGLE
```

前端也已经从 checkbox 改成 radio。

因此当前不会再出现：

```text
页面显示 5 个 Feature
↓
实际只执行 JOIN
```

这种 Product Truth 错误。

### 当前状态

```text
Multi-feature Mission：
尚未实现

Single-feature Mission：
行为已经诚实
```

---

# 4. Strategy 开始真正控制执行

当前 Mission 会将以下信息传入 TestIntent：

```text
strategy
data_scale
risk_focus
```

Strategy 已经真正影响 Coverage / Generation：

```text
SMOKE
→ Pairwise
→ Candidate Budget = 30

STANDARD
→ Pairwise

FULL
→ All Values

AI_EXPLORATORY
→ Pairwise Baseline
→ 当前仍只有 Exploration Briefing
```

这一点已经比上一版有本质进步。

---

# 5. data_scale / risk_focus 仍然没有真正生效

虽然 Mission 已经持久化：

```text
SMALL / MEDIUM / LARGE
risk_focus
```

但当前它们仍然没有实际改变：

```text
Fixture 数据规模
Candidate Selection
Generation Priority
Execution Budget
```

好的一点是，当前 Product View 已经明确返回：

```text
data_scale_applied = false
risk_focus_applied = false
```

这至少不会误导用户。

### 后续建议

等 Standard E2E 跑通后再实现：

```text
data_scale
→ Fixture Profile

risk_focus
→ Candidate Ranking / Exploration Priority
```

现在不建议为了这两个字段阻塞 MVP。

---

# 6. 五 Feature Coverage Dashboard 已经做对

当前新增：

```text
feature_coverages()
```

针对：

```text
JOIN
Filter
Aggregate
Subquery
Sort / Limit
```

逐个读取 Core Coverage。

前端 Dashboard 已经改成：

```text
五个 Feature 覆盖（Pairwise）
```

并展示：

```text
Requirements
Covered
Missing
Active Cases
Status
```

这是正确的产品方向。

现在：

```text
Feature Coverage
```

和：

```text
Query Module Full Completion
```

已经不再混淆。

---

# 7. Scope 状态语义已经修正

Mission View 目前区分：

```text
requested_scope
executed_scope
covered_scope
excluded_scope
unmodelled_scope
```

这是正确的。

尤其修掉了之前：

```text
用户刚选择 Feature
=
tested_scope
```

这种错误。

---

# 8. 当前新增 P0：Smoke Generation / Completion 语义存在风险

当前 Smoke：

```text
coverage_strategy = pairwise
candidate_budget = 30
```

但 Candidate Generator 选择 Gap 时仍主要基于：

```text
Active Cases
```

并且 Controller 的后续逻辑仍然以：

```text
provisional_missing > 0
```

判断是否继续：

```text
candidate.generate
```

这存在一个风险：

```text
第一次生成 30 条
↓
处理完 30 条
↓
Pairwise Coverage 仍有缺口
↓
Controller 再次允许 candidate.generate
↓
Generator 又从 Active Case Gap 选择
↓
可能再次命中相同前 30 条
```

最终可能出现：

```text
Smoke 模式重复 generate
```

甚至循环。

---

# 9. Smoke 应该拥有独立 Completion Definition

Smoke 的目标不应该是：

```text
Pairwise Coverage = 100%
```

否则它和 Standard 的本质区别会消失。

建议定义：

```text
SMOKE_COMPLETE =
    regression_pass
    AND smoke_budget_consumed_or_no_gap
    AND generated_cases_valid
    AND no_blocking_failure
```

而：

```text
STANDARD_COMPLETE =
    pairwise_defined_scope_complete

FULL_COMPLETE =
    all_values_defined_scope_complete
```

AI_EXPLORATORY 则应：

```text
baseline_complete
+
exploration_round_complete
```

---

# 10. 建议增加显式 Generation Progress

Job / Mission 中增加：

```text
generation_policy:
  strategy
  budget
  generated_total
  remaining_budget
  coverage_target
```

例如：

```text
SMOKE

Budget:            30
Generated:         30
Remaining Budget:   0
Pairwise Missing:  48

Result:
SMOKE_DEFINED_SCOPE_COMPLETE
```

注意：

```text
Smoke Complete
```

不等于：

```text
Pairwise Complete
```

这样产品语义才清楚。

---

# 11. 当前 Framework Test 可能存在一个小冲突

现在合同里同时存在：

```python
features: list[str] = Field(min_length=1, max_length=1)
```

和：

```python
if len(values) != 1:
    raise ValueError(
        "MISSION_FEATURE_SCOPE_MUST_BE_SINGLE_UNTIL_ORCHESTRATION"
    )
```

但测试中仍存在：

```text
features = ["join", "join"]
expect MISSION_FEATURE_DUPLICATE
```

Pydantic 很可能先命中：

```text
max_length = 1
```

而不是业务 validator。

结果可能无法得到：

```text
MISSION_FEATURE_DUPLICATE
```

### 建议

只保留业务层验证：

```python
features: list[str] = Field(min_length=1)
```

然后：

```text
len != 1
→ MISSION_FEATURE_SCOPE_MUST_BE_SINGLE_UNTIL_ORCHESTRATION
```

因为当前本来就不允许多 Feature，所以 Duplicate Code 已经没有太大意义。

---

# 12. covered_scope 与 COMPLETED 可能存在状态不一致

当前 Mission 判断：

```text
covered_scope
```

依赖 Job 历史中真实存在：

```text
feature.coverage
PASS
active_missing == 0
```

但 Controller 在：

```text
module.regression PASS
```

后内部可能直接调用：

```text
module.inspect_coverage()
```

如果：

```text
active_missing == 0
AND
no candidates
```

Controller 可以直接把 Job 标成：

```text
COMPLETED
```

但没有记录一条独立：

```text
feature.coverage ActionResult
```

因此理论上会出现：

```text
Mission State = COMPLETED
covered_scope = []
```

### 建议

Completion 之前显式记录：

```text
feature.coverage
```

不要让 Product Layer 自己再重算。

这样：

```text
Job Event
Mission View
Evidence
```

看到的是同一个事实。

---

# 13. 测试用例规模仍然是最大产品短板之一

目前：

```text
Test Space Model
```

已经明显变丰富。

但：

```text
正式 Active Case Pack
```

还没有达到真正 Query Product MVP 应有的体量。

建议 Standard 目标：

```text
JOIN            40~60
Filter          40~70
Aggregate       30~60
Subquery        30~60
Sort / Limit    20~40
---------------------
Total          180~300 Cases
```

SQL Execution：

```text
500~1000
```

目前不要再扩：

```text
Window
CTE
Set Operation
```

先把已有 5 个 Feature 的内容做厚。

---

# 14. AI Exploratory 当前仍只是 Briefing

当前 AI Exploratory 能做到：

```text
Read Coverage Gap
Read Failure
Risk Classification
Suggestion
```

但还没有：

```text
AI Select Gap
↓
Generate Limited Candidates
↓
Execute
↓
Observe Result
↓
Next Round
```

所以现在应准确称为：

```text
AI Exploratory Briefing v1
```

而不是完整 AI Exploratory Testing。

---

# 15. 当前尚未完成的关键决策：Signed Approval / Human Gate

这是之前已经遇到、但至今没有完成的一个独立决策。

真实流程会卡在：

```text
acceptance.preflight
→ WAITING_APPROVAL
→ SIGNED_APPROVAL_NOT_CONFIGURED
```

这里不是 Bug。

这是当前 Governance Design 的刻意 Gate。

---

# 16. Signed Approval Gate 到底在保证什么

当前设计要求最终 Promotion 前必须存在：

```text
真实 Human Review
+
真实 Signer
+
真实 Approval File
+
真实 Cryptographic Verification
```

也就是说：

```text
AI Technical Review
```

不能替代：

```text
Human Approval
```

AI 可以：

```text
生成 Case
执行 Trial
分析 Failure
做 Technical Review
建议 Promotion
```

但不能：

```text
给自己签名
自己生成合法 Human Approval
自己绕过 Promotion Gate
```

这是目前最重要的一条 Human-in-the-loop 安全边界。

---

# 17. 当前这一步必须做一个明确决策

目前有三个可选方向。

## 方案 A：继续把 Human Approval 作为设计终点

也就是：

```text
acceptance.preflight
→ WAITING_APPROVAL
```

作为一个正常终态。

如果用户不提供签名材料：

```text
Workflow 停止
```

这是最严格的治理模式。

优点：

```text
最安全
治理语义最清楚
AI 永远不能自行 Promotion
```

缺点：

```text
每次完整 E2E 都需要真实审批材料
```

---

## 方案 B：建立正式的本地“真实签名”工具

这是我最推荐的方案。

不是绕过 Gate。

而是提供正式 Operator Workflow：

```text
xgtest approval signer-init
xgtest approval prepare
xgtest approval sign
xgtest approval verify
```

或同等级的工具链。

核心原则：

```text
私钥只在人工 Operator 手里
AI 无法读取私钥
AI 无法调用 sign
签名材料来自人工动作
```

系统只负责：

```text
生成待签名 Approval Payload
验证签名
验证 Signer 是否在 Allowed Signers
检查 Revocation
```

### 推荐原因

这样既保留：

```text
Human Gate
```

又不会让每次测试人员自己手写：

```text
JSON
Hash
Signature
Signer Registry
```

对 MVP 使用体验会好很多。

---

# 18. 推荐的人机分工

建议明确写进架构：

```text
AI：
    负责准备“待批准内容”
    负责解释为什么建议晋升
    负责展示 Evidence
    不能签名

Human：
    查看 Technical Review / Evidence
    点击“批准并签名”
    本机签名器完成 cryptographic signing

Core：
    校验 Approval Payload
    校验 Signature
    校验 Allowed Signer
    校验 Revocation
    决定 Promotion 是否允许
```

这才是：

```text
AI Driven
+
Human Governed
+
Core Verified
```

---

# 19. 强烈不建议的方案

不要做：

```text
development_mode = true
→ 自动跳过签名
```

也不要做：

```text
AI 自动生成 private key
AI 自动写 XGTEST_APPROVAL
AI 自动签名
```

更不要：

```text
如果没有 signer 就默认 PASS
```

否则此前建立的：

```text
TechnicalReview
HumanReview
PromotionApproval
```

三层分离会失去意义。

---

# 20. 建议将 Approval 做成前端明确步骤

现在用户如果看到：

```text
SIGNED_APPROVAL_NOT_CONFIGURED
```

体验比较工程化。

建议 Product Layer 直接展示：

```text
AI 测试阶段
━━━━━━━━━━━━━━━━
✓ Regression
✓ Coverage
✓ Mutation
✓ Trial
✓ AI Technical Review

人工审批
━━━━━━━━━━━━━━━━
● 等待项目负责人批准

当前状态：
尚未配置签名人

[查看待审批内容]
[人工批准并签名]
```

而不是只显示：

```text
WAITING_APPROVAL
SIGNED_APPROVAL_NOT_CONFIGURED
```

---

# 21. Approval 页面应该展示什么

Human Approval 页面至少展示：

```text
Mission
Feature
Build
Runtime Profile
Execution Contract
Candidate Count
Coverage Before
Coverage After Promotion
Regression Result
Mutation Result
Trial Result
AI Technical Review
Known Risks
Untested Scope
Promotion Plan ID
Manifest Hash
```

最后人只做一个清晰决策：

```text
[拒绝]
[批准并签名]
```

不要让人工审批变成自己去理解几十个 Artifact Path。

---

# 22. MVP 阶段建议的 Approval 实现

我建议 Product MVP 采用：

```text
Local Human Signer
```

特点：

```text
单机
单项目负责人
真实非对称签名
私钥不进入项目仓库
Allowed Signer 显式登记
Approval 是独立文件
```

先不做：

```text
企业 CA
多人会签
RBAC
审批中心
Remote KMS
HSM
```

这些都可以 Post-MVP。

---

# 23. Signed Approval 应该成为 Product MVP 的正式 DoD

Product MVP 不能只做到：

```text
WAITING_APPROVAL
```

而从未跑通过：

```text
Human Sign
↓
Preflight PASS
↓
Promotion
↓
Post Regression
↓
Post Acceptance
```

至少必须真实跑通一次。

否则：

```text
Human Gate
```

只是代码里存在，而不是经过验证的真实流程。

---

# 24. 当前 Runtime Profile 也需要重新生成

随着 Registry / Execution Schema 变化，当前 Contract 已经更新。

在真实 Xugu E2E 前必须：

```text
重新 Probe
↓
重新生成 Runtime Profile
↓
确认 Contract Set ID
↓
确认 Xugu Build
```

否则：

```text
RUNTIME_PROFILE_STALE
```

是正常结果。

---

# 25. 当前 GitHub Gate 仍未建立

当前远端仍然：

```text
Branch Protection OFF
Commit Status none
Workflow Runs none
Commit unsigned
```

这不阻塞当前 Product MVP。

但进入：

```text
24h Autonomous Testing
Auto Repair
Auto PR
```

之前必须补：

```text
CI
Required Checks
Branch Protection
```

---

# 26. 当前项目综合评价

| 维度 | 当前 |
|---|---:|
| Deterministic Core | 9.0 / 10 |
| Evidence / Acceptance | 9.0 / 10 |
| AI Control | 8.6 / 10 |
| Test Product Layer | 8.0 / 10 |
| 前端认知体验 | 7.6 / 10 |
| Feature 丰富度 | 8.2 / 10 |
| Strategy 真实性 | 7.0 / 10 |
| Active Case 内容规模 | 5.0 / 10 |
| AI Exploratory | 5.5 / 10 |
| Human Approval UX | 4.5 / 10 |
| Real Xugu E2E | 未完成 |

Product MVP：

```text
约 86~89%
```

---

# 27. 更新后的优先级

## P0-1 Smoke Completion

修：

```text
Smoke Budget
Smoke Completion
Repeated Candidate Generation
```

## P0-2 Framework Validation

修：

```text
features max_length
vs
business validator
vs
duplicate test
```

## P0-3 Human Approval 决策正式落地

决定：

```text
保留真实 Human Gate
+
增加 Local Signer UX
```

不要绕过。

## P1-1 covered_scope 状态一致性

确保：

```text
COMPLETED
```

之前有明确：

```text
feature.coverage ActionResult
```

## P1-2 Active Case Pack

达到：

```text
180~300 Standard Cases
```

## P1-3 Runtime Profile Refresh

基于当前 Contract 重新 Probe。

## P1-4 Approval Product UI

把：

```text
WAITING_APPROVAL
```

变成清楚的人类审批页面。

---

# 28. 下一阶段建议 Commit 顺序

```text
01 fix: define smoke generation completion semantics

02 test: align single-feature mission validation errors

03 fix: persist explicit feature coverage before job completion

04 feat: add approval payload preparation service

05 feat: add local human signer initialization workflow

06 feat: add operator-only approval signing command

07 feat: add signed approval verification status view

08 feat: add approval page and waiting-approval UX

09 test: add real human-gated promotion e2e

10 chore: refresh runtime profile for current contract

11 feat: expand standard active case pack

12 test: run real five-feature Xugu standard e2e
```

---

# 29. 真实 MVP E2E 应该怎么跑

当前最终应该跑通：

```text
Create Mission
↓
Select Feature
↓
Project Preflight
↓
Regression
↓
Coverage
↓
Candidate Generation
↓
Static Validation
↓
Mutation
↓
Trial
↓
AI Technical Review
↓
WAITING_APPROVAL
↓
Human Review
↓
真实签名
↓
acceptance.preflight PASS
↓
Promotion
↓
Post Regression
↓
Post Verify
↓
Final Report
```

至少五个 Feature 分别跑通一次：

```text
JOIN
Filter
Aggregate
Subquery
Sort / Limit
```

然后再做：

```text
Multi-feature Mission Orchestration
```

---

# 30. Product MVP 最终 DoD

只有下面全部满足，才建议宣布：

```text
XG DB Test AI-Driven Product MVP v1 = DONE
```

## 产品

- [ ] 测试目的明确
- [ ] 测试范围明确
- [ ] Tested / Untested Scope 明确
- [ ] Feature Coverage 可读
- [ ] Case 语义可读
- [ ] AI 分析可读
- [ ] WAITING_APPROVAL 有清楚产品页面

## 测试能力

- [ ] JOIN
- [ ] Filter
- [ ] Aggregate
- [ ] Subquery
- [ ] Sort / Limit
- [ ] Standard Active Cases 180~300
- [ ] SQL Execution 500~1000

## Strategy

- [ ] Smoke Completion 正确
- [ ] Standard Pairwise 正确
- [ ] Full All Values 正确
- [ ] AI Exploratory 至少完成一轮受控补测

## Governance

- [ ] AI 不能签 Human Approval
- [ ] 真实 Signer 可初始化
- [ ] 真实 Approval 可签名
- [ ] Allowed Signer 校验通过
- [ ] Promotion Gate 真实跑通
- [ ] Post Acceptance 真实跑通

## Runtime

- [ ] 当前 Contract 对应 Runtime Profile
- [ ] Real Xugu E2E 完整跑通

---

# 31. 最终建议

之前尚未处理的：

```text
SIGNED_APPROVAL_NOT_CONFIGURED
```

必须正式纳入项目路线。

它不是一个“小配置问题”。

它代表整个项目目前最后一条最重要的人类治理边界：

```text
AI 自动执行
≠
AI 自动批准
```

我的建议不是删除这个 Gate，而是：

> **保留真实签名审批，同时把签名过程产品化。**

让使用者体验变成：

```text
AI 已完成测试
↓
系统展示完整证据和建议
↓
负责人点击“批准并签名”
↓
Core 验证签名
↓
Promotion
```

而不是：

```text
AI 已经全部跑完
↓
用户自己研究 XGTEST_APPROVAL / XGTEST_ALLOWED_SIGNERS / JSON / 签名格式
```

这是当前产品从“工程系统”走向“可用测试产品”必须补上的一块。

---

# 32. 当前最应该做的事情

现在不要继续增加：

```text
Window
CTE
Set Operation
Remote ArtifactStore
Multi-Agent
复杂治理层
```

近期主线应固定为：

```text
Smoke Completion
↓
Validation Fix
↓
Coverage State Fix
↓
Human Approval Productization
↓
Runtime Profile Refresh
↓
Active Case Expansion
↓
Real Xugu E2E
↓
AI Exploratory Loop
↓
============================
AI-Driven Product MVP v1
============================
```

这样才能同时保证：

```text
用户体验
+
测试内容
+
AI 自动化
+
Human Governance
+
Core Truth
```

五个方向不会再失衡。
