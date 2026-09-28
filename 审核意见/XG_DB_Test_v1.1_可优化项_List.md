# XG DB Test v1.1 架构优化项清单

> 评审状态：已于 2026-09-11 完成逐项评审并纳入 v1.1 工程化补充。下文第 1–8 节保留原建议；采纳结论、修正点和落地位置见第 9 节。原流程、资源类型冲突表及目录建议不直接作为实现契约。

> 日期：2026-09-11  
> 适用范围：当前 GitHub `main` 分支 v1.1 架构设计  
> 目标：在不继续扩大总体架构范围的前提下，将现有设计进一步工程化、机器化、可验证化，为后续 Agent 并行开发和正式实现提供执行清单。

## 1. 总体结论

当前总体架构已经较完整，核心闭环已经形成：

```text
Feature / Test / Coverage Model
        ↓
Case + Coverage Claim
        ↓
Compiler / Catalog
        ↓
Immutable Manifest / Bundle
        ↓
Selector / Target Expansion
        ↓
Resource Admission + Lease / Fencing
        ↓
Runner / Agent
        ↓
Cleanup / Reset / Probe
        ↓
Canonical Compare / Validator
        ↓
Durable Result Event
        ↓
Result Projection
        ↓
Baseline / Delta / Quality Gate
        ↓
Coverage Feedback
```

下一阶段不建议继续扩展 K8s、Controller HA、复杂 Web UI、云调度等非核心能力，而应重点把现有文档契约转化为可执行 Schema、统一 Registry、Contract Test 和 Golden Vector。

## 2. P0：正式编码前必须完成

### 2.1 Markdown 契约转换为机器 Schema

**问题**

Metadata、Test Model、Coverage Claim、Manifest、Result Event、Environment、Scenario 等规则当前主要由 Markdown 描述。多个 Agent 并行开发时，容易出现 Compiler、Scheduler、Result 对同一字段有不同理解。

**建议**

建立：

```text
schemas/
├── metadata.schema.json
├── test_model.schema.json
├── coverage_claim.schema.json
├── scenario.schema.json
├── test_plan.schema.json
├── environment.schema.json
├── manifest.schema.json
├── result_event.schema.json
└── result_snapshot.schema.json
```

Python 使用 Pydantic Model；多集群阶段 Agent Protocol 推荐 Protobuf/gRPC，MVP 可使用 JSON Schema + HTTP/JSON。

**验收**

- 所有输入必须 Schema 校验；
- 未知字段、重复字段拒绝；
- 枚举值统一；
- 版本显式；
- Compiler、Catalog、Runner 使用同一 Model；
- 不允许模块自行拼装协议字典。

---

### 2.2 建立 Contract Test / Golden Vector

**问题**

Canonical、Hash、Event、Coverage、Lease/Fencing 契约已经很细，但还缺标准输入与标准输出测试。

**建议目录**

```text
tests/contract/
├── canonical/
│   ├── null.json
│   ├── decimal.json
│   ├── float_nan.json
│   ├── timestamp.json
│   ├── timestamp_tz.json
│   ├── bytes.json
│   ├── rowsort.json
│   └── hash_v1.json
├── event/
│   ├── duplicate.json
│   ├── out_of_order.json
│   ├── event_gap.json
│   ├── conflicting_duplicate.json
│   └── late_pass_after_lost.json
├── coverage/
│   ├── duplicate_claim.yaml
│   ├── unmapped.yaml
│   ├── unsupported.yaml
│   └── invalid_assertion_ref.yaml
├── manifest/
│   ├── canonical_manifest.json
│   └── manifest_hash.json
└── lease/
    ├── expired_token.yaml
    ├── old_agent_return.yaml
    └── exclusive_conflict.yaml
```

不同语言实现必须对同一 Golden Vector 得到完全一致结果。

### 2.3 Resource Model 与 Conflict Matrix 正式化

**问题**

Lease/Fencing 已比较完整，但资源冲突规则仍主要是文字描述。Global Scheduler、Local Planner、Resource Manager 如果各自实现冲突判断，后续一定会产生不一致。

**建议资源树**

```text
Environment
└── Cluster
    ├── Node
    ├── Database
    │   └── Schema
    │       └── Session
    ├── BackupDir
    └── TempDir
```

统一增加：

```text
ResourceAdmissionEngine
```

所有资源准入都经过同一组件。

建议正式定义 READ / WRITE / EXCLUSIVE 三种访问模式，并建立 Conflict Matrix。

| 请求类型 | Session | Schema Write | DB Exclusive | Node Exclusive | Cluster Exclusive |
|---|---:|---:|---:|---:|---:|
| Session | 允许 | 条件允许 | 冲突 | 条件允许 | 冲突 |
| Schema Write | 条件允许 | 冲突 | 冲突 | 条件允许 | 冲突 |
| DB Exclusive | 冲突 | 冲突 | 冲突 | 冲突 | 冲突 |
| Node Exclusive | 条件允许 | 条件允许 | 冲突 | 冲突 | 冲突 |
| Cluster Exclusive | 冲突 | 冲突 | 冲突 | 冲突 | 冲突 |

**验收**

- Scheduler/Local Planner 不自行实现资源冲突；
- 多资源申请支持原子批量准入；
- 部分失败必须回滚预留；
- Cluster Exclusive 阻止全部子资源新任务进入。

---

### 2.4 Enum / Registry 建立单一事实源

建议：

```text
registry/
├── failure_types.yaml
├── statuses.yaml
├── capabilities.yaml
├── features.yaml
├── reason_codes.yaml
├── resource_types.yaml
├── execution_classes.yaml
└── isolation_levels.yaml
```

由 Registry 自动生成：

```text
Python Enum
JSON Schema Enum
Protobuf Enum
Markdown 文档
CLI completion
```

目标是禁止出现：

```text
Scheduler: INFRA_AGENT_LOST
Result: AGENT_LOST
Retry: infrastructure_error
```

新增枚举只能修改 Registry，不允许业务代码自行新增字符串常量。

---

### 2.5 Manifest Canonical Serialization 正式化

Manifest 已成为执行输入事实源，并参与 `manifest_hash`，因此必须规定统一 Canonical Serialization：

```text
UTF-8
LF
Object Key 词典序
无无意义空白
数组保留语义顺序
禁止 NaN / Infinity
数字固定编码规则
Boolean/null 使用 JSON 标准值
```

Manifest Hash 应被定义为“执行输入身份”，不是普通文件 Hash。

必须提供 Manifest Golden Vector，确保 Python、Go、Java 等实现一致。

## 3. P1：Phase 1 开发过程中完成

### 3.1 增加 Catalog Verify

建议增加：

```bash
xgtest catalog verify
```

至少验证：

```text
case_id 唯一
effective_metadata_json 与索引列一致
case_inputs 与 dependency_hash 一致
Coverage Claim 与 Test Model 一致
compiled_hash 与 Bundle 一致
semantic_hash 可重新计算
Suite 继承结果正确
不存在 dangling assertion_ref
```

全量 rebuild 与增量 index 的 Catalog 结果必须等价。

---

### 3.2 Coverage Claim 增加 Review 机制

显式 Coverage Claim 是正确方向，但 Claim 本身也可能写错，例如 SQL 为 INNER JOIN、Claim 却声明 LEFT JOIN。

对于 `status=active` 且存在 Coverage Claim 的 Case，建议要求 Coverage Review 证据。

Review 至少展示：

```text
Case SQL
Expected
Coverage Assignment
Assertion Refs
Model Definition
```

建议记录：

```yaml
coverage_review:
  reviewer: user-a
  reviewed_at: "2026-09-11"
  review_revision: abc123
  evidence_hash: xxx
```

未经 Review 的 Claim 不进入正式 Available Coverage 分子。

---

### 3.3 INFRA_RECOVERED 增加独立 Quality Gate

产品结果和测试基础设施健康度应分开。

建议支持：

```yaml
quality_gate:
  max_infra_recovered:
    op: lte
    value: 0
```

或：

```yaml
quality_gate:
  infra_recovered_rate:
    op: lt
    value: 0.01
```

避免大量基础设施失败重试成功后被整体 PASS 掩盖。

---

### 3.4 Reset / Probe Contract Test

Persistent Worker / Connection 是性能基础，同时也是污染风险最大的位置。

必须覆盖：

```text
未提交事务
autocommit
isolation
current schema
search_path
timezone
locale
session parameter
role
temporary table
cursor
prepared statement
lock
```

典型反例：

```text
Case A:
BEGIN
SET timezone
CREATE TEMP TABLE
PREPARE ...
异常退出

Case B:
验证 Session / Schema 干净
```

如果 Adapter 无法证明恢复成功，应销毁 Connection 或隔离资源，禁止继续复用。

---

### 3.5 semantic_hash 边界固定

`semantic_hash` 应明确定义为：

> 执行语义输入 Hash。

它可包含：

```text
Step Tree
SQL 原文规范化换行
Fixture
Oracle
Expected
Comparison Profile
重要执行参数
```

但禁止做 SQL 逻辑等价推断，例如：

```sql
SELECT a+b
SELECT b+a
```

不能因为数学上可能等价就自动生成相同 semantic_hash。

---

### 3.6 Phase 1 性能预算正式化

建议 Phase 1 就建立 Benchmark：

```text
benchmarks/
├── catalog_benchmark.py
├── compiler_benchmark.py
├── runner_overhead.py
├── canonical_benchmark.py
└── result_event_benchmark.py
```

至少观测：

```text
100k Case Catalog Selector
增量 Compiler
Fast Runner Framework Overhead
PASS Result 大小
大结果内存占用
RowSort 外部排序
Result Event 吞吐
```

目标不是第一版就追求极限，而是保证后续能判断慢点来自数据库还是测试框架。

## 4. P2：Scenario / Multi-cluster 阶段完成

### 4.1 Scenario Cancel / Barrier 极端测试

重点验证某个并发分支失败后整个 Scenario 能否有界结束。

建议场景：

```text
Branch A:
开启事务并持锁

Branch B:
等待该锁

Branch C:
Barrier Timeout

Scenario:
Cancel
```

必须验证：

```text
A rollback
B cancel
C timeout
所有 Session reset
所有资源释放
Attempt 得到确定终态
```

---

### 4.2 Lease / Fencing Chaos Test

典型场景：

```text
Agent A 获得 token=10
Agent A 与 Controller 断网
Lease 过期
Controller 将资源给 Agent B，token=11
Agent A 网络恢复
```

必须确保旧 token 不再拥有执行权限。

如果数据库入口无法真正使用 fencing：

```text
必须确认旧 Session/进程停止
+
Reset
+
Probe
```

否则资源进入 `QUARANTINED`。

---

### 4.3 Agent WAL / Event Replay Test

必须覆盖：

```text
Controller Down
ACK 丢失
Event 重发
Agent Restart
Controller Restart
乱序 Event
重复 Event
Event Gap
```

并保证：

```text
最终投影一致
Attempt 终态不可回退
LOST 不被迟到 PASS 覆盖
同 event_id 不同 payload 必须报协议错误
```

---

### 4.4 QUARANTINED Recovery Workflow 正式化

建议状态流程：

```text
ONLINE
  ↓
异常
  ↓
QUARANTINED
  ↓
Recovery Check
  ↓
Reset
  ↓
Probe
  ↓
Evidence Persist
  ↓
ONLINE
```

失败则进入：

```text
MAINTENANCE
```

建议 CLI：

```bash
xgtest env quarantine cluster-a
xgtest env recover cluster-a
xgtest env probe cluster-a
xgtest env enable cluster-a
```

---

### 4.5 Matrix Target Mapping Contract Test

必须保证 `target_id` 和 `environment_id` 不混淆。

例如：

```text
Target:
XG 5.1 / Linux / x86

Attempt 1:
Cluster A → LOST

Attempt 2:
Cluster B → PASS
```

最终只能有一个 CaseExecution，`target_id` 不变，两个 Attempt 分别记录实际 `environment_id`。

## 5. 建议新增工程目录

```text
allone/

├── schemas/
├── registry/
├── tests/
│   ├── contract/
│   ├── integration/
│   ├── scenario/
│   └── chaos/
├── benchmarks/
└── xgtest/
```

## 6. 推荐实施顺序

当前建议停止继续扩大总体架构，直接进入：

```text
架构冻结
   ↓
Schema 化
   ↓
Registry 单一事实源
   ↓
Contract Test
   ↓
Golden Vector
   ↓
Core Model
   ↓
Metadata
   ↓
XGT Parser
   ↓
Compiler
   ↓
Catalog
   ↓
Coverage Claim
   ↓
Selector
   ↓
Manifest / Bundle
   ↓
Local Runner
   ↓
Xugu Adapter
   ↓
Reset / Probe
   ↓
Canonical
   ↓
Result
```

首批真实验证功能：

```text
JOIN
UNION
DDL TABLE
STRING FUNCTION
```

暂时后置：

```text
Agent
Global Scheduler
HA
Backup / Restore
Web UI
Pairwise Generator
Controller HA
K8s
```

## 7. 优先级汇总

### P0：编码前必须完成

```text
1. Markdown 契约 → JSON Schema / Pydantic
2. Enum / Registry 单一事实源
3. Contract Test / Golden Vector
4. Resource Conflict Matrix
5. Manifest Canonical Serialization
```

### P1：Phase 1 开发过程中完成

```text
6. Catalog Verify
7. Coverage Claim Review
8. INFRA_RECOVERED Quality Gate
9. Reset / Probe Contract Test
10. semantic_hash 边界固定
11. Phase 1 Performance Budget
```

### P2：Scenario / Multi-cluster 阶段完成

```text
12. Scenario Cancel / Barrier 极端测试
13. Lease / Fencing Chaos Test
14. Agent WAL / Event Replay Test
15. QUARANTINED Recovery Workflow
16. Matrix Target Mapping Contract Test
```

## 8. 最终建议

当前 XG DB Test v1.1 已经不缺“大架构”。

后续最有价值的方向是：

> 把自然语言设计转化为机器可验证的执行契约。

核心目标应从：

```text
“架构设计是否完整”
```

转变为：

```text
“实现是否严格符合架构契约”
```

下一阶段优先建设：

```text
Schema
Registry
Contract Test
Golden Vector
Resource Admission
Canonical Serialization
```

这些基础设施稳定后，再使用多个 Agent 并行开发 Parser、Catalog、Runner、Coverage、Result、Scheduler，可以显著降低返工和接口漂移风险。

## 9. 逐项评审与纳入结果

总体方向正确：已有架构需要机器契约和可重复验收，而不是继续增加平台范围。16 项都包含有价值的目标，但其中若干规则、示例和时间安排需修正后采用。

| 原项 | 判断 | 纳入内容与边界 | 权威规范 |
|---|---|---|---|
| 2.1 机器 Schema | 调整后采纳 | Registry 枚举 + 严格 Pydantic Core Model 为源，JSON Schema 派生；重复键由解码器拒绝，语义/运行时验证不能省略 | [12 §2–4](12_Machine_Contracts_and_Engineering_Validation.md) |
| 2.2 Contract/Golden | 采纳，分阶段完成 | 固定字节、Hash、状态轨迹与拒绝结果；人工审定，真实故障集成测试后置到对应阶段 | [12 §6–7](12_Machine_Contracts_and_Engineering_Validation.md) |
| 2.3 Resource/Matrix | 原树和类型表不直接采纳 | Session 不属于固定 Schema；用稳定身份、影响范围与访问模式计算冲突，共享准入引擎与权威事务授予 | [06 §38](06_Distributed_Scheduler_Design.md) |
| 2.4 单一 Registry | 调整后采纳 | 状态分命名空间；框架 isolation 与事务隔离分开；Protobuf 编号不可按列表顺序生成 | [12 §2–3](12_Machine_Contracts_and_Engineering_Validation.md) |
| 2.5 Manifest Canonical | 细化后采纳 | 固定身份投影、数字/Unicode/数组/URI规则及 XGMJ1 字节；不是普通文件 Hash | [11 §12](11_Execution_Consistency_and_Validation_Contract.md) |
| 3.1 Catalog Verify | 采纳 | 只读检查绑定快照；区分损坏、工作区漂移、证据不足；不自动修复 | [05 §27–28](05_Case_Catalog_Design.md) |
| 3.2 Claim Review | 加强后采纳 | 独立 review_input_hash 绑定语义、完整 Claim、模型与断言；只改 Claim 也使证据失效 | [08 §19–20](08_Test_Model_and_Coverage_Design.md) |
| 3.3 INFRA_RECOVERED Gate | 采纳，调整时序 | Phase 1 留统计，Phase 6 实现可选门禁；不默认零容忍、不改变产品通过语义 | [07 §36](07_Result_Model_Design.md)、[10 §23](10_Release_Baseline_and_Delta_Design.md) |
| 3.4 Reset/Probe | 已有原则，补验收 | 按真实 Adapter 能力构造污染与恢复场景；无法证明恢复就不复用 | [11 §14](11_Execution_Consistency_and_Validation_Contract.md) |
| 3.5 semantic_hash | 已有原则，固定边界 | 不推断 SQL 等价，明确 timeout 等输入；Coverage Review 使用独立指纹 | [11 §13](11_Execution_Consistency_and_Validation_Contract.md) |
| 3.6 性能预算 | 采纳 | 建立可重复对照和分阶段基线；不把未经测量的目标宣称已达标 | [11 §15](11_Execution_Consistency_and_Validation_Contract.md) |
| 4.1 Scenario 极端测试 | 调整后采纳 | Barrier 配置必须合法；取消不能证明停止，失败时允许隔离而非强行释放所有资源 | [03 §29](03_Scenario_DSL_Specification.md) |
| 4.2 Lease 混沌 | 修正重分配顺序后采纳 | Lease 到期不能先授予新执行权；实际 fencing/停止与恢复证明先成立 | [06 §40](06_Distributed_Scheduler_Design.md) |
| 4.3 WAL 重放 | 采纳 | 本地重放 Phase 1；网络/Agent 崩溃 Phase 4，比较稳定投影和 ACK | [07 §35](07_Result_Model_Design.md) |
| 4.4 隔离恢复 | 修正后采纳 | 恢复期间关闭准入，证据绑定 epoch，enable 不可绕过恢复；失败是否维护取决于原因 | [06 §39](06_Distributed_Scheduler_Design.md) |
| 4.5 Matrix Mapping | 采纳 | 同 target 等价环境迁移只有一个 CaseExecution；不等价环境拒绝 | [06 §40](06_Distributed_Scheduler_Design.md) |

## 10. 原建议中需要明确纠正的关系

1. Run Manifest 必须在 Selector/target expansion 冻结预期集合后生成。可以先构建候选 Bundle，但不能在选例前就得到最终运行清单。
2. SQL 结果的 Canonical/Validator 随业务 Step 执行；不能默认 Cleanup/Reset 后才读取或比较结果。Cleanup 后进行的是最终结果裁决和资源释放。
3. 原冲突表缺 resource_id、祖先/依赖作用域和容量，容易错误禁止不同 Database 并行，又漏掉 Session 跨 Schema 或 Node 影响范围。已由 06 的明确冲突域矩阵替代。
4. tests/ 在现有架构中是数据库用例资产根；平台自身测试放 framework_tests/，避免被 Catalog 错误发现。旧 configs/Feature/Capability 规划合并到 registry/ 单一源。
5. “所有 Golden/Chaos Test 在编码前完成”不可作为交付顺序；先冻结当前阶段的规范与标准向量，Core Model 和测试共同建立，真实故障验证随实现完成。

当前正确主路径：

```text
Registry / Core Model → Feature/Test/Coverage
→ Case/Claim + Review → Compiler/Catalog Verify
→ Selector/target expansion → immutable Manifest/Bundle
→ Resource Admission → Steps（Canonical/Validator）
→ Cleanup/Reset/Probe → Result Finalize/Release
→ Event/Projection → Baseline/Delta/Gate → Coverage Feedback
```

WAL/事件可随执行过程持续持久化，不必等所有步骤结束才开始记录。第 2、3、4 节的 P0/P1/P2 是优化优先级，与数据库 Case 的 P0/P1 级别不同，不直接决定阶段交付。
本次纳入的是设计、结构和验收要求；机器 Schema、框架命令与测试目录尚待对应阶段开发。总架构和架构图已同步这些关系。
