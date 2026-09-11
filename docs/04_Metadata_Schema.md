# XG DB Test Metadata Schema

> Metadata Version：1.1

## 1. 目标

Metadata 统一回答：

```text
这个 Case 是什么？
覆盖什么功能？
重要程度是什么？
适用于哪些版本和环境？
需要哪些资源？
能否并行？
能否重试？
是否具有破坏性？
```

Metadata 必须机器可验证，禁止依赖人为约定。所有 YAML 使用 YAML 1.2 Core Schema，重复键拒绝；on/off 为字符串而非布尔，版本和日期按 Schema 要求使用引号字符串，禁止自动日期对象。

---

## 2. 标识字段

```yaml
id: QUERY.JOIN.LEFT.000001
title: Left Join NULL
```

`id` 必须：

- 全仓库唯一；
- 稳定；
- 不随文件移动改变；
- 产生历史结果后不应随意修改。

---

## 3. 分类字段

```yaml
module: query
feature: join
subfeature: left_join
scenario: null_match
```

全部通过 Feature Registry 校验。

---

## 4. Level

```yaml
level: P0
```

枚举：

```text
P0 核心主路径 / Smoke / 严重历史 Bug
P1 正式版本常规回归
P2 完整回归 / 复杂组合
P3 长稳 / 大规模 / 极端专项
```

---

## 5. Complexity

```yaml
complexity: basic
```

枚举：

```text
basic
normal
complex
extreme
```

Complexity 不等于 Level。

---

## 6. Tags

```yaml
tags:
  - "null"
  - varchar
  - optimizer
```

Tag 用于横向分类，不应用来替代 module/feature/level。

---

## 7. Source

```yaml
source: manual
```

枚举：

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

---

## 8. Oracle

```yaml
oracle: exact
```

建议枚举：

```text
exact
rowsort
valuesort
hash
expected_error
state
property
differential
metamorphic
```

---

## 9. Version

```yaml
since: 5.0.0
until: null
```

语义：

```text
since <= target_version
AND
(until is null OR target_version <= until)
```

版本必须使用项目统一 Version Comparator，禁止字符串比较。

---

## 10. Issue / Owner

```yaml
issue: XGDB-12345
owner: query-team
```

Regression Case 强烈建议填 issue。

---

## 11. Timeout

```yaml
timeout: 30s
```

支持：

```text
ms
s
m
h
```

内部统一转毫秒。

---

## 12. Execution Class

```yaml
execution_class: fast
```

枚举：

```text
fast
normal
heavy
exclusive
```

含义：

- fast：轻量 SQL 功能 Case；
- normal：事务、复杂 SQL、索引分区等；
- heavy：大数据、恢复、大对象等；
- exclusive：重启、Failover、全局配置等。

---

## 13. Isolation

```yaml
isolation: worker_schema
```

枚举：

```text
session
worker_schema
case_schema
database
cluster
```

推荐默认：

```text
SQL-only      → worker_schema
Transaction   → case_schema
HA/Restore    → cluster/database
```

---

## 14. Destructive

```yaml
destructive: false
```

破坏性 Case 必须显式：

```yaml
destructive: true
```

---

## 15. Idempotency

```yaml
idempotency: safe
```

枚举：

```text
safe
conditional
unsafe
```

定义：

```text
safe
  可以自动重复执行

conditional
  cleanup/reset 成功后才可重试

unsafe
  Scheduler 禁止自动重放
```

---

## 16. Requirements

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

  labels:
    lab: a
```

未声明表示 `any`。

---

## 17. Resource Requirement

```yaml
resources:
  sessions: 2
  schemas: 1
  databases: 0
  nodes: 0
  cluster: 0
```

Cluster 独占场景：

```yaml
resources:
  cluster: 1

execution_class: exclusive
```

---

## 18. Parallel

```yaml
parallel: safe
```

枚举：

```text
safe
restricted
exclusive
```

与 `execution_class` 不同：

```text
execution_class → 资源重量
parallel        → 并发语义
```

---

## 19. Retry

```yaml
retry:
  max_attempts: 2
  on:
    - INFRA_NETWORK
    - INFRA_AGENT_LOST
```

默认不允许 Assertion Fail 自动重试。

---

## 20. Fixtures

```yaml
fixtures:
  - join_base_dataset
```

Fixture 定义自身 Scope：

```text
run
environment
worker
suite
case
```

---

## 21. Metadata 继承

顺序：

```text
Global Defaults
       ↓
Parent _suite.yaml
       ↓
Child _suite.yaml
       ↓
Case Metadata
```

规则：

- Scalar：后者覆盖；
- Tags：合并去重；
- Requirements：字典递归合并，列表集合并集；
- Resources：按字段覆盖，未声明字段继承；
- Fixtures：有序去重追加；Retry：按字段覆盖；Coverage：仅 Case 声明。

未知字段报错；null 只允许清空可空字段；父级能力约束不允许隐式删除。

---

## 22. `_suite.yaml`

示例：

```yaml
metadata_version: "1.1"

module: query
feature: join

defaults:
  level: P1
  execution_class: fast
  isolation: worker_schema
  destructive: false
  idempotency: safe

tags:
  - join
```

---

## 23. Required Fields

所有 Case 必须：

```text
id
module
feature
level
execution_class
isolation
idempotency
destructive
```

合并后 title、source、status、parallel、timeout、metadata_version 也必填；缺省规则见第 28 节。

---

## 24. Capability Registry

建议文件：

```text
configs/capabilities.yaml
```

示例：

```yaml
sql:
  - sql.query
  - sql.ddl
  - sql.dml

transaction:
  - tx.multi_session
  - tx.deadlock

cluster:
  - cluster.3node
  - cluster.failover
  - cluster.rebalance

storage:
  - storage.backup
  - storage.restore
```

Case 与 Environment 必须使用同一套 Capability Key。

---

## 25. Feature Registry

建议：

```text
configs/features.yaml
```

示例：

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

用于：

```text
Metadata 校验
Selector
报告
Coverage
Web UI
```

---

## 26. Validation 时机

以下问题必须在：

```text
xgtest validate
xgtest index
```

阶段失败：

```text
unknown module
unknown feature
unknown capability
invalid level
illegal isolation
duplicate Case ID
invalid version range
```

不要等到运行时才发现。

---

## 27. Catalog Materialization

Metadata 在编译阶段解析完继承关系后进入 Case Catalog。

运行时 Selector 只读 Catalog，不重复解析 `_suite.yaml`。

---

## 28. 完整字段与默认值

版本 1.1 的 Metadata 除前述字段，还包含以下正式字段；不是可忽略扩展。

| 字段 | 类型 / 规则 | 默认值 |
|---|---|---|
| metadata_version | 字符串 | Suite/全局必须显式声明 "1.1"，无隐式跨版本默认 |
| status | generated/draft/review/active/deprecated/disabled | draft；Generator 明确写 generated |
| source / title | Source 枚举 / 非空字符串 | manual / 无默认 |
| issue / owner | 可空字符串 | null |
| disable_reason | disabled 时非空 | null |
| replaced_by | Case ID 列表 | [] |
| generated_by | generator、generator_version、model_id、model_version、strategy、seed、generated_at | null；自动生成时必填 |
| parallel | safe/restricted/exclusive | safe |
| timeout | 正数 duration，覆盖整个业务执行 | 30s |
| retry | max_attempts >= 1；on 为 07 的 failure_type 子集 | {max_attempts: 1, on: []} |
| reset_contract | 已注册的 Fixture/Adapter 复位契约 ID | null；conditional 时必填 |
| cleanup_timeout | 独立、有上限的清理预算 | 30s |
| coverage | 08 定义的 claim 对象列表 | []，计为 UNMAPPED |
| comparison_profile | 11 定义的 Canonical 比较策略 | canonical-v1-strict |
| oracle_provenance | kind、reference、reviewer、evidence_hash | null；active 必须有可信来源 |
| validation_evidence | semantic_hash、trial_run_id、trial_evidence_hash、review_revision、reviewer | null；active 时必填并与当前语义匹配 |

字段名 `oracle` 只声明 Case 的主要验证类别；具体比较参数由 Step.expect 和 comparison_profile 决定，两者必须相容。
`model_id` 为不带版本的稳定标识（如 query.join），`model_version` 为字符串（如 "1"）。禁止同时把版本嵌入 ID 并另填矛盾版本。

## 29. 跨字段约束

- execution_class 控制资源池，parallel 控制并发许可；exclusive 动作必须同时 parallel=exclusive。
- node stop/kill/restart、restore、cluster failover 和全局配置动作由类型化 Step 推导最低 destructive/isolation/resource 要求；Metadata 不可降级。
- destructive=true 的自动 max_attempts 必须为 1；unsafe 同样禁止自动重放。
- conditional 必须有 reset_contract；safe 也必须完成 11 的停止与清洁验证，不能继承 safe 后跳过验证。
- restricted 必须声明受限资源，不能只有标签而没有准入对象。
- sessions 不小于并发 Session 峰值；同一 Session 不允许被不同并发分支同时使用。
- status=active 要求至少一个有效断言、Oracle 来源和 Review 证据；coverage 声明必须引用存在的断言 step_id。
- since/until 在 Resolver 中与 target 数据库版本比较；环境缺失、资源暂时不足与版本不支持分别记录，不混成 SKIP。

## 30. 跨模块字段映射

| Metadata / 编译产物 | Unified Case | Catalog 2 | Manifest / Result 2 |
|---|---|---|---|
| id、分类、level、status、source、issue、owner | Identity/Classification/Lifecycle | cases 对应列 | 冻结 Metadata / case_id + level |
| tags | Classification.tags | case_tags | frozen metadata |
| requirements、resources、parallel | Requirements/Resources | 专表 + cases.parallel | target 匹配证据 / Attempt.environment_id |
| retry、reset_contract、fixtures | RetryPolicy/Fixtures | cases / case_fixtures | Bundle / cleanup_status |
| coverage、model refs | CoverageClaim[] | case_coverage_claims | coverage snapshot / model hash |
| generated_by、oracle_provenance | Provenance | cases JSON | frozen metadata |
| comparison_profile | ComparisonProfile | cases + effective_metadata_json | canonical_version / semantic_hash |
| source / dependencies / compiled | SourceInfo | hashes + case_inputs | manifest_hash + compiled_hash + semantic_hash |

所有已验证 Metadata 同时序列化到 effective_metadata_json；索引列必须与该 JSON 在同一事务内一致。Selector 禁止通过重新读源文件补缺失字段。
