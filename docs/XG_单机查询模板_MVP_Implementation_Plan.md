# XG DB Test 单机 Query MVP 完整代码实现方案

> 目标版本：`v0.1.0-query-mvp`  
> 基线：当前 `main`（以 `fba6b79` 一线代码为基础）  
> MVP 范围：**单机、单数据库目标、顺序执行、只实现查询类测试闭环**  
> 暂不实现：多机、多目标调度、Agent、Catalog、Selector、Manifest、Lease/Fencing、HA、Scenario、Coverage Generator、Result DB、Dashboard 等。

---

# 1. MVP 目标

本阶段不追求完整测试平台，而是先打通一条可长期保留的纵向主链路：

```text
Query YAML
   ↓
Typed Query Case
   ↓
Query Loader / Validator
   ↓
Single Target Query Runner
   ↓
XuguSession.query()
   ↓
Driver Type Mapping
   ↓
Canonical / XGC1
   ↓
Comparator
   ↓
PASS / FAIL / ERROR
   ↓
JSON Result Report
```

MVP 完成后应具备以下能力：

- 从目录读取 Query Case；
- 对 Case 做强类型校验；
- 在单个 Xugu 数据库上顺序执行；
- 读取 DB-API 元数据和查询结果；
- 对返回类型执行 Logical Type 映射；
- 对结果按 XGC1 Canonical 规则进行标准化；
- 支持 `exact / rowsort / sha256 / expected_error`；
- 输出结构化 JSON Report；
- 能明确区分：
  - PASS：实际结果符合预期；
  - FAIL：SQL 执行成功，但断言不符合；
  - ERROR：SQL、驱动或框架执行异常；
  - SKIPPED：前置条件导致未执行；
- 对不支持或语义不可靠的 DB 类型，不允许静默比较或误判 PASS。

---

# 2. 本阶段明确不做的功能

为了防止 MVP 持续膨胀，本阶段明确不实现以下模块：

```text
多节点调度
多 Target 并发
Agent
Catalog2
Selector
TestPlan
Manifest / Bundle Publisher
Resource Admission Engine
Lease / Fencing
Cluster Drain
Scenario DSL
HA / Backup / Restore
Coverage Model
AI Case Generator
Result DB
Dashboard
Flaky Detection
Release Baseline / Delta
```

说明：

- 这些能力仍属于完整 XG DB Test 架构；
- 当前不删除已有模型；
- 只是不把它们作为 Query MVP 的阻塞项；
- Query MVP 要保证未来可被 Compiler / Catalog / Selector / Scheduler 复用，不做一次性实现。

---

# 3. 当前已有代码基础

当前代码已经具备以下可复用能力。

## 3.1 Adapter

文件：

```text
src/xgtest/adapter/xugu.py
```

已具备：

- `XuguConnectionConfig`
- `connect()`
- `smoke_probe()`
- `XuguSession.open()`
- `XuguSession.query()`
- `XuguSession.iter_query_rows()`
- `XuguSession.execute()`
- `rollback_transaction()`
- `cancel()`
- `extract_error()`
- `map_driver_type()`

其中 `XuguSession.query()` 已支持读取 `cursor.description`、返回列名、Driver 类型、Logical Type，并通过 `fetchmany(1000)` 分批获取结果。这部分直接作为 Query MVP 的数据库执行层。

## 3.2 Canonical / Comparator

文件：

```text
src/xgtest/core/canonical.py
src/xgtest/runtime/comparator.py
```

已具备：

- XGC1 编码；
- Logical Type 推导；
- `rows_sha256()`；
- `compare_rows()`；
- `compare_error()`；
- Exact；
- RowSort；
- Hash；
- Expected Error。

Query MVP 不再新增新的比较协议，先把现有能力正式化。

## 3.3 Typed Expected

文件：

```text
src/xgtest/core/models.py
```

已有：

```python
ExpectedRows
ExpectedHash
ExpectedError
ExpectedStatement
decode_expected()
```

已经处理：

- `{}` 非法；
- `rows + sha256` 混合非法；
- Error + Rows 混合非法；
- 负数 `affected_rows` 非法；
- 空 `code/sqlstate/message_pattern` 非法；
- `rows: []` 与 `rows: [[]]` 区分。

Query MVP 直接继承这一套边界。

## 3.4 Runtime Profile

已有：

```text
src/xgtest/runtime/profile.py
framework_tests/contract/runtime_profile/
```

已经具备 Runtime Profile Identity、Profile ID、语义变化影响 ID、运行时噪声不影响 ID，以及 Driver / Target / Capability 基本身份。

## 3.5 Bootstrap Runner

文件：

```text
src/xgtest/runtime/runner.py
```

已经具备 YAML 加载、Typed Model 转换、Setup / Statement / Query / Cleanup、PASS / FAIL / ERROR、Cleanup / Recovery 状态和 Result JSON。

本阶段不继续扩展这个文件，而是把其中“纯 Query 能力”迁移成正式 Query 模块。

---

# 4. 实施顺序总览

推荐严格按以下顺序实现：

```text
Phase 0  Contract 收口
   ↓
Phase 1  Driver Mapping 语义收口
   ↓
Phase 2  Query Case Contract
   ↓
Phase 3  Query Loader
   ↓
Phase 4  Query Runner
   ↓
Phase 5  Comparator 收口与大结果支持
   ↓
Phase 6  Query Result Model
   ↓
Phase 7  CLI
   ↓
Phase 8  Read-only Query Case 验收集
   ↓
Phase 9  Query MVP Gate
```

建议每个 Phase 独立 commit，尽量做到：

```text
一个问题
一个改动目标
一组测试
一个提交
```

---

# 5. Phase 0：修复 Contract Descriptor

## 5.1 目标

解决当前 `contract_set_id` 没有完整覆盖 Query 关键行为实现的问题。

当前 Contract Hash 主要覆盖：

```text
registry/
src/xgtest/core/
framework_tests/contract/
schemas/
src/xgtest/generated/registry_enums.py
src/xgtest/cli.py
```

但 Query 的真实语义还依赖：

```text
src/xgtest/runtime/profile.py
src/xgtest/runtime/comparator.py
src/xgtest/adapter/xugu.py
```

如果这些代码改变，而 `contract_set_id` 不变，会导致：

```text
相同 contract_set_id
对应不同 Query 语义
```

这是 Freeze 之前必须修复的问题。

## 5.2 修改文件

```text
src/xgtest/core/contract_set.py
framework_tests/contract/test_contract_set.py
docs/g0a/contract-descriptor-candidate.json
```

## 5.3 建议修改

短期 MVP 方案直接扩充：

```python
_SOURCE_FILES = (
    "src/xgtest/cli.py",
    "src/xgtest/runtime/profile.py",
    "src/xgtest/runtime/comparator.py",
    "src/xgtest/adapter/xugu.py",
)
```

长期完整版本可再考虑把 Runtime Profile Identity Projection 移入：

```text
src/xgtest/core/runtime_profile_identity.py
```

但 MVP 不要求立即重构。

## 5.4 增加 Candidate Stale Check

增加测试：

```python
def test_committed_g0a_candidate_matches_current_contract():
    actual = build_contract_descriptor(ROOT)

    expected = json.loads(
        (
            ROOT /
            "docs/g0a/contract-descriptor-candidate.json"
        ).read_text(encoding="utf-8")
    )

    assert actual == expected
```

目标：

```text
Contract 文件变化
      ↓
candidate JSON 未更新
      ↓
测试失败
```

## 5.5 验收条件

- 修改 `runtime/comparator.py` → `contract_set_id` 必须变化；
- 修改 `runtime/profile.py` → `contract_set_id` 必须变化；
- 修改 `adapter/xugu.py` → `contract_set_id` 必须变化；
- CRLF/LF 切换 → `contract_set_id` 不变化；
- Candidate Descriptor 过期 → Framework Test 必须失败。

## 5.6 建议 Commit

```text
fix: close query MVP contract identity gaps
```

---

# 6. Phase 1：拆分 Driver Mapping 语义

## 6.1 当前问题

现在 Driver Probe 使用：

```text
canonical_compatibility
```

一个字段同时表达：

1. Driver 类型映射是否保持 DB 原始语义；
2. Python value 是否能被 Canonical 编码。

这两个概念不能混用。

例如：

```text
DB: BINARY(8)
Driver: VARCHAR
Framework: string
Python: str
```

字符串当然可以编码成 Canonical string，因此：

```text
canonical encoding = VERIFIED
```

但 `BINARY → VARCHAR → string` 已经丢失二进制语义，因此：

```text
mapping fidelity != EXACT
```

## 6.2 修改模型

修改：

```text
src/xgtest/core/models.py
```

建议：

```python
class TypeMappingProfile(StrictModel):
    mapping_fidelity: Literal[
        "EXACT",
        "LOSSY",
        "AMBIGUOUS",
        "UNKNOWN",
    ]

    canonical_encoding: Literal[
        "VERIFIED",
        "FAILED",
        "UNKNOWN",
    ]

    support_status: Literal[
        "SUPPORTED",
        "UNSUPPORTED",
    ]
```

如果需要兼容 Runtime Profile v0.2，可先保留旧字段，增加新字段，然后在 v0.3 再完全删除旧字段。

## 6.3 Probe 结果定义

建议最终状态：

| DB 类型 | Driver 返回 | Mapping Fidelity | Canonical Encoding | MVP Support |
|---|---|---:|---:|---:|
| INT | INTEGER/int | EXACT | VERIFIED | SUPPORTED |
| BIGINT | BIGINT/int | EXACT | VERIFIED | SUPPORTED |
| SMALLINT | SMALLINT/int | EXACT | VERIFIED | SUPPORTED |
| FLOAT | FLOAT/float | EXACT | VERIFIED | SUPPORTED |
| DOUBLE | DOUBLE/float | EXACT | VERIFIED | SUPPORTED |
| VARCHAR | VARCHAR/str | EXACT | VERIFIED | SUPPORTED |
| CHAR | VARCHAR/str | EXACT/ACCEPTABLE | VERIFIED | SUPPORTED |
| DATE | DATE/str | EXACT/ACCEPTABLE | VERIFIED | SUPPORTED |
| TIME | TIME/str | EXACT/ACCEPTABLE | VERIFIED | SUPPORTED |
| NUMERIC | NUMERIC/float | LOSSY | FAILED | UNSUPPORTED |
| DECIMAL | NUMERIC/float | LOSSY | FAILED | UNSUPPORTED |
| NUMBER | NUMERIC/float | LOSSY | FAILED | UNSUPPORTED |
| DATETIME | DATETIME/str | AMBIGUOUS | FAILED | UNSUPPORTED |
| TIMESTAMP | DATETIME/str | AMBIGUOUS | FAILED | UNSUPPORTED |
| TIMESTAMP TZ | DATETIME/str | AMBIGUOUS | FAILED | UNSUPPORTED |
| BINARY | VARCHAR/str | LOSSY | VERIFIED | UNSUPPORTED |
| RAW | VARCHAR/str | LOSSY | VERIFIED | UNSUPPORTED |
| VARBINARY | syntax error | UNKNOWN | UNKNOWN | UNSUPPORTED |
| BLOB | BLOB/bytes | EXACT | VERIFIED | SUPPORTED |
| BOOLEAN | BOOLEAN/bool | EXACT | VERIFIED | SUPPORTED |

## 6.4 修改文件

```text
src/xgtest/core/models.py
tools/probes/xugu_driver_type_mapping_probe.py
framework_tests/fixtures/xugu_driver_type_mapping_v1.json
framework_tests/contract/test_driver_mapping_fixture.py
src/xgtest/runtime/profile.py
```

## 6.5 验收条件

必须保证：

```text
能编码
!=
语义支持
```

即 `BINARY -> VARCHAR -> string` 不能最终进入 `SUPPORTED`。

## 6.6 建议 Commit

```text
fix: separate driver mapping fidelity from canonical encoding
```

---

# 7. Phase 2：建立 Query Case Contract

## 7.1 目标

当前 `SqlStep` 同时支持：

```text
setup
statement
query
cleanup
```

Query MVP 不应继续允许所有 Step 类型。

MVP 需要一个明确的 Query 输入边界：

```text
QueryCaseInput
  └── QueryStep[]
```

## 7.2 新增模型

修改：

```text
src/xgtest/core/models.py
```

建议：

```python
class QueryStep(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    kind: Literal["query"] = "query"
    sql: str = Field(min_length=1)
    comparison: ComparisonProfile
    expected: ExpectedRows | ExpectedHash | ExpectedError


class QueryCaseInput(StrictModel):
    metadata: EffectiveMetadata
    steps: tuple[QueryStep, ...] = Field(min_length=1)
```

Query MVP 不允许：

```text
ExpectedStatement
affected_rows
statement
setup
cleanup
```

## 7.3 Query Case 示例

```yaml
metadata:
  id: QUERY.STRING_FUNCTION.000001
  title: upper and length
  feature: string_function
  level: P1
  status: active
  isolation: session

steps:
  - id: q1
    kind: query
    sql: SELECT UPPER('xugu'), LENGTH('xugu')
    comparison:
      mode: exact
    expected:
      rows:
        - [XUGU, 4]
```

## 7.4 Expected Error 示例

```yaml
metadata:
  id: QUERY.ERROR.000001
  title: invalid table error
  feature: basic_query

steps:
  - id: q1
    kind: query
    sql: SELECT * FROM TABLE_NOT_EXISTS_XGT
    comparison:
      mode: expected_error
    expected:
      code: E5021
```

## 7.5 Schema Export

把：

```text
QueryStep
QueryCaseInput
```

加入：

```python
MODEL_EXPORTS
```

生成：

```text
schemas/QueryStep.schema.json
schemas/QueryCaseInput.schema.json
```

## 7.6 验收条件

以下必须加载失败：

```yaml
kind: statement
```

```yaml
expected:
  affected_rows: 1
```

```yaml
expected: {}
```

```yaml
expected:
  rows: []
  sha256: ...
```

```yaml
sql: ""
```

## 7.7 建议 Commit

```text
feat: add query MVP case contract
```

---

# 8. Phase 3：新增 Query Loader

## 8.1 目标

把 YAML 解析和 Runner 解耦。

Runner 不再自己处理：

```text
YAML
dict
enum conversion
default metadata
expected decode
```

而是只接收：

```text
QueryCaseInput
```

## 8.2 新增目录

```text
src/xgtest/query/
├── __init__.py
├── loader.py
├── runner.py
└── result.py
```

## 8.3 Loader API

文件：

```text
src/xgtest/query/loader.py
```

核心：

```python
def load_query_case(path: Path) -> QueryCaseInput:
    ...
```

## 8.4 Loader 责任

```text
读取 YAML
↓
重复 Key 检测
↓
Metadata 类型转换
↓
默认值解析
↓
ComparisonProfile 校验
↓
Expected decode
↓
QueryStep 校验
↓
QueryCaseInput
```

## 8.5 Loader 不负责

不得在 Loader 内：

```text
连接数据库
执行 SQL
做比较
写 Result
```

## 8.6 重复 Step ID 校验

建议 QueryCaseInput 增加：

```python
@model_validator(mode="after")
def unique_step_id(self):
    ids = [step.id for step in self.steps]
    if len(ids) != len(set(ids)):
        raise ValueError("QUERY_STEP_ID_DUPLICATED")
    return self
```

## 8.7 SourceSpan

MVP 可以继续复用当前 YAML Loader 的行列信息。

错误最好能输出：

```text
cases/query/a.yaml:17:5
EXPECTED_AMBIGUOUS
```

## 8.8 测试文件

新增：

```text
framework_tests/query/test_loader.py
```

至少覆盖：

```text
合法 query case
缺 metadata
缺 id
缺 feature
steps 为空
非法 kind
重复 step id
空 SQL
非法 comparison
非法 expected
expected 混合类型
```

## 8.9 建议 Commit

```text
feat: add typed query case loader
```

---

# 9. Phase 4：实现 Single Target Query Runner

## 9.1 目标

实现正式 Query 执行器。

文件：

```text
src/xgtest/query/runner.py
```

## 9.2 Runner API

建议：

```python
class QueryRunner:
    def __init__(
        self,
        session: XuguSession,
        runtime_profile: RuntimeProfile | None,
    ) -> None:
        ...

    def run_case(
        self,
        case: QueryCaseInput,
    ) -> QueryCaseReport:
        ...

    def run_step(
        self,
        step: QueryStep,
    ) -> QueryStepReport:
        ...
```

外层：

```python
def run_query_cases(
    config: XuguConnectionConfig,
    case_dir: Path,
    output: Path,
    runtime_profile: dict | None = None,
) -> QueryRunReport:
    ...
```

## 9.3 Query Runner 生命周期

单 Case 第一版建议：

```text
Open Connection
    ↓
Run Query Step 1
    ↓
Run Query Step 2
    ↓
...
    ↓
Rollback Transaction
    ↓
Close Connection
```

MVP 不做连接池，不做 WorkerPool。

## 9.4 Step 执行逻辑

```text
QueryStep
   ↓
session.query(sql)
   ↓
XuguQueryResult
   ├── columns
   ├── column_types
   ├── logical_types
   └── rows
   ↓
validate supported logical type
   ↓
Comparator
   ↓
PASS / FAIL
```

如果 SQL 报错：

```text
SQL Error
  ↓
ExpectedError ?
   ├── Yes → compare_error()
   │          ├── match → PASS
   │          └── mismatch → FAIL
   │
   └── No  → ERROR
```

## 9.5 状态语义

### PASS

```text
SQL 正常
+
结果符合 Expected
```

或：

```text
SQL 报错
+
符合 ExpectedError
```

### FAIL

```text
SQL 正常
+
结果不符合 Expected
```

或者预期错误与实际错误不一致。

### ERROR

```text
数据库异常
Driver 异常
框架内部异常
unsupported type
Canonical 编码异常
```

## 9.6 不支持类型处理

不能通过：

```python
str(value)
```

再继续比较。

必须返回：

```text
failure_type = UNSUPPORTED_TYPE
status = ERROR
```

如果当前 `FailureType` Registry 没有该值，可 MVP 增加 `UNSUPPORTED_TYPE`；如果暂时不想扩 Registry，可临时映射到明确的 Contract/Type 类错误，但不建议长期复用 `INFRA_RESOURCE`。

## 9.7 Session 恢复

Query MVP 结束时：

```text
rollback_transaction()
close()
```

不要调用：

```text
reset()
```

因为当前 Xugu 完整 Reset 语义尚未验证。

## 9.8 测试文件

新增：

```text
framework_tests/query/test_runner.py
```

Mock Session 至少覆盖：

```text
exact pass
exact fail
rowsort pass
hash pass
expected error pass
expected error mismatch
query unexpected error
unsupported type
session close
rollback failure
multi step case
```

## 9.9 建议 Commit

```text
feat: add single target query runner
```

---

# 10. Phase 5：Comparator 最终收口

## 10.1 MVP 支持模式

只保留：

```text
exact
rowsort
expected_error
sha256
```

暂不实现：

```text
subset
contains
regex rows
numeric epsilon
fuzzy timestamp
unordered nested structures
external sort
```

## 10.2 Exact

适合小结果、有稳定顺序的场景。

语义：

```text
列数一致
Logical Type 一致
行数一致
行顺序一致
值一致
```

## 10.3 RowSort

适合结果顺序无意义场景。

```text
每行先 XGC1 Canonical
↓
按 Row Frame 排序
↓
比较
```

## 10.4 SHA256

用于大结果。

不要把所有结果全部保存在内存。建议新增：

```python
def rows_sha256_stream(
    rows: Iterable[tuple[Any, ...]],
    ...
) -> str:
    ...
```

执行：

```text
iter_query_rows()
      ↓
Canonical Row Frame
      ↓
hash.update()
```

必须确保 Hash 完全兼容已有 XGC1 定义，不自行创造第二套编码格式。

## 10.5 行数阈值

MVP 建议：

```text
materialized row limit = 10,000
```

对于：

```text
exact / rowsort
```

超过阈值返回：

```text
QUERY_RESULT_TOO_LARGE_FOR_COMPARISON
```

提示改用：

```text
sha256
```

## 10.6 空结果边界

继续严格保持：

```yaml
rows: []
```

表示 `0 行`。

```yaml
rows:
  - []
```

表示 `1 行 0 列`。

## 10.7 建议 Commit

```text
feat: formalize query comparator profiles
```

---

# 11. Phase 6：建立 Query Result Model

## 11.1 不建议继续使用 Mvp* 命名

新增：

```text
QueryStepReport
QueryCaseReport
QueryTargetReport
QueryRunReport
```

## 11.2 建议模型

```python
class QueryStepReport(StrictModel):
    id: str
    status: StepStatus
    duration_ms: float
    columns: tuple[str, ...] = ()
    column_types: tuple[str | None, ...] = ()
    logical_types: tuple[str | None, ...] = ()
    row_count: int | None = None
    result_sha256: str | None = None
    error_type: str | None = None
    error_code: str | None = None
    sqlstate: str | None = None
    error: str | None = None


class QueryCaseReport(StrictModel):
    case_id: str
    status: CaseExecutionStatus
    failure_type: FailureType | None = None
    duration_ms: float
    steps: tuple[QueryStepReport, ...]


class QueryTargetReport(StrictModel):
    database_alias: str
    host_hash: str
    sql_runtime_profile_id: str | None = None
    contract_set_id: str | None = None


class QueryRunReport(StrictModel):
    schema_version: Literal["1"] = "1"
    run_id: str
    started_at: datetime
    finished_at: datetime
    target: QueryTargetReport
    cases: tuple[QueryCaseReport, ...]
    status: CaseExecutionStatus
```

## 11.3 不默认保存全部大结果行

旧 `MvpStepReport` 有 `rows`。

正式 Query MVP 不建议默认保存所有 Rows，建议只保存：

```text
row_count
result_sha256
columns
types
```

调试模式才允许保存：

```text
preview_rows
```

例如最多前 20 行。

## 11.4 建议 Commit

```text
feat: add typed query result reports
```

---

# 12. Phase 7：正式 CLI

## 12.1 新增命令

```bash
xgtest query validate
xgtest query run
```

## 12.2 Validate

示例：

```bash
xgtest query validate \
  --cases cases/query
```

输出：

```json
{
  "status": "PASS",
  "cases": 28,
  "invalid": 0
}
```

有错误则：

```text
exit code = 1
```

## 12.3 Run

```bash
xgtest query run \
  --cases cases/query \
  --runtime-profile artifacts/runtime-profile.json \
  --output artifacts/runs/query-latest.json
```

## 12.4 推荐环境变量

继续使用：

```bash
XGTEST_DB_HOST
XGTEST_DB_PORT
XGTEST_DB_NAME
XGTEST_DB_USER
XGTEST_DB_PASSWORD
```

密码禁止：

```text
CLI 明文参数
日志输出
Report 输出
异常回显
```

## 12.5 保留旧命令

当前：

```bash
xgtest run
```

暂时保留，文档明确标记为：

```text
bootstrap diagnostic runner
```

Query MVP 稳定后再废弃。

## 12.6 建议 Commit

```text
feat: add query validate and query run commands
```

---

# 13. Phase 8：建立 Read-only Query Case 验收集

## 13.1 新目录

```text
cases/query/
```

## 13.2 第一批规模

建议：

```text
20～30 条
```

不要一开始做几百条。目的不是覆盖所有 SQL，而是验证 MVP 执行闭环。

## 13.3 建议第一批测试分类

### 基础查询

```text
SELECT 常量
列别名
算术表达式
NULL
CASE WHEN
```

### 过滤

```text
WHERE
BETWEEN
IN
LIKE
IS NULL
```

### 函数

```text
UPPER
LOWER
LENGTH
CONCAT
数值函数
日期函数
```

### 聚合

```text
COUNT
SUM
AVG
MIN
MAX
GROUP BY
HAVING
```

### JOIN

```text
INNER JOIN
LEFT JOIN
```

### 集合

```text
UNION
UNION ALL
```

### 子查询

```text
scalar subquery
IN subquery
derived table
```

### CTE

```text
WITH
```

### 排序去重

```text
ORDER BY
DISTINCT
```

### 窗口

如数据库支持：

```text
ROW_NUMBER()
SUM() OVER()
```

### 错误验证

```text
不存在的表
不存在的列
非法函数
```

### 边界

```text
0 行
1 行
NULL
空串
大整数
float
中文
特殊字符
```

## 13.4 Query Case 尽量不依赖 DDL

例如 UNION：

```sql
SELECT 1 AS value
UNION
SELECT 2 AS value
```

函数：

```sql
SELECT UPPER('xugu'), LENGTH('xugu')
```

JOIN：

```sql
SELECT a.id, b.name
FROM (SELECT 1 AS id) a
JOIN (SELECT 1 AS id, 'xugu' AS name) b
  ON a.id = b.id
```

这样当前只读数据库也可以完成 Query MVP。

## 13.5 建议 Commit

```text
test: add read only query MVP acceptance cases
```

---

# 14. Phase 9：Query MVP Acceptance Gate

## 14.1 Framework Tests

至少要求：

```text
现有 Framework Tests 全部通过
+
新增 Query Contract / Loader / Runner / Comparator Tests 全部通过
```

建议目标：

```text
>= 120 framework tests
```

数量不是硬指标，重点是关键边界全部有测试。

## 14.2 Query Case Gate

要求：

```text
20～30 条真实 Query Case
100% 可执行
```

结果可以包含正常 PASS 和预期错误 PASS，但不能存在：

```text
UNKNOWN 类型被误判 PASS
不支持类型静默转换
未捕获异常
```

## 14.3 Contract Gate

必须通过：

```text
contract descriptor rebuild
candidate descriptor stale check
schema export compare
registry validate
```

## 14.4 Runtime Profile Gate

必须确认：

```text
Profile ID 可重复
运行噪声不改变 ID
语义变更改变 ID
contract_set_id 已进入 Profile Identity
```

## 14.5 Driver Type Gate

至少要求：

```text
SUPPORTED 类型全部有真实 Driver Evidence
UNSUPPORTED 类型明确记录
UNKNOWN 不允许执行 Exact 比较
```

## 14.6 Result Gate

必须满足：

```text
JSON Schema 校验通过
不输出密码
不输出 Token
错误信息已脱敏
Run / Case / Step 状态语义一致
```

## 14.7 性能 Gate

MVP 可先设：

```text
1000 个简单 Query Case
单机顺序执行
无连接泄漏
无 Cursor 泄漏
内存不随 Case 数无限增长
```

暂时不要求高并发。

---

# 15. 最终代码目录建议

Query MVP 完成后的目录控制在：

```text
src/xgtest/

├── adapter/
│   ├── __init__.py
│   └── xugu.py
│
├── core/
│   ├── __init__.py
│   ├── canonical.py
│   ├── contract_set.py
│   ├── errors.py
│   ├── identity.py
│   ├── logical_types.py
│   ├── models.py
│   ├── registry.py
│   └── yaml_loader.py
│
├── generated/
│   └── registry_enums.py
│
├── query/
│   ├── __init__.py
│   ├── loader.py
│   ├── runner.py
│   └── result.py
│
├── runtime/
│   ├── __init__.py
│   ├── comparator.py
│   └── profile.py
│
├── cli.py
└── __main__.py
```

测试目录：

```text
framework_tests/

├── contract/
│   ├── runtime_profile/
│   ├── test_canonical.py
│   ├── test_contract_set.py
│   ├── test_driver_mapping_fixture.py
│   ├── test_expected_boundary.py
│   ├── test_models.py
│   └── test_registry.py
│
├── query/
│   ├── test_loader.py
│   ├── test_runner.py
│   └── test_result.py
│
└── runtime/
    ├── test_comparator.py
    └── test_profile.py
```

Case：

```text
cases/query/
```

---

# 16. 推荐 Commit 顺序

严格建议按以下顺序提交：

```text
1. fix: close query MVP contract identity gaps

2. fix: separate driver mapping fidelity from canonical encoding

3. feat: add query MVP case contract

4. feat: add typed query case loader

5. feat: add single target query runner

6. feat: formalize query comparator profiles

7. feat: add typed query result reports

8. feat: add query validate and query run commands

9. test: add read only query MVP acceptance cases

10. chore: establish query MVP acceptance gate
```

不要把十个 Phase 一次性做成一个大 commit。

---

# 17. 开发过程中的强制规则

## 17.1 Runner 只接受 Typed Object

禁止：

```text
Runner
直接读 YAML dict
```

必须：

```text
YAML
→ Loader
→ QueryCaseInput
→ Runner
```

## 17.2 不允许 Silent Fallback

禁止：

```python
logical_type = logical_type or "string"
```

禁止：

```python
value = str(value)
```

来绕过类型问题。

未知类型必须显式失败。

## 17.3 不允许 Comparator 自建第二套 Canonical

必须统一使用：

```text
XGC1
```

Hash、Exact、RowSort 都不能各自发明编码方式。

## 17.4 Query MVP 不碰 Resource Admission

即使代码里已经有 Admission Conflict Rules v0.1，本阶段 Query MVP 单机顺序执行，因此不需要接入。

## 17.5 不实现连接池

第一版：

```text
一个 Case 一个 Session
```

即可。

等性能瓶颈真实出现后再做 persistent worker/session。

## 17.6 不扩展 Comparison Mode

当前模式足够 MVP 使用。

---

# 18. 开发完成后的标准执行命令

## 18.1 Registry 校验

```bash
python -m xgtest registry validate
```

## 18.2 Schema 导出

```bash
python -m xgtest schema export
```

## 18.3 Contract Verify

建议最终增加：

```bash
python -m xgtest contract verify
```

输出：

```text
CONTRACT_DESCRIPTOR_OK
```

## 18.4 Case Validate

```bash
python -m xgtest query validate \
  --cases cases/query
```

## 18.5 Query Run

```bash
python -m xgtest query run \
  --cases cases/query \
  --runtime-profile artifacts/runtime-profile.json \
  --output artifacts/runs/query-latest.json
```

## 18.6 Framework Test

```bash
pytest framework_tests -q
```

---

# 19. Query MVP DoD（Definition of Done）

只有以下条件全部满足，才算 Query MVP 完成。

## Contract

- [ ] Query 关键实现进入 Contract Descriptor；
- [ ] Candidate Descriptor 有 stale check；
- [ ] CRLF/LF 不影响 Hash；
- [ ] Contract 变化会改变 Contract Set ID。

## Driver

- [ ] Mapping Fidelity 与 Canonical Encoding 分离；
- [ ] Supported / Unsupported 明确；
- [ ] Unknown Type 不允许静默继续。

## Query Model

- [ ] `QueryStep`；
- [ ] `QueryCaseInput`；
- [ ] JSON Schema；
- [ ] Expected Union 强校验；
- [ ] 重复 Step ID 拒绝。

## Loader

- [ ] YAML → Typed Case；
- [ ] Fail Fast；
- [ ] Error 有文件定位信息。

## Runner

- [ ] 单 Target；
- [ ] 顺序执行；
- [ ] PASS / FAIL / ERROR 清晰；
- [ ] Expected Error 正确；
- [ ] Session 必须关闭；
- [ ] Rollback 异常可记录。

## Comparator

- [ ] Exact；
- [ ] RowSort；
- [ ] SHA256；
- [ ] Expected Error；
- [ ] 空结果边界；
- [ ] Unsupported Type 拒绝；
- [ ] 大结果 Hash 可流式处理。

## Result

- [ ] QueryRunReport；
- [ ] QueryCaseReport；
- [ ] QueryStepReport；
- [ ] 不默认保存大量 Rows；
- [ ] JSON Schema 可验证。

## CLI

- [ ] `xgtest query validate`；
- [ ] `xgtest query run`；
- [ ] Exit Code 正确。

## Acceptance

- [ ] >= 20～30 条真实 Query Case；
- [ ] 当前 Framework Tests 全部通过；
- [ ] 新增 Query Tests 全部通过；
- [ ] Registry 校验通过；
- [ ] Schema 比对通过；
- [ ] Contract Verify 通过；
- [ ] Runtime Profile 验证通过。

---

# 20. MVP 完成后的下一阶段

Query MVP 完成后，不建议马上做多机。

第二阶段建议：

```text
XGT Parser
   ↓
Metadata Resolver
   ↓
Compiler
   ↓
Catalog2
   ↓
Selector
   ↓
TestPlan
```

完成后再进入：

```text
Multi Target
Scheduler
Agent
Resource Admission
Lease
Fencing
```

也就是说，开发顺序应保持：

```text
先把“单机 Query 执行纵向链路”做稳
           ↓
再把“测试资产编译与选择”做完整
           ↓
最后进入“多机调度和分布式控制”
```

---

# 21. 最终建议

当前项目已经拥有不少底层基础能力，因此 Query MVP 不应该重新发明一套系统。

正确方式是：

```text
复用现有 Core Contract
复用 Xugu Adapter
复用 XGC1
复用 Comparator
复用 Runtime Profile
复用 Typed Expected

只新增：
Query Contract
Query Loader
Query Runner
Query Result
Query CLI
Query Acceptance Cases
```

本阶段最重要的不是功能数量，而是形成一条：

```text
可运行
可验证
可回归
可解释
可继续演进
```

的正式链路。

如果按照本文 10 个 Commit 顺序推进，Query MVP 完成后即可打：

```text
v0.1.0-query-mvp
```

然后进入下一阶段的 XGT Parser / Compiler / Catalog2 实现。
