# XG DB Test 最新提交代码审核

## 1. 审核基线

- 仓库：`xunyuxingkong/allone`
- 分支：`codex/join-model-v2`
- 当前远端 HEAD：`564b82da3c61c8bb049847397663e6d7842a8ff7`
- 提交：`fix: enforce job review gates and show query results as tables`
- 父提交：`6311887d8dffd69c5727d4b6059ce7b9077273fa`
- 提交时间：2026-10-09
- 分支保护：OFF
- GitHub Required Checks：无
- GitHub Workflow Runs：无
- Commit Signature：unsigned

本次相对上一提交：

```text
16 files changed
+1765 additions
-42 deletions
```

其中大量新增来自审核文档；真正代码修改集中在：

```text
src/xgtest/ai/controller.py
src/xgtest/ai/identity.py
src/xgtest/ai/models.py
src/xgtest/application/services.py
src/xgtest/application/db_worker.py
src/xgtest/application/worker_results.py
framework_tests/test_ai_review_fixes.py
Web 结果表格组件
```

---

# 2. 总体结论

这次提交**确实针对上一轮 4 个关键问题做了实质修复**：

```text
1. Technical Review FAIL/CONCERNS Gate
2. Durable Job Control Plane Identity
3. Single Mutable Job Policy
4. Credential / Raw Error Redaction
```

其中前三项已经真正进入控制流程，不是只补测试；第四项也把数据库密码从 WSL argv 中移除，并对 Worker Error 做了安全投影。

当前评价：

| 维度 | 评分 |
|---|---:|
| AI / Core 权责边界 | 9.3 |
| Technical Review Gate | 9.2 |
| Job Identity | 8.4 |
| Job 并发治理 | 8.0 |
| Secret / Error Redaction | 9.0 |
| Application Service | 8.6 |
| 测试质量 | 9.0 |
| 真实 E2E 完整度 | 6.8 |
| MVP 可用性 | 8.1 |
| **综合实现质量** | **8.8 / 10** |

最重要的结论：

> **上一轮指出的 4 个问题基本都修了，但 Single Mutable Job 的修复引入了一个新的实际阻塞：旧 BLOCKED Job 没有“正式放弃/终止”入口，会永久占住唯一可修改任务槽。**

而当前仓库自己的真实历史任务正好处于这个状态，所以这是现在最应该先修的问题。

---

# 3. Technical Review Gate 已正确修复

上一版的问题是 AI Review 即使 `decision = FAIL`，仍可能因为记录有效而进入 acceptance。现在已经拆成：

```text
technical_review_valid
technical_review_accepted
```

只有：

```text
decision == PASS
AND recommendation == READY_FOR_HUMAN_REVIEW
```

才算 accepted。否则分别返回：

```text
AI_TECHNICAL_REVIEW_FAILED
AI_TECHNICAL_REVIEW_NEEDS_HUMAN_CHECK
```

Controller 的 Candidate Readiness 已经依赖 `technical_review_accepted`。这项修复正确。

---

# 4. Review 上下文失效处理正确

Review 文件继续绑定 `input_hash`。Trial、Mutation、Candidate 或 Runtime Profile 上下文变化时：

```text
valid = false
accepted = false
```

因此旧 PASS 评审不会跨上下文复用。

---

# 5. Human Gate 仍然没有被 AI 绕过

即使 Technical Review Accepted，后面也只是进入：

```text
acceptance.inspect
→ WAITING_APPROVAL
```

正式 Promotion 仍要求真实 `ReviewEvidence / CoverageReview / Signed Approval`。

---

# 6. Durable Job Identity 已实现第一版

创建 Job 时冻结：

```text
control_plane_layer_id
git_commit
```

Action / Resume 前检查当前 control plane；变化则：

```text
JOB_CONTROL_PLANE_CHANGED
```

老任务缺少身份则：

```text
JOB_CONTROL_PLANE_IDENTITY_MISSING
```

不会静默采用新逻辑。方向正确。

---

# 7. Job Identity 仍有边界问题

当前真正用于阻断的是 `control_plane_layer_id`，但 control_plane Layer 同时包含 AI/Application/Web/WebUI。

这会造成两个相反问题：

## 7.1 太宽

只修改 UI 表格、CSS、展示代码，也可能让 Durable Job 变成 `JOB_CONTROL_PLANE_CHANGED`。

## 7.2 又不够完整

Job 真正还调用：

```text
generator/package.py
generator/promotion_batch.py
generator/post_acceptance.py
generator/lifecycle.py
generator/review.py
```

这些治理逻辑变化未必改变 control_plane Layer。

建议以后定义专门的：

```text
job_logic_id
```

只绑定真正影响 Durable Workflow 语义的 AI/Application/Governance 核心代码，不绑定 UI。此项为 P1，可在真实 E2E 后继续收敛。

---

# 8. Single Mutable Job Policy 已解决并发污染

现在同一项目最多一个非终态：

```text
query.full_test
query.join.verify
```

PLANNED/RUNNING/WAITING_APPROVAL/BLOCKED 都占槽，FAILED/COMPLETED 释放；`query.status` 可并存。创建还受 project execution lock 保护。

这个方向正确。

---

# 9. 新 P0：旧 BLOCKED Job 会永久占槽

当前真实历史 Job：

```text
94b3d304119446a3bb5cc3ffe78dd33a
```

来自 identity 字段引入之前，因此现在：

```text
JOB_CONTROL_PLANE_IDENTITY_MISSING
→ BLOCKED
```

但 BLOCKED 又占唯一 Mutable Slot；同时 resume 会再次被 identity gate 拒绝。当前没有：

```text
cancel
abandon
supersede
migrate
```

正式入口。结果是：

```text
旧 BLOCKED Job
→ 永远占槽
→ 无法创建新的 query.full_test
→ 新版本真实 E2E 无法开始
```

这是当前最重要的可用性 Blocker。

---

# 10. MVP 最简单修法：增加 abandon

不要现在做复杂 Migration。新增人工明确操作：

```text
abandon(job_id, expected_revision, reason)
```

执行后：

```text
state = FAILED
current_action = None
blockers += JOB_ABANDONED_BY_OPERATOR
```

并记录不可删除的 Event：

```text
ABANDONED
```

保留旧 Job、旧 Event、旧 identity、旧 evidence 和 abandon reason。绝不能删除 Job 或伪造成 COMPLETED。

建议同步提供：

```text
xgtest ai abandon JOB_ID
abandon_test_job MCP
```

这是 P0。

---

# 11. WSL 密码 argv 泄露已修复

现在使用子进程环境 + WSLENV 传递数据库变量，命令行只包含固定 Worker 命令，不再出现 user/password。测试也覆盖 argv 不含敏感值及父环境不被修改。

---

# 12. Worker 原始异常泄露基本修复

新增 `safe_worker_error()`：只有已知 Domain Code 可以直接离开 Worker；Driver 异常统一为 `DATABASE_EXECUTION_ERROR`。密码、连接串、SQL、路径不会复制到 result/event/final report。

---

# 13. Regression Failure 投影合理收缩

Job 只保存：

```text
case_id
step_id
status
failure_type
safe_error_code
artifact_ref
```

完整结果仍在原始 `regression.json`，不再复制进每个 Job Checkpoint。这个修复正确。

---

# 14. Raw Artifact 仍是本地原始数据

需要明确：当前只是“不把敏感内容复制进 Job/UI 默认结果”，并不等于 Raw Artifact 已经加密或做访问控制。MVP 当前可以接受，但后续 Remote ArtifactStore 时需重新设计权限边界。

---

# 15. MCP stdio Git 子进程挂起问题也已修复

`git_output()` 改为 `stdin=DEVNULL + TemporaryFile stdout + timeout`，避免 stdio MCP 的协议 stdin 被 Git 继承后挂住。并新增真实 stdio MCP 子进程 create/inspect 测试。这属于很有价值的真实环境修复。

---

# 16. 当前测试状态

仓库实施记录：

```text
278 passed
1 skipped
```

相对上一版增加 18 项针对性回归测试。

但 GitHub 远端仍然：

```text
Commit statuses = []
Workflow runs = []
Branch protection = OFF
Commit unsigned
```

所以 278 PASS 是本地/仓库内证据，不是远端独立 CI。

---

# 17. 真实 AI Full-Test E2E 仍未完成

目标数据库当前仍连接超时，所以没有新的完整真实链：

```text
External Agent
→ live preflight
→ Query regression
→ Candidate workflow
→ 21 AI reviews
→ Human approval
→ Promotion
→ Post regression
→ Post acceptance
```

因此当前只能说明控制面越来越成熟，不能宣布真实 E2E 已完成。

---

# 18. 当前 MVP 状态

```text
Deterministic Core: 成熟
External AI Semantic API: 第一版成熟
Job Persistence: 第一版成熟
Technical Review Gate: 已修
Secret Boundary: 显著改善
MCP: 真实调用已验证
Single Mutable Workflow: 有生命周期死锁
Real Xugu AI E2E: 未完成
AI-Driven Usable MVP: 约 88~90%
```

---

# 19. 下一提交只建议做两件事

## P0

```text
Job Abandon / Supersede
```

解决旧 BLOCKED Job 永久占槽。

## P1

```text
job_logic_id
```

把 Durable Job 身份从过宽的 UI control_plane 中进一步收敛，同时覆盖实际 Governance Workflow 代码。若希望尽快跑 E2E，这项可延后。

---

# 20. 修完 P0 后立刻跑真实 E2E

流程：

```text
1. abandon 旧 legacy Job
2. 创建新的 query.full_test
3. live preflight
4. Query regression
5. Coverage
6. Candidate readiness
7. Mutation / Trial
8. 21 AI Technical Review
9. WAITING_APPROVAL
10. Human ReviewEvidence / CoverageReview
11. Re-Freeze
12. Signed Approval
13. Resume
14. Preflight
15. Promotion
16. Post Regression
17. Post Verify
18. Final Report
```

不要在这之前再开 Contract v4、Filter、ActiveManifest、Remote Store 等新主线。

---

# 21. 最终判断

`564b82d` 修复质量总体不错。上一轮四个问题：

```text
Technical Review Gate   → 已解决
Control Plane Identity  → 已解决第一版
Single Mutable Job      → 并发污染已解决，但引入生命周期死锁
Credential/Error Leak   → 基本解决
```

当前真正最需要处理的不是更多架构，而是让永久 BLOCKED 的旧 Job 能以可审计方式退出生命周期。

补上 `abandon` 后，应立即恢复真实数据库并跑完整 AI E2E。若整条链跑通，就可以正式把当前阶段定义为：

```text
XG DB Test AI-Driven MVP v1
```

---

# 22. 产品层面的核心问题

前面的代码审核主要解决：

```text
AI Control
Job
Evidence
Security
Acceptance
```

但从真正使用者视角，目前项目还存在明显产品层短板：

```text
测试目的不明确
测试范围不明确
测试强度不明确
测试用例数量偏少
Coverage 与 Case 数量关系难理解
AI 价值在界面上感知不强
测试完成与“未测试范围”没有清晰分开
```

当前前端更像：

```text
Job / Evidence / Candidate Viewer
```

而不是：

```text
AI 驱动数据库测试产品
```

因此下一阶段必须在现有：

```text
AI Control Plane
Application Service
Deterministic Core
Evidence
```

之上新增一层：

```text
Test Product Layer
```

目标不是增加新的复杂底层，而是：

> **让测试人员一眼知道：为什么测、测什么、测到什么程度、漏了什么、AI 帮他做了什么。**

---

# 23. 新增 Test Product Layer

建议形成：

```text
┌─────────────────────────────────────────┐
│           Test Product Layer            │
│ Mission / Scope / Strategy / Report     │
│ Coverage / Case / AI Summary / Risk     │
└───────────────────┬─────────────────────┘
                    │
┌───────────────────▼─────────────────────┐
│            AI Control Plane             │
├─────────────────────────────────────────┤
│          Application Services           │
├─────────────────────────────────────────┤
│        Deterministic Test Core          │
├─────────────────────────────────────────┤
│          Evidence / Runtime             │
└─────────────────────────────────────────┘
```

Test Product Layer 第一版只负责：

```text
测试任务定义
测试范围展示
测试强度选择
测试内容矩阵
测试结果汇总
未覆盖范围展示
AI 测试分析
用户友好的 Case 查看
```

不重新实现：

```text
PASS / FAIL
Coverage 计算
Mutation 判定
Promotion Gate
Evidence Verify
```

这些仍然全部来自 Core。

---

# 24. P0：先解决当前 E2E 阻塞——Job Abandon

产品层优化之前，先补当前实际阻塞：

```text
旧 BLOCKED Job
→ 永久占 Mutable Slot
```

新增：

```text
abandon(job_id, expected_revision, reason)
```

要求：

```text
必须人工明确执行
必须记录 reason
必须保留旧 Job
必须保留旧 Evidence
不得删除旧 Job
不得伪造成 COMPLETED
```

建议状态：

```text
state = FAILED
blocker = JOB_ABANDONED_BY_OPERATOR
event = ABANDONED
```

CLI：

```bash
xgtest ai abandon <job_id> --revision <rev> --reason "legacy job before control-plane identity"
```

MCP：

```text
abandon_test_job
```

完成标准：

```text
旧 Job 可审计
新 query.full_test 可以重新创建
```

---

# 25. P1：引入 Test Mission——让用户先知道“为什么测”

新建产品模型：

```text
TestMission
```

建议字段：

```text
mission_id
name
purpose
module
features
strategy
data_scale
risk_focus
acceptance_goal
excluded_scope
created_by
```

示例：

```json
{
  "name": "Query 语义正确性标准测试",
  "purpose": "验证当前 Xugu Build 下 Query 模块核心语义正确性",
  "module": "query",
  "features": [
    "join",
    "filter",
    "aggregate",
    "subquery",
    "sort_limit"
  ],
  "strategy": "STANDARD",
  "risk_focus": [
    "NULL",
    "duplicate",
    "boundary",
    "type_conversion"
  ],
  "excluded_scope": [
    "performance",
    "concurrency",
    "transaction"
  ]
}
```

用户启动测试时不应该先看到：

```text
Intent
Action
Job Revision
```

而应该先看到：

```text
测试目的
测试范围
测试策略
预计规模
验收标准
明确不测范围
```

---

# 26. P2：前端新增“创建测试任务”页面

新增入口：

```text
/tests/new
```

页面结构：

```text
① 测试目的
② 测试模块
③ 测试范围
④ 测试强度
⑤ 风险重点
⑥ 数据规模
⑦ 预计测试规模
⑧ 明确不测范围
⑨ 启动 AI 测试
```

示例：

```text
测试目的
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

验证 Query 模块当前定义能力的语义正确性

测试范围
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

☑ JOIN
☑ Filter / WHERE
☑ Aggregate / GROUP BY
☑ Subquery
☐ Window
☐ CTE
☐ Set Operation

测试强度
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

○ Smoke
● Standard
○ Full
○ AI Exploratory

预计执行
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

约 220 个 Case
约 650 次 SQL 执行
预计 10~20 分钟
```

用户点击：

```text
开始 AI 测试
```

之后才创建：

```text
TestJob
```

这样：

```text
Mission
→ Job
```

而不是现在：

```text
Job
→ 用户自己猜这次测什么
```

---

# 27. P3：定义测试强度等级

不要简单用“Case 越多越好”。

第一版提供四个等级：

## Smoke

目标：

```text
快速发现明显功能错误
```

策略：

```text
基础语法
关键路径
最小边界
```

目标规模：

```text
30~50 Case
```

---

## Standard

作为默认。

策略：

```text
Pairwise
NULL
空结果
重复值
边界值
类型变化
典型组合
```

目标规模：

```text
150~300 Case
```

---

## Full

策略：

```text
更多维度组合
多表
更多类型组合
高阶边界
嵌套查询
复杂 Predicate
```

目标规模：

```text
500~2000 Case
```

---

## AI Exploratory

这是项目真正体现 AI 价值的模式：

```text
基础 Model 测试
↓
AI 分析 Coverage / Failure / Risk
↓
AI 找出未覆盖风险
↓
动态生成补充 Case
↓
执行
↓
分析新结果
↓
继续探索
```

这应该成为 MVP 后最重要的差异化能力。

---

# 28. P4：重新设计首页

当前首页应从：

```text
Job / Run / Candidate
```

转为：

```text
Mission / Coverage / Result
```

建议首页：

```text
┌────────────────────────────────────────────┐
│ XG DB Test                    Xugu ● Ready │
│ AI 驱动数据库自动测试平台                  │
├────────────────────────────────────────────┤
│ 当前测试目标                               │
│ Query 模块语义正确性                       │
│ 范围：JOIN / Filter / Aggregate / Subquery │
│ 模式：Standard                             │
│                     [ 开始 AI 测试 ]       │
├────────────────────────────────────────────┤
│ Query Coverage                             │
│                                            │
│ JOIN                 137 / 137   100%      │
│ Filter                64 / 96     67%      │
│ Aggregate             28 / 88     32%      │
│ Subquery               0 / 72      0%      │
├────────────────────────────────────────────┤
│ 最近测试                                   │
│ 186 Cases | 552 SQL | 184 PASS | 2 FAIL   │
└────────────────────────────────────────────┘
```

首页首先回答：

```text
现在系统在测什么？
目前覆盖到什么程度？
最近结果怎么样？
```

而不是首先展示内部技术对象。

---

# 29. P5：重做 Job Detail 的信息层级

Job Detail 页面不要先放：

```text
Action Timeline
Revision
Evidence ID
```

建议主页面顺序：

## ① 测试目的

```text
验证 Query 模块在当前 Xugu Build 下的语义正确性
```

## ② 测试范围

```text
JOIN
Filter
Aggregate
Subquery
```

## ③ 当前进度

```text
Regression       PASS
Coverage         RUNNING
Generation       PASS
Mutation         PASS
Trial            PASS
AI Review        RUNNING
Human Approval   WAITING
```

## ④ 测试结果

```text
Cases
SQL Executions
PASS
FAIL
BLOCKED
```

## ⑤ AI 分析

```text
风险
失败解释
新增 Case
下一步建议
```

## ⑥ 高级信息

折叠展示：

```text
Job Revision
Runtime Profile
Contract ID
Manifest ID
Artifact Ref
```

这样普通用户与高级用户都能使用。

---

# 30. P6：增加 Scope Matrix——让测试范围真正可见

当前最大的体验问题之一是：

```text
用户看不到“到底测了哪些场景”
```

建议新增：

```text
/tests/:missionId/scope
```

展示 Feature Matrix：

| Feature | Dimension | Required | Covered | Case | 状态 |
|---|---|---:|---:|---:|---|
| JOIN | INNER | 24 | 24 | 8 | ✅ |
| JOIN | LEFT | 26 | 26 | 9 | ✅ |
| JOIN | NULL | 18 | 18 | 6 | ✅ |
| JOIN | Duplicate | 16 | 16 | 5 | ✅ |
| Filter | Comparison | 20 | 14 | 12 | 🔄 |
| Filter | NULL | 12 | 7 | 7 | 🔄 |
| Aggregate | GROUP BY | 20 | 0 | 0 | ⏳ |

必须明确区分：

```text
Requirement Count
Case Count
Execution Count
```

避免用户看到 21 Case 就认为：

```text
只有 21 个场景
```

---

# 31. P7：重构 Test Case 页面

Case 页面不应该只展示：

```text
QUERY.JOIN.203908E1
```

首先展示语义路径：

```text
JOIN
└── LEFT JOIN
    └── NULL Key
        └── Duplicate Rows
            └── Additional Predicate
```

列表建议：

| Case | 场景 | 来源 | 类型 | 状态 |
|---|---|---|---|---|
| JOIN-001 | INNER + Equal | Model | 基础 | PASS |
| JOIN-034 | LEFT + NULL | Model | 边界 | PASS |
| JOIN-071 | LEFT + Duplicate | AI | 组合 | PASS |
| JOIN-103 | Multi Predicate | AI | 风险探索 | FAIL |

Case Detail：

```text
测试目的
为什么生成
覆盖哪些 Requirement
输入数据
SQL
Expected
实际结果
Mutation
AI Review
Evidence
```

这样测试人员才能理解 Case 的价值。

---

# 32. P8：明确展示 Tested Scope / Untested Scope

专业测试报告必须明确：

```text
测了什么
没测什么
```

结果页增加：

```text
Tested Scope
━━━━━━━━━━━━━━━━━━━━
✓ JOIN
✓ Filter
✓ Aggregate

Untested Scope
━━━━━━━━━━━━━━━━━━━━
✗ Window Function
✗ CTE
✗ Set Operation
✗ Performance
✗ Concurrency
✗ Transaction
```

不要再出现：

```text
Query PASS
```

但用户误以为：

```text
整个 Query 模块都已经完整测试
```

正确表达应该是：

```text
Query / Current Defined Scope = PASS
Query Module Full = INCOMPLETE
```

---

# 33. P9：加强 AI 在前端的存在感

目前 AI 实际参与：

```text
选择动作
Failure Analyze
Technical Review
```

但用户体验上未必感觉到。

新增：

```text
AI Test Summary
```

例如：

```text
AI 本轮发现 4 个高风险区域：

1. LEFT JOIN + NULL Key 覆盖不足
2. Duplicate Key + Predicate 缺少组合
3. INTEGER/VARCHAR 隐式转换未覆盖
4. 缺少多表 JOIN 场景

AI 自动生成：
27 条补充测试

结果：
24 PASS
2 FAIL
1 BLOCKED

优先建议：
调查 QUERY.JOIN.91AC23
```

这能让用户真正感受到：

```text
AI 不只是启动脚本
而是在分析测试空间
```

---

# 34. 测试用例数量：MVP 必须从 JOIN Demo 扩展成 Query MVP

当前实际成熟 Feature 主要是：

```text
JOIN
```

这对于技术验证足够，但对于产品体验不够。

MVP 用户版建议至少覆盖：

```text
Query
├── JOIN
├── Filter / WHERE
├── Aggregate / GROUP BY / HAVING
├── Subquery
└── Sort / Limit
```

这五个 Feature 基本可以让使用者感受到：

```text
这是一个 Query 测试平台
```

而不是：

```text
JOIN 测试 Demo
```

MVP 后再扩：

```text
Window
CTE
Set Operation
Expression
Function
```

---

# 35. Feature 扩展优先级

推荐：

```text
F1 Filter
F2 Aggregate
F3 Subquery
F4 Sort / Limit
```

每个 Feature 必须遵循同一结构：

```text
Model
Plugin
Coverage Strategy
Generator
Mutation Specs
Trial
AI Review
Acceptance
```

如果新增 Feature 时需要大量修改：

```text
Controller
Job
Acceptance
Evidence Core
```

说明 Generic Platform 仍未真正稳定。

---

# 36. Filter MVP 范围建议

Filter 先覆盖：

```text
Comparison
AND / OR / NOT
NULL
BETWEEN
IN
LIKE
Arithmetic Predicate
Type Conversion
Boolean Combination
```

至少构造：

```text
60~100 Requirements
30~60 Executable Cases
```

重点不是追求 Case 数字，而是让用户看到：

```text
Filter Feature 有明确测试空间
```

---

# 37. Aggregate MVP 范围建议

Aggregate：

```text
COUNT
SUM
AVG
MIN
MAX
GROUP BY
HAVING
NULL
Empty Set
Duplicate Values
Multiple Groups
```

目标：

```text
60~100 Requirements
30~60 Cases
```

---

# 38. Subquery MVP 范围建议

Subquery：

```text
IN
NOT IN
EXISTS
NOT EXISTS
Scalar Subquery
Correlated Subquery
ANY
ALL
NULL
Empty Result
```

目标：

```text
60~100 Requirements
30~60 Cases
```

---

# 39. Sort / Limit MVP 范围建议

覆盖：

```text
ORDER BY ASC/DESC
NULL Ordering
Multi-column Sort
LIMIT
OFFSET
Sort + Filter
Sort + Join
```

目标：

```text
30~60 Requirements
20~40 Cases
```

---

# 40. Query MVP 的产品级规模目标

建议第一版可用 MVP：

```text
Feature：
5 个

Coverage Requirements：
约 350~500

Executable Cases：
约 180~300

单次 Standard Run SQL：
约 500~1000

真实数据库：
Xugu

模式：
Smoke / Standard / Full / AI Exploratory
```

这样用户看到的就不再是：

```text
21 条 Candidate
```

而是：

```text
一个有规模的 Query 测试系统
```

---

# 41. 产品报告必须重新定义统计口径

首页和报告固定显示四个数字：

```text
Requirements
Cases
SQL Executions
Failures
```

例如：

```text
Coverage Requirements   428
Executable Cases        236
SQL Executions          708
Failures                  3
```

然后说明：

```text
一个 Case 可以覆盖多个 Requirement
一个 Case 可以执行多个 SQL Step
```

这样用户不会再把：

```text
Case 少
```

直接等价为：

```text
测试范围少
```

---

# 42. 产品层新的核心状态

建议增加用户层状态，而不是直接暴露 Core 状态。

Mission：

```text
DRAFT
READY
RUNNING
WAITING_APPROVAL
BLOCKED
COMPLETED
```

Feature：

```text
NOT_MODELED
PARTIAL
DEFINED_SCOPE_COMPLETE
```

Coverage：

```text
covered / required
```

Formal：

```text
NOT_STARTED
WAITING_APPROVAL
HOLD
PASS
```

UI 可以同时展示：

```text
Workflow: COMPLETED
Formal Acceptance: HOLD
```

避免一个绿色 COMPLETED 误导用户。

---

# 43. 产品层不应该破坏当前架构

实现原则：

```text
Product Layer 只组合 Core State
```

例如：

```text
Mission Coverage
= ModuleService + Feature Scope

Mission Result
= Job ActionResult + Regression Result

Case Detail
= QueryReadService + CandidateService

AI Summary
= Agent advisory result
```

禁止 Product Layer 自己重新计算：

```text
Coverage
PASS / FAIL
Mutation
Acceptance
```

---

# 44. 产品优化实施顺序

建议重新安排下一阶段：

```text
P0  Job abandon

P1  TestMission / TestScope 模型

P2  创建测试任务页面

P3  首页 Mission + Coverage Dashboard

P4  Scope Matrix

P5  Case List / Case Detail 重构

P6  Tested / Untested Scope

P7  AI Test Summary

P8  Filter Plugin

P9  Aggregate Plugin

P10 Subquery Plugin

P11 Sort / Limit Plugin

P12 Standard Query Mission E2E

P13 AI Exploratory

P14 Repair Loop
```

---

# 45. 建议 Commit 顺序

```text
01 fix: add auditable job abandon lifecycle

02 feat: add test mission and scope contracts

03 feat: expose mission read service

04 feat: add mission creation page

05 feat: add query coverage dashboard

06 feat: add scope matrix view

07 feat: redesign case list and case detail

08 feat: show tested and untested scope

09 feat: add ai test summary presentation

10 feat: implement filter query plugin

11 feat: implement aggregate query plugin

12 feat: implement subquery plugin

13 feat: implement sort-limit plugin

14 test: add standard query mission e2e

15 feat: add ai exploratory query testing

16 docs: freeze ai-driven product mvp v1
```

---

# 46. 产品 MVP DoD

只有满足以下条件，才建议宣布：

```text
AI-Driven Usable MVP v1
```

## 用户体验

- [ ] 用户能明确填写测试目的
- [ ] 用户能明确选择测试范围
- [ ] 用户能明确选择 Smoke / Standard / Full
- [ ] 页面显示预计 Case / SQL 数量
- [ ] 首页显示 Feature Coverage
- [ ] Job Detail 先显示测试目标/范围/结果，而不是内部 ID
- [ ] Scope Matrix 可查看测试空间
- [ ] Case 页面能解释“为什么测这条”
- [ ] 页面明确展示 Untested Scope

## 测试内容

- [ ] JOIN
- [ ] Filter
- [ ] Aggregate
- [ ] Subquery
- [ ] Sort / Limit
- [ ] Standard 模式至少 180~300 Case
- [ ] Coverage Requirements 至少 350+

## AI 体验

- [ ] AI 自动决定下一 Semantic Action
- [ ] AI 能分析 Coverage Gap
- [ ] AI 能做 Technical Review
- [ ] AI 能生成测试摘要
- [ ] AI 能指出高风险区域
- [ ] AI Exploratory 至少完成第一版

## Core 可信性

- [ ] PASS/FAIL 仍由 Core 决定
- [ ] Coverage 仍由 Core 决定
- [ ] Human Gate 不被 AI 绕过
- [ ] Raw Evidence 可复核
- [ ] Job 可恢复
- [ ] Job 可人工 abandon
- [ ] 完整真实 Xugu E2E 跑通

---

# 47. 下一阶段资源分配建议

从现在开始建议投入比例：

```text
产品体验 / 前端        35%
测试内容 / Feature     35%
AI 行为                20%
底层治理               10%
```

不再保持过去：

```text
70% Evidence / Governance
20% Feature
10% Product
```

因为当前短板已经发生变化。

---

# 48. 最终产品目标

项目最终不应该让使用者感受到：

```text
我在操作一个很复杂的 Evidence 系统
```

而应该让使用者感受到：

```text
我告诉 AI 我要测试什么
AI 自动完成测试设计、执行、分析、补充
系统给我一个可信、可复核的结果
```

因此从这一阶段开始，所有需求都应该优先回答：

```text
用户能不能看懂？
用户知不知道测了什么？
用户知不知道没测什么？
用户能不能理解失败？
用户能不能看到 AI 做了什么？
```

如果不能，即使底层再严谨，也还不是一个真正“可用”的 AI 测试产品。

---

# 49. 更新后的近期主线

最终建议近期主线调整为：

```text
Job Abandon
↓
Test Mission / Scope
↓
前端 Mission 创建
↓
Coverage Dashboard
↓
Scope Matrix
↓
Case UX
↓
JOIN + Filter + Aggregate + Subquery + Sort/Limit
↓
AI Test Summary
↓
Standard Query E2E
↓
AI Exploratory
↓
=============================
AI-Driven Product MVP v1
=============================
↓
Repair Loop
↓
24h Autonomous Testing
```

这个顺序能够同时满足两个目标：

```text
不丢掉当前已经建立的可信 Core
+
把项目重新拉回“AI 驱动测试产品”
```
