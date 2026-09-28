# XG DB Test Query Generation MVP 完整实施步骤计划

> 基线仓库：`xunyuxingkong/allone`  
> 当前基线提交：`927d883c669735c4192183d98d51b18782eb72be`  
> 当前能力：单机 Query MVP 已具备 Loader / Runner / Comparator / Result / CLI / Runtime Profile / Contract Identity  
> 本文目标：在不推翻现有 Query MVP 的前提下，实现 **Test Model → Coverage Gap → Template Generator → Candidate → Static Validate → Trial Run → Review → Active Case** 的最小完整闭环。  
> 推荐定位：**Query Generation MVP / Phase-2 Vertical Slice**  
> 第一验证 Feature：**JOIN**

---

# 1. 最终目标

本阶段不是做“SQL 批量生成器”，而是实现原完整架构中的用例生成核心逻辑：

```text
定义功能维度
    ↓
定义取值
    ↓
定义组合约束
    ↓
定义覆盖策略
    ↓
计算应该覆盖的组合
    ↓
读取已有 Active Case 的 CoverageClaim
    ↓
计算 Coverage Gap
    ↓
只针对 Gap 生成 Candidate
    ↓
去重
    ↓
静态校验
    ↓
Trial Run
    ↓
Review
    ↓
Promote
    ↓
Active Case
    ↓
正式 Query Regression
    ↓
Coverage Snapshot
    ↓
形成新的 Coverage Gap
```

核心原则：

```text
Generator 不追求生成数量
Generator 只为 Coverage Gap 服务
```

---

# 2. 本阶段范围

## 2.1 必须实现

本次 Query Generation MVP 必须具备：

```text
1. Query Case 能声明 CoverageClaim
2. 结构化 Generation Provenance
3. Query Test Model
4. Dimension / Value
5. Constraint
6. Coverage Strategy
7. Required Coverage Set
8. Existing Active Coverage
9. Coverage Gap
10. Deterministic Template
11. Candidate Generation
12. Candidate Deduplication
13. Static Validation
14. Trial Run
15. Review Evidence
16. generated → draft → review → active
17. Candidate Promote
18. Coverage Snapshot
19. CLI
20. Framework Tests
```

## 2.2 第一版只实现的策略

第一版只正式实现：

```text
all_values
pairwise
```

接口预留：

```text
boundary
negative
interaction
```

但不要求第一版完成。

## 2.3 第一版只做一个真实 Feature

第一纵向切片：

```text
query.join
```

暂不同时实现：

```text
filter
aggregate
set
subquery
window
cte
```

JOIN 闭环完成后，再复用同一框架扩展。

## 2.4 明确不做

本阶段不做：

```text
AI 自动生成 SQL
SQLancer 接入
随机 SQL Runtime Generation
完整 Catalog2
完整 Selector
完整 TestPlan
多集群
Agent
Scheduler
Lease/Fencing
复杂 Web 审批平台
自动 Oracle 推断
自动把 Xugu 实际结果当 Expected
```

---

# 3. 先完成 Query MVP 前置收口

Query Generation 建议建立在 Query Runner 已经可靠的基础上。

在开始 Generator 前，先完成以下两个 P0：

```text
P0-01 Query Timeout
P0-02 Real Xugu Query Acceptance
```

推荐顺序：

```text
Timeout
→ Real Xugu Acceptance
→ Query Generation MVP
```

原因：

```text
Candidate Trial Run
依赖 QueryRunner

如果 Runner 自己不能可靠 Timeout / Exit
Generator 会把执行层问题放大
```

---

# 4. 整体模块规划

建议最终增加：

```text
src/xgtest/

├── core/
│   ├── models.py
│   └── ...
│
├── design/
│   ├── __init__.py
│   ├── model.py
│   ├── constraint.py
│   ├── coverage.py
│   └── signature.py
│
├── generator/
│   ├── __init__.py
│   ├── template.py
│   ├── candidate.py
│   ├── dedup.py
│   ├── provenance.py
│   ├── lifecycle.py
│   └── review.py
│
├── query/
│   ├── loader.py
│   ├── runner.py
│   ├── result.py
│   └── ...
│
└── cli.py
```

资产目录：

```text
models/
└── query/
    └── join.yaml

generators/
└── query/
    └── templates/
        └── join.yaml

candidates/
└── query/
    └── join/

cases/
└── query/
```

---

# 5. Phase 0：冻结本阶段 Contract

## 5.1 新增共享模型

在 `core/models.py` 增加：

```python
class GenerationProvenance(StrictModel):
    generator: str
    generator_version: str
    model_id: str
    model_version: str
    template_id: str
    template_version: str
    strategy: str
    seed: int | None = None
    input_hash: str

class OracleProvenance(StrictModel):
    kind: Literal[
        "manual",
        "reference_database",
        "known_result",
        "property",
    ]
    reference: str | None = None
    reviewer: str | None = None
    evidence_hash: str | None = None

class ValidationEvidence(StrictModel):
    semantic_hash: str
    static_validation_hash: str | None = None
    trial_run_hash: str | None = None
    review_hash: str | None = None
```

## 5.2 扩展 QueryCaseInput

当前：

```python
class QueryCaseInput(StrictModel):
    metadata: EffectiveMetadata
    steps: tuple[QueryStep, ...]
```

建议扩展为：

```python
class QueryCaseInput(StrictModel):
    metadata: EffectiveMetadata
    coverage: tuple[CoverageClaim, ...] = ()
    generation: GenerationProvenance | None = None
    oracle: OracleProvenance | None = None
    validation_evidence: ValidationEvidence | None = None
    steps: tuple[QueryStep, ...]
```

## 5.3 generated_by 字段收口

当前：

```python
generated_by: str | None
```

不建议继续保存复杂生成来源。真正生成事实统一使用：

```text
generation: GenerationProvenance
```

## 5.4 Contract Identity

新增以下目录进入 Contract Descriptor：

```text
src/xgtest/design
src/xgtest/generator
models
generators
```

保证：

```text
Test Model 变化
Constraint 变化
Template 变化
Coverage 算法变化
Generator 变化
```

都能反映到契约或资产身份。

## 5.5 Phase 0 验收

必须通过：

```text
Schema Export
Contract Descriptor Rebuild
Candidate Descriptor Update
Framework Tests
```

---

# 6. Phase 1：定义 Test Model Contract

新增：

```text
src/xgtest/design/model.py
```

建议模型：

```python
class Dimension(StrictModel):
    name: str
    values: tuple[str, ...]

class CoverageStrategy(StrictModel):
    type: Literal[
        "all_values",
        "pairwise",
        "boundary",
        "negative",
        "interaction",
    ]
    strength: int | None = None

class TestModel(StrictModel):
    model_id: str
    model_version: str
    module: str
    feature: str
    subfeature: str | None
    dimensions: dict[str, tuple[str, ...]]
    constraints: tuple[ConstraintRule, ...]
    strategies: tuple[CoverageStrategy, ...]
```

---

# 7. Phase 2：建立 JOIN Test Model

创建：

```text
models/query/join.yaml
```

推荐第一版：

```yaml
model_id: query.join
model_version: "1"

module: query
feature: query
subfeature: join

dimensions:
  join_type:
    values: [inner, left, right, full, cross]
  predicate:
    values: [none, equality, inequality, range]
  datatype:
    values: [int, varchar, date]
  null_side:
    values: [none, left, right, both]
  interaction:
    values: [none, where, group_by, subquery]

coverage:
  strategies:
    - type: all_values
    - type: pairwise
      strength: 2

constraints:
  - if:
      join_type: cross
    then:
      predicate: none

  - if:
      join_type: cross
    exclude:
      interaction: [subquery]
```

---

# 8. Phase 3：实现 Constraint Engine

新增：

```text
src/xgtest/design/constraint.py
```

职责：

```text
Assignment
→ Constraint Evaluate
→ VALID / INVALID
```

第一版只需要支持：

```text
if + then
if + exclude
```

Constraint 必须是纯函数、确定性、无数据库依赖、无 Template 依赖。禁止把非法组合规则偷偷写进模板。

测试至少覆盖：

```text
合法组合通过
cross + predicate none 通过
cross + equality 拒绝
exclude 正确
未知 Dimension 拒绝
未知 Value 拒绝
相同输入结果稳定
```

---

# 9. Phase 4：Coverage Signature

新增：

```text
src/xgtest/design/signature.py
```

Assignment：

```python
{
    "join_type": "left",
    "predicate": "equality",
    "datatype": "int",
    "null_side": "right",
    "interaction": "where",
}
```

建议：

```text
XGMJ1(normalized assignment + model identity)
→ SHA256
→ coverage_signature
```

必须满足：

```text
键顺序变化不影响 Hash
平台换行不影响
Python dict 顺序不影响
模型版本变化可改变 identity
```

---

# 10. Phase 5：Required Coverage Engine

新增：

```text
src/xgtest/design/coverage.py
```

目标：

```text
Test Model
+ Strategy
+ Constraint
→ Required Coverage Set
```

## 10.1 all_values

每个 Dimension 的每个合法 Value 至少被覆盖一次。

## 10.2 pairwise

任意两个 Dimension 的合法 Value Pair 至少出现一次。

## 10.3 Pairwise 实现建议

第一版可以：

```text
生成合法 Assignment Space
→ 生成 Pair Requirement Set
→ greedy set cover
→ 选择确定性 Assignment 集
```

不要求第一版就做最优 Covering Array，但必须：

```text
确定性
可复现
可解释
```

固定排序，不使用无 seed 随机算法。

---

# 11. Phase 6：给现有 Query Case 增加 CoverageClaim

先给现有 JOIN Case 补 Coverage。

例如：

```yaml
metadata:
  id: QUERY.JOIN_01_INNER
  feature: query
  subfeature: join
  status: active

coverage:
  - claim_id: join_inner_equality_int
    model_id: query.join
    model_version: "1"
    assignment:
      join_type: inner
      predicate: equality
      datatype: int
      null_side: none
      interaction: none
    assertion_refs:
      - q1
```

Coverage Claim 必须校验：

```text
model_id 存在
model_version 匹配
所有 Dimension 齐全
没有未知 Dimension
Value 合法
Assignment 满足 Constraint
assertion_refs 指向真实 Step
```

---

# 12. Phase 7：Existing Coverage Engine

输入 Active Query Cases，第一版只统计：

```text
status = active
```

Candidate 不参与 Available Coverage。

输出例如：

```text
query.join

Active Case: 2
Covered assignments: 2
Covered pairwise requirements: 14 / 42
```

建议定义接口：

```python
class CoverageSource(Protocol):
    def active_claims(self, model_id: str) -> Iterable[CoverageClaim]:
        ...
```

MVP：

```text
FileCoverageSource
```

未来：

```text
CatalogCoverageSource
```

避免 Coverage Engine 与文件目录强耦合。

---

# 13. Phase 8：Coverage Gap

定义：

```text
Coverage Gap
=
Required Coverage
-
Available Active Coverage
```

输出建议：

```json
{
  "model_id": "query.join",
  "model_version": "1",
  "strategy": "pairwise",
  "required": 42,
  "covered": 14,
  "missing": 28
}
```

同时列出 Missing Requirement 与 Suggested Assignment。

---

# 14. Phase 9：Template Contract

新增：

```text
src/xgtest/generator/template.py
```

Template 必须满足：

```text
同一 Assignment
+ 同一 Template Version
→ 完全一致输出
```

禁止：

```text
当前时间进入 SQL
随机 UUID 对象名
未固定 random
执行时随机 Expected
```

---

# 15. Phase 10：JOIN Template

创建：

```text
generators/query/templates/join.yaml
```

模板职责：

```text
Assignment
→ SQL
→ Expected
→ Metadata
→ CoverageClaim
```

第一版数据来源建议只使用：

```text
VALUES
UNION ALL
Derived Table
Literal
```

目的：

```text
不依赖 CREATE TABLE
不依赖 INSERT
不依赖外部 Fixture
只读环境即可 Trial Run
Expected 可静态推导
```

示例 Assignment：

```yaml
join_type: left
predicate: equality
datatype: int
null_side: right
interaction: none
```

模板生成：

```sql
SELECT a.id, b.name
FROM (
    SELECT 1 AS id
) a
LEFT JOIN (
    SELECT 2 AS id, 'xugu' AS name
) b
ON a.id = b.id
```

Expected：

```yaml
rows:
  - [1, null]
```

Oracle：

```yaml
oracle:
  kind: known_result
  reference: join-template-v1
```

---

# 16. Phase 11：Candidate ID

必须确定性。

建议：

```text
QUERY.JOIN.<SIGNATURE_PREFIX>
```

Signature 输入：

```text
model_id
model_version
template_id
template_version
assignment
```

通过 XGMJ1 + SHA256 得到。

不要使用：

```text
当前时间
随机 UUID
不稳定顺序号
```

---

# 17. Phase 12：Generation Provenance

所有生成 Candidate 必须保存：

```yaml
generation:
  generator: query_template_generator
  generator_version: "1"
  model_id: query.join
  model_version: "1"
  template_id: query.join.default
  template_version: "1"
  strategy: pairwise
  seed: null
  input_hash: ...
```

保证以后可以回答：

```text
为什么存在这条 Case？
谁生成的？
基于哪个 Model？
哪个 Template？
哪个 Strategy？
输入是什么？
```

---

# 18. Phase 13：Candidate 目录

Generator 输出：

```text
candidates/query/join/
```

不要直接写：

```text
cases/query/
```

自动生成初始状态：

```yaml
status: generated
```

---

# 19. Phase 14：Deduplication

新增：

```text
src/xgtest/generator/dedup.py
```

至少检查：

```text
Case ID
Normalized SQL
Coverage Signature
Template Parameter Signature
```

去重分类：

```text
EXACT_DUPLICATE
POSSIBLE_SQL_DUPLICATE
COVERAGE_DUPLICATE
PARAMETER_DUPLICATE
UNIQUE
```

除精确 Case ID/内容冲突外，其他重复只作为 Review 信息，不能自动删除不同测试目的的 Case。

---

# 20. Phase 15：Static Validate

Candidate Static Validation 直接复用：

```text
query.loader.load_query_case()
```

再增加 Generator 专项检查：

```text
Model Assignment
Constraint
CoverageClaim
assertion_refs
Provenance
Oracle Provenance
Case ID
Dedup
Template Input
```

通过后：

```text
generated
→ draft
```

失败则保持 generated，并记录原因。

---

# 21. Phase 16：Trial Run

直接复用现有：

```text
QueryRunner
```

不要为 Candidate 再写数据库执行器。

第一版每条 Candidate 建议运行两次：

```text
Run #1
Run #2
```

要求：

```text
两次 Status 一致
两次 Row Count 一致
两次 Result SHA256 一致
均符合 Expected
```

满足后：

```text
draft
→ review
```

Trial Artifact：

```text
artifacts/trial-runs/
└── <case_id>/
    └── <semantic_hash>.json
```

记录：

```text
case_id
semantic_hash
runtime_profile_id
contract_set_id
database_version
driver_version
run1
run2
result_hash
status
```

---

# 22. Phase 17：Oracle 规则

Candidate Active 前必须有明确 Oracle。

允许：

```text
manual
reference_database
known_result
property
```

第一版 JOIN Template 统一使用：

```text
known_result
```

禁止：

```text
执行 Xugu
↓
拿 Xugu 实际 Result
↓
自动写成 Expected
```

否则被测数据库 Bug 可能被固化成正确答案。

---

# 23. Phase 18：Review Evidence

第一版 Review 不建设 Web 审批，直接使用 Git PR Review。

Review 至少检查：

```text
功能归属
Coverage Assignment
SQL
Expected
Oracle Provenance
是否重复
是否稳定
Trial Run
Level
Tags
```

Review Evidence 建议保存：

```text
review_input_hash
semantic_hash
trial_run_artifact_hash
reviewer
review_reference
```

状态：

```text
review
→ active
```

---

# 24. Phase 19：Promote

新增：

```text
src/xgtest/generator/lifecycle.py
```

Promote 条件：

```text
status = review
Static Validate PASS
Trial Run Evidence 有效
Oracle Provenance 存在
Review Evidence 有效
Coverage Review 有效
semantic_hash 未变化
```

通过：

```text
candidates/query/join/
↓
cases/query/
```

并设置：

```yaml
status: active
```

---

# 25. Phase 20：Semantic Hash 与证据失效

修改以下任一内容：

```text
SQL
Expected
Fixture
Comparison
```

导致：

```text
semantic_hash 变化
```

必须使：

```text
Trial Run Evidence
Review Evidence
```

失效，并重新执行：

```text
trial
→ review
→ active
```

---

# 26. Phase 21：Coverage Review 失效规则

修改：

```text
CoverageClaim
Model Version
assertion_refs
```

即使 SQL 不变，Coverage Review 也必须失效。

原因：

```text
执行语义
≠
覆盖声明语义
```

两者证据必须独立。

---

# 27. Phase 22：Coverage Snapshot

Candidate Promote 后重新计算：

```text
Designed Coverage
Available Coverage
Coverage Gap
```

第一版至少输出：

```json
{
  "model_id": "query.join",
  "designed": {
    "pairwise_required": 42
  },
  "available": {
    "pairwise_covered": 42
  },
  "gap": 0
}
```

形成真正闭环：

```text
Coverage Gap
→ Generator
→ New Active Case
→ Coverage 提升
→ 新 Gap
```

---

# 28. CLI 完整规划

```bash
# Model 校验
xgtest model validate models/query/join.yaml

# 查看 Coverage
xgtest coverage show query.join

# 查看 Gap
xgtest coverage gap query.join

# 根据 Gap 生成 Candidate
xgtest generate query.join --strategy pairwise

# Candidate 静态校验
xgtest candidate validate candidates/query/join

# Trial Run
xgtest candidate trial candidates/query/join

# 查看待 Review
xgtest candidate list --status review

# Promote
xgtest candidate promote QUERY.JOIN.A17F92D1

# 正式 Query Regression
xgtest query run --cases cases/query
```

---

# 29. 推荐代码目录最终形态

```text
src/xgtest/
├── adapter/
│   └── xugu.py
├── core/
│   ├── canonical.py
│   ├── contract_set.py
│   ├── models.py
│   ├── registry.py
│   └── ...
├── design/
│   ├── __init__.py
│   ├── model.py
│   ├── constraint.py
│   ├── coverage.py
│   └── signature.py
├── generator/
│   ├── __init__.py
│   ├── template.py
│   ├── candidate.py
│   ├── dedup.py
│   ├── provenance.py
│   ├── lifecycle.py
│   └── review.py
├── query/
│   ├── __init__.py
│   ├── loader.py
│   ├── runner.py
│   └── result.py
├── runtime/
│   ├── comparator.py
│   └── profile.py
└── cli.py
```

资产：

```text
models/query/join.yaml
generators/query/templates/join.yaml
candidates/query/join/
cases/query/
```

---

# 30. Framework Tests 规划

新增：

```text
framework_tests/
├── design/
│   ├── test_model.py
│   ├── test_constraint.py
│   ├── test_coverage_all_values.py
│   ├── test_coverage_pairwise.py
│   └── test_signature.py
├── generator/
│   ├── test_template.py
│   ├── test_candidate.py
│   ├── test_dedup.py
│   ├── test_lifecycle.py
│   └── test_review.py
└── query/
    └── existing tests...
```

---

# 31. 必须有的 Golden Tests

## Model

```text
相同 Model → 相同 canonical hash
非法 Dimension → fail
重复 Value → fail
未知 Strategy → fail
```

## Constraint

```text
合法 Assignment → PASS
非法 Assignment → FAIL
```

## Pairwise

```text
固定 Model
→ 固定 Assignment 集
→ 固定 Coverage Signature
```

不能每次运行产生不同结果。

## Template

```text
相同 Assignment
→ 完全相同 YAML
→ 完全相同 SQL
→ 完全相同 Expected
→ 完全相同 Case ID
```

## Lifecycle

```text
generated
→ draft
→ review
→ active
```

非法跳转必须失败。

---

# 32. 集成测试

必须有一条完整纵向测试：

```text
load model
↓
calculate required coverage
↓
load existing active case
↓
calculate gap
↓
generate candidate
↓
validate
↓
trial run fake session
↓
review
↓
promote
↓
recalculate gap
```

最终验证：

```text
Gap 数量减少
```

这是本阶段最关键的一条集成测试。

---

# 33. 真实 Xugu Acceptance

JOIN Generation MVP 完成后，在真实 Xugu 上执行：

```text
生成 5～20 条 Candidate
↓
Static Validate
↓
Trial Run × 2
↓
Review
↓
Promote
↓
正式 Query Run
```

记录：

```text
Model Version
Template Version
Generator Version
Runtime Profile
Contract Set
Git Commit
Candidate Count
Promoted Count
Pass/Fail/Error/Timeout
Coverage Before
Coverage After
```

---

# 34. 性能要求

本阶段不追求大规模性能，但至少要求：

```text
1,000 合法 Assignment
→ Coverage 计算可接受

10,000 Active Coverage Claims
→ Gap 计算不出现明显 O(N²) 退化

Generator 不一次性制造无意义巨量 Case
```

Pairwise 推荐：

```text
预计算 requirement set
+
倒排索引
+
greedy cover
```

---

# 35. 安全与可重复性

Generator 禁止：

```text
随机 SQL 未记录 seed
生成时间影响 Case Identity
使用环境变量决定 Expected
使用 Xugu Result 自动构造 Expected
Candidate 自动进入 active
```

要求：

```text
模型版本化
模板版本化
生成器版本化
输入 Hash
稳定 Case ID
稳定 Coverage Signature
稳定 Semantic Hash
```

---

# 36. 与现有 Query Runner 的边界

Generator 负责：

```text
决定生成什么 Case
```

Runner 负责：

```text
执行已经确定的 Case
```

禁止：

```text
Runner 运行时临时生成随机 Query
```

正式 Release Regression 始终执行：

```text
Git 中已 Review 的 active Case
```

---

# 37. 与未来 Catalog2 的关系

当前 MVP 可以直接读取：

```text
cases/query
```

未来改为：

```text
Case Source
↓
Compiler
↓
Catalog2
```

Coverage Engine 从 Catalog2 读取 Active CoverageClaim，但以下模块不需要重写：

```text
Test Model
Constraint
Coverage Strategy
Coverage Signature
Generator
Template
```

所以本阶段必须通过 `CoverageSource` 抽象避免绑定具体存储。

---

# 38. 与未来 Web UI 的关系

Query Generation MVP 完成后，前端可以增加：

```text
Coverage
Coverage Gap
Candidate
Candidate Detail
Trial Result
Review
```

页面可以扩展为：

```text
Dashboard
Coverage
  └── query.join
      ├── Dimension Coverage
      ├── Pairwise Coverage
      └── Gap
Candidates
  ├── generated
  ├── draft
  └── review
Cases
  └── active
```

UI 仍然只消费 Core API，不自行计算 Coverage 或状态迁移。

---

# 39. 建议 Commit 顺序

```text
01 feat: add query coverage and generation provenance models
02 feat: add query test model contract
03 feat: add deterministic constraint engine
04 feat: add coverage signatures
05 feat: add all-values coverage strategy
06 feat: add deterministic pairwise coverage strategy
07 test: add coverage claims to existing join cases
08 feat: calculate active query coverage gaps
09 feat: add deterministic join template contract
10 feat: generate join candidates from coverage gaps
11 feat: add candidate deduplication
12 feat: add candidate static validation
13 feat: add candidate trial-run workflow
14 feat: add review evidence contract
15 feat: add generated-draft-review-active lifecycle
16 feat: promote reviewed candidates to active cases
17 feat: emit query coverage snapshots
18 feat: add model coverage generate candidate CLI commands
19 test: add real Xugu join generation acceptance
20 docs: document query generation MVP workflow
```

每个 Commit 坚持：

```text
一个主要问题
+
一个实现目标
+
一组对应测试
```

---

# 40. Query Generation MVP DoD

## Contract

- [ ] QueryCaseInput 支持 CoverageClaim
- [ ] GenerationProvenance 结构化
- [ ] OracleProvenance 结构化
- [ ] ValidationEvidence 结构化
- [ ] Schema 已重新导出
- [ ] Contract Descriptor 更新
- [ ] Candidate Descriptor 非 stale

## Test Model

- [ ] JOIN Model
- [ ] Dimension
- [ ] Value
- [ ] Constraint
- [ ] Strategy
- [ ] Model Hash

## Coverage

- [ ] all_values
- [ ] pairwise
- [ ] Active Coverage
- [ ] Coverage Gap
- [ ] Coverage Signature
- [ ] Coverage Snapshot

## Generator

- [ ] Deterministic Template
- [ ] Stable Case ID
- [ ] Provenance
- [ ] Candidate Output
- [ ] Dedup

## Validation

- [ ] Static Validate
- [ ] Trial Run ×2
- [ ] Determinism Check
- [ ] Oracle Provenance
- [ ] Review Evidence

## Lifecycle

- [ ] generated
- [ ] draft
- [ ] review
- [ ] active
- [ ] 非法状态跳转拒绝
- [ ] semantic hash 变化使证据失效

## Execution

- [ ] Active Case 可被现有 QueryRunner 执行
- [ ] Candidate 不进入正式 Regression
- [ ] Real Xugu Acceptance

---

# 41. 最终验收场景

必须能够完整演示：

```text
STEP 1
已有 INNER JOIN / LEFT JOIN Active Case
Pairwise Coverage = 35%

STEP 2
xgtest coverage gap query.join
输出缺失组合

STEP 3
xgtest generate query.join --strategy pairwise
只针对 Gap 输出 Candidate

STEP 4
Static Validate
generated → draft

STEP 5
Trial Run ×2
draft → review

STEP 6
Git PR / 人工 Review
review → active

STEP 7
Promote 到 cases/query

STEP 8
正式 Query Regression
全部 PASS

STEP 9
重新计算 Coverage
35% → 100%
Gap N → 0
```

完成这条演示，即可认为：

```text
Query Generation MVP 真正成立
```

---

# 42. 后续扩展顺序

JOIN 成功后建议：

```text
1. filter
2. aggregate
3. set operation
4. subquery
5. cte
6. window
7. complex query
```

之后再增加：

```text
boundary
negative
interaction
```

最后才考虑：

```text
Property
Metamorphic
Differential
AI-assisted Candidate Draft
```

---

# 43. 最终路线图

```text
当前 Query MVP
    ↓
Timeout / Real Acceptance
    ↓
CoverageClaim / Provenance
    ↓
JOIN Test Model
    ↓
Constraint
    ↓
all_values / pairwise
    ↓
Coverage Gap
    ↓
JOIN Template
    ↓
Candidate
    ↓
Dedup
    ↓
Static Validate
    ↓
Trial Run
    ↓
Review
    ↓
Active
    ↓
Coverage Snapshot
    ↓
Query Generation MVP DONE
    ↓
扩展其他 Query Feature
    ↓
接入 Catalog2 / Selector / TestPlan
    ↓
接入 Web Coverage / Candidate Review
```

---

# 44. 最终原则

本阶段始终遵守五条：

```text
1. Test Model 决定“应该测什么”
2. Coverage Engine 决定“还缺什么”
3. Generator 只负责“把 Gap 变成 Candidate”
4. Review 决定“Candidate 能否成为正式资产”
5. Runner 只执行已经确定的 Active Case
```

最终不要做成：

```text
模板
→ 笛卡尔积
→ 生成几千 SQL
→ 全部执行
```

而应该做到：

```text
Model
→ Coverage
→ Gap
→ Candidate
→ Validation
→ Review
→ Active Asset
```

这样才与 XG DB Test 原完整架构一致，也能保证未来接入 Catalog2、Selector、TestPlan、Web UI、分布式执行时不推翻当前实现。
