# XG DB Test MVP 后续完整实施计划
## 基于当前 Query MVP + Query Generation MVP Review Gate 状态

> 当前远端主干基线：`main@927d883c669735c4192183d98d51b18782eb72be`
> 当前本地阶段状态：22 条 pairwise 缺口候选已生成、静态校验并在真实 Xugu 上双跑通过，均处于 `review`；尚未完成真实评审、晋升、晋升后正式回归和最终覆盖快照。
> 本文目标：统一整理 MVP 未完成能力、问题项、优化改进项、实施顺序和验收门禁。

---

# 1. 当前阶段判断

项目当前已形成：

```text
Query Execution MVP
+
Query Generation MVP
```

Query Generation 已经跑通：

```text
Test Model
→ Constraint
→ Pairwise
→ Active Coverage
→ Coverage Gap
→ Candidate Generation
→ Static Validate
→ Real Xugu Trial Run ×2
→ review
```

因此当前状态应定义为：

```text
Query Generation MVP = Review Gate / RC
```

还不能定义为 DONE，因为仍缺：

```text
真实 Review
→ Review Evidence
→ Promote
→ Active Case
→ Full Regression
→ Active Coverage Snapshot
→ Final Acceptance
```

---

# 2. 当前已完成能力

## 2.1 Query Execution

已具备：

```text
Query YAML
→ Query Loader
→ Typed QueryCaseInput
→ QueryRunner
→ Xugu Adapter
→ Type Mapping
→ Canonical
→ Comparator
→ QueryRunReport
```

支持：

```text
exact
rowsort
sha256
expected_error
```

## 2.2 Runtime Profile

已验证：

```text
连接
事务 commit
事务 rollback
基本类型读取
SQL 错误映射
测试表创建与清理
```

并已据此生成 Runtime Profile。

## 2.3 Query Generation

已完成：

```text
Test Model
Dimension / Value
Constraint
Pairwise Strategy
Existing Active Coverage
Coverage Gap
Candidate Generation
Static Validate
Trial Run
Determinism Check
Projected Coverage
```

## 2.4 当前候选状态

```text
Active Coverage        17 / 149
Missing                132
Pairwise Candidates    22
Static Validate        22 / 22 PASS
Real Xugu Trial        22 / 22 PASS
Double-run Hash        22 / 22 MATCH
Candidate Status       review

Projected Coverage     149 / 149
Projected Gap          0
```

这里的 `149` 必须明确表示 **pairwise coverage requirement points**，不是 149 条 Case。


# 3. MVP 未完成能力总表

| 优先级 | 未完成项 | 当前状态 | 是否阻塞 MVP Done |
|---|---|---|---|
| P0 | Candidate 纳入 Git | 未跟踪 | 是 |
| P0 | 真实人工 Review | 未完成 | 是 |
| P0 | Review Evidence | 未完成 | 是 |
| P0 | Coverage Review Evidence | 未完成 | 是 |
| P0 | Promote 到 Active | 未完成 | 是 |
| P0 | 晋升后 Full Regression | 未完成 | 是 |
| P0 | 晋升后 Active Coverage Snapshot | 未完成 | 是 |
| P0 | Final Acceptance Summary | 未完成 | 是 |
| P0 | Query Timeout / Stop Safety | 未完全收口 | 建议阻塞正式 v0.1 |
| P1 | Cancel Stop Proof | UNKNOWN | 阻塞完整 Runtime 能力声明 |
| P1 | Full Session Reset | UNKNOWN | 当前 one-case-one-session 下非硬阻塞 |
| P1 | NUMERIC 精度问题 | LOSSY | 需显式 UNSUPPORTED |
| P1 | Acceptance Evidence 持久化 | raw artifacts 被忽略 | 必须改进 |
| P1 | GitHub CI | 尚无有效 Workflow Gate | 强烈建议 |
| P1 | main Branch Protection | 未启用 | 强烈建议 |
| P1 | Result Provenance | 需增强 | 建议补 |
| P1 | Run History | 不完整 | 建议补 |
| P1 | Web Read-only Dashboard | 未实现 | 非核心阻塞 |
| P2 | Catalog2 | 未实现 | 后续 |
| P2 | Selector / TestPlan | 未实现 | 后续 |
| P2 | Multi-worker | 未正式进入 | 后续 |
| P2 | Allure / JUnit | 未完整接入 | 后续 |
| P2 | Result DB | 未实现 | 后续 |
| P2 | Baseline / Delta | 未实现 | 后续 |

---

# 4. 第一阶段：Candidate Git 化

当前 `candidates/query/join/` 仍是 untracked，但状态已经是 `review`，这会导致生命周期状态与 Git 资产状态不一致。

建议：

```bash
git checkout -b feature/query-generation-review
git add candidates/query/join
git commit -m "test: add join generation review candidates"
```

此时仍然不要直接进入 `cases/query/`。

验收要求：

```text
22 Candidate 全部进入 Git
每条 Candidate 有稳定 Case ID
每条 Candidate 有 CoverageClaim
每条 Candidate 有 Generation Provenance
每条 Candidate 有 Oracle Provenance
每条 Candidate status = review
```

---

# 5. 第二阶段：固化 Trial Run Evidence

Raw Artifact 继续放：

```text
artifacts/
```

并继续由 `.gitignore` 忽略，这没有问题。

但必须新增 Git 可追溯的发布证据摘要：

```text
acceptance/
└── query-generation-mvp/
    ├── acceptance-summary.json
    ├── runtime-profile.json
    ├── trial-run-index.json
    └── coverage-summary.json
```

`trial-run-index.json` 建议记录：

```text
git_commit
contract_set_id
runtime_profile_id
case_id
semantic_hash
run1_result_hash
run2_result_hash
trial_run_hash
status
```

这样 Raw Evidence 不进 Git，但 Git 中仍然保留不可变引用和 SHA256。


# 6. 第三阶段：真实 Candidate Review

每一条 Candidate 至少审查：

```text
Case ID
测试目的
Feature/Subfeature
Dimension Assignment
Constraint 合法性
CoverageClaim
assertion_refs
SQL 是否真实体现 CoverageClaim
Expected 是否正确
Oracle Provenance
Comparison Mode
是否重复
Trial Run Evidence
可重复性
可读性
```

最关键的是校验：

```text
CoverageClaim
↔ SQL
↔ Expected
```

三者必须一致。

例如声明：

```text
join_type = left
datatype = varchar
null_side = right
```

SQL 中就必须真的存在：

```text
LEFT JOIN
字符串/VARCHAR 数据
右侧未匹配产生 NULL
```

否则属于 Coverage False Claim。

---

# 7. 第四阶段：Review Evidence

不能只写一个 reviewer 字段。

建议保存：

```text
case_id
semantic_hash
coverage_review_input_hash
trial_run_hash
reviewer
review_reference
reviewed_at
decision
```

并且拆分：

```text
Execution Review
Coverage Review
```

因为 SQL 不变但 CoverageClaim 改变时，执行 Trial 可能仍有效，但 Coverage Review 必须重新做。

---

# 8. 第五阶段：Promotion Gate

Promote 必须验证全部条件：

```text
status = review
Static Validate PASS
Trial Evidence 有效
Review Evidence 有效
Coverage Review 有效
Oracle Provenance 存在
Model Version 一致
Template Version 可追溯
semantic_hash 一致
coverage_review_input_hash 一致
```

最关键的 Gate：

```text
current_semantic_hash
=
trial_run.semantic_hash
=
review.semantic_hash
```

同时：

```text
current_coverage_review_input_hash
=
coverage_review.review_input_hash
```

任意一个不一致：

```text
PROMOTION_REJECTED
```

---

# 9. 第六阶段：Promote Candidate

通过 Promotion Gate 后：

```text
review → active
```

MVP 当前可采用：

```text
candidates/query/join/
→
cases/query/
```

并更新：

```yaml
status: active
```

未来 Catalog2 上线后再改为 Catalog 驱动，不要把这一步的业务规则写死在文件移动逻辑里。

---

# 10. 第七阶段：晋升后全量正式回归

不要只跑新增 22 条 Candidate。

必须执行：

```text
全部 cases/query/
```

并使用：

```text
正式 Runtime Profile
正式 Contract Set
正式 Active Assets
```

确保：

```text
旧 Case
+
新 Case
```

一起执行仍然全部稳定。

---

# 11. 第八阶段：Active Coverage Snapshot

晋升后重新计算：

```text
Active Coverage
```

目标：

```text
query.join pairwise
149 / 149
gap = 0
```

建议输出：

```json
{
  "model_id": "query.join",
  "model_version": "1",
  "strategy": "pairwise",
  "required_points": 149,
  "active_covered_points": 149,
  "gap_points": 0
}
```

注意只能称为：

```text
query.join pairwise model coverage = 100%
```

不要称：

```text
JOIN 功能覆盖率 = 100%
```

因为 pairwise 100% 不等于 Boundary、Negative、Interaction、Bug Regression 全部覆盖。

---

# 12. 第九阶段：Final Acceptance

生成：

```text
acceptance/query-generation-mvp/final-acceptance.json
```

至少记录：

```text
git_commit
contract_set_id
runtime_profile_id
model_id
model_version
generator_version
template_version
candidate_count
promoted_count
active_case_count
pairwise_required_points
pairwise_covered_points
pairwise_gap_points
regression_pass
regression_fail
regression_error
regression_timeout
framework_tests
schema_verify
contract_verify
runtime_profile_verify
```


# 13. Query Timeout / Stop Safety

这是 Query Execution MVP 最大的未收口项之一。

目前虽然 Case 有 `timeout`，但 Cancel/Stop Proof 尚未验证。

目标至少做到：

```text
超时
→ TIMEOUT
→ connection discard
→ 不复用不确定状态连接
```

长期推荐：

```text
Parent Process
→ Worker Process
→ Driver Query
```

超时：

```text
terminate Worker
→ discard connection
```

比线程方案更可靠。

---

# 14. Cancel 能力验证

Probe 应验证：

```text
长查询
锁等待
driver.cancel()
服务端 session 状态
SQL 是否真的停止
```

不能只验证：

```text
cancel() 调用返回成功
```

必须证明：

```text
server-side execution stopped
```

---

# 15. Full Session Reset

当前 one-case-one-session：

```text
open
→ query
→ rollback
→ close
```

因此 Full Reset 不是当前 Query MVP 的硬阻塞。

但未来如果启用：

```text
Connection Pool
Session Reuse
```

就必须验证：

```text
transaction state
schema
role
temp object
session parameter
lock
cursor
```

是否完全恢复。

---

# 16. NUMERIC → float 问题

已确认：

```text
NUMERIC
→ Python float
```

应明确标记：

```text
mapping_fidelity = LOSSY
support_status = UNSUPPORTED
```

不要因为能编码为 float 就认为支持 exact semantic comparison。

正式 Generator 的 datatype 维度只能从：

```text
support_status = SUPPORTED
```

中选值。

---

# 17. Runtime Profile 严格模式

建议增加两个模式。

## diagnostic

```text
runtime_profile optional
```

用于：

```text
开发
probe
临时验证
```

## regression

```text
runtime_profile required
```

并校验：

```text
database
driver
contract_set_id
runtime_profile_id
type_support
```

正式回归默认使用 regression。

---

# 18. Result Provenance

建议 QueryRunReport 增加：

```text
git_commit
source_snapshot_hash
```

QueryCaseReport 增加：

```text
source_file
source_hash
semantic_hash
```

形成：

```text
Run
→ Git Commit
→ Case Source
→ Semantic Hash
```

的完整追溯链。

---

# 19. Run History

建议：

```text
artifacts/runs/
├── index.json
├── run-001.json
└── run-002.json
```

后续 Web UI、Baseline、Delta 都直接建立在这一层之上。

---

# 20. QueryRunner 模块拆分

建议保持职责单一：

```text
query/
├── loader.py
├── runner.py
├── timeout.py
├── result.py
├── history.py
└── service.py
```

不要把 timeout、history、web、report 都继续塞进 runner。

---

# 21. Generator 与 Runner 边界

必须长期保持：

```text
Generator
= 决定应该产生什么 Case

Runner
= 执行已经确定的 Active Case
```

禁止：

```text
正式 Regression 时 Runtime 随机生成 SQL
```

正式发布测试始终执行：

```text
Git 中经过 Review 的 active Case
```

---

# 22. CoverageSource 抽象

当前 MVP 可以扫描 `cases/query`，但 Coverage Engine 不要直接绑定目录。

建议：

```python
class CoverageSource(Protocol):
    def active_claims(self, model_id: str):
        ...
```

当前：

```text
FileCoverageSource
```

未来：

```text
CatalogCoverageSource
```

这样 Catalog2 上线后 Coverage Engine 不需要重写。

---

# 23. CandidateStore 抽象

建议：

```python
class CandidateStore(Protocol):
    def list(...)
    def save(...)
    def promote(...)
```

当前：

```text
FileCandidateStore
```

未来再替换为：

```text
Git/Catalog-backed CandidateStore
```


# 24. GitHub CI

当前项目已经进入正式资产 Review 阶段，CI 应尽快变成强制门禁。

最低 CI：

```text
pytest
registry validate
schema verify
contract verify
query validate
candidate validate
```

后续加入：

```text
coverage model validate
generation golden tests
```

---

# 25. Branch Protection

建议 main 开启：

```text
Require Pull Request
Require Status Checks
No Direct Push
```

否则 Review Gate 只存在于文档约定中，而没有工程强制。

---

# 26. Commit 粒度

后续建议：

```text
test: add reviewed join generation candidates
feat: publish query generation acceptance evidence
feat: add review evidence validation
feat: add candidate promotion gate
test: promote reviewed join candidates
test: run post-promotion query regression
feat: persist active coverage snapshots
fix: mark numeric mapping as lossy unsupported
feat: enforce regression runtime profiles
fix: add query timeout isolation
ci: add contract and query validation workflow
```

要求始终保持：

```text
一个问题
+
一个实现目标
+
一组测试
```

---

# 27. Query Generation MVP 最终 DoD

- [x] Test Model
- [x] Dimension / Value
- [x] Constraint
- [x] Pairwise
- [x] Existing Active Coverage
- [x] Coverage Gap
- [x] Candidate Generation
- [x] Static Validate
- [x] Real Xugu Trial ×2
- [x] Result Hash Match
- [ ] Candidate Git Tracking
- [ ] Human Review
- [ ] Review Evidence
- [ ] Coverage Review Evidence
- [ ] Promotion Gate
- [ ] Promote
- [ ] Full Regression
- [ ] Active Coverage 149/149
- [ ] Final Coverage Snapshot
- [ ] Final Acceptance Summary

---

# 28. Query Execution MVP 最终 DoD

- [x] Query Loader
- [x] Typed Models
- [x] Xugu Adapter
- [x] Exact
- [x] RowSort
- [x] SHA256
- [x] Expected Error
- [x] Runtime Profile
- [x] Real Connection Probe
- [x] Commit/Rollback Probe
- [x] SQL Error Mapping
- [ ] Timeout Stop Safety
- [ ] Cancel Stop Proof
- [ ] Formal Run History
- [ ] Result Git Provenance
- [ ] Strict Regression Runtime Profile

---

# 29. 推荐下一轮严格执行顺序

```text
STEP 1
提交 22 条 review Candidate 到 Git

STEP 2
发布 Runtime Profile / Trial Evidence Index

STEP 3
执行人工 Review

STEP 4
生成 Execution Review Evidence

STEP 5
生成 Coverage Review Evidence

STEP 6
运行 Promotion Gate

STEP 7
Promote 22 条 Candidate

STEP 8
全量 cases/query 静态校验

STEP 9
真实 Xugu Full Regression

STEP 10
重新计算 Active Coverage

STEP 11
生成 149/149 Coverage Snapshot

STEP 12
生成 Final Acceptance Summary

STEP 13
修正 NUMERIC Runtime Profile 为 LOSSY/UNSUPPORTED

STEP 14
增加 strict regression mode

STEP 15
补 Timeout Isolation / Cancel Stop Proof

STEP 16
增加 Result Provenance / Run History

STEP 17
增加 GitHub CI

STEP 18
开启 main Branch Protection

STEP 19
再开始 Read-only Web Dashboard
```

---

# 30. 前端实施时机

前端不应阻塞 Query Generation MVP 收尾。

Core 完成后先做只读：

```text
Dashboard
Run History
Case Detail
Runtime Profile
Type Support
Coverage
Coverage Gap
Candidate Status
```

等：

```text
Timeout
Promotion
Review
```

都稳定后，再增加：

```text
Candidate Review
Promote
Run Trigger
```

UI 只调用 Core API，不得自行实现：

```text
Coverage Calculation
Review Logic
Promotion Logic
PASS/FAIL 判定
```

---

# 31. MVP 完成后的完整架构恢复顺序

Query MVP 和 Generation MVP 完成后，继续原总架构：

```text
XGT Parser
→ Metadata Resolver
→ Compiler
→ Catalog2
→ Selector
→ TestPlan
```

之后：

```text
Worker Pool
→ Agent
→ Scheduler
→ Multi Cluster
→ Lease/Fencing
```

最后：

```text
Result DB
→ Baseline
→ Delta
→ Quality Gate
→ Dashboard
```

---

# 32. 最终目标状态

完成本计划后应达到：

```text
Query Execution MVP = DONE
Query Generation MVP = DONE

query.join pairwise coverage = 149 / 149
gap = 0

Candidate Lifecycle = 可实际使用
Runtime Profile = 有真实证据
Review = 有可追溯 Evidence
Regression = 有真实 Xugu 结果
CI = 有工程门禁
```

项目将从：

```text
“能跑 SQL 的测试程序”
```

进入：

```text
“具备用例设计、覆盖分析、候选生成、评审准入、真实回归和资产治理能力的 Query 测试平台 MVP”
```

---

# 33. 最重要的实施原则

当前不要继续优先增加更多模板、更多 Feature、更多 Case。

优先完成：

```text
资产治理闭环
+
证据闭环
+
执行安全闭环
```

即：

```text
Candidate
→ Review
→ Active
→ Regression
→ Coverage
→ Evidence
```

这条链一旦做扎实，后续：

```text
Filter
Aggregate
Subquery
Window
CTE
```

主要只是扩展 Test Model 与 Template，而不是重新设计框架。
