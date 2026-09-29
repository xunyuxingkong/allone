# XG DB Test MVP 最新代码校准版实施计划
## 基于 `main@fbef12339f38e1384efb305a679be35b9d44d91a`

> 最新提交：`fbef12339f38e1384efb305a679be35b9d44d91a`
> 提交说明：`Implement JOIN query generation MVP`
> 提交时间：2026-09-28
> 上一关键提交：`0ef9f0b2a1c7ced1556a0abdd6029df944d6e499` — `Implement query MVP history timeout and web UI`
> 本计划基于最新远端 `main` 实际代码重新校准，替换之前基于旧提交的未完成项判断。

---

# 1. 当前阶段重新定级

按最新代码，项目已经不再只是“单机 Query MVP”。

当前实际能力应定义为：

```text
Query Execution MVP
≈ 基本完成

Query Read-only Web MVP
≈ 已实现

Query Generation MVP
≈ 框架链路已完成
≈ 真实 JOIN 模型已进入 Review Gate
```

当前 Query Generation 主链已经真实落地：

```text
Test Model
→ Constraint
→ all_values / pairwise
→ Active Coverage
→ Coverage Gap
→ Deterministic Candidate Generation
→ Dedup
→ Static Validate
→ Real Xugu Trial Run ×2
→ Review
→ Promotion Gate
```

但仍不能直接宣布：

```text
Query Generation MVP = DONE
```

当前最关键的阻塞点已经从“框架功能没实现”变成：

```text
JOIN Test Model / Template 的 Coverage 语义是否可信
+
Promotion Evidence 是否绑定完整运行契约
+
真实 Review / Promote / Full Regression 是否完成
```

---

# 2. 最新代码已经完成的能力

以下项目在旧计划中曾被列为待实现，但在最新提交中已经完成。

## 2.1 Query Timeout

已经实现：

```text
Parent Process
→ spawn Worker Process
→ Worker 独占 Xugu Session
```

超时后：

```text
terminate
→ grace join
→ kill
```

因此当前已经具备：

```text
Case Timeout
Worker Isolation
Connection Disposal
TIMEOUT Report
已完成 Step 保留
当前 Step 标记 TIMEOUT
后续 Step 标记 SKIPPED
```

结论：

```text
“Query Timeout 尚未实现”
```

应从待办清单删除。

仍未完成的是：

```text
Driver Cancel Proof
Server-side Stop Proof
```

但它们已经不再影响 Runner 自身有界退出。

---

## 2.2 Query Read-only Safety

当前已经有两层保护。

### Typed Boundary

Query SQL 仅允许：

```text
SELECT
WITH
```

并拒绝：

```text
INSERT
UPDATE
DELETE
CREATE
DROP
ALTER
SET
CALL
EXEC
MERGE
COMMIT
ROLLBACK
...
```

### Database Boundary

Xugu Session 以：

```sql
SET TRANS_READONLY TO TRUE
```

进入只读模式。

设置失败：

```text
Fail Closed
→ Close Connection
```

QueryRunner 对非只读 XuguSession 直接拒绝：

```text
QUERY_SESSION_NOT_READ_ONLY
```

因此 Query MVP 的只读边界已经比旧版本明显完整。

---

## 2.3 Strict Runtime Profile

现在 Query Run 已区分：

```text
diagnostic
regression
```

### diagnostic

Runtime Profile 可选。

### regression

Runtime Profile 必须存在：

```text
RUNTIME_PROFILE_REQUIRED_FOR_REGRESSION
```

并检查：

```text
host
database
driver version
contract_set_id
```

类型比较又进一步要求：

```text
support_status = SUPPORTED
mapping_fidelity = EXACT
canonical_encoding = VERIFIED
logical_type 正确
```

该能力已经完成，不再作为后续 P0。

---

## 2.4 Result Provenance

最新 Query Report 已包含：

```text
git_commit
source_file
case_source_hash
```

当前链路已经可以做到：

```text
Run
→ Git Commit
→ Case Source
→ Case Source Hash
```

Web Case Detail 读取当前 Case Definition 时还会重新比对：

```text
source_file
+
case_source_hash
```

不匹配则：

```text
source_available = false
```

不会把当前文件错误冒充为历史执行资产。

---

## 2.5 Run History

已经有：

```text
src/xgtest/query/history.py
```

支持：

```text
immutable run JSON
index.json
run list
status filter
date filter
pagination
case query
atomic file write
```

所以：

```text
“Run History 尚未实现”
```

从旧计划删除。

---

## 2.6 FastAPI Web API

已经实现只读 API：

```text
/api/health
/api/runs
/api/runs/{run_id}
/api/runs/{run_id}/cases
/api/runs/{run_id}/cases/{case_id}
/api/runtime/profile
/api/runtime/contract
/api/runtime/types
```

---

## 2.7 Vue Web UI

最新仓库已经包含：

```text
Vue 3
TypeScript
Vite
Element Plus
Pinia
Vue Router
ECharts
```

并已有页面：

```text
Dashboard
Run List
Run Detail
Case Detail
Runtime
```

所以前端当前不再是“是否实现”的问题，而是：

```text
下一阶段增加 Coverage / Candidate / Review 可视化
```

---

## 2.8 Query Generation 基础框架

最新代码已经真实存在：

```text
src/xgtest/design/
├── model.py
├── constraint.py
├── coverage.py
└── signature.py

src/xgtest/generator/
├── candidate.py
├── dedup.py
├── lifecycle.py
├── review.py
└── template.py
```

以及：

```text
models/query/join.yaml
generators/query/templates/join.yaml
candidates/query/join/
```

---

## 2.9 CoverageClaim / Provenance / Review Contract

`QueryCaseInput` 已支持：

```text
coverage
generation
oracle
validation_evidence
review_evidence
coverage_review
```

并已经定义：

```text
GenerationProvenance
OracleProvenance
ValidationEvidence
ReviewEvidence
CoverageReview
```

旧计划中这部分不再列为待开发。

---

## 2.10 Candidate Lifecycle

当前已经存在：

```text
generated
→ draft
→ review
→ active
```

并实现：

```text
static_validate_candidate()
trial_candidate()
record_review()
promote_candidate()
```

---

## 2.11 Promotion Stale Evidence Gate

已经具备：

```text
semantic_hash stale 检查
static_validation_hash stale 检查
trial artifact hash 检查
review_input_hash stale 检查
coverage review stale 检查
candidate ID consistency
Oracle consistency
```

且框架测试已经覆盖：

```text
修改 SQL 后不能 Promote
修改 CoverageClaim 后不能 Promote
```

这部分设计是正确的。

---

## 2.12 Candidate 已进入 Git

最新提交中：

```text
candidates/query/join/
```

已经包含 22 条 Candidate。

因此：

```text
“Candidate 仍为 untracked”
```

这一旧问题已经解决。

---

# 3. 当前真实状态

当前 JOIN Query Generation 已经达到：

```text
Active Coverage:
17 / 149

Missing Pairwise Requirement Points:
132

Review Candidates:
22

Static Validation:
22 / 22 PASS

Real Xugu Double Trial:
22 / 22 PASS

Double-run Result Hash:
一致

Candidate Status:
review
```

Projected 状态：

```text
22 条 Candidate 全部 Promote 后
→ 149 / 149
→ Gap = 0
```

但这个 `149/149` 当前只能表示：

```text
当前 Test Model 定义下的 pairwise requirement coverage
```

不能直接解释为：

```text
JOIN 功能整体 100% 覆盖
```

---

# 4. 当前最高优先级问题 P0-01
## JOIN Test Model 与 SQL Template 语义不完全一致

这是最新代码审计后发现的最重要问题。

当前模型：

```yaml
null_side:
  values:
    - none
    - left
    - right
    - both
```

但当前 Template 中：

```text
null_side != none
```

主要用于改变左右数据值，使 JOIN 变为匹配或不匹配。

并没有真正按：

```text
left
right
both
```

分别产生明确、独立的 NULL 语义。

---

## 4.1 当前风险

Coverage Engine 会把：

```text
null_side=left
null_side=right
null_side=both
```

当成三个不同 Coverage Value。

但 Template 生成出的 SQL / Expected 并没有稳定地保证：

```text
left
right
both
```

三个声明都被实际表达。

因此可能产生：

```text
CoverageClaim = 已覆盖
```

但实际 SQL 并没有真正测试该语义。

这种问题属于：

```text
False Coverage Claim
```

其严重程度高于普通测试数量不足。

---

## 4.2 必须先决定 null_side 的业务定义

建议不要直接修代码，先写明确语义规范。

例如定义为：

```text
none
= JOIN 输出中不产生 NULL 扩展行

left
= 输出中左侧为 NULL 的 unmatched row

right
= 输出中右侧为 NULL 的 unmatched row

both
= 同一个结果集中同时存在 left-null 和 right-null 行
```

然后校验：

```text
INNER JOIN
是否允许 left/right/both？

LEFT JOIN
是否允许 left？

RIGHT JOIN
是否允许 right？

FULL OUTER JOIN
是否才能表达 both？
```

如果某组合语义本身不可实现：

```text
Constraint Engine
```

必须把它排除。

不要让 Template 静默“近似实现”。

---

# 5. P0-02：重新设计 null_side Constraint

当前 Test Model 对：

```text
join_type
null_side
```

的合法关系还不够精细。

建议显式加入：

```text
INNER JOIN
→ null_side = none

CROSS JOIN
→ null_side = none

LEFT JOIN
→ null_side ∈ {none, right}

RIGHT JOIN
→ null_side ∈ {none, left}

FULL OUTER JOIN
→ null_side ∈ {none, left, right, both}
```

是否采用上述定义，需要以最终测试目的为准。

关键原则：

```text
不能定义 Template 无法忠实表达的合法 Assignment
```

---

# 6. P0-03：predicate=none 命名与实现不一致

当前：

```yaml
predicate:
  values:
    - none
    - equality
    - inequality
    - range
```

但非 CROSS JOIN 时：

```text
predicate = none
```

实际上生成：

```sql
ON 1 = 1
```

它不是：

```text
no predicate
```

而是：

```text
constant true predicate
```

建议二选一。

## 方案 A

把 `none` 只允许给：

```text
CROSS JOIN
```

## 方案 B

改名为：

```text
constant_true
```

然后保留：

```sql
ON 1 = 1
```

推荐优先方案 A，使模型语义更自然。

---

# 7. P0-04：range 语义需要重新定义

当前：

```text
range
```

生成：

```sql
a.k <= b.k
```

这更像：

```text
ordered comparison
```

而不是明确的 Range Join。

如果目标是：

```text
Range Join
```

建议改成真正区间：

```sql
a.k BETWEEN b.low AND b.high
```

或：

```sql
a.k >= b.low
AND a.k < b.high
```

如果只是想覆盖：

```text
<=
```

建议把维度值改名为：

```text
less_equal
```

避免 Coverage 名称与 SQL 意义不一致。

---

# 8. P0-05：增加 Coverage Claim Conformance Tests

当前测试主要验证：

```text
同 Assignment 输出稳定
Candidate 可 round-trip
Lifecycle 可运行
```

但还缺一个非常关键的层：

```text
Assignment
→ SQL
→ Expected
→ CoverageClaim
```

语义一致性测试。

建议新增：

```text
framework_tests/generator/test_join_template_semantics.py
```

至少覆盖：

```text
join_type=inner
→ SQL 必须体现 INNER/JOIN

join_type=left
→ SQL 必须体现 LEFT JOIN

join_type=right
→ SQL 必须体现 RIGHT JOIN

join_type=full
→ SQL 必须体现 FULL OUTER JOIN

join_type=cross
→ SQL 必须体现 CROSS JOIN

predicate=equality
→ ON a.k = b.k

predicate=inequality
→ ON a.k <> b.k

predicate=range/less_equal
→ SQL 真实体现对应语义

null_side=left
→ SQL/Expected 真正出现 left-null 语义

null_side=right
→ SQL/Expected 真正出现 right-null 语义

null_side=both
→ SQL/Expected 真正出现双侧 unmatched 语义

interaction=where
→ WHERE 真实影响查询

interaction=group_by
→ GROUP BY 真实影响查询

interaction=subquery
→ Subquery 真实参与执行
```

---

# 9. P0-06：修模型后必须升级版本

如果修改：

```text
Dimension Value
Constraint
Template SQL semantics
```

不能继续保留：

```text
model_version = 1
template_version = 1
```

应至少：

```text
model_version: "2"
template_version: "2"
```

因为原版本已经生成过：

```text
Candidate ID
Coverage Signature
Generation Provenance
Trial Evidence
```

修改语义后必须产生新的 identity。

---

# 10. P0-07：废弃当前 22 条旧语义 Candidate

如果 JOIN Model / Template 做了语义修正，则当前 22 条：

```text
status = review
```

不能继续沿用旧 Evidence 直接 Promote。

正确方式：

```text
旧 Candidate
→ deprecated / 删除 review candidate
```

然后：

```text
Model v2
Template v2
→ 重新算 Gap
→ 重新生成 Candidate
```

不能手工修改 SQL 后继续复用旧：

```text
trial_run_hash
review evidence
coverage claim
```

---

# 11. P0-08：重新计算 Coverage Gap

修完 Model 后：

```text
149
```

这个 Required Coverage 数量可能发生变化。

所以不要假设修完仍然：

```text
149
```

必须重新执行：

```bash
xgtest model validate models/query/join.yaml

xgtest coverage show query.join --strategy pairwise

xgtest coverage gap query.join --strategy pairwise
```

重新记录：

```text
Required
Covered
Missing
```

---

# 12. P0-09：重新生成 Candidate

运行：

```bash
xgtest generate query.join \
  --strategy pairwise
```

要求：

```text
只针对新 Gap
确定性生成
Case ID 稳定
CoverageClaim 与 Model v2 一致
Template v2 可追溯
```

---

# 13. P0-10：重新 Static Validate

每条 Candidate：

```text
generated
→ static validate
→ draft
```

必须重新生成：

```text
semantic_hash
static_validation_hash
```

旧 Evidence 不允许继承。

---

# 14. P0-11：重新真实 Xugu Trial ×2

修 Model / Template 后：

```text
Candidate
→ Real Xugu Trial #1
→ Real Xugu Trial #2
```

要求：

```text
PASS
Row Count 一致
Result SHA256 一致
Expected PASS
```

通过：

```text
draft
→ review
```

---

# 15. P0-12：Promotion Gate 绑定当前 Contract Set

当前 Trial Artifact 已记录：

```text
contract_set_id
runtime_profile_id
```

但 Promote 阶段当前主要检查：

```text
case_id
semantic_hash
trial result hash
review input hash
```

建议增加：

```text
artifact.contract_set_id
==
current_contract_set_id
```

否则理论上存在：

```text
Contract A 下 Trial PASS
↓
Framework Contract 变成 B
↓
Case semantic_hash 未变化
↓
旧 Trial Artifact 仍可能通过 Promote
```

应该拒绝。

---

# 16. P0-13：Promotion Gate 绑定 Runtime Profile

建议 `promote_candidate()` 增加正式 Profile 输入：

```text
expected_runtime_profile_id
```

校验：

```text
trial_artifact.runtime_profile_id
==
expected_runtime_profile_id
```

这样 Review 绑定的不是抽象：

```text
“某一次 Xugu Trial”
```

而是：

```text
“指定 Runtime Contract 下的 Xugu Trial”
```

---

# 17. P1-01：Trial Artifact 完整 Hash

当前：

```text
trial_run_hash
```

主要 hash：

```text
Run1 Projection
+
Run2 Projection
```

但没有把：

```text
runtime_profile_id
contract_set_id
database_version
driver_version
```

绑定进去。

建议区分：

```text
trial_result_hash
artifact_sha256
```

其中：

```text
trial_result_hash
= 双跑结果投影

artifact_sha256
= 整个 immutable Trial Artifact
```

ReviewEvidence 应优先绑定：

```text
artifact_sha256
```

---

# 18. P1-02：Trial Evidence 持久化

当前：

```text
artifacts/
```

被 `.gitignore` 忽略。

本地 Fail Closed 是正确的，但跨机器协作能力不足。

推荐最终：

```text
Raw Artifact
→ MinIO / S3 / 内部制品库

Git Candidate
→ artifact URI
→ sha256
```

MVP 过渡方案：

```text
acceptance/query-generation-mvp/
```

保存小型不可变摘要：

```text
runtime-profile-summary.json
trial-run-index.json
coverage-summary.json
final-acceptance.json
```

Raw 日志仍不进 Git。

---

# 19. P1-03：G0A Acceptance 文档必须更新

当前：

```text
docs/G0A_ACCEPTANCE.md
```

仍然是旧状态：

```text
2026-09-24
HOLD
旧 contract_set_id
113 tests
数据库只读阻塞
DDL/write blocked
```

但最新：

```text
docs/g0a/contract-descriptor-candidate.json
```

已经是新的 Contract Set。

因此文档当前已经 stale。

必须重新生成：

```text
G0A Acceptance Snapshot
```

但不要因为 Query Generation 已完成就直接宣布：

```text
FREEZE
```

Freeze 必须按原 G0A Gate 重新判断。

---

# 20. P1-04：重新判断 G0A Freeze 条件

建议重新跑：

```text
Registry Validate
Schema Export Verify
Framework Tests
Contract Verify
Runtime Profile Build
Real Driver Probe
Type Mapping Probe
Transaction Probe
Error Mapping Probe
Original MVP Cases
Cleanup Verification
```

然后重新决定：

```text
HOLD
或
FREEZE
```

不要继续引用旧 Acceptance 文档中的 ID。

---

# 21. P1-05：Contract Set 边界优化

当前 `contract_set.py` 已把：

```text
src/xgtest/design
src/xgtest/generator
framework_tests/design
framework_tests/generator
models
generators
```

全部纳入 `contract_set_id`。

这会导致：

```text
改 JOIN Test Model
↓
contract_set_id 变化
↓
Runtime Profile contract binding 变化
```

长期建议拆分：

```text
core_contract_set_id
runtime_contract_id
test_model_id / model_hash
generator_contract_id
source_snapshot_hash
```

尤其：

```text
models/
generators/
```

更适合作为 Test Asset Identity，而不是 G0A Core Runtime Contract。

---

# 22. P1-06：CI 已存在，但需要真正形成 Gate

当前已经有：

```text
.github/workflows/contract.yml
```

运行：

```text
pytest -m "not xugu_integration"
registry validate
registry generate-enums
schema export
git diff
```

所以“没有 CI”已经不准确。

但最新 `fbef123` 当前没有可见：

```text
combined status
workflow run
```

并且：

```text
main protected = false
```

因此：

```text
CI 配置存在
≠
CI 已形成工程强制门禁
```

---

# 23. P1-07：Branch Protection

建议对：

```text
main
```

开启：

```text
Require Pull Request
Require Status Checks
No Direct Push
```

Candidate Review / Promotion 已经进入资产治理阶段，不应继续仅靠人工约定。

---

# 24. P1-08：前端 Build 纳入 CI

现在仓库已经正式包含 Vue UI。

现有 Workflow 没有验证：

```text
npm install
TypeScript
Vite Build
```

建议新增：

```bash
cd webui
npm ci
npm run build
```

否则：

```text
Python CI PASS
```

并不能证明前端可以构建。

---

# 25. P1-09：清理前端构建缓存文件

当前仓库已经跟踪：

```text
.vite/deps/_metadata.json
.vite/deps/package.json
webui/tsconfig.node.tsbuildinfo
```

这些属于生成缓存。

建议 `.gitignore` 增加：

```gitignore
.vite/
*.tsbuildinfo
```

然后从 Git Index 删除已跟踪文件。

---

# 26. P1-10：真实 Xugu Integration Test 扩展

当前：

```text
framework_tests/generator/test_real_xugu_acceptance.py
```

真实数据库自动集成测试生成：

```text
limit=5
```

所以自动测试只验证 5 条 Candidate。

建议保留两级：

```text
CI Real DB Smoke
= 5 条

Formal Acceptance
= 当前全部 Gap Candidates
```

有稳定专用测试库以后，再考虑将全量 Candidate 纳入自动 Integration。

---

# 27. P1-11：Run History 并发安全

当前 `index.json` 写入使用原子 replace，这对单写进程很好。

但未来多个：

```text
Runner
Worker
API-triggered Run
```

可能同时更新 History Index。

后续应增加：

```text
File Lock
或
Result DB
```

MVP 当前单机串行运行下不阻塞。

---

# 28. P1-12：host_hash 隐私/稳定性优化

当前：

```text
host_hash = SHA256(host)
```

对于低熵主机名或固定内网 IP，有被字典反推的可能。

长期建议：

```text
HMAC(host, deployment_secret)
```

或者直接使用：

```text
target_id
```

Web 层只展示匿名 Target Alias。

---

# 29. P2-01：Full Session Reset

当前 Query 采用：

```text
one case
→ one child process
→ one connection
→ close
```

因此：

```text
Full Session Reset
```

当前不是硬阻塞。

但如果未来启用：

```text
Connection Pool
Session Reuse
Worker Reuse
```

就必须验证：

```text
transaction
schema
role
session parameter
temp object
lock
cursor
```

完整 reset 语义。

---

# 30. P2-02：Driver Cancel / Server-side Stop Proof

当前进程隔离已经保证 Framework 不永久挂死。

Cancel 的后续价值主要是：

```text
减少服务端残留 SQL
减少长事务
减少资源占用
```

Probe 应真实验证：

```text
发起长查询
→ cancel()
→ 查看 server session
→ SQL 确认停止
```

而不是只检查：

```text
driver.cancel() method exists
```

---

# 31. P2-03：Batch Promotion 原子性

当前：

```text
candidate promote CASE_ID
```

是一条一条 Promote。

22 条批量 Promote 时可能出现：

```text
前 10 条已 active
第 11 条失败
剩余未 Promote
```

长期建议增加：

```text
promotion plan
preflight validation
batch commit
```

至少先实现：

```text
--dry-run
```

提前验证全部 Candidate 是否可 Promote。

---

# 32. P2-04：Web Coverage 页面

当前 Web UI 已有基础 Dashboard。

下一阶段增加：

```text
Coverage Overview
Coverage Matrix
Coverage Gap
Model Detail
```

展示：

```text
required
covered
missing
strategy
model_version
```

注意 UI 不允许自己重算 Coverage。

---

# 33. P2-05：Web Candidate 页面

增加：

```text
Candidate List
Candidate Detail
Coverage Assignment
Generated SQL
Expected
Trial Evidence
Review Status
```

第一版仍保持只读。

---

# 34. P2-06：Web Review / Promote

只有以下 Core API 稳定后：

```text
Review Evidence
Promotion Gate
Artifact Store
Auth / Audit
```

才增加 Web 操作：

```text
Review
Reject
Promote
```

UI 不自行写 YAML，不自行计算 Hash。

---

# 35. 当前 MVP 正确的实施顺序

推荐从现在开始严格按以下顺序：

```text
STEP 1
写 JOIN Dimension Semantic Specification

STEP 2
修 null_side 定义与 Constraint

STEP 3
修 predicate=none 语义

STEP 4
修 range 命名或实现

STEP 5
新增 Coverage Claim Conformance Tests

STEP 6
Model Version bump

STEP 7
Template Version bump

STEP 8
重新计算 Required Coverage

STEP 9
废弃当前旧语义 22 Candidate

STEP 10
重新生成 Candidate

STEP 11
Static Validate

STEP 12
真实 Xugu Trial ×2

STEP 13
Promotion Gate 增加 contract_set_id 检查

STEP 14
Promotion Gate 增加 runtime_profile_id 检查

STEP 15
真实人工 Review

STEP 16
生成 Review Evidence / Coverage Review Evidence

STEP 17
Promotion Preflight

STEP 18
Promote

STEP 19
全量 cases/query 正式 Regression

STEP 20
重新计算 Active Pairwise Coverage

STEP 21
生成 Final Coverage Snapshot

STEP 22
更新 Final Acceptance

STEP 23
更新 G0A Acceptance

STEP 24
完善 CI / Branch Protection

STEP 25
再扩 Web Coverage / Candidate 页面
```

---

# 36. 修正后最终验收场景

必须完整跑通：

```text
JOIN Model v2
        ↓
Constraint Validate
        ↓
Pairwise Required Coverage
        ↓
Active Coverage
        ↓
Gap
        ↓
Deterministic Candidate
        ↓
Coverage Semantic Conformance
        ↓
Static Validate
        ↓
Real Xugu Trial #1
        ↓
Real Xugu Trial #2
        ↓
Contract/Profile Evidence Binding
        ↓
Human Review
        ↓
Coverage Review
        ↓
Promotion Gate
        ↓
Active Case
        ↓
Full Query Regression
        ↓
Active Coverage Snapshot
        ↓
Gap = 0
```

---

# 37. Query Execution MVP 最新 DoD

- [x] Query Loader
- [x] Typed Query Model
- [x] Read-only SQL Boundary
- [x] Database Read-only Session
- [x] Exact
- [x] RowSort
- [x] SHA256
- [x] Expected Error
- [x] Runtime Profile
- [x] Regression Strict Profile
- [x] Process-isolated Timeout
- [x] Timeout Report
- [x] Result Git Commit
- [x] Source File / Source Hash
- [x] Run History
- [x] FastAPI Read-only API
- [x] Vue Read-only Dashboard
- [ ] Driver Cancel Stop Proof
- [ ] Server-side Stop Proof
- [ ] Full Session Reset（连接复用前）
- [ ] Result DB（后续阶段）

---

# 38. Query Generation Framework 最新 DoD

- [x] Test Model
- [x] Dimension
- [x] Value
- [x] Constraint
- [x] all_values
- [x] pairwise
- [x] CoverageSource Interface
- [x] Required Coverage
- [x] Active Coverage
- [x] Coverage Gap
- [x] Deterministic Greedy Candidate Selection
- [x] Stable Candidate ID
- [x] Generation Provenance
- [x] Oracle Provenance
- [x] Dedup
- [x] Static Validation
- [x] Trial Run ×2
- [x] Review Evidence Contract
- [x] Coverage Review Contract
- [x] Promotion Gate
- [x] Semantic stale rejection
- [x] Coverage stale rejection
- [x] Candidate Git Tracking
- [ ] JOIN Dimension-to-SQL 语义完全可信
- [ ] Coverage Claim Conformance Tests
- [ ] Trial Evidence Contract Set Binding
- [ ] Trial Evidence Runtime Profile Binding
- [ ] Real Human Review
- [ ] Real Promote
- [ ] Post-Promotion Full Regression
- [ ] Final Active Coverage Snapshot
- [ ] Final Acceptance

---

# 39. Web MVP 最新 DoD

- [x] FastAPI
- [x] Run List API
- [x] Run Detail API
- [x] Case Detail API
- [x] Runtime Profile API
- [x] Runtime Type Support API
- [x] Vue App
- [x] Dashboard
- [x] Run List
- [x] Run Detail
- [x] Case Detail
- [x] Runtime View
- [ ] Coverage View
- [ ] Coverage Gap View
- [ ] Candidate View
- [ ] Trial Evidence View
- [ ] Review Status View
- [ ] Frontend Build CI
- [ ] Web Review / Promote（后续）

---

# 40. CI / Repository 最新 DoD

- [x] GitHub Workflow 文件存在
- [x] Python Framework Tests 已配置
- [x] Registry Validate
- [x] Schema Export Check
- [ ] 最新 Commit 有可见 Workflow PASS 证据
- [ ] Frontend Build CI
- [ ] Candidate / Coverage 专项 CI Command
- [ ] main Branch Protection
- [ ] Required Status Checks
- [ ] 清理 `.vite/`
- [ ] 清理 `*.tsbuildinfo`

---

# 41. 当前真正的 P0 / P1 / P2

## P0

```text
JOIN null_side 语义修正
predicate=none 语义修正
range 语义修正
CoverageClaim Conformance Tests
Model/Template Version bump
重新生成 Candidate
重新真实 Xugu 双跑
Promotion 绑定 current contract_set_id
Promotion 绑定 runtime_profile_id
真实 Review
Promote
Full Regression
Final Active Coverage Snapshot
```

## P1

```text
完整 Trial Artifact Hash
Artifact durable storage
更新 G0A Acceptance
重新评估 G0A Freeze
Contract Set Identity 分层
CI Required Gate
Branch Protection
Frontend Build CI
清理 Vite/TS 缓存
全量 Real Acceptance 自动化
Run History 并发安全
Host Identity 隐私优化
```

## P2

```text
Cancel Server-side Proof
Full Session Reset
Batch Promotion
Coverage Web UI
Candidate Web UI
Review/Promote Web UI
Catalog2
Selector
TestPlan
Result DB
Baseline
Delta
Quality Gate
```

---

# 42. 当前项目重新评价

## Query Execution MVP

当前已经达到较高完成度：

```text
Process Isolation
Timeout
Read-only
Runtime Contract
Result Provenance
Run History
Web API
Web UI
```

其剩余问题主要已经从“基础可用性”转成：

```text
Driver cancel proof
长期存储
分布式阶段准备
```

---

## Query Generation Framework

框架设计本身已经基本验证：

```text
Model
→ Coverage
→ Gap
→ Candidate
→ Validate
→ Trial
→ Review
→ Promote
```

链路是真实存在的。

当前最需要提升的是：

```text
Test Model 语义质量
```

而不是继续增加框架层。

---

# 43. 当前最重要原则

现在不要优先扩：

```text
Filter
Aggregate
Subquery
Window
CTE
```

也不要因为：

```text
Projected 149/149
```

就立即宣布 JOIN Coverage 完成。

当前最重要的是先证明：

```text
CoverageClaim
=
实际 SQL 测试语义
```

只有这件事成立：

```text
Pairwise 100%
```

才有真正意义。

---

# 44. 下一阶段完成标志

当以下全部满足时，可以正式宣布：

```text
Query Generation MVP = DONE
```

条件：

```text
1. JOIN Model 语义经过校准
2. Template 能忠实表达每个合法 Dimension Value
3. Coverage Claim Conformance Tests PASS
4. 新 Candidate 全部 Static Validate PASS
5. 新 Candidate 全部真实 Xugu 双跑 PASS
6. Trial Evidence 与 Contract/Profile 绑定
7. Human Review 完成
8. Coverage Review 完成
9. Promotion Gate PASS
10. Active Promotion 完成
11. 全量 Query Regression PASS
12. Active Pairwise Gap = 0
13. Final Acceptance 可追溯
14. README / G0A Acceptance 不再 stale
```

---

# 45. 后续扩 Feature 的条件

只有 JOIN MVP 真正 DONE 后，再依次扩：

```text
1. Filter
2. Aggregate
3. Set Operation
4. Subquery
5. CTE
6. Window
7. Complex Query
```

每个 Feature 都必须重复相同闭环：

```text
Semantic Model
→ Constraint
→ Coverage
→ Gap
→ Template
→ Conformance Test
→ Candidate
→ Trial
→ Review
→ Active
```

禁止回退成：

```text
写模板
→ 批量生成 SQL
→ 直接执行
```

---

# 46. 最终路线

```text
当前 fbef123
    ↓
JOIN Semantic Calibration
    ↓
Coverage Conformance
    ↓
Model / Template v2
    ↓
New Gap
    ↓
New Candidates
    ↓
Real Xugu Trial ×2
    ↓
Evidence Contract/Profile Binding
    ↓
Human Review
    ↓
Promotion
    ↓
Full Regression
    ↓
Final Pairwise Snapshot
    ↓
Query Generation MVP DONE
    ↓
CI / G0A / Artifact Governance 收口
    ↓
Coverage / Candidate Web UI
    ↓
扩其他 Query Feature
    ↓
Catalog2 / Selector / TestPlan
    ↓
Distributed Execution
    ↓
Result DB / Baseline / Delta / Quality Gate
```

---

# 47. 本版与上一版计划的核心差异

上一版仍把很多已经完成的能力列为待实现。

本次最新代码确认后，应删除这些旧 TODO：

```text
Query Timeout
Process Isolation
Run History
Result Git Commit
Source Hash
Strict Runtime Profile
FastAPI
Vue Dashboard
CoverageClaim
Generation Provenance
Test Model
Constraint
Pairwise
Coverage Gap
Candidate Generator
Dedup
Static Validate
Trial Run ×2
Review Evidence Contract
Promotion Gate
Candidate Git Tracking
```

当前真正的主线已经变成：

```text
“把框架做出来”
```

转为：

```text
“证明生成出来的 Coverage 是真实可信的”
```

这是项目进入下一成熟阶段的重要变化。
