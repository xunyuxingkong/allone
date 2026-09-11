# XG Query Test 架构设计方案

> 历史背景稿：当前实施以 [总架构 v1.1](XG_DB_Test_Architecture_Design_v1.md)及 01–11 专项契约为准。本文原有 DSL、工期估计和范围不作为当前验收依据。

> 面向数据库原厂查询模块的确定性功能测试、版本回归、用例资产管理与可选择执行框架。
>
> 文档状态：方案设计稿
> 适用范围：Xugu/虚谷数据库 Query 模块
> 核心目标：**分类分层、稳定复现、精确选择、批量执行、可靠校验、长期沉淀**

---

## 1. 背景

数据库原厂在查询模块测试中，通常会长期积累大量 SQL 功能用例，覆盖从简单查询到复杂组合查询，例如：

- 基础 SELECT、投影、别名、常量；
- WHERE、谓词、NULL 语义；
- ORDER BY、LIMIT/OFFSET、DISTINCT；
- 聚合、GROUP BY、HAVING；
- JOIN：INNER/LEFT/RIGHT/FULL/CROSS/SELF/多表 JOIN；
- 子查询：标量、IN、EXISTS、相关子查询、嵌套子查询；
- 集合运算：UNION/UNION ALL/INTERSECT/EXCEPT；
- CTE、递归 CTE；
- 窗口函数；
- 多功能组合查询；
- 历史 Bug 回归。

随着数据库版本持续迭代，单纯把 SQL 脚本散落在目录中会逐渐出现以下问题：

1. 用例缺乏统一的功能分类和层级模型；
2. 无法明确知道一条 SQL 到底覆盖哪些查询能力；
3. 发布新版本时无法方便地只选择 JOIN、UNION 等指定范围进行回归；
4. 用例执行逻辑、结果校验逻辑与 SQL 本身耦合；
5. 大结果集、无序结果、NULL、浮点、时间等场景容易产生大量误报；
6. 并发执行后出现表名冲突、会话污染、环境污染；
7. Bug 修复后缺少稳定、可追踪的永久回归资产；
8. 自动生成用例容易组合爆炸，且生成结果不可重复；
9. 传统 TCMS 更擅长测试计划和人工用例管理，并不天然适合数万级 SQL 自动化资产。

因此需要建设一套面向数据库原厂的 **XG Query Test**。

---

## 2. 建设目标

XG Query Test 的核心定位不是“通用测试管理平台”，而是：

> **面向数据库 Query 模块的 SQL 功能测试基础设施。**

系统重点解决以下问题：

### 2.1 用例分类与分层

建立稳定的 Query Feature Taxonomy，使所有测试用例都能映射到明确的功能树。

### 2.2 用例资产化

SQL、预期结果、预期错误、测试元数据统一存放在 Git 中，可 Review、Diff、Branch、Merge、Tag、回滚和版本追踪。

### 2.3 精确选择执行

支持按以下维度选择测试范围：

- directory；
- module；
- feature；
- subfeature；
- level；
- tag；
- complexity；
- source；
- version；
- issue；
- 组合表达式。

例如：

```bash
xgtest run --feature join --feature union
```

或者：

```bash
xgtest run \
  --select "(feature=join or feature=union) and level in (P0,P1) and not tag=slow"
```

### 2.4 稳定、确定性的版本回归

同一用例在 5.0、5.1、5.2 等版本之间保持稳定 Case ID、SQL 和验证规则，便于版本间结果对比。

### 2.5 可靠的结果校验

第一阶段支持：

- Exact Result；
- Unordered Result；
- Expected Error；
- Result Hash。

后续扩展：

- Differential；
- Property；
- Metamorphic。

### 2.6 工程化执行

支持：

- CLI；
- Test Plan；
- 并行 Worker；
- Sharding；
- 失败重跑；
- 超时；
- 环境隔离；
- JUnit XML；
- Allure；
- Jenkins/CI/K8s 集成。

---

## 3. 非目标

第一阶段明确不建设以下能力：

- 不做完整 TCMS；
- 不做需求管理；
- 不做 Bug 管理系统；
- 不做复杂 Web 平台；
- 不把 pytest 当作核心执行模型；
- 不把 SQLancer 纳入 Query Test 核心链路；
- 不在第一阶段建设复杂 Differential/Metamorphic 系统；
- 不在第一阶段做 AI 自动生成和 AI 自动判定正确结果。

目标是先把：

> **分类管理 + 精确选择 + 稳定执行 + 正确校验**

四件事做好。

---

# 4. 总体架构

```text
                         XG QUERY TEST
                              │
                    ┌─────────┴──────────┐
                    │                    │
                Test Assets          XG Test Core
                    │                    │
             XG SQLLogic DSL        Parser
             + Metadata             Case Model
                    │               Selector
                    │               Planner
                    │               Runner
                    │               Validator
                    │                    │
                    └──────────┬─────────┘
                               │
                         Database Adapter
                               │
                          Xugu Adapter
                               │
                             Xugu
                               │
                       Result Normalizer
                               │
                    ┌──────────┴──────────┐
                    │                     │
                 Validator             Artifact
                    │
      ┌─────────────┼────────────┐
      ↓             ↓            ↓
    Exact        Expected       Hash
                 Error
                    │
                    ↓
                 Result Store
                    │
         ┌──────────┼──────────┐
         ↓          ↓          ↓
       Allure     JUnit       CLI
                              │
                         Jenkins / CI
```

外围增强能力：

```text
Template Generator
Pairwise Generator
pytest Plugin
Differential Validator
Metamorphic Plugin
Change Impact Analysis
Web UI
```

SQLancer 等随机/逻辑一致性探索工具保持独立，只在发现 Bug 后将最小复现用例沉淀为 XG Query Test Regression Case。

---

# 5. 核心设计原则

## 5.1 SQL 是测试资产主体

测试人员不应为了写一条查询测试而编写大量 Python：

```python
cursor.execute(...)
assert actual == expected
```

查询功能测试应尽量保持：

```text
SQL
+
Expected Result / Expected Error
+
Metadata
```

因此 DSL 借鉴 DuckDB/SQLite SQLLogicTest 的思想，但扩展 XG 自己的 Metadata 和运行能力。

## 5.2 目录、Metadata、Tag 各司其职

约定：

```text
Directory = 主功能树
Metadata  = 正式测试属性
Tag       = 横向自由组合标签
```

不要把 NULL、VARCHAR、P0、Regression 等全部继续做成目录，否则最终目录结构会失控。

## 5.3 Git 是测试资产唯一事实源

测试用例必须支持：

- Commit；
- Review；
- Diff；
- Branch；
- Merge；
- Cherry-pick；
- Tag；
- 历史回溯。

因此用例主体不应该优先存放在 Kiwi TCMS/TestLink 等数据库中。

## 5.4 Query Test Core 不绑定 pytest

核心链路：

```text
DSL
 ↓
Parser
 ↓
Case Model
 ↓
Selector
 ↓
Planner
 ↓
Runner
 ↓
Adapter
 ↓
Validator
```

pytest 只作为可选开发者入口/生态插件。

## 5.5 Generator 是“用例生产工具”，不是默认运行时随机生成器

推荐流程：

```text
Template/Pairwise
       ↓
Generate .xgt
       ↓
Review
       ↓
Git
       ↓
Release Regression
```

保证每次版本回归执行相同的测试资产。

---

# 6. Query 功能分类模型

建议第一版固定如下功能树。

```text
tests/query/

00_basic/
    select/
    projection/
    alias/
    wildcard/
    literal/

01_expression/
    arithmetic/
    comparison/
    logical/
    conditional/
    cast/
    null/

02_filter/
    where/
    between/
    in/
    like/
    exists/

03_sort_limit/
    order_by/
    limit/
    offset/
    distinct/

04_aggregate/
    aggregate/
    group_by/
    having/
    grouping_sets/
    rollup/
    cube/

05_join/
    inner_join/
    left_join/
    right_join/
    full_join/
    cross_join/
    self_join/
    semi_join/
    anti_join/
    multi_join/

06_subquery/
    scalar/
    row/
    in/
    exists/
    correlated/
    nested/

07_set/
    union/
    union_all/
    intersect/
    except/

08_cte/
    simple/
    multiple/
    nested/
    recursive/

09_window/
    partition/
    order/
    frame/
    ranking/
    aggregate/
    navigation/

10_advanced/
    lateral/
    derived_table/
    pivot/
    hierarchical/
    db_specific/

11_complex/
    join_subquery/
    join_aggregate/
    union_join/
    cte_join/
    window_join/
    mixed/

12_regression/
```

其中：

- `00~10` 主要验证单功能；
- `11_complex` 验证 Feature Interaction；
- `12_regression` 保存重要历史 Bug 的永久回归用例。

---

# 7. 用例 DSL

建议定义 XG 自己的测试扩展名：

```text
.xgt
```

含义：XG Test。

示例：

```text
# xg:id QUERY.JOIN.INNER.000001
# xg:title Inner Join 基本等值连接
# xg:level P0
# xg:complexity basic
# xg:tags join,inner_join,equi_join,int
# xg:since 5.0.0
# xg:oracle exact
# xg:timeout 10s

statement ok
CREATE TABLE t1(
    id INT,
    name VARCHAR(20)
);

statement ok
CREATE TABLE t2(
    id INT,
    score INT
);

statement ok
INSERT INTO t1 VALUES
(1,'A'),
(2,'B');

statement ok
INSERT INTO t2 VALUES
(1,100),
(2,200);

query rowsort
SELECT
    t1.id,
    t1.name,
    t2.score
FROM t1
INNER JOIN t2
ON t1.id = t2.id;
----
1   A   100
2   B   200
```

建议第一阶段支持的 DSL 指令：

```text
statement ok
statement error
query
query rowsort
query valuesort
query hash
setup
cleanup
skipif
onlyif
```

后续再扩展 session/config/plan 等能力。

---

# 8. Metadata 模型

建议核心字段如下：

| 字段 | 示例 | 用途 |
|---|---|---|
| id | QUERY.JOIN.LEFT.0001 | 全局唯一 Case ID |
| title | LEFT JOIN NULL 匹配 | 用例名称 |
| module | query | 一级模块 |
| feature | join | 功能 |
| subfeature | left_join | 子功能 |
| scenario | null_match | 测试场景 |
| level | P0 | 回归等级 |
| complexity | basic | 复杂度 |
| tags | null,int,boundary | 横向标签 |
| oracle | exact | 验证类型 |
| since | 5.0.0 | 起始版本 |
| until | null | 结束版本，可选 |
| issue | XGDB-12345 | Bug 来源 |
| source | manual | 用例来源 |
| timeout | 10s | 超时 |
| isolation | schema | 隔离策略 |
| requires | feature_x | 前置能力 |
| owner | query | 维护团队 |

`source` 建议固定枚举：

```text
manual
template
pairwise
bug
import
```

---

# 9. Metadata 继承

不建议所有信息重复写在每个测试文件中。

支持目录级 `_suite.yaml`。

例如：

```text
tests/query/join/_suite.yaml
```

```yaml
module: query
feature: join

default:
  level: P1
  timeout: 30s
  isolation: schema

tags:
  - query
  - join
```

子目录：

```text
tests/query/join/left_join/_suite.yaml
```

```yaml
subfeature: left_join

tags:
  - left_join
```

具体用例只需要补充：

```text
# xg:level P0
# xg:tags null,boundary
```

最终合并结果：

```text
module      = query
feature     = join
subfeature  = left_join
level       = P0
tags        = query,join,left_join,null,boundary
```

优先级建议：

```text
Global Default
     ↓
Parent _suite.yaml
     ↓
Child _suite.yaml
     ↓
Case Header
```

Case Header 优先级最高。

---

# 10. Level 分级规范

等级必须有统一定义，否则几年后不同人员会随意标记。

## P0

核心语法、核心主路径、严重历史 Bug。

适用于：

- 每个 Build；
- Smoke；
- 快速准入。

## P1

常见场景、边界、主要功能组合。

适用于：

- 正式版本必跑；
- 日常回归。

## P2

复杂组合、低频特性、特殊类型。

适用于：

- 完整回归；
- Nightly。

## P3

超大规模、极端组合、长时间测试。

适用于：

- 专项；
- 周期性长稳。

以 JOIN 为例：

```text
P0
  INNER JOIN
  LEFT JOIN
  RIGHT JOIN
  基本 ON 条件
  NULL
  多行匹配

P1
  FULL JOIN
  多表 JOIN
  复杂 ON
  表达式 JOIN
  类型转换
  JOIN + WHERE
  JOIN + GROUP BY

P2
  JOIN + correlated subquery
  JOIN + window
  JOIN + UNION
  JOIN + CTE
  复杂 NULL 组合

P3
  20 表 JOIN
  超深嵌套
  超大数据组合
```

---

# 11. XG Test Core

建议核心代码结构：

```text
xgquery/
│
├── parser/
│   ├── lexer.py
│   ├── parser.py
│   └── metadata.py
│
├── model/
│   ├── case.py
│   ├── statement.py
│   ├── query.py
│   ├── result.py
│   └── plan.py
│
├── selector/
│   ├── directory.py
│   ├── feature.py
│   ├── tag.py
│   └── expression.py
│
├── planner/
│   ├── planner.py
│   ├── shard.py
│   └── dependency.py
│
├── runner/
│   ├── executor.py
│   ├── worker.py
│   ├── lifecycle.py
│   ├── retry.py
│   └── timeout.py
│
├── adapter/
│   ├── base.py
│   └── xugu.py
│
├── normalizer/
│   ├── value.py
│   ├── row.py
│   └── error.py
│
├── validator/
│   ├── exact.py
│   ├── unordered.py
│   ├── hash.py
│   ├── error.py
│   └── differential.py
│
├── generator/
│   ├── template.py
│   └── pairwise.py
│
├── reporter/
│   ├── console.py
│   ├── junit.py
│   ├── allure.py
│   └── json.py
│
├── config/
│   ├── loader.py
│   └── schema.py
│
└── cli/
    └── main.py
```

---

# 12. Case Model

Parser 不直接执行 SQL，而是先转换成统一 Case Model。

示意：

```python
@dataclass
class TestCase:
    id: str
    title: str
    metadata: CaseMetadata
    steps: list[TestStep]
    source_file: str
```

Step 可以是：

```python
StatementStep
QueryStep
SetupStep
CleanupStep
```

好处：

1. DSL 与执行器解耦；
2. 后续可以增加 YAML/JSON/API 等新的 Case Source；
3. pytest Collector 也可以直接消费 Case Model；
4. Web UI 不需要理解 `.xgt` 内部语法。

---

# 13. Selector

Selector 是整个框架的核心价值之一。

第一阶段至少支持：

```bash
xgtest run tests/query/join
```

```bash
xgtest run --module query
```

```bash
xgtest run --feature join
```

```bash
xgtest run --feature join --feature union
```

```bash
xgtest run --feature join --level P0,P1
```

```bash
xgtest run --tag null
```

```bash
xgtest run --tag regression --issue XGDB-12345
```

第二阶段支持表达式：

```bash
xgtest run \
  --select "(feature=join or feature=union) and level in (P0,P1) and not tag=slow"
```

Selector 的选择逻辑必须建立在统一 Case Metadata 上，而不是文件名模糊匹配。

---

# 14. Test Plan

正式版本测试不建议每次手工拼接大量命令行参数。

建议引入：

```text
plans/
```

例如：

```text
plans/release_query.yaml
```

```yaml
name: Query Release Regression

select:
  module:
    - query

  level:
    - P0
    - P1

exclude_tags:
  - slow
  - experimental

parallel: 20

retry:
  failed: 1

timeout: 60

report:
  allure: true
  junit: true
```

JOIN + UNION 专项：

```text
plans/join_union.yaml
```

```yaml
name: Join Union Regression

select:
  feature:
    - join
    - union

  level:
    - P0
    - P1
    - P2
```

执行：

```bash
xgtest run --plan join_union
```

---

# 15. Runner 生命周期

标准 Case 生命周期：

```text
Environment Prepare
        ↓
Database Connect
        ↓
Session Init
        ↓
Case Setup
        ↓
Statement / Query
        ↓
Result Normalize
        ↓
Validation
        ↓
Case Cleanup
        ↓
Environment Cleanup
```

失败时至少保存：

```text
Case ID
Metadata
SQL
Expected
Actual
Error Code
Error Message
Duration
DB Version
Node
Session Config
Worker ID
Source File
```

后续可附加：

- Execution Plan；
- Server Log；
- Trace；
- Core/Pstack；
- 失败现场保留信息。

---

# 16. Database Adapter

Runner 中禁止散落大量：

```python
if db == "xugu":
```

定义统一接口：

```python
class DatabaseAdapter:

    def connect(self):
        ...

    def close(self):
        ...

    def execute(self, sql):
        ...

    def query(self, sql):
        ...

    def begin(self):
        ...

    def commit(self):
        ...

    def rollback(self):
        ...

    def reset_session(self):
        ...

    def normalize_result(self, result):
        ...

    def normalize_error(self, error):
        ...
```

第一版实现：

```text
XuguAdapter
```

后续可以增加：

```text
PostgresAdapter
OracleAdapter
MySQLAdapter
```

用于兼容性或 Differential 场景。

---

# 17. Result Normalizer

这是整个系统难度最高、最值得认真设计的部分之一。

数据库结果不能简单做：

```python
actual == expected
```

至少需要处理：

- NULL；
- 空字符串；
- CHAR 尾空格；
- VARCHAR；
- INT/BIGINT；
- DECIMAL；
- FLOAT/DOUBLE；
- NaN；
- Infinity；
- DATE；
- TIME；
- TIMESTAMP；
- TIMEZONE；
- BOOLEAN；
- BINARY；
- CLOB/BLOB；
- 编码；
- 排序规则。

建议统一：

```text
Raw DB Result
       ↓
Canonical Result
       ↓
Validator
```

例如内部表示：

```text
SQL NULL      → CanonicalNull
Empty String  → ""
Decimal       → Decimal
Timestamp     → CanonicalTimestamp
Binary        → canonical hex/base64
```

不要简单把 NULL 转成字符串 `"NULL"`，否则无法与真实字符串 `NULL` 区分。

---

# 18. Validator

## 18.1 Exact

有明确排序语义：

```text
query
SELECT ... ORDER BY ...;
----
1 A
2 B
```

按照规范化结果逐行比较。

## 18.2 Unordered / RowSort

SQL 没有 ORDER BY 时，不应依赖数据库返回顺序。

```text
query rowsort
SELECT id,name FROM t;
----
1 A
2 B
```

比较前进行稳定排序。

## 18.3 Expected Error

不要只匹配完整错误文本。

建议支持：

```text
error_code
sqlstate
error_class
message_regex
```

示例：

```text
statement error code=XG-10023
SELECT unknown_column FROM t;
```

## 18.4 Result Hash

大结果集不适合把数十万行全部写进 Expected。

支持：

```text
query hash rowsort
SELECT ...;
----
rows: 100000
sha256: xxx
```

注意：必须先执行 Canonical Normalization，再计算 Hash。

## 18.5 Differential

属于扩展验证方式，不作为默认 Oracle。

不同数据库在以下语义上可能存在差异：

- NULL 排序；
- 隐式转换；
- 字符比较；
- 时间；
- 精度；
- 兼容模式。

因此 Differential Case 必须显式声明参考数据库和允许差异规则。

## 18.6 Metamorphic

属于高级正确性验证，不作为基础功能测试主流程。

建议做成独立 Validator/Plugin。

---

# 19. 并行执行与隔离

## 19.1 为什么必须有隔离模型

多个 Worker 同时执行：

```sql
CREATE TABLE t1(...);
```

会直接发生对象冲突。

因此 isolation 必须是一等属性。

建议支持：

```text
session
schema
database
cluster
```

Query 功能回归默认推荐：

```text
schema
```

示例：

```text
xgtest_worker_001
xgtest_worker_002
...
```

必要时支持 Case 独立 Schema。

## 19.2 Sharding

不要只简单使用：

```text
case_count / worker_count
```

后续应根据历史耗时进行均衡切分：

```text
CASE_A  0.2s
CASE_B  50s
CASE_C  0.4s
```

Planner 根据历史 duration 进行近似均衡分配，减少长尾 Worker。

## 19.3 失败现场

支持：

```bash
--keep-env-on-failure
```

便于研发直接进入失败 Schema/Session 排查。

---

# 20. Retry 与 Flaky

失败重跑不能直接把第二次成功视为“通过”。

Result Model 建议记录：

```text
PASS
FAIL
ERROR
SKIP
FLAKY
TIMEOUT
```

例如：

```text
attempt 1 = FAIL
attempt 2 = PASS
final     = FLAKY
```

后续可统计：

- Flaky Rate；
- 连续失败次数；
- 首次失败版本；
- 最近一次成功版本。

---

# 21. Result Store

Allure 只做展示，不作为历史结果数据库。

建议每次执行输出结构化 JSON：

```json
{
  "run_id": "20260911_001",
  "db_version": "5.0.3",
  "case_id": "QUERY.JOIN.LEFT.00032",
  "status": "FAILED",
  "duration_ms": 531,
  "worker": "worker-03",
  "expected": "...",
  "actual": "..."
}
```

第二阶段可落地 Result DB，用于：

- 历史趋势；
- 版本比较；
- Flaky 检测；
- 失败聚类；
- 用例耗时；
- Shard 调度；
- Dashboard；
- Change Impact；
- 后续 AI 分析。

第一版可先 JSON/JSONL，不必立即建设复杂数据库。

---

# 22. 报告

第一阶段直接使用 Allure + JUnit XML。

建议映射：

```text
Epic     = Query
Feature  = Join
Story    = Left Join
Severity = P0/P1/P2/P3
Tag      = null,int,regression,...
```

期望报告层次：

```text
Query
├── Basic
├── Filter
├── Aggregate
├── Join
│   ├── Inner Join
│   ├── Left Join
│   ├── Right Join
│   └── Full Join
├── Subquery
├── Set
├── CTE
├── Window
└── Complex
```

报告中至少展示：

- SQL；
- Expected；
- Actual；
- Error；
- Metadata；
- Duration；
- Database Version；
- Worker；
- Source File。

---

# 23. Generator

## 23.1 Template Generator

例如 JOIN 维度：

```text
JOIN TYPE
  INNER
  LEFT
  RIGHT
  FULL

CONDITION
  =
  <>
  >
  <
  IS NULL
  expression

DATA TYPE
  INT
  BIGINT
  DECIMAL
  VARCHAR
  DATE
  TIMESTAMP

DATA DISTRIBUTION
  normal
  NULL
  duplicate
  empty
  boundary
```

模板渲染生成 `.xgt`。

## 23.2 Pairwise Generator

如果全笛卡尔积：

```text
4 × 6 × 6 × 5 = 720
```

维度继续增加时会迅速爆炸。

Pairwise 用于在控制用例规模的同时覆盖主要二维组合关系。

需要同时支持 Constraint，例如：

```text
FULL JOIN 不支持某模式
某数据类型不能使用某操作符
某语法仅兼容模式生效
```

## 23.3 生成结果必须入 Git

推荐：

```text
Model
 ↓
Generator
 ↓
.xgt
 ↓
Review
 ↓
Git
 ↓
Stable Regression
```

不建议正式 Release Regression 每次运行时临时随机生成不同 SQL。

---

# 24. SQLancer 的边界

SQLancer 不属于 XG Query Test Core。

建议体系关系：

```text
                  Database Quality System

       ┌──────────────────┴──────────────────┐
       │                                     │
XG Query Test                           SQLancer
       │                                     │
确定性功能回归                           随机探索
       │                                     │
Feature Coverage                       Logic Bug Finding
       │                                     │
Release Validation                     Continuous Fuzzing
```

唯一推荐的连接方式：

```text
SQLancer
   ↓
发现 Bug
   ↓
最小化
   ↓
人工确认预期语义
   ↓
转换为 .xgt
   ↓
进入 XG Query Test Regression
```

这样职责清晰，不让探索性测试污染确定性发布回归体系。

---

# 25. pytest 的定位

pytest 不作为核心 Runner，但可以提供：

```text
pytest-xgquery
```

插件。

架构：

```text
                XG Test Core
                    │
         ┌──────────┼───────────┐
         ↓          ↓           ↓
       CLI      pytest Plugin   CI API
```

开发者可以：

```bash
pytest --xg tests/query/join
```

而正式发布回归仍推荐：

```bash
xgtest run --plan release_query
```

这样既获得 pytest 生态，又不让核心执行能力受 pytest Collection/Marker 模型限制。

---

# 26. CLI 设计

推荐命令：

```bash
xgtest list
xgtest run
xgtest validate
xgtest generate
xgtest plan
xgtest report
```

示例：

```bash
xgtest list --feature join
```

```bash
xgtest run --feature join --feature union
```

```bash
xgtest run --feature join --level P0,P1
```

```bash
xgtest run --plan join_union
```

```bash
xgtest validate tests/query
```

`validate` 用于提交前检查：

- Metadata 合法性；
- Case ID 唯一；
- DSL 语法；
- 缺失 Expected；
- 不存在 Feature；
- 重复 Case；
- 非法 Level；
- since/until 范围。

---

# 27. 推荐仓库结构

```text
allone/
│
├── docs/
│   └── XG_Query_Test_Architecture_Design.md
│
├── xgquery/
│   ├── parser/
│   ├── model/
│   ├── selector/
│   ├── planner/
│   ├── runner/
│   ├── adapter/
│   ├── normalizer/
│   ├── validator/
│   ├── reporter/
│   ├── generator/
│   └── cli/
│
├── tests/
│   └── query/
│       ├── 00_basic/
│       ├── 01_expression/
│       ├── 02_filter/
│       ├── 03_sort_limit/
│       ├── 04_aggregate/
│       ├── 05_join/
│       ├── 06_subquery/
│       ├── 07_set/
│       ├── 08_cte/
│       ├── 09_window/
│       ├── 10_advanced/
│       ├── 11_complex/
│       └── 12_regression/
│
├── plans/
│   ├── smoke.yaml
│   ├── release_query.yaml
│   └── join_union.yaml
│
├── configs/
│   ├── local.yaml
│   ├── ci.yaml
│   └── metadata_schema.yaml
│
├── generators/
│   ├── join/
│   ├── union/
│   └── models/
│
├── scripts/
│
├── pyproject.toml
└── README.md
```

---

# 28. Git 工作流

建议要求每个 Query Bug 修复尽量绑定 Regression Case。

示例：

```text
Bug XGDB-12345
       ↓
定位/修复
       ↓
新增 QUERY.REGRESSION.XGDB12345.xgt
       ↓
Code Review
       ↓
Merge
```

推荐规则：

> 对能够通过 SQL 稳定复现的 Query Bug，修复提交原则上必须同时增加 Regression Case。

这样测试资产会随着真实缺陷持续变强。

---

# 29. Change Impact Test（后续能力）

第二/三阶段可以建立：

```text
Source Change
      ↓
Git Diff
      ↓
Code → Feature Mapping
      ↓
Recommended Cases
      ↓
Generated Test Plan
```

例如修改：

```text
optimizer/join/
executor/hash_join/
```

推荐：

```text
join P0/P1
multi_join
join_subquery
join_union
optimizer_regression
```

未来提供：

```bash
xgtest recommend --commit abc123
```

但该功能依赖长期积累的 Code-to-Feature Mapping 和历史结果，不建议放在 MVP。

---

# 30. 可选 Web UI

第一阶段不建议开发。

真正需要多人版本管理、测试计划审批、可视化选择后，再建设轻量 UI。

理想交互：

```text
Query
☑ Join
   ☑ Inner Join
   ☑ Left Join
   ☑ Right Join

☑ Set
   ☑ Union

Level
☑ P0
☑ P1
□ P2

Tag
NULL
VARCHAR
Optimizer
Regression

[Preview Cases]
[Start Run]
```

Web UI 只调用 XG Test Core API，不重新实现 Selector/Runner。

---

# 31. 技术栈建议

第一版推荐 Python。

建议：

```text
Python              3.11+
Data Model          dataclasses / Pydantic
CLI                 Typer 或 Click
YAML                PyYAML / ruamel.yaml
DSL Parser          自研轻量 Parser
Parallel            multiprocessing / concurrent.futures
Result JSON         json/jsonl
Allure              allure result format/integration
JUnit               XML
Pairwise            现成 all-pairs 库或内部实现
Result DB           第二阶段再选 SQLite/PostgreSQL
```

不要因为未来可能有几十万用例就过早把整个系统写成复杂分布式服务。

测试 Runner 的主要瓶颈通常是数据库执行时间，而不是 Python 本身。

---

# 32. 开发复杂度评估

按照：

```text
1 = 普通脚本
10 = 数据库内核
```

粗略评估：

```text
MVP             4/10
稳定 V1         6/10
成熟原厂平台     8/10
```

模块难度：

| 模块 | 难度 | 说明 |
|---|---:|---|
| DSL/Parser | ★★☆ | 语法本身不复杂 |
| Metadata | ★★☆ | 实现简单，模型设计重要 |
| Case Model | ★★☆ | 需要保持稳定 |
| Xugu Adapter | ★★☆ | 数据库连接层封装 |
| Selector | ★★★ | 重要核心能力 |
| Exact/Error Validator | ★★☆ | 第一版较简单 |
| Result Normalizer | ★★★★ | 最容易产生误报 |
| CLI | ★★☆ | 成熟生态 |
| Allure/JUnit | ★★☆ | 直接复用 |
| Test Plan | ★★☆ | YAML + Selector |
| Parallel Runner | ★★★★ | 隔离、调度、长尾问题 |
| Hash | ★★★ | 依赖稳定规范化 |
| Result Store | ★★★ | 数据模型与历史查询 |
| Template Generator | ★★★ | 容易起步 |
| Pairwise | ★★★ | 主要难在 Constraint |
| Differential | ★★★★ | 数据库语义差异复杂 |
| Metamorphic | ★★★★☆ | 规则正确性难 |
| Change Impact | ★★★★★ | 长期高级能力 |
| Web UI | ★★★★ | 前后端、状态、权限 |

---

# 33. 开发工作量建议

单人估算：

```text
可运行原型          1~2 周
可投入项目的 MVP     4~6 周
稳定 V1             2~3 个月
成熟原厂级平台       6 个月以上
```

真正影响周期的主要因素是是否同时要求：

- 并发；
- K8s；
- 多数据库；
- 环境部署；
- 失败重跑；
- Result DB；
- Web；
- Generator；
- Differential；
- Metamorphic；
- Change Impact。

因此必须按阶段控制范围。

---

# 34. 分阶段实施方案

## Phase 0：规范冻结

先完成设计，不急于写 Runner。

输出：

- Query Feature Taxonomy；
- Metadata Schema；
- Level 定义；
- `.xgt` DSL 最小规范；
- Case ID 规范；
- Result Canonicalization 规范；
- 目录规范。

这是整个系统最关键的阶段。

---

## Phase 1：MVP

目标：真正能够替代一部分 Query 回归测试流程。

必须实现：

```text
.xgt DSL
Metadata
Parser
Case Model
Selector
Runner
Xugu Adapter
Result Normalizer V1
Exact Validator
Rowsort Validator
Expected Error Validator
CLI
JUnit
Allure
Git
```

至少支持：

```bash
xgtest run --feature join
```

```bash
xgtest run --feature join --feature union
```

```bash
xgtest run --feature join --level P0,P1
```

MVP 优先迁移：

```text
JOIN
UNION
```

两类用例，用它们验证整个架构。

---

## Phase 2：工程化 V1

增加：

```text
Test Plan
Parallel Worker
Schema Isolation
Shard
Retry / Flaky
Timeout
Hash Validator
Result JSON/DB
历史执行时间
Jenkins/CI
pytest Plugin
```

达到正式版本发布可稳定使用的程度。

---

## Phase 3：用例生产能力

增加：

```text
Template Generator
Pairwise Generator
Constraint Model
Coverage Model
Generator → .xgt → Git 流程
```

目标不是“生成越多越好”，而是可以回答：

> 当前 JOIN 测试到底覆盖了哪些条件组合？

---

## Phase 4：高级正确性能力

按实际价值逐步加入：

```text
Differential
Property
Metamorphic
Change Impact
Web UI
```

不要同时启动。

---

# 35. MVP 验收标准

第一版建议满足以下条件才算完成，而不是“CLI 能运行”就算完成。

## 功能

- 可以解析 `.xgt`；
- Case ID 唯一校验；
- Metadata 可继承；
- 支持 JOIN/UNION 用例；
- 支持 Exact；
- 支持 Rowsort；
- 支持 Expected Error；
- 支持 NULL/INT/VARCHAR/DECIMAL/DATE/TIMESTAMP 的基础规范化。

## 选择执行

必须可以：

```bash
xgtest run --feature join
```

```bash
xgtest run --feature union
```

```bash
xgtest run --feature join --feature union
```

```bash
xgtest run --feature join --level P0,P1
```

```bash
xgtest run --tag regression
```

## 报告

失败必须能直接看到：

```text
Case ID
SQL
Expected
Actual
Error
Source File
DB Version
Duration
```

## 稳定性

- 连续重复运行结果一致；
- 无 ORDER BY 用例不会因为返回顺序不同产生误报；
- Setup/Cleanup 失败有清晰状态；
- 单条用例异常不会导致整个 Test Run 无结果。

---

# 36. 第一批建议落地的 JOIN 用例矩阵

建议使用 JOIN 作为第一个 Feature，因为它足以验证 DSL、Selector、Normalizer、复杂结果比较和组合模型。

第一批维度：

```text
JOIN TYPE
INNER / LEFT / RIGHT / FULL

INPUT SIZE
0 / 1 / N

MATCH
none / one / many

NULL
left-null / right-null / both / join-key-null

DATA TYPE
INT / BIGINT / DECIMAL / VARCHAR / DATE / TIMESTAMP

PREDICATE
= / <> / > / < / expression

FILTER
none / WHERE-left / WHERE-right / WHERE-both

PROJECTION
left / right / both / expression
```

先人工设计 P0/P1 基线，再用 Pairwise 补充组合。

---

# 37. 第一批建议落地的 UNION 用例矩阵

```text
TYPE
UNION / UNION ALL

ROWS
empty / one / many

DUPLICATE
none / partial / all

NULL
none / some / all

DATA TYPE
same / compatible / implicit-cast / incompatible

COLUMN COUNT
one / multiple

ORDER
none / outer-order

SOURCE
base-table / subquery / aggregate / join
```

UNION 和 JOIN 同时落地，可以验证“单 Feature”和“Feature Interaction”两种测试模型。

---

# 38. 关键风险

## 风险 1：一开始做成“大而全平台”

最常见失败原因。

控制方式：第一阶段只做 Query + JOIN/UNION + CLI + 报告。

## 风险 2：Metadata 无规范

如果不同测试人员自由写：

```text
join
JOIN
inner-join
inner_join
join_inner
```

后续 Selector 和报告会不可维护。

必须建立 Schema 和枚举校验。

## 风险 3：Result Normalizer 不完善

会产生大量 False Failure。

必须把 Normalizer 当核心模块，而不是简单工具函数。

## 风险 4：目录与 Tag 混用

最终目录会无限加深。

严格执行：Directory = 主功能树；Tag = 横向标签。

## 风险 5：自动生成用例不可重复

正式回归不要每次随机生成一批新 SQL。

生成后必须固化到 Git。

## 风险 6：过早开发 Web

Web 容易消耗大量时间，却不提升 Query 测试本身的可靠性。

应晚于 CLI、Selector、Runner、Result Store。

---

# 39. 最终推荐技术路线

最终方案总结：

> **借鉴 DuckDB SQLLogicTest 的测试资产表达思想，自研 XG Query Test Core，不直接 Fork DuckDB。**

核心自研：

```text
Feature Taxonomy
Metadata Model
XG SQLLogic DSL
Parser
Case Model
Selector
Planner
Runner
Xugu Adapter
Result Normalizer
Validator
Test Plan
```

成熟组件复用：

```text
Git
Allure
JUnit XML
pytest Plugin（可选）
Pairwise Library
Jenkins/K8s
```

高级能力后置：

```text
Differential
Metamorphic
Change Impact
Web UI
```

独立体系：

```text
SQLancer
```

SQLancer 仅负责探索未知逻辑缺陷；发现问题并确认语义后，将最小复现转为 `.xgt` 永久回归用例。

---

# 40. 一句话结论

XG Query Test 最核心的价值不是“把 SQL 跑起来”，而是建立一套能够长期支撑数据库版本演进的：

> **查询能力模型 + 稳定测试资产 + 精确选择机制 + 可靠结果语义 + 可扩展执行框架。**

第一阶段只要把 **分类、DSL、Metadata、Selector、Runner、Xugu Adapter、Normalizer、Validator、Allure** 做稳，就已经能够形成真正可用于数据库版本发布的 Query 功能回归基础设施。
