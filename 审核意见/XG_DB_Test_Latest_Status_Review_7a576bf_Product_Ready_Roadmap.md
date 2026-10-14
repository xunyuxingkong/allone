# XG DB Test 最新提交审核：7a576bf

## 1. 当前基线

- 仓库：`xunyuxingkong/allone`
- 分支：`codex/join-model-v2`
- HEAD：`7a576bf1797a8e340fb943e2ab29256a7031da77`
- 提交：`feat: advance approval and candidate workflow`
- 父提交：`f1687021967712fca0573d099881a5728c2a243d`
- Branch Protection：OFF
- Commit：unsigned
- GitHub Commit Status：0
- GitHub Workflow Runs：0

本次只有 1 个增量提交，但内容较多：补 Job-owned Candidate Scope、冻结 Strategy Completion、改进 Approval Current Status，并新增 110 个 Query Candidate YAML。

## 2. 总体判断

上一轮最重要的两个问题已经得到实质修复：

```text
Promotion 后 Smoke Completion 反向失效
Smoke Job 被历史 Candidate backlog 污染
```

当前 Product MVP 可评估为约 91~93%。

不过本轮发现两个新的高优先级问题：

```text
P0  Trial Index Verifier 仍按整个 Candidate Root 校验，和 Job-owned Candidate Scope 不一致
P0  signer-init 强制生成无口令私钥，与“人工真实签名”设计及 CLI 文案不一致
```

因此暂不建议冻结 Product MVP v1。

---

## 3. 已解决：Job-owned Candidate Set

`TestJob` 新增：

```text
candidate_scope_ids
strategy_completion
```

Controller 创建 ServiceContext 时把 `candidate_scope_ids` 带入 Application Service。

后续：

```text
Candidate readiness
Coverage provisional calculation
Acceptance freeze
Manifest candidate members
```

都开始按 Job 自己的 Candidate Set 工作。

Candidate Generator 还支持“adopt existing deterministic candidate”：共享 Candidate Root 中已有但不属于当前 Job 的候选，不会自动算入当前 Job Coverage；如果它恰好是当前 Gap 的确定性 Candidate，生成动作可以显式返回该已有文件并把它纳入本 Job。

这个设计方向正确，比“每次任务人工清空 candidates 目录”可靠很多。

---

## 4. 已解决：Strategy Completion 在 Promotion 后保留

`strategy_completion` 现在会在 `acceptance.inspect` 时冻结到 Job，并随着 Job checkpoint 持久化。

Mission View 读取 Smoke Completion 时：

```text
如果存在 frozen strategy_completion
→ 不再依赖 Candidate 文件仍然存在
```

所以 Candidate Promotion 后从 candidate root 移到 active root，不会再导致 Smoke Completion 自动反向变成 false。

同时历史 BLOCKED/FAIL 的判断开始使用每个 `(action, case_id)` 的 latest effective result，修复“网络曾经失败一次，后续恢复后永远不能完成”的问题。

---

## 5. 已解决：Approval Current / Stale 状态

Mission Approval View 不再只看历史 `acceptance.preflight == PASS`。

现在区分：

```text
APPROVED_CURRENT
APPROVED_STALE
WAITING_APPROVAL
INVALID
NOT_READY
```

并会用当前：

```text
Approval
Manifest
Promotion Plan
Allowed Signers
Revocation
```

进行只读复核。

这修掉了之前“昨天验签通过，今天 Approval 已过期/变更，但页面仍显示 APPROVED”的 Product Truth 问题。

---

## 6. 已解决：Operator Approval 真正端到端测试

新增测试已经真正串起：

```text
initialize_local_signer
→ prepare_approval_payload
→ sign_approval_payload
→ verify_operator_approval
```

并覆盖：

```text
Revocation
Stale Plan
Expired Approval
Wrong / Untrusted Key
```

这个补充很有价值。

---

## 7. 测试内容规模明显增加

本次新增 110 个 Candidate YAML：

```text
Aggregate    27
Filter       44
Subquery     27
Sort/Limit   12
----------------
Total       110
```

这是本轮很重要的产品进展。

但这些文件位于 `candidates/query/*`，抽查的 Filter Candidate 当前状态为：

```text
status: draft
```

并且目前只有 Static Validation Evidence，还不是正式 Active Regression Case。

所以应准确表述为：

```text
Candidate Test Content 大幅扩展
≠
Active Case Pack 已经扩展完成
```

后续仍需真实：

```text
Mutation
Trial
AI Technical Review
Human Review
Signed Approval
Promotion
```

之后才能计入 Active Case Library。

---

## 8. 新 P0：Trial Index Verifier 仍然不是 Job-scoped

这是本轮最重要的新问题。

`AcceptanceService.freeze()` 现在只为：

```text
ctx.candidate_scope_ids
```

生成 Trial Index / Mutation Index / Coverage Summary / Manifest。

这一步是对的。

但是 `verify_pre_promotion_package()` 调用：

```text
verify_trial_artifact_index(..., scope=scope)
```

而 `verify_trial_artifact_index()` 内部仍会扫描：

```text
scope.asset_paths(candidate_root)
```

并把 **整个 Feature Candidate Root 中所有 status=review 的 Candidate** 当作 `expected_ids`。

因此场景：

```text
Candidate Root
├─ A  当前 Job selected / review
├─ B  当前 Job selected / review
└─ C  上一个 Job 遗留 / review
```

当前 Job Freeze 的 Trial Index 只有：

```text
A, B
```

但 Trial Verifier 会期待：

```text
A, B, C
```

最终产生：

```text
CANDIDATE_MISSING_FROM_INDEX
```

导致 Package Verification BLOCKED。

这说明 Job-owned Candidate Scope 目前只贯通了：

```text
Generation
Readiness
Coverage
Freeze
Manifest
```

还没有贯通 Trial Evidence Verifier。

### 修复建议

给：

```text
verify_trial_artifact_index()
```

增加：

```text
candidate_ids: Iterable[str] | None
```

Job Acceptance 路径必须把 Manifest / Job Selected IDs 传进去。

Legacy CLI 不传时，可以继续保持“验证整个 Candidate Scope”的旧行为。

优先级：P0。

---

## 9. 新 P0：Local Signer 当前强制生成无口令私钥

最新 `initialize_local_signer()` 实际执行：

```text
ssh-keygen -t ed25519 -N "" ...
```

也就是：

```text
强制空 passphrase
```

但 CLI 帮助仍写：

```text
ssh-keygen prompts for a passphrase
```

两者直接矛盾。

更重要的是，这会削弱 Human Gate 的实际密钥保护：私钥即使放在项目外，只要文件被读取就能直接签名，不再需要负责人输入 passphrase。

### 建议

生产默认：

```text
交互式设置 passphrase
```

测试模式才允许：

```text
passphrase=""
```

可以设计：

```text
initialize_local_signer(..., passphrase=None)
```

语义：

```text
None  → 交互式，生产默认
""    → 仅测试显式使用
```

或者把测试 key generation 独立放在 test helper，不改变生产 signer-init 行为。

优先级：P0 Human Governance / Security。

---

## 10. P1：Strategy Completion 还是松散 dict

`strategy_completion` 当前类型：

```text
dict[str, Any] | None
```

虽然已经进入 Durable Job checkpoint，但还不是严格版本化 Contract，也没有自己的 hash。

建议下一步变成：

```text
StrategyCompletionEvidence
```

字段至少：

```text
schema_version
strategy
candidate_scope_ids
regression_result_identity
coverage_snapshot
budget
completion_reason
completed_at
completion_hash
```

如果它要长期承担“Smoke 已完成”的 Product Truth，最好最终绑定进 Acceptance Manifest 或 Final Report。

---

## 11. P1：Final Report 还没带新的 Job Truth

`TestJob` 已经新增：

```text
candidate_scope_ids
strategy_completion
```

但 `final-report.json` 当前仍主要写：

```text
results
blockers
abandonment
agent_explanation
```

建议把新的两项也写入 Final Report，让最终报告自包含，不必依赖 state.json 才知道：

```text
这个 Job 到底拥有哪批 Candidate
策略为什么算完成
```

---

## 12. Runtime Contract

当前 Execution Contract Set ID 仍是：

```text
663374ea6b647f4f7f27a706bc8d1a3e2c6a0c725052e8cb3c7bb10ca6f7dba6
```

说明这轮主要变化仍在 Product / Control / Governance / Generator，而没有改变 Execution Projection。

真实 Xugu E2E 前仍要确认：

```text
runtime-profile-v15
真实 Probe Evidence
DB Build
Contract Set ID
```

完全匹配。

---

## 13. GitHub 工程 Gate 仍为空

当前远端：

```text
Branch Protection: OFF
Commit unsigned
Commit Statuses: 0
Workflow Runs: 0
```

因此这轮新测试是否整体 PASS，GitHub 没有独立 CI 证据。

---

## 14. 当前评分

| 维度 | 当前 |
|---|---:|
| Deterministic Core | 9.0 |
| Evidence / Acceptance | 9.1 |
| AI Control | 8.8 |
| Product Layer | 8.6 |
| Frontend UX | 8.1 |
| Human Approval UX | 8.2 |
| Candidate Ownership | 8.0 |
| Strategy Semantics | 8.3 |
| Test Content | 7.0 |
| Active Case Scale | 5.5 |
| AI Exploratory | 5.5 |
| Real Xugu E2E | 未完成 |

Product MVP：约 91~93%。

---

## 15. 下一提交建议

```text
P0-1 让 Trial Artifact Verifier 支持 Job candidate_scope_ids
P0-2 恢复 signer-init 的真实 passphrase 保护
P1-1 StrategyCompletionEvidence 严格模型化 / hash
P1-2 final-report 写入 candidate_scope_ids + strategy_completion
P1-3 110 个 Draft Candidate 逐步做 Trial/Mutation/Review/Promotion
P1-4 真实 runtime-profile-v15 Probe
P1-5 Real Xugu Smoke / Standard E2E
```

暂时不要继续新增第六个 Feature。

---

## 16. 最终判断

`7a576bf` 是一笔明显向前的提交。

上一轮提出的：

```text
Strategy Completion
Job-owned Candidate Set
Approval Current Validity
Operator Signing E2E
```

大部分都已经真正落地，而且测试内容一次新增 110 个 Candidate，项目已经不再只是“框架丰富、内容很少”。

现在最关键的不是继续加功能，而是把 Candidate Ownership **贯穿到最底层 Evidence Verifier**，同时把真实 Human Signer 的私钥保护补回来。

这两个 P0 修掉后，就可以集中进入：

```text
Candidate Evidence Completion
→ Human Sign
→ Promotion
→ Post Regression
→ Post Acceptance
→ Real Xugu Product E2E
```

---

# 17. 面向测试人员使用的“产品级”要求

前面的审核主要关注代码正确性、Evidence、Candidate Ownership、Approval、Strategy 和真实 E2E。

但如果目标不是“技术 MVP”，而是：

> **真正交给测试人员长期使用**

那么评价标准必须进一步升级。

当前项目已经具备较强的：

```text
Deterministic Core
Evidence / Acceptance
AI Control
Product Mission
Human Approval
```

但距离测试人员日常使用，还需要补齐：

```text
Product Truth
Test Content
Multi-feature Experience
Failure Analysis
Reporting
Environment Setup
Team Workflow
AI Exploratory
```

因此：

```text
AI-Driven MVP 成熟度：
约 91~93%

面向内部测试人员的产品化成熟度：
约 70~75%
```

这里的差距不是“大架构没做好”，而是：

```text
测试人员能不能理解
测试人员能不能直接操作
测试内容够不够
失败是否容易分析
报告是否能直接交付
长期使用是否稳定
```

---

# 18. P0：Product Truth——页面事实必须与 Core 执行事实完全一致

产品级系统最不能接受的是：

```text
UI 说 A
Core 实际执行 B
```

当前最典型的是 Candidate Scope。

虽然：

```text
TestJob.candidate_scope_ids
```

已经建立，

并且：

```text
Readiness
Coverage
Acceptance Freeze
Manifest
```

已经开始使用 Job-owned Candidate Set，

但 Trial Evidence Verifier 仍可能从整个 Feature Candidate Root 推导 expected cases。

因此 Product Ready 前必须实现：

```text
Mission
  ↓
Job
  ↓
Candidate Scope
  ↓
Static Validation
  ↓
Mutation
  ↓
Trial
  ↓
AI Review
  ↓
Coverage
  ↓
Manifest
  ↓
Human Approval
  ↓
Promotion
  ↓
Post Verify
```

全链路都使用同一批：

```text
candidate_scope_ids
```

## Product Ready DoD

- [ ] Candidate Scope 从 Job 创建到 Post Acceptance 全链路一致
- [ ] Trial Verifier 支持显式 candidate_ids
- [ ] Mutation Index 只验证当前 Job Scope
- [ ] Manifest 只冻结当前 Job Scope
- [ ] Promotion 只晋升当前 Job Scope
- [ ] 其他 Mission 遗留 Candidate 不影响当前任务
- [ ] 不依赖人工清理 candidates 目录

---

# 19. P0：真实 Human Signer 必须具备生产级最小安全性

当前 Human Approval 设计原则是正确的：

```text
AI 不能签名
Human 真实签名
Core 验证
```

但是 Local Signer 的生产路径必须与测试路径严格区分。

Product Ready 要求：

```text
生产 signer-init
→ 默认要求 passphrase

测试 signer
→ 才允许空 passphrase
```

不能为了：

```text
自动化 framework test
```

而让正式 Operator Private Key 默认：

```text
-N ""
```

## 推荐接口

```text
initialize_local_signer(
    ...,
    passphrase=None
)
```

语义：

```text
None
→ 生产默认
→ 交互式输入 passphrase

""
→ 仅 test helper 显式使用
```

## Product Ready DoD

- [ ] 私钥永远不进入 Project Root
- [ ] 私钥默认带 passphrase
- [ ] Web 不上传私钥
- [ ] MCP / AI 无 sign 权限
- [ ] Allowed Signers 只存公钥
- [ ] Approval 可撤销
- [ ] Approval 有有效期
- [ ] Manifest / Plan 变化会使签名失效
- [ ] UI 可显示 APPROVED_CURRENT / APPROVED_STALE

---

# 20. P0：真实 Xugu E2E 必须成为正式 Release Gate

目前 Framework / Synthetic Workflow 已经比较成熟。

但产品是否可用，最终必须由：

```text
真实 Xugu
```

证明。

不能只证明：

```text
Controller
Job
MCP
Fake DB
Schema
Evidence
```

而必须至少真实跑通：

```text
Create Mission
↓
Preflight
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
Human Review
↓
Signed Approval
↓
Promotion
↓
Post Regression
↓
Post Acceptance
↓
Final Report
```

## Product Ready DoD

至少：

```text
JOIN
Filter
Aggregate
Subquery
Sort / Limit
```

五个 Feature 分别真实跑通一次。

再额外跑：

```text
Smoke
Standard
```

两种 Strategy。

---

# 21. P0：正式 Active Case Library 必须达到产品级规模

当前测试内容已经比之前丰富很多。

最新提交新增约：

```text
110 Candidate YAML
```

这是很大进步。

但 Product Ready 不能把：

```text
Candidate
```

直接当成：

```text
正式 Test Case Asset
```

真正可交给测试人员使用的正式资产必须经过：

```text
Static Validation
Mutation
Trial
AI Technical Review
Human Review
Signed Approval
Promotion
Regression
```

然后成为：

```text
Active Case
```

## 第一版产品规模目标

```text
JOIN             40~60
Filter           40~70
Aggregate        30~60
Subquery         30~60
Sort / Limit     20~40
-----------------------
Total           180~300
```

Standard Mission：

```text
Coverage Requirements   350~500
Executable Cases        180~300
SQL Executions          500~1000
```

## 产品原则

不要只追求：

```text
Requirement Count
```

必须同时展示：

```text
Requirements
Cases
SQL Executions
Failures
```

因为：

```text
一个 Case 可以覆盖多个 Requirement
一个 Case 也可能执行多个 SQL Step
```

---

# 22. P1：Multi-Feature Mission——测试人员不应该手工拆五个任务

当前：

```text
1 Job = 1 Feature
```

这是正确的 Core/Isolation 设计。

但测试人员真正想要的是：

```text
Query 标准测试

☑ JOIN
☑ Filter
☑ Aggregate
☑ Subquery
☑ Sort / Limit

[开始测试]
```

而不是自己重复创建五个 Mission。

因此 Product Layer 下一步必须引入：

```text
Parent Mission
+
Child Feature Jobs
```

推荐结构：

```text
Query Mission
├── JOIN Job
├── Filter Job
├── Aggregate Job
├── Subquery Job
└── SortLimit Job
```

Parent Mission 只负责聚合：

```text
Feature Status
Coverage
Case Count
SQL Count
Failures
AI Findings
Approval State
Completion
```

不要把 5 个 Feature 强塞进一个 Job。

## Product Ready DoD

- [ ] Mission 可选择多个 Feature
- [ ] 每个 Feature 创建独立 Child Job
- [ ] Child Job 仍保留自己的 Candidate Scope
- [ ] Parent Mission 聚合而不重算 Core Truth
- [ ] 单个 Feature 失败不会破坏其他 Feature Evidence
- [ ] 用户可以重跑单个失败 Feature

---

# 23. P1：Strategy 必须真正改变测试行为

目前：

```text
SMOKE
STANDARD
FULL
AI_EXPLORATORY
```

已经开始影响执行。

但 Product Ready 需要达到：

## Smoke

```text
目标：
快速健康检查

内容：
核心场景
最小边界
有限 Candidate Budget

典型规模：
30~50 Cases

典型用途：
提交后快速验证
环境验证
每日轻量回归
```

---

## Standard

```text
目标：
日常功能回归

内容：
Pairwise
NULL
Empty
Duplicate
Boundary
Type Combination
Typical Nesting

典型规模：
180~300 Cases
```

---

## Full

```text
目标：
发版级回归

内容：
all_values
高阶组合
更多数据类型
更多嵌套
更复杂 Predicate

典型规模：
500+
```

---

## AI Exploratory

```text
目标：
模型外风险探索

流程：
Standard Baseline
↓
Coverage / Failure Analysis
↓
AI Risk Selection
↓
Limited Candidate Generation
↓
Core Execution
↓
Observe
↓
Next Round
```

---

# 24. P1：data_scale / risk_focus 不能长期停留在“只展示”

目前 Product View 已经诚实标记：

```text
data_scale_applied = false
risk_focus_applied = false
```

这比假装生效要好。

但真正 Product Ready 后，这两个参数必须进入执行策略。

## data_scale

建议控制：

```text
Fixture Size
Row Count
Duplicate Density
NULL Ratio
Group Cardinality
Subquery Result Size
```

示例：

```text
SMALL
→ 单元级语义验证

MEDIUM
→ 更真实的数据分布

LARGE
→ 兼顾功能 + 轻量数据规模风险
```

注意：

```text
LARGE
```

不是性能测试，

只是更大的功能数据集。

---

## risk_focus

应该控制：

```text
Candidate Ranking
Generation Priority
AI Exploratory Priority
Report Highlight
```

例如：

```text
☑ NULL
☑ Type Conversion
☑ Duplicate
```

则优先探索相关 Coverage Gap。

---

# 25. P1：Failure Center——测试人员第一关注对象应该是“失败”

当前 Evidence 很强。

但普通测试人员最先想知道的不是：

```text
Manifest ID
Artifact SHA
Contract ID
```

而是：

```text
今天发现了几个问题？
哪个最严重？
哪条 SQL 错了？
预期是什么？
实际是什么？
第一次在哪个 Build 出现？
重跑还会不会出现？
```

建议新增一级页面：

```text
Failures
```

列表：

| Failure | Feature | Scenario | Failure Type | Build | Status |
|---|---|---|---|---|---|
| F-001 | Filter | NULL + OR | Result mismatch | B11679 | New |
| F-002 | Aggregate | COUNT + NULL | Wrong result | B11679 | New |
| F-003 | Subquery | NOT IN + NULL | DB Error | B11679 | Known |

Failure Detail：

```text
测试目的
Case Semantic Path
SQL
Fixture
Expected
Actual
Diff
Failure Type
Runtime
Database Build
First Seen
Last Seen
Reproduce Count
AI Analysis
Related Cases
Evidence
```

Evidence/Hash 放在：

```text
高级信息
```

折叠区。

---

# 26. P1：Expected vs Actual 必须成为失败详情核心

数据库测试产品最重要的失败展示之一是：

```text
Expected
vs
Actual
```

不要只给：

```text
FAIL
```

推荐：

```text
Expected Rows
--------------------------------
1 | alice
2 | bob

Actual Rows
--------------------------------
1 | alice
2 | bob
3 | null

Diff
--------------------------------
+ 3 | null
```

其他类型：

```text
Expected Error
Actual Error

Expected Row Count
Actual Row Count

Expected Type
Actual Type
```

这会大幅降低测试人员定位成本。

---

# 27. P1：自动测试报告必须成为正式产品能力

产品级测试平台不能只提供 Dashboard。

至少要自动生成：

```text
Mission Summary
Test Purpose
Database / Build
Environment
Strategy
Tested Scope
Untested Scope
Feature Coverage
Case Count
SQL Count
PASS / FAIL
Failure Summary
AI Risk Summary
Human Approval
Promotion Result
Post Regression
Final Conclusion
```

推荐输出：

```text
JSON
Markdown
HTML
PDF
```

用途：

```text
JSON
→ CI / API / AI

Markdown
→ 开发 / Git

HTML
→ Web

PDF
→ 测试报告 / 客户 / 验收
```

---

# 28. P1：环境配置必须产品化

测试人员不应该手工理解：

```text
XGTEST_DB_HOST
XGTEST_DB_PORT
XGTEST_DB_NAME
XGTEST_DB_USER
XGTEST_DB_PASSWORD
XGTEST_RUNTIME_PROFILE
XGTEST_ALLOWED_SIGNERS
...
```

Product Ready 建议增加：

```text
Environment Setup Wizard
```

页面：

```text
数据库连接
━━━━━━━━━━━━━━━━━━
Host
Port
Database
User
Password

[测试连接]

Runtime
━━━━━━━━━━━━━━━━━━
Driver             ✓
Database Build     ✓
Contract           ✓
Runtime Profile    ✓
Probe Evidence     ✓
Xugu Console       ✓

[保存环境]
```

首页只显示：

```text
Environment Ready ✓
```

高级用户才去看环境变量。

---

# 29. P1：Preflight 结果需要人类可读解释

现在 Core Blocker 是好事，例如：

```text
RUNTIME_PROFILE_STALE
DATABASE_CONFIG_MISSING
SIGNED_APPROVAL_NOT_CONFIGURED
```

但 Product Layer 应转换成：

```text
Runtime Profile 已过期
原因：
当前 Contract 与 Probe 时版本不一致。

建议：
重新执行 Runtime Probe。

[重新 Probe]
```

而不是只展示：

```text
RUNTIME_PROFILE_STALE
```

错误码继续保留在高级信息中。

---

# 30. P1：Test Case Library 应成为一级产品能力

Case 页面不应该只是 Candidate/Active 文件浏览器。

应该提供：

```text
Test Library
```

维度：

```text
Feature
Scenario
Risk
Status
Origin
Coverage
Last Run
Last Result
Database Build
```

Case Origin：

```text
Built-in
Model Generated
AI Generated
Human Added
Imported
```

Case Lifecycle：

```text
Draft
Review
Active
Deprecated
```

用户应该能理解：

> 这是一个长期积累的数据库测试资产库。

---

# 31. P1：Case Detail 需要解释“为什么有这条测试”

建议固定展示：

```text
Case ID

测试目的
语义路径

JOIN
└── LEFT JOIN
    └── NULL Key
        └── Duplicate Right
            └── Additional Predicate

来源
AI Generated

覆盖 Requirement
R-xxx
R-yyy

为什么生成
当前 Pairwise Gap 缺少此组合

SQL

Expected

Last Actual

Mutation

Trial Evidence

AI Review

Human Review

Lifecycle
```

这会把“生成器产物”变成“测试人员能理解的测试用例”。

---

# 32. P1：AI Summary 要进一步升级为“测试负责人摘要”

当前 AI Summary 已经有基础。

产品级建议变成：

```text
AI Test Summary
```

示例：

```text
本轮共执行：
236 Cases
708 SQL

AI 发现：
4 个高风险区域
3 个新失败
2 个 Coverage Gap

重点风险：
1. LEFT JOIN + NULL Key
2. NOT IN + NULL
3. COUNT(column) + NULL
4. VARCHAR/INT comparison

AI 自动补充：
18 Cases

结果：
15 PASS
2 FAIL
1 BLOCKED

建议：
优先调查 F-002
```

这才是测试负责人真正有价值的信息。

---

# 33. P1：AI Exploratory 要从 Briefing 升级为受控 Loop

当前：

```text
AI Exploratory Briefing
```

还主要是建议。

Product Ready 的第一版真正 Loop 应限制得非常严格：

```text
最多 1~3 Round
每 Round 最多 N Candidate
只能调用 Semantic Action
不能执行任意 SQL
不能直接修改 Active Case
不能自动 Promotion
```

流程：

```text
Observe
↓
Rank Risk
↓
Generate Limited Candidate
↓
Core Validate
↓
Core Execute
↓
Observe Result
↓
Stop / Next Round
```

Stop Conditions：

```text
Budget exhausted
No meaningful gap
Repeated result
Blocking DB error
Human approval required
```

---

# 34. P1：报告“没测什么”必须成为硬要求

专业测试产品不能只写：

```text
PASS
```

必须明确：

```text
Tested Scope
Untested Scope
Unsupported Scope
Excluded Scope
```

例如：

```text
Tested
✓ JOIN
✓ Filter
✓ Aggregate

Untested
○ Subquery
○ Sort / Limit

Unsupported
✗ Window
✗ CTE

Excluded by Mission
✗ Performance
✗ Concurrency
```

并且：

```text
Query Defined Scope = PASS
```

不能显示成：

```text
Query Module = PASS
```

除非整个模块真的完成。

---

# 35. P1：Build-to-Build 对比与历史趋势

测试人员长期使用后一定会问：

```text
这个版本比上一个版本多失败了什么？
哪些失败修复了？
Coverage 上升了吗？
哪个 Feature 最近最不稳定？
```

因此建议 Mission History 支持：

```text
Build A
vs
Build B
```

至少比较：

```text
New Failures
Fixed Failures
Persistent Failures
Coverage Delta
Case Count Delta
Execution Time Delta
```

这是从“单次测试工具”走向“测试平台”的关键能力。

---

# 36. P2：团队使用——角色与权限

如果目标只是：

```text
1~2 个内部测试人员
```

当前单用户模式可以继续。

如果目标是：

```text
整个测试团队
```

则 Post-MVP 需要：

```text
Tester
Reviewer
Approver
Admin
```

最小权限建议：

```text
Tester
→ 创建 / 执行 Mission

Reviewer
→ Review Candidate / Failure

Approver
→ Human Sign / Promotion

Admin
→ Environment / Signer / Policy
```

不要一开始做复杂 RBAC。

---

# 37. P2：多 Mission 并发

当前：

```text
Single Mutable Job
```

适合 MVP。

团队级以后应逐步升级为：

```text
多个 Mission
↓
独立 Job Workspace
↓
受控 Worker Pool
↓
DB Session Limit
↓
Feature / Environment Resource Lock
```

而不是直接做复杂 Distributed Scheduler。

建议顺序：

```text
单用户稳定
↓
2~5 人团队
↓
本机多 Mission
↓
远程 Worker
↓
分布式 Scheduler
```

---

# 38. P2：CI / GitHub Gate

当前 GitHub 仍然：

```text
Branch Protection OFF
Statuses 0
Workflow Runs 0
Commit unsigned
```

在 Product MVP 阶段可以暂缓。

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
PR Review
```

尤其：

```text
AI 自动生成 Patch
```

绝不能直接进入主分支。

---

# 39. 产品级首页最终应回答的 6 个问题

首页不要让测试人员先理解系统内部对象。

应该一屏回答：

```text
1. 我现在在测什么？
2. 测到什么程度？
3. 跑了多少 Case？
4. 发现多少问题？
5. 哪些范围还没测？
6. AI 建议我下一步看什么？
```

建议首页最终结构：

```text
Current Mission
━━━━━━━━━━━━━━━━━━━━━━
Query Standard Regression

Scope
JOIN / Filter / Aggregate / Subquery / SortLimit

Progress
4 / 5 Features Complete

Result
236 Cases
708 SQL
231 PASS
3 FAIL
2 BLOCKED

Coverage
412 / 448

AI Summary
3 New Risks

Untested Scope
Window / CTE / Set Operation

[查看失败]
[查看 Coverage]
[查看报告]
```

---

# 40. 面向内部测试人员的 Product Ready Gate

以下 10 项全部满足后，建议正式宣布：

```text
XG DB Test
Internal Tester Ready v1
```

## 必须满足

1. **真实 Xugu 一键连接 / Preflight**
2. **五个 Query Feature 都能真实执行**
3. **Standard 至少 180~300 个 Active Cases**
4. **测试目的 / Scope / Untested Scope 清楚**
5. **Smoke / Standard / Full 行为真实不同**
6. **Failure Detail 有 Expected vs Actual**
7. **AI 能解释 Failure / Gap / Risk**
8. **Human Approval 能通过正常产品流程完成**
9. **完整 Test → Sign → Promote → Post Regression → Report 跑通**
10. **中断 / 重启后可以 Resume**

只要这 10 项完成：

> **就已经可以交给内部测试人员日常使用。**

---

# 41. 团队级 / 企业级 Product Ready Gate

内部测试人员版本之后，再考虑：

```text
Multi-user
RBAC
Parallel Missions
Remote Artifact Store
CI Integration
GitHub Required Checks
Historical Trend
Team Dashboard
Central Signer / KMS
Audit Export
```

不要把这些提前当成当前 MVP 阻塞项。

---

# 42. 更新后的阶段路线

建议从当前 `7a576bf` 开始，后续路线调整为：

```text
阶段 1：Product Truth
━━━━━━━━━━━━━━━━━━━━
Trial Verifier candidate_scope_ids
Signer passphrase
StrategyCompletionEvidence
Final Report self-contained
Runtime Profile v15 Probe

阶段 2：Product Content
━━━━━━━━━━━━━━━━━━━━
110 Draft Candidates
→ Mutation
→ Trial
→ AI Review
→ Human Review
→ Promotion
→ 180~300 Active Cases

阶段 3：Product UX
━━━━━━━━━━━━━━━━━━━━
Multi-feature Mission
Failure Center
Expected vs Actual
Environment Wizard
Test Report
Case Library
Build Comparison

阶段 4：AI Differentiation
━━━━━━━━━━━━━━━━━━━━
Risk-driven Exploration
Controlled Exploration Loop
Failure Clustering
Adaptive Candidate Generation

==============================
XG DB Test Internal Tester Ready
==============================

阶段 5：Team / Enterprise
━━━━━━━━━━━━━━━━━━━━
RBAC
Parallel Missions
Remote Artifact Store
CI
Branch Protection
Auto Repair PR
24h Autonomous Runner
```

---

# 43. 更新后的研发资源分配建议

当前阶段建议：

```text
测试内容 / Case Library      30%
产品体验 / 前端              25%
真实 E2E / Runtime           20%
AI Exploratory               15%
底层 Governance / Evidence   10%
```

不再继续让 Governance 占据主要研发时间。

当前底层已经足够强。

最大的边际收益来自：

```text
把测试内容做厚
把失败分析做清楚
把真实流程跑通
让测试人员不用理解底层
```

---

# 44. 产品层最终原则

从现在开始，所有新需求都应该优先经过下面 8 个问题判断：

```text
1. 测试人员能不能看懂？
2. 测试人员知不知道为什么要测？
3. 测试人员知不知道测了什么？
4. 测试人员知不知道没测什么？
5. 失败能不能快速定位？
6. AI 到底帮测试人员做了什么？
7. 页面展示是否完全对应 Core Truth？
8. 这个能力是否能减少测试人员的手工操作？
```

如果不能改善这些问题，

即使技术上很漂亮，

也不应该成为当前阶段的优先项。

---

# 45. 最终目标重新定义

项目最终不应该让测试人员感受到：

```text
“我在操作一个 Evidence / Candidate / Manifest 系统”
```

而应该是：

```text
“我告诉 AI 我要测试什么，
它自动设计、执行、补充、分析，
最后给我一个可信、可复核、可交付的结果。”
```

真正产品级体验应该是：

```text
测试人员描述目标
↓
选择测试范围 / 强度
↓
AI 编排
↓
Core 执行
↓
自动分析失败
↓
AI 补充探索
↓
Human Review / Sign
↓
Promotion
↓
Post Regression
↓
自动报告
```

其中：

```text
AI 决定下一步
Core 决定真相
Human 决定高风险治理动作
```

这三条边界继续保持不变。
