# XG DB Test 总体架构设计

> 版本：v1.1（设计修订，2026-09-11；非已实现声明）
> 项目定位：面向数据库原厂的统一功能测试、测试资产管理与版本质量验证平台
> 适用范围：Xugu/自研数据库功能测试、回归测试、事务并发、备份恢复、集群 HA、兼容性与版本发布验证
> 工程化补充：已评审优化清单；共享机器契约、准入规则与阶段验收见第 135 节及专项 12。

---

# 1. 文档目的

本文作为 XG DB Test 的正式首版架构基线，用于统一：

- 项目目标；
- 测试资产模型；
- 测试设计模型；
- 覆盖度模型；
- DSL 与 Metadata；
- Case 编译与 Catalog；
- 用例选择与 Test Plan；
- 单机/单集群/多集群执行；
- 分布式调度；
- Resource Lease；
- Executor / Adapter / Validator；
- Result / Baseline / Delta；
- 自动生成与生命周期；
- 性能与扩展性；
- 分阶段实施计划。

本文不以某个现有开源测试框架为主框架，而是定义 XG DB Test 自身的稳定架构。pytest、Allure、SQLancer 等只能作为可选能力或外围工具使用。

---

# 2. 最初需求与核心目标

XG DB Test 的原始目标不是构建一个简单 SQL Runner，而是解决数据库原厂长期存在的几类问题：

```text
数据库到底有哪些功能需要测试？
每个功能应该怎么分层、怎么组合？
测试用例如何生成、审查、沉淀和维护？
发布版本时能否只选择 JOIN / UNION / P0 / P1 等范围？
10 万级以上 Case 如何快速选择并执行？
多个数据库集群如何并行分摊回归任务？
复杂事务、并发、Backup/Restore、HA 如何统一表达？
新版本相对于上一版本到底新增了哪些失败？
当前测试到底覆盖了哪些能力，还缺哪些？
```

因此平台必须同时覆盖五个核心问题：

```text
1. Database Feature Model
2. Test Model / Coverage Model
3. Case Asset Management
4. Selective & Distributed Execution
5. Result / Release Quality Analysis
```

---

# 3. 一句话定位

> XG DB Test 是以数据库 Feature Model 与 Coverage Model 为起点，以测试用例作为长期资产，通过统一 DSL、Case Catalog、Selector、执行引擎、分布式调度和版本质量分析完成数据库全功能持续验证的平台。

---

# 4. 总体闭环

完整闭环：

```text
Database Feature Model
        ↓
Test Model
        ↓
Coverage Model
        ↓
Case Design / Generator
        ↓
Review / Git
        ↓
Case Compiler
        ↓
Case Catalog
        ↓
Selector / Test Plan
        ↓
Single / Multi Cluster Execution
        ↓
Validator
        ↓
Result Store
        ↓
Release Baseline / Delta
        ↓
Coverage Feedback
        ↓
Coverage Gap
        ↓
继续补充 Test Model / Case
```

平台必须始终围绕这个闭环建设，而不是单独追求“执行速度”或“用例数量”。

---

# 5. 总体架构分层

XG DB Test 划分为五个平面：

```text
1. Test Design Plane
2. Test Asset Plane
3. Control Plane
4. Execution & Environment Plane
5. Result & Quality Plane
```

---

# 6. Test Design Plane

Test Design Plane 负责回答：

```text
有什么功能？
应该怎么测？
覆盖是否充分？
缺口如何转化为新的测试资产？
```

核心组件：

```text
Domain Taxonomy
Feature Registry
Test Model
Coverage Model
Generation Model
Constraint Model
```

---

# 7. Domain Taxonomy

数据库测试范围不能只覆盖 Query，需要覆盖完整数据库功能域。

建议一级 Domain：

```text
query
ddl
dml
transaction
concurrency
datatype
function
index
partition
view
sequence
procedure
trigger
privilege
security
session
optimizer
storage
backup_restore
import_export
cluster
ha
distributed
compatibility
protocol_driver
configuration
administration
regression
```

目录负责主分类，Metadata 负责机器属性，Tag 负责横向标签。

---

# 8. Query Domain 建议结构

```text
query/
├── select_basic/
├── predicate/
├── join/
│   ├── inner/
│   ├── left/
│   ├── right/
│   ├── full/
│   ├── cross/
│   ├── semi/
│   └── anti/
├── subquery/
│   ├── in/
│   ├── exists/
│   ├── scalar/
│   └── correlated/
├── setop/
│   ├── union/
│   ├── union_all/
│   ├── intersect/
│   └── except/
├── group_having/
├── window/
├── cte/
├── order_limit/
└── expression/
```

---

# 9. Transaction Domain 建议结构

```text
transaction/
├── begin_commit_rollback/
├── savepoint/
├── isolation/
├── visibility/
├── lock/
├── deadlock/
├── multi_session/
└── failure_recovery/
```

---

# 10. Backup / Restore Domain

```text
backup_restore/
├── full_backup/
├── incremental_backup/
├── logical_backup/
├── physical_backup/
├── restore/
├── point_in_time/
├── corrupt_backup/
├── permission/
├── large_database/
└── cross_version/
```

---

# 11. Cluster / HA Domain

```text
cluster/
├── topology/
├── node_join/
├── node_remove/
├── replication/
├── rebalance/
└── consistency/

ha/
├── failover/
├── switchover/
├── primary_failure/
├── replica_failure/
├── network_partition/
├── restart/
└── recovery/
```

---

# 12. Test Model

Domain Taxonomy 只能回答“有哪些功能”，不能回答“每个功能应该怎么测”。

因此每个 Feature 必须有对应 Test Model。

以 JOIN 为例：

```text
Feature: JOIN

Dimensions
├── join_type
│   ├── inner
│   ├── left
│   ├── right
│   ├── full
│   └── cross
│
├── table_count
│   ├── 2
│   ├── 3
│   └── N
│
├── predicate
│   ├── equality
│   ├── inequality
│   ├── range
│   ├── expression
│   └── function
│
├── datatype
│   ├── int
│   ├── decimal
│   ├── varchar
│   ├── date
│   └── timestamp
│
├── data_distribution
│   ├── normal
│   ├── duplicate
│   ├── null
│   ├── empty
│   └── boundary
│
├── index
│   ├── none
│   ├── left
│   ├── right
│   └── both
│
└── interaction
    ├── join + where
    ├── join + group
    ├── join + subquery
    ├── join + union
    └── join + window
```

---

# 13. Test Model Schema

建议模型文件：

```text
models/tests/query/join.yaml
```

示例：

```yaml
model_id: query.join
model_version: "1"

module: query
feature: join

dimensions:

  join_type:
    values:
      - inner
      - left
      - right
      - full
      - cross

  predicate:
    values: [none, equality, inequality, range, expression, function]

  datatype:
    values:
      - int
      - decimal
      - varchar
      - date
      - timestamp

  null_side:
    values:
      - none
      - left
      - right
      - both

  index:
    values:
      - none
      - left
      - right
      - both

  interaction:
    values:
      - none
      - where
      - group_by
      - subquery
      - union
      - window
```

---

# 14. Constraint Model

Test Model 不能简单做笛卡尔积，必须支持组合约束。

例如：

```yaml
constraints:

  - if:
      join_type: cross
    then:
      predicate: none

  - if:
      join_type: cross
    exclude:
      interaction:
        - subquery
```

约束用于：

```text
Pairwise
Boundary
Negative
Template Generation
Coverage Calculation
```

---

# 15. Coverage Model

Coverage 不等于 Case 数量。

平台必须衡量：

```text
Feature Coverage
Dimension Coverage
Value Coverage
Pairwise Coverage
Boundary Coverage
Negative Coverage
Interaction Coverage
Datatype Coverage
Regression Coverage
Level Coverage
Environment Coverage
```

---

# 16. Coverage 五阶段

必须区分：

```text
Designed Coverage
Available Case Coverage
Selected Coverage
Executed Coverage
Passed Coverage
```

示例：

```text
设计要求组合：100
已有 Active Case：92
本次选择：80
实际执行：78
通过：77
```

这五个指标含义完全不同。

---

# 17. Coverage Gap

Coverage Engine 应能输出：

```text
JOIN × TIMESTAMP × NULL 缺 Case
JOIN × WINDOW 缺 P1 Case
FULL JOIN × VARCHAR × DUPLICATE 未覆盖
ARRAY × JOIN 尚未覆盖
```

Coverage Gap 可以直接成为 Generator 输入。

---

# 18. Test Asset Plane

Test Asset Plane 负责：

```text
Case Source
DSL
Metadata
Lifecycle
Provenance
Fixture
Test Plan
Compiler
Catalog
```

Git 是测试资产事实源。

---

# 19. Git 作为事实源

正式测试资产包括：

```text
.xgt
.xgs.yaml
_suite.yaml
fixture
test model
coverage model
generator model
test plan
feature registry
capability registry
```

Case Catalog 只是派生索引，不能替代 Git。

---

# 20. Case Lifecycle

建议生命周期：

```text
generated
   ↓
draft
   ↓
review
   ↓
active
   ↓
deprecated
   ↓
disabled
```

正式 Release Regression 默认只执行：

```text
status = active
```

---

# 21. Case Provenance

自动生成 Case 必须记录来源：

```yaml
source: pairwise

generated_by:
  generator: join_generator
  generator_version: "1.4"
  model_id: query.join
  model_version: "3"
  seed: 1729
  strategy: pairwise
```

这样以后可以回答：

```text
这批 Case 为什么存在？
由哪个模型生成？
由哪个 Generator 版本生成？
```

---

# 22. Bug Regression Case 的归属

Regression Case 应优先归入实际功能树，而不是全部塞入独立 `regression/`。

例如：

```text
tests/query/join/left/
```

Metadata：

```yaml
source: bug
issue: XGDB-12345
tags:
  - regression
```

这样 JOIN Coverage 能包含历史 Bug。

独立 regression 目录仅用于跨多个 Domain、无法自然归属的案例。

---

# 23. 多 DSL 策略

不同数据库功能的执行模型差异很大，因此不强行使用一种 DSL。

采用：

```text
.xgt
→ SQL-centric Case

.xgs.yaml
→ Scenario-centric Case
```

二者最终编译为统一 Case Model。

---

# 24. XGT DSL

`.xgt` 适用于：

```text
Query
DDL
DML
Datatype
Function
Index
Partition
View
Sequence
简单 Procedure / Trigger
Privilege SQL
```

示例：

```text
# xg:dsl_version 1.1
# xg:metadata_version 1.1
# xg:id QUERY.JOIN.INNER.000001
# xg:title Inner Join 基本等值连接
# xg:module query
# xg:feature join
# xg:subfeature inner_join
# xg:level P0
# xg:status draft
# xg:execution_class fast
# xg:isolation worker_schema
# xg:idempotency conditional
# xg:reset_contract worker_schema_clean
# xg:destructive false

statement ok id=create-t1
CREATE TABLE t1(id INT, name VARCHAR(20));
@end-sql

statement ok id=insert-t1
INSERT INTO t1 VALUES(1,'A'),(2,'B'),(3,'C');
@end-sql

statement ok id=create-t2
CREATE TABLE t2(id INT);
@end-sql

statement ok id=insert-t2
INSERT INTO t2 VALUES(1),(2);
@end-sql

query rowsort id=rows-t1
SELECT t1.id,t1.name FROM t1 INNER JOIN t2 ON t1.id=t2.id;
@end-sql
----
[1, "A"]
[2, "B"]
@end-expect

cleanup id=drop-t2
DROP TABLE t2;
@end-sql

cleanup id=drop-t1
DROP TABLE t1;
@end-sql
```

---

# 25. XGT Query Validation Mode

建议支持：

```text
exact
rowsort
valuesort
hash
expected_error
```

Large Result 默认不使用 `fetchall()`。

---

# 26. Scenario DSL

`.xgs.yaml` 适用于 Transaction、Concurrency、Multi-session、Backup/Restore、Cluster/HA、Configuration、Administration、Node Restart 和 Import/Export。

以下 RC 可见性样例显式建立初始数据并设置 Session；完整并发与取消语义见 [03](03_Scenario_DSL_Specification.md)。

```yaml
dsl_version: "1.1"
metadata_version: "1.1"

id: TX.RC.VISIBILITY.0001
title: Read Committed visibility

module: transaction
feature: isolation
subfeature: read_committed
level: P0

execution_class: normal
isolation: case_schema
idempotency: conditional
reset_contract: case_schema_clean
destructive: false
status: draft

resources:
  sessions: 2

sessions:
  s1: {autocommit: true, isolation_level: read_committed}
  s2: {autocommit: true, isolation_level: read_committed}

setup:
  - sql:
      session: s1
      statement: CREATE TABLE t1(id INT PRIMARY KEY, value INT)
  - sql:
      session: s1
      statement: INSERT INTO t1 VALUES(1,10)

steps:
  - sql:
      session: s1
      statement: BEGIN

  - sql:
      session: s1
      statement: |
        UPDATE t1 SET value=100 WHERE id=1

  - query:
      session: s2
      statement: |
        SELECT value FROM t1 WHERE id=1
      expect:
        order: exact
        rows:
          - [10]

  - sql:
      session: s1
      statement: COMMIT

  - query:
      session: s2
      statement: |
        SELECT value FROM t1 WHERE id=1
      expect:
        order: exact
        rows:
          - [100]

cleanup:
  - transaction:
      session: s1
      action: rollback
  - sql:
      session: s1
      statement: DROP TABLE t1
```

---

# 27. Scenario 并发同步原语

事务并发不能依赖固定 sleep。

第一版必须支持：

```text
parallel
barrier
signal
wait_signal
condition wait
```

例如：

```yaml
- barrier:
    name: before_update
    parties: 2
```

---

# 28. Unified Case Model

所有 DSL 编译成统一、类型化的 Case Model；Core Runner 不感知源 DSL。

```text
TestCase
├── Identity / Classification / Lifecycle / Provenance
├── Requirements / Resources / Isolation / RetryPolicy
├── CoverageClaim[] / ModelRef[]
├── Fixtures / Setup / Steps / Cleanup
├── ComparisonProfile / OracleProvenance
└── SourceInfo / DependencyManifest / compiled_hash / semantic_hash
```

`Steps` 是有稳定层级 step_id 的树，含 parallel 分支，不是只有 SQL 的平面列表。
跨模块字段映射见 [04 Metadata](04_Metadata_Schema.md)，执行内容和比较契约见 [11](11_Execution_Consistency_and_Validation_Contract.md)。

---

# 29. Metadata

核心字段：

```yaml
id:
title:

module:
feature:
subfeature:
scenario:

level:
complexity:
tags:

status:
source:
oracle:
oracle_provenance:
validation_evidence:
coverage:
comparison_profile:

since:
until:

issue:
owner:

timeout:

execution_class:
isolation:
parallel:

destructive:
idempotency:
retry:
reset_contract:
cleanup_timeout:

requirements:
resources:
fixtures:

generated_by:
```

---

# 30. Level

建议：

```text
P0 核心主路径 / Smoke / 严重历史 Bug
P1 正式发布常规回归
P2 完整功能回归 / 复杂组合
P3 长稳 / 极端 / 大规模 / 低频专项
```

Level 不等于 Complexity。

---

# 31. Complexity

```text
basic
normal
complex
extreme
```

用于：

```text
报告
生成策略
测试设计分析
```

不直接等价于调度重量。

---

# 32. Execution Class

```text
fast
normal
heavy
exclusive
```

用途：

```text
fast
  SQL-only，轻量功能测试

normal
  复杂 SQL、索引、分区、事务

heavy
  大数据、大对象、Restore 等

exclusive
  Restart、Failover、Global Config 等
```

---

# 33. Isolation

```text
session
worker_schema
case_schema
database
cluster
```

建议：

```text
普通 Query/Function
→ worker_schema

Transaction
→ case_schema

Restore
→ database / cluster

HA
→ cluster
```

---

# 34. Destructive

破坏性 Case 必须显式：

```yaml
destructive: true
```

典型：

```text
DROP DATABASE
Restore
Cluster Restart
Failover
Global Configuration
Disk Fault
```

Test Plan 可排除。

---

# 35. Idempotency

```text
safe
conditional
unsafe
```

定义：

```text
safe
  可以自动重跑

conditional
  cleanup/reset 成功后才能重跑

unsafe
  Scheduler 禁止自动重放
```

---

# 36. Requirements

示例：

```yaml
requirements:

  topology: 3-node

  mode: default

  os:
    - linux

  arch:
    - x86_64

  storage:
    - nvme

  capabilities:
    - cluster.failover
    - sql.dml
```

---

# 37. Capability Registry

Case 与 Environment 必须共享统一 Capability Registry。

示例：

```text
sql.query
sql.ddl
sql.dml

tx.multi_session
tx.deadlock

storage.backup
storage.restore

cluster.3node
cluster.failover
cluster.rebalance
```

禁止自由写同义词。

---

# 38. Feature Registry

Feature Registry 用于：

```text
Metadata Validation
Selector
Coverage
Web UI
Report
Generator
```

例如：

```yaml
query:
  join:
    - inner_join
    - left_join
    - right_join
    - full_join

transaction:
  isolation:
    - read_committed
    - repeatable_read
    - serializable
```

---

# 39. Metadata 继承

固定顺序：Global Defaults → Parent `_suite.yaml` → Child `_suite.yaml` → Case。

- Scalar：后者覆盖；Tags：合并去重。
- Requirements：字典递归合并，列表按集合并集；不允许隐式放宽父级能力要求。
- Resources：按字段覆盖，未写字段继承；显式 0 合法，但必须通过 Step 需求下限校验。
- Fixtures：有序去重追加；Retry：字段覆盖；CoverageClaim：仅 Case 声明，不继承。
- `null` 仅在字段允许为空时清空；未知字段和非法类型直接失败。

合并后执行跨字段校验，再保存完整 effective_metadata；运行时不重新继承。

---

# 40. Fixture Model

Fixture 必须定义生命周期：

```text
run
environment
worker
suite
case
```

并分类：

```text
immutable
mutable
exclusive
```

例如：

```text
Query 公共基础表
→ worker / suite + immutable

Transaction 临时数据
→ case + mutable

HA 环境初始化
→ environment + exclusive
```

---

# 41. Case Compiler

Compiler 流程：

```text
Discover
  ↓
Resolve Metadata Inheritance
  ↓
Parse DSL
  ↓
Validate Feature / Capability / Metadata
  ↓
Compile Unified Case
  ↓
Generate Coverage Signature
  ↓
Generate Compiled Hash
  ↓
Write Catalog
```

Compiler 不连接数据库。

---

# 42. Case Catalog

Catalog 用于：

```text
快速选例
增量索引
版本追踪
Coverage 查询
Generator 关联
历史耗时关联
```

MVP 推荐 SQLite。

---

# 43. Catalog Source Traceability

每条 Case 保存 source_hash、dependency_hash、compiled_hash、semantic_hash、Git commit、dirty 标记及 DSL/Metadata/Compiler/Canonical 版本。

- compiled_hash：完整编译内容指纹，包括最终 Metadata、依赖与工具版本。
- semantic_hash：SQL/Step、Fixture、Oracle、比较策略及运行参数默认值的语义指纹；标题、Owner、Tag 不参与。
- Git 是资产事实源；Catalog 是可重建索引；不可变 Run Manifest 与 Bundle 固定本次实际执行内容。

Result 引用 manifest_hash、compiled_hash、semantic_hash。仅保存 Git commit 不足以恢复脏工作区执行内容。详见 [11](11_Execution_Consistency_and_Validation_Contract.md)。

---

# 44. Catalog 增量构建

源文件、所有父级 Suite、全局默认值、Fixture、脚本、Feature/Capability Registry、Test Model/约束、比较策略和编译器版本构成依赖图。

依赖变化重编译受影响 Case；模型变化也重算 Coverage Claim。删除、改 ID、移动文件在一次 Catalog 事务中处理。
mtime/size 只是开发索引的快速提示。Release 规划必须核对内容哈希或使用干净 Git tree 的对象哈希，不能依赖时间戳跳过验证。
索引与 Bundle 完成后核对同一快照，任一依赖变化则失败并重新规划，禁止执行“半新半旧”资产。

---

# 45. Coverage Signature

Case 必须显式声明 `coverage[]`：model_id、model_version、完整 assignment、assertion_refs。
每个模型可有多个声明；同一 Case 可覆盖多个 Feature。Compiler 校验声明和断言引用，不能仅凭 SQL 关键字推断覆盖。
人工声明仍需 Review 和可信 Oracle；未声明的 Case 标为 UNMAPPED，不计入覆盖分子。

Coverage Engine 对合法组合投影得到 coverage point 集合，按点去重。五阶段采用同一模型版本、目标矩阵和分母，详见 [08](08_Test_Model_and_Coverage_Design.md)。

---

# 46. Selector

必须支持：

```text
directory
module
feature
subfeature
scenario
tag
level
status
version
issue
source
expression
```

例如：

```bash
xgtest run --feature join --feature union
```

```bash
xgtest run --module transaction --level P0,P1
```

```bash
xgtest run --tag regression
```

```bash
xgtest run --select "(feature in (join,union)) and level in (P0,P1) and status=active"
```

---

# 47. Test Plan

Test Plan 固化一次测试目标：

```yaml
name: XG 5.1 Functional Regression

baseline:
  run_id: release-5.0.3-final

select:
  status:
    - active

  level:
    - P0
    - P1

exclude:
  destructive: true

distribution:
  mode: shard

environment:
  pool: release-clusters

coverage_policy:
  unsupported: count_as_gap

reproducibility:
  require_clean_git: true
```

---

# 48. Control Plane

Control Plane 包含：

```text
Case Catalog
Selector
Test Plan
Run Manager
Global Planner
Global Scheduler
Environment Registry
Capability Resolver
ResourceAdmissionEngine
Lease Manager
Result Aggregator
```

---

# 49. Environment Model

Environment 表示一个可执行数据库测试的逻辑环境。

字段建议：

```text
environment_id
database_version
topology
node_count
os
arch
storage
mode
capabilities
labels
capacity
weight
health
agent_id
last_heartbeat
```

---

# 50. Environment 状态

```text
ONLINE
DEGRADED
OFFLINE
DRAINING
MAINTENANCE
QUARANTINED
```

只有符合策略的环境参与调度。

---

# 51. Environment Registry

负责：

```text
环境注册
Capability Probe
Health
Capacity
Version
Topology
Agent Heartbeat
Drain / Enable
```

---

# 52. Global Planner

Global Planner 决定：

```text
Case → Environment
```

考虑：

```text
Case Requirements
Environment Capabilities
Version
Topology
Execution Class
Resource Requirement
Historical Duration
Environment Weight
Fixture Affinity
```

---

# 53. Local Planner

Local Planner 位于 Agent 内部。

负责：

```text
Shard → Worker
```

考虑：

```text
Worker Pool
Session Requirement
Worker Schema
Fixture Locality
Resource Availability
Execution Class
```

---

# 54. 两级并行

```text
Cluster-level Parallelism
+
Worker-level Parallelism
```

例如：

```text
4 Clusters
×
32 Fast Workers
=
128 Fast Workers
```

---

# 55. Shard Mode

同一 Case 在同一逻辑 target_id 下执行一次，可以在多个等价物理环境分摊任务。

target 定义数据库构建、OS、Arch、Topology、Mode、配置与数据集版本；Shard 池必须满足这些属性一致。
不能把 5.0 与 5.1 混成一个 Shard 池后宣称两个版本都被验证。跨版本/跨架构使用 Matrix。
CaseExecution 统一键为 run_id + case_id + target_id；故障迁移只改变 Attempt.environment_id。

---

# 56. Matrix Mode

同一 Case 在多个逻辑 target 上执行；每个 target 内允许等价环境分片和重试。

```text
10000 Case × 3 target = 30000 expected CaseExecution
```

不兼容和未调度目标也保留 CaseExecution 与 reason_code，不能在规划时静默删除。
environment_id 表示物理环境，target_id 表示测试目标；报告保留两者，跨 Run 按标准化目标属性匹配。

---

# 57. Weighted LPT

Shard 初始调度推荐使用 Weighted Longest Processing Time。

流程：

```text
Case 按 estimated_duration 降序
→ 找 Compatible Environment
→ 计算 normalized_load
→ 放入当前归一化负载最低环境
```

公式：

```text
normalized_load =
assigned_duration / capacity_weight
```

比按 Case 数量平均更合理。

---

# 58. Resource Model

资源必须成为一等公民。

ResourceAdmissionEngine 为共享规则库；Controller 的权威事务负责授予，Local Planner 只能在已授权范围内分配。资源有包含关系和访问/影响依赖，Session 可跨 Schema/Database，不能固定挂在单一 Schema 下。
READ/WRITE/EXCLUSIVE 以稳定 resource_id 和影响范围为前提判断；同冲突域默认仅 READ/READ 共享，祖先独占阻止后代/依赖使用，不相交的资源可并行。它是框架资源许可，不替代数据库内部事务锁。详细矩阵与原子申请规则见 [06 §38](06_Distributed_Scheduler_Design.md)。

资源类型：

```text
Connection
Session
Schema
Database
Node
Cluster
Backup Directory
Temp Directory
Port
File
```

生命周期：

```text
Reserve
→ Prepare
→ Use
→ Release
```

---

# 59. Resource Lease

Lease 包含 lease_id、resource_type/resource_id、owner_run/attempt、fencing_token、issued_at、expires_at、state。

到期仅表示持有权失效，不等于旧 SQL 或进程已经停止。控制端以事务原子地更新租约和递增 token。
能验证 token 的 Adapter 在每次资源操作前校验；无法 fencing 的直连 SQL/系统动作必须确认旧执行终止及资源复位，才能回收。
续租失败的 Agent 停止启动新动作，在保守本地截止时间前停止受租约保护的执行；无法确认停止时环境进入 QUARANTINED。
网络分区时宁可暂停相关资源，也不能允许新旧持有者并发操作。详见 [06](06_Distributed_Scheduler_Design.md)。

隔离恢复必须依次完成 Check、Stop/Fence Verify、Reset、Probe 和证据持久化，最后按 admission_epoch 原子恢复 ONLINE；env enable 不能绕过恢复流程。见 [06 §39](06_Distributed_Scheduler_Design.md)。

---

# 60. Exclusive Case

Environment 原子进入 DRAINING → 阻止所有 Run 的新分配 → 等待存量执行退出 → 获取层级互斥 Lease → 执行 → Cleanup/Reset/Probe → 释放 → ONLINE。

Cluster 独占与下属 database/schema/node 租约冲突；普通任务也必须经过同一资源准入检查。
排空、清理或健康验证失败进入 QUARANTINED，不得无条件 ONLINE；取消任务同样需要清理与停止证明。

---

# 61. Execution Plane

每个 Agent 包含：

```text
Local Planner
Resource Manager
Worker Pools
Session Manager
Executors
Adapters
Validator
Result Buffer
Heartbeat
```

---

# 62. Fast Path

Fast Path 用于：

```text
SQL-only
Single Session
Worker Schema
Non-destructive
```

关键优化：

```text
Persistent Worker
Persistent Connection
Worker Schema Reuse
Fixture Reuse
Minimal Logging
Streaming Result
Batch Result Event
```

---

# 63. Persistent Worker

Fast Path 默认避免：

```text
1 Case
→ 1 Process
→ 1 Connection
```

推荐：

```text
1 Fast Worker
≈
1 Long-lived Process
+
1 Persistent DB Connection
+
1 Worker Schema
```

---

# 64. Schema Strategy

worker_schema 用于已验证可复位的普通 SQL；case_schema 用于强隔离；database 用于 Restore/DB-level；cluster 用于 HA。

每个 Attempt 执行 Prepare → Setup → Steps → Cleanup → Reset → Probe。连接复位必须覆盖事务、会话参数、角色、schema/search path、游标、临时对象和锁；按 Adapter 明确支持范围。
Cleanup 是必尝试，不表示忽略失败。复位失败保留测试主结论和 cleanup_status，并将最终 Attempt 记为 ERROR；资源不可复用。
safe 重试仍需旧执行停止与资源清洁证明；conditional 还必须满足声明的 reset_contract。见 [11](11_Execution_Consistency_and_Validation_Contract.md)。

---

# 65. Scenario Path

Scenario Path 用于：

```text
Transaction
Concurrency
Backup
Restore
HA
Cluster
Administration
Configuration
```

依赖：

```text
Session Manager
Step State Machine
Resource Lease
System Executor
Cluster Executor
DB State Validator
```

---

# 66. Executor 体系

建议拆分：

```text
SQL Executor
Session Executor
System Executor
Cluster Executor
```

职责：

```text
SQL Executor
→ statement/query/prepare/metadata

Session Executor
→ multi-session/blocking/transaction

System Executor
→ process/file/script/service/config/backup/restore

Cluster Executor
→ node lifecycle/failover/switchover/rejoin/rebalance
```

---

# 67. Adapter 体系

数据库差异必须隔离在 Adapter 层。

建议：

```text
DatabaseAdapter
AdminAdapter
ClusterAdapter
BackupAdapter
```

先实现：

```text
XuguDatabaseAdapter
```

后续再扩展：

```text
PostgreSQL
MySQL
Oracle
```

Core 禁止出现大量：

```python
if db_type == "xugu":
```

---

# 68. Result Normalizer

所有比较使用版本化 Canonical Result（canonical_version=1），策略与语义哈希绑定。

默认保留类型、空值、字符串空白、Decimal 精度、时间精度和行重复次数；不能静默 trim、字符串化或转换时区。
类型映射、列类型断言、浮点容差、NaN/Infinity、时间与二进制编码、分帧 Hash 和流式限制由 [11](11_Execution_Consistency_and_Validation_Contract.md)统一规定。
按列预绑定 Normalizer 是优化，不得改变比较语义。未知类型显式 FRAMEWORK_NORMALIZATION，不自动退化成字符串比较。

---

# 69. Validator Framework

Validator 不只验证 SQL Result。

建议：

```text
SQL Result Validator
Expected Error Validator
Catalog Validator
Transaction Validator
Cluster Validator
Backup Validator
State Validator
```

---

# 70. SQL Result Validator

支持：

```text
Exact
RowSort
ValueSort
Hash
```

Hash 用于大结果，不代表所有 Query 默认 Hash。

---

# 71. Expected Error Validator

建议匹配：

```text
error_code
sqlstate
error_class
message_regex
```

不要默认完整 Error Message 字符串完全相等。

---

# 72. Catalog Validator

用于验证：

```text
Table
Column
Index
Constraint
Partition
View
Sequence
Procedure
Trigger
```

在系统 Catalog 中是否符合预期。

---

# 73. Transaction Validator

用于：

```text
Visibility
Blocking
Commit
Rollback
Isolation
Deadlock
Lock State
```

---

# 74. Cluster Validator

用于：

```text
Primary Count
Replica State
Node Health
Replication
Data Consistency
Failover Result
Rejoin Result
```

---

# 75. Backup Validator

用于：

```text
Backup Success
Restore Success
Object Count
Data Hash
Recovery Point
Backup Integrity
```

---

# 76. Large Result

exact 使用 fetchmany 与流式分帧比较；hash exact 使用同一 Canonical 编码增量 SHA-256。
rowsort/hash rowsort 使用有内存上限的外部归并排序，按完整 Canonical Row 字节排序，保留重复次数，不能仅对分批结果分别排序。
达到临时磁盘或 Artifact 限额时报告 INFRA_RESOURCE；禁止截断后仍判 PASS。MVP 不支持的模式在 validate 阶段拒绝。

---

# 77. Logging Strategy

默认 INFO 日志只记录：

```text
Case ID
Status
Duration
Environment
Progress
```

失败时再追加：

```text
SQL
Expected
Actual
Diff
Error
Execution Plan
Server Log
```

不要让 PASS 日志淹没系统。

---

# 78. Agent Heartbeat

Agent 周期上报：

```text
agent_id
environment_id
health
running_shards
worker_usage
connection_count
resource_usage
result_buffer_size
timestamp
```

---

# 79. Agent Lost

Agent Lost 后：

```text
RUNNING Attempt → LOST
Pending Case    → Requeue
```

是否重试由：

```text
Failure Type
+
Idempotency
+
Destructive
+
Retry Policy
```

共同决定。

---

# 80. Retry 分类

建议区分：

```text
TEST_ASSERTION
TEST_EXPECTED_ERROR_MISMATCH
TEST_SQL_EXECUTION
TEST_TIMEOUT

INFRA_NETWORK
INFRA_AGENT_LOST
INFRA_DB_UNAVAILABLE
INFRA_RESOURCE

FIXTURE_SETUP / FIXTURE_CLEANUP
FRAMEWORK_NORMALIZATION / FRAMEWORK_PROTOCOL / FRAMEWORK_ERROR
```

完整枚举与归类以 [07 Result](07_Result_Model_Design.md) 为准。

默认：

```text
Assertion Fail
→ 不自动重试

Infrastructure Error
→ safe Case 可重试

unsafe/destructive
→ 不自动重放
```

---

# 81. Attempt Model

Case 是测试资产。

Attempt 是执行实例。

例如：

```text
Attempt 1
Cluster A
LOST

Attempt 2
Cluster B
PASS
```

两个 Attempt 都必须保留。

---

# 82. Result Event

Agent → Controller 使用 ResultEvent。

字段：

```text
event_id
schema_version
run_id
case_id
target_id
attempt_id
producer_epoch / sequence
fencing_token
step_id
environment_id
timestamp
event_type
payload
```

---

# 83. Event Idempotency

Event 使用稳定 event_id=(attempt_id, producer_epoch, sequence)，另有 target_id、lease token、schema_version；step_id 是载荷维度，sequence 在 Attempt 内递增。
Controller 持久化事件、去重记录与状态投影后才 ACK 连续序列；乱序暂存，冲突重复进入协议错误。
终态不可被迟到事件覆盖。LOST 后到达的旧 PASS 仅保留审计，不改变新 Attempt 或已锁定 Baseline。见 [07](07_Result_Model_Design.md)。

---

# 84. Agent Local Result Buffer

Worker → 持久化本地 WAL → Controller Durable ACK → Compact。
Controller 短暂不可用时，只能在租约仍有效、WAL 有可用空间且资源可安全控制时继续已有任务；不得无限离线运行。
WAL 达到高水位暂停新 Case；达到硬上限停止可停止执行并保留故障证据。恢复重放不绕过终态和租约规则。

---

# 85. Result Model

层级：

```text
Run
 └── CaseExecution (case_id + target_id)
      └── Attempt
           └── StepResult
                └── Artifact
```

---

# 86. Run State

```text
CREATED
PLANNING
RUNNING
COMPLETED
FAILED
CANCELLED
```

---

# 87. Attempt State

```text
PENDING
ASSIGNED
RUNNING
PASS
FAIL
ERROR
TIMEOUT
LOST
CANCELLED
SKIP
```

FLAKY 建议作为 CaseExecution 聚合结论，不作为 Attempt 状态。

---

# 88. Case Final Status

建议：

```text
PASS
FAIL
ERROR
TIMEOUT
SKIP
FLAKY
INFRA_RECOVERED
CANCELLED
INCOMPLETE
```

例如：

```text
A1 LOST
A2 PASS
→ INFRA_RECOVERED

A1 FAIL
A2 PASS
→ FLAKY
```

---

# 89. Artifact

失败 Artifact 可包含：

```text
SQL
Expected
Actual
Diff
Server Log
Execution Plan
Stack
pstack
Core Info
Cluster State
Backup Log
```

Result DB 不直接保存大文件，只保存：

```text
URI
size
sha256
metadata
```

---

# 90. Result Storage

MVP：

```text
JSONL
Local Artifact Directory
```

成熟阶段：

```text
PostgreSQL Result DB
MinIO/S3 Artifact Store
```

---

# 91. Allure / JUnit

Durable Event Log 是执行历史事实源；Result DB 是可重建查询投影及锁定发布快照。
Allure 为展示层，JUnit 为 CI 集成层。Reporter 不得改变原始终态或统计分母；CI 退出码结合 Run/Quality Gate，不能仅依据报告中没有 failure。

---

# 92. Release Baseline

发布验证不能只输出总通过率。

Test Plan 可以：

```yaml
baseline:
  run_id: release-5.0.3-final
```

Current Run 与 Baseline 进行比较。

---

# 93. Delta 分类

Delta 分 membership、case、context、outcome 四个维度，完整枚举以 [10](10_Release_Baseline_and_Delta_Design.md) 为准。

NEW_CASE/REMOVED_CASE 与 NEWLY_SELECTED/NOT_SELECTED 区分；CASE_CHANGED 与 METADATA_CHANGED 区分；环境/运行时/模型变化单列。
只有语义和目标可比的样本产生严格 NEW_FAILURE/FIXED/PERSISTENT_FAILURE；不可比样本保留原始状态并标 NOT_COMPARABLE，不伪装成产品回归。

---

# 94. New Failure

可比集合内：Baseline=PASS/INFRA_RECOVERED，Current=FAIL/ERROR/TIMEOUT → NEW_FAILURE。
进一步按 failure_type 区分产品、基础设施、框架/Fixture 失败。未知或缺失结果影响完整性门禁，不能简单计为零新增失败。

---

# 95. Fixed

可比集合内：Baseline=FAIL/ERROR/TIMEOUT，Current=PASS/INFRA_RECOVERED → FIXED。
区分产品修复与环境/框架恢复；用例语义已改变或基线不完整时不能宣称确定修复。

---

# 96. Persistent Failure

Baseline 与 Current 在可比语义和目标条件下均失败，标为 PERSISTENT_FAILURE。
Failure Signature 仅用于候选问题聚类，不能证明同一根因；同时报告 signature_changed 供分析。

---

# 97. Failure Signature

Failure Signature 规则统一由 [07 Result](07_Result_Model_Design.md)定义：failure_type、规范错误、规范 stack、稳定 failing_step_id 与 semantic_hash。
剔除时间戳、随机 schema/对象名、Session ID 和地址；归一化规则也必须版本化。
签名只用于相似失败候选聚类，不作为根因相同或版本质量不变的充分证据。

---

# 98. Coverage Feedback

每次 Run 完成后产生 Coverage Snapshot：

```text
Designed
Available
Selected
Executed
Passed
```

用于回答：

```text
P0 是否 100% 执行？
哪些 Feature 被跳过？
哪些环境未覆盖？
哪些 Coverage Gap 仍存在？
```

---

# 99. Quality Gate

门禁用结构化阈值，比例统一为 0..1 数值；不解析任意表达式。

```yaml
quality_gate:
  p0_execution_rate: {op: gte, value: 1.0}
  p0_pass_rate: {op: gte, value: 1.0}
  p1_execution_rate: {op: gte, value: 0.98}
  new_failure: {op: eq, value: 0}
  unsupported_rate: {op: lt, value: 0.01}
  max_flaky: {op: lte, value: 5}
```

分母在能力过滤和实际调度前冻结，SKIP/未执行不得缩小分母。模型变化、环境变化和用例变化单列。
门禁为 PASS / FAIL / INDETERMINATE / NOT_APPLICABLE；发布只有所有必需门禁 PASS 才可通过。详见 [10](10_Release_Baseline_and_Delta_Design.md)。

---

# 100. Generator Framework

Generator 不应成为“随机 SQL 工厂”。

应围绕：

```text
Test Model
Coverage Gap
Coverage Strategy
Constraint
Template
```

生成 Candidate Case。

---

# 101. Generation Strategy

支持：

```text
manual
template
pairwise
boundary
negative
interaction
bug
import
```

SQLancer 不属于这里的核心 Generator。

---

# 102. SQLancer 的正确位置

SQLancer 适合：

```text
Exploratory / Logic Bug Discovery
```

流程：

```text
SQLancer
→ 发现 Bug
→ Minimize
→ 人工确认语义
→ 转成确定性 XG Case
→ active Regression Asset
```

SQLancer 不应直接作为 Release Regression 主执行框架。

---

# 103. Pairwise 的正确位置

Pairwise 不是直接生成随机 SQL。

而是：

```text
从 Test Model 维度
选择高价值组合
```

再结合 Template 形成 Case。

---

# 104. Case Deduplication

至少检查：

```text
Case ID
Normalized SQL
Coverage Signature
Template Parameter Signature
```

后续可扩展 SQL Semantic Fingerprint。

---

# 105. Candidate Trial Run

生成 Case 进入 Active 前至少验证：

```text
Syntax
Setup
Expected Result
Cleanup
Repeatability
Determinism
```

---

# 106. Review Workflow

建议：

```text
Generator / Author
→ branch
→ validate
→ trial-run
→ PR
→ review
→ merge
→ catalog update
```

---

# 107. Web UI

Web UI 不应在早期成为核心逻辑层。

UI 仅调用 Core API：

```text
Feature / Coverage
Case Catalog
Selector
Test Plan
Run
Result
Baseline
Environment
```

禁止 UI 自己实现一套独立 Selector/Scheduler 逻辑。

---

# 108. CLI

建议命令：

```text
xgtest validate
xgtest index
xgtest catalog verify
xgtest list
xgtest coverage
xgtest generate
xgtest run
xgtest plan
xgtest env
xgtest agent
xgtest report
xgtest baseline
```

---

# 109. 推荐仓库结构

```text
allone/

├── docs/
│   ├── architecture/
│   ├── specifications/
│   ├── modules/
│   └── README.md                 # 当前文档入口
│
├── models/
│   ├── tests/
│   └── coverage/
│
├── tests/
│   ├── query/
│   ├── ddl/
│   ├── dml/
│   ├── transaction/
│   ├── concurrency/
│   ├── datatype/
│   ├── function/
│   ├── index/
│   ├── partition/
│   ├── view/
│   ├── procedure/
│   ├── trigger/
│   ├── privilege/
│   ├── security/
│   ├── storage/
│   ├── backup_restore/
│   ├── cluster/
│   ├── ha/
│   └── regression/
│
├── fixtures/
│
├── generators/
│   ├── models/
│   ├── templates/
│   └── constraints/
│
├── plans/
├── environments/
├── configs/                       # 运行配置
├── registry/                      # Feature/Capability/Enum 唯一源
├── schemas/                       # 由严格 Core Model 生成
├── framework_tests/               # 平台测试，不进入 Case Catalog
│   ├── contract/
│   ├── integration/
│   ├── scenario/
│   └── chaos/
├── benchmarks/
│
├── xgtest/
│   ├── design/
│   │   ├── model/
│   │   ├── coverage/
│   │   └── generator/
│   │
│   ├── core/
│   │   ├── model/
│   │   ├── registry/
│   │   ├── contracts/
│   │   ├── resource_admission/
│   │   ├── metadata/
│   │   ├── capability/
│   │   └── result/
│   │
│   ├── parser/
│   │   ├── xgt/
│   │   └── scenario/
│   │
│   ├── compiler/
│   ├── catalog/
│   ├── selector/
│   ├── control/
│   │   ├── planner/
│   │   ├── scheduler/
│   │   ├── environment/
│   │   └── run_manager/
│   │
│   ├── agent/
│   │   ├── planner/
│   │   ├── resource/
│   │   ├── worker/
│   │   └── heartbeat/
│   │
│   ├── executor/
│   │   ├── sql/
│   │   ├── session/
│   │   ├── system/
│   │   └── cluster/
│   │
│   ├── adapter/
│   │   ├── database/
│   │   ├── admin/
│   │   ├── cluster/
│   │   └── backup/
│   │
│   ├── normalizer/
│   ├── validator/
│   ├── result/
│   ├── reporter/
│   └── cli/
│
├── scripts/
└── pyproject.toml
```

tests/ 继续保存数据库功能用例；framework_tests/ 验证平台本身。Registry 与模型生成链详见 [12](12_Machine_Contracts_and_Engineering_Validation.md)，不要在多个目录维护重复 Feature 定义。

---

# 110. 性能原则

目标规模：

```text
S   1,000 Case
M   10,000 Case
L   100,000 Case
XL  500,000+ Case
```

禁止：

```text
Fast Path 默认每 Case 建 Connection（故障恢复或强隔离例外）
Fast Path 默认每 Case 建 Schema（强隔离 Case 例外）
每 Case 启 Process
每次扫描所有文件
每条 PASS 写大量日志
每个 Case 一个独立小报告文件
大结果 fetchall
```

---

# 111. Catalog 性能

Catalog 目标：

```text
100,000 Case
按 module / feature / level / tag / issue / status
热查询 p95 <= 2s；硬件和缓存条件见 11
```

实际目标需 Benchmark 验证。

---

# 112. Worker 性能

理想情况下：

```text
Framework Overhead
<<
Database Execution Time
```

对于 Fast Case：

```text
Connection Reuse
Prepared Metadata
Normalizer Pre-binding
Minimal Result Event
```

非常关键。

---

# 113. Result 性能

PASS：

```text
只保存必要摘要
```

FAIL：

```text
保存详细上下文
```

防止 10 万 PASS Case 生成数 GB 报告。

---

# 114. Controller 性能

Controller 不应：

```text
每条 SQL RPC
每个 Value RPC
```

正确：

```text
Controller
→ 下发 Shard

Agent
→ 本地连续执行大量 Case
```

---

# 115. 分布式可靠性

必须考虑：

```text
Agent Crash
Controller Restart
Network Partition
DB Environment Failure
Result Duplicate
Lease Expiry
Partial Cleanup
```

从第一版模型就保留：

```text
Attempt
Lease
Event ID
Heartbeat
Idempotency
Destructive
```

---

# 116. Security

禁止在 Catalog / Result / Log 中存：

```text
password
token
private key
connection secret
```

需要：

```text
Secret Provider
Log Redaction
TLS
Agent Authentication
```

---

# 117. Plugin / pytest 边界

pytest 可以作为：

```text
开发者入口
插件
局部测试
```

但正式 Release Runner 应是：

```bash
xgtest run --plan ...
```

这样 Core 生命周期和执行模型由 XG DB Test 自己控制。

---

# 118. Allure 边界

Allure：

```text
结果展示
趋势展示
附件展示
```

不负责：

```text
Case Source of Truth
Scheduler
Result Truth
Coverage Truth
```

---

# 119. Change Impact

后期能力：

```text
Git Diff
→ Code-to-Feature Mapping
→ Feature Impact
→ Recommended Test Plan
```

不进入 MVP，但架构预留。

---

# 120. 第一阶段必须冻结的契约

开发前必须冻结：

```text
Domain Taxonomy
Feature Registry
Capability Registry
Case ID
Metadata Schema
Test Model Schema
Coverage Signature
Case Lifecycle
.xgt v1.1
.xgs.yaml v1.1
Unified Case Model
Catalog Schema
Result Model
Attempt State Machine
Retry Rules
Idempotency
Resource Lease
Environment Model
```

---

# 121. Phase 0：规范冻结

完整前置条件、Driver 探测、首条用例闭环及 Phase 0–6 工作包顺序见 [13 工程实施顺序与阶段验收](13_Engineering_Implementation_Order.md)。下列各节继续定义架构阶段范围，具体实施依赖由 13 展开。

目标：

```text
只定模型，不追求大规模运行
```

产出：

```text
Feature Registry
Test Model Schema
Metadata
DSL
Case Model
Catalog Model
Result Model
Environment Model
```

同时冻结当前 SQL MVP 所需 Registry/严格 Core Model 与 Schema 生成方向、XGMJ1/Canonical 基础向量、共享准入规则和反例。模型与标准测试向量可以共同迭代；不要求尚未实现的分布式混沌测试在编码前完成。

---

# 122. Phase 1：单集群 SQL MVP

范围：JOIN、UNION、DDL TABLE、STRING FUNCTION 各 10~50 个真实样板；不立即铺全库。

实现 Metadata 1.1、XGT 1.1 SQL 子集、Unified Case、Catalog 2、Selector、不可变 Manifest/Bundle、本地 target、Attempt/Result 2、Persistent Worker、Xugu Adapter、Reset/Probe、Canonical 1、Exact/RowSort/Error、JSONL/JUnit。

同时实现最小手工覆盖声明与 all-values/mandatory-combination Snapshot，确保 MVP 可回答 Coverage Gap；自动组合生成不在本阶段。
本地执行也保留 Attempt、资源所有权和最终状态；分布式续租、Agent RPC 在 Phase 4 实现。
验收与量化性能场景见 [11](11_Execution_Consistency_and_Validation_Contract.md)。

工程化交付还包括 Catalog Verify、非空 Claim 的有效覆盖审查、Schema/Registry 导出一致性、本地事件重放和 Reset/Probe 集成反例。INFRA_RECOVERED 统计从本阶段保存；完整发布门禁仍按 Phase 6 实施。

---

# 123. Phase 2：Coverage 与 Generator

在 Phase 1 的显式覆盖声明与基础 Snapshot 上扩展 pairwise/boundary/negative/interaction，加入 Template Generator、约束求解、去重与 Trial Run。
Lifecycle 校验从 Phase 1 存在；Phase 2 完成生成候选、Review 和覆盖缺口反馈流程。不得用 Generator 补偿不可信 Oracle。

---

# 124. Phase 3：Transaction / Concurrency

实现：

```text
Scenario DSL
Session Manager
Parallel
Barrier
Signal
Blocking
Deadlock
Isolation
Transaction Validator
```

---

# 125. Phase 4：多集群

实现：

```text
Environment Registry
Agent
Heartbeat
Global Planner
Global Scheduler
Shard
Matrix
分布式 Lease / Fencing
Attempt 迁移与恢复
Agent Result Buffer
```

---

# 126. Phase 5：System Feature

实现：

```text
Backup
Restore
Cluster
HA
Configuration
Administration
System Executor
Cluster Executor
Backup Adapter
Cluster Adapter
```

---

# 127. Phase 6：Release Quality

实现：

```text
Result DB
Baseline / Delta 引擎（所需快照从 Phase 1 保存）
Failure Signature 聚类
Flaky 历史分析（基础聚合从 Phase 1 存在）
Coverage Snapshot 历史比较
Quality Gate
Dashboard
Change Impact
```

---

# 128. MVP 验收标准

第一版不是只看 Runner 是否能执行。

至少能回答：

```text
1. 当前有哪些 Feature？
2. JOIN 有哪些测试维度？
3. 当前 JOIN 有多少 Active Case？
4. 哪些 Coverage Gap 还没补？
5. 能否只跑 JOIN + UNION？
6. 能否只跑 P0/P1？
7. 能否按 Bug Issue 选例？
8. Case 来源是否可追踪？
9. Case 生命周期是否明确？
10. Case 是否能稳定重复执行？
11. Result 是否可确定性比较？
12. 下一版本能否复用同一套资产？
```

---

# 129. 多集群阶段验收标准

至少：

```text
1. 多 Environment 注册
2. Capability Match
3. Shard 分配
4. Worker Pool 并行
5. Agent Heartbeat
6. Agent Lost → LOST Attempt
7. safe Case 自动重新调度
8. exclusive Case 使用 Lease/Fencing，恢复失败隔离
9. Matrix 保留 target 与实际 Environment 维度
10. ResultEvent 持久化、有序幂等重放，迟到事件不回退终态
```

---

# 130. Release 阶段验收标准

至少能够输出：

```text
New Failure
Fixed
Persistent Failure
New Case
Removed Case
Flaky
Coverage Delta
P0/P1 Execution Rate
Quality Gate
```

---

# 131. 核心架构原则

1. Feature Model 是测试体系起点。
2. Test Model 定义“应该怎么测”。
3. Coverage Model 衡量“测得够不够”。
4. Case 是长期资产，不是临时 SQL 脚本。
5. Git 是测试资产事实源。
6. Catalog 是执行索引，不是事实源。
7. Generator 服务 Coverage，不追求 Case 数量。
8. Regression Case 优先归入实际 Feature。
9. Selector 是 Release 回归核心能力。
10. Persistent Worker/Connection 是大规模性能基础。
11. Case 与 Attempt 必须分离。
12. Destructive/Idempotency 必须进入正式模型。
13. Resource 使用 Lease、Fencing 和停止/恢复证明，过期不等于可回收。
14. Controller 做 Run/Shard 级控制，不做 SQL 级调度。
15. Agent 仅在租约有效、WAL 可用和资源安全条件满足时离线继续执行。
16. ResultEvent 必须持久化、幂等、有序投影且不能回退终态。
17. Validator 必须覆盖数据库状态，而非只比 ResultSet。
18. Durable Event Log 是执行历史事实源，Result DB 是投影/锁定快照，Allure 是展示层。
19. Release 必须做 Baseline/Delta，不只看通过率。
20. Coverage 必须形成反馈闭环。
21. 分布式能力设计完整，但实现优先级低于测试资产闭环。
22. SQLancer 只作为探索性 Bug 发现工具，不作为正式回归主框架。

---

# 132. 推荐第一批真实样板

为验证整体设计，建议第一批不要铺全库，选择四类：

```text
Query JOIN
Query UNION
DDL TABLE
Function STRING
```

每类完成：

```text
Feature Registry
Test Model
Coverage Model
10~50 条手工/生成 Case
XGT
Catalog
Selector
Local Runner
Result
Coverage Snapshot
```

当这条链真正跑通后，再扩展 Transaction 和 Multi-cluster。

---

# 133. 最终结论

XG DB Test 的核心不是：

```text
“把很多 SQL 跑得很快”
```

而是：

> **建立数据库原厂可持续演进的功能测试资产体系：从 Feature Model 和 Test Model 出发，通过 Coverage 驱动 Case 建设，利用 Catalog 和 Selector 精确组织版本回归，通过单集群/多集群执行引擎高效验证，并使用 Baseline、Delta 和 Coverage Feedback 形成长期质量闭环。**

这应作为 XG DB Test v1.1 的正式架构基线。


# 134. v1.1 契约责任与兼容边界

本修订保持五平面和阶段范围，补齐可实现契约。01 是修订与验收索引；04 管 Metadata；05 管 Catalog；06 管资源调度；07 管事件与状态；08 管覆盖；10 管发布口径；11 管不可变执行、隔离和结果比较；12 管机器契约源、生成与工程验收。

架构文档版本 1.1；DSL/Metadata/Protocol 1.1；Catalog/Result Schema 2；Canonical 1。数据 Schema 不兼容升级独立编号，不因总体架构仍为 v1 而静默兼容。
旧 Query 方案仅保留背景；DSL 1.0 必须走独立解析器/显式转换，历史 Result 1 不直接并入 Result 2。尚无实现时，以下验收均为待开发要求，不代表已经通过。

当前图：[SVG](../架构图_v1.svg) · [PNG](../架构图.png)。关键路径为显式覆盖声明 → 编译/索引 → Manifest/Bundle → 受控执行 → WAL/投影 → 可比 Delta/门禁 → 覆盖缺口。

# 135. v1.1 工程化补充

[优化清单评审](XG_DB_Test_v1.1_可优化项_List.md)中的 16 项有价值目标已按阶段纳入，原建议的资源类型冲突表、Session 归属树、清理后才比较结果的顺序和 tests/ 目录布局已修正。

| 共享能力 / 模块 | 职责与落地位置 |
|---|---|
| Registry / Core Model / Schema | Registry 统一枚举，严格 Core Model 生成结构 Schema，语义与运行时校验独立，见 12 |
| Contract Test / Golden Vector | 固定字节、哈希、状态与反例，按阶段在 framework_tests/ 落地；不由被测实现自动生成期望值 |
| ResourceAdmissionEngine | 共用冲突域算法与原子授予，跨库 Session/Node 影响/容量不可遗漏，见 06 |
| Catalog Verify | 对绑定快照只读检查 Metadata/依赖/Claim/Hash；损坏、漂移、证据不足分别报告，见 05 |
| Coverage Review | review_input_hash 绑定执行语义、Claim、Model、断言；仅改声明也失效，见 04/08/09 |
| Manifest Serialization | XGMJ1 身份投影、数字、Unicode、数组和内容引用规则，见 11 |
| Recovery Workflow | 隔离期间关闭准入，恢复证明绑定当前 epoch，enable 不能直接解封，见 06 |
| 基础设施门禁 | 可选 max_infra_recovered / infra_recovered_rate，使用冻结分母，不改变产品通过语义，见 07/10 |
| Benchmark | 对照执行与固定测量条件，区分框架开销、数据库时间、内存和事件成本，见 11/12 |

这是一组横跨现有五平面的共用契约和验收，非新增运行平面。模型、Schema 与网络协议有显式生成/映射关系；Protobuf/gRPC 不作为 SQL MVP 必需项。
