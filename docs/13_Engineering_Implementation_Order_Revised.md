# XG DB Test 工程实施顺序与阶段验收（修订版）

> 日期：2026-09-14
> 依据：XG DB Test v1.1 架构、02–12 专项契约及当前 `main` 分支最新设计
> 状态：实施计划 / 待实现
> 修订目的：明确向量定义与执行验收的阶段边界，区分 Core Contract 与 Runtime Profile 冻结，补齐共享 Core Model、Adapter、Timeout/Cancel/Stop Proof、安全与可观测性工作项，并调整可并行实施路径。

---

## 1. 使用方式与总体顺序

本文将设计转为按依赖排序的实施工作包。当前运行框架尚未实现；以下步骤、目录、命令和验收均为计划，不代表功能已经完成。

实施原则：

1. 先冻结 SQL MVP 真正需要的共享契约，不提前实现后续分布式/HA 全部能力；
2. Xugu Driver / 数据库行为探测与离线框架开发并行；
3. 先用 1–3 条真实 JOIN 用例打通完整纵向链，再扩大到约 20 条种子，最后扩展四类样板；
4. 先单 Worker，再 Worker Pool；
5. Coverage Engine 不与 Runner 混合，Runner 只产生执行证据；
6. Phase 2、Phase 3、Phase 4 在 G1 后可按需要并行，不强制全部串行；
7. Mock/Fake 只能验证框架接口，不能代替真实 Xugu Adapter、Reset/Probe、取消和资源恢复验收。

总体路线：

```text
Phase 0A：工程骨架 + Core Contract Freeze
  ├── 最小 Registry / Core Model / Schema
  ├── XGMJ1 / XGC1 基础 Golden Vector
  └── 纯函数状态与静态规则
           │
           ├───────────────────────┐
           ↓                       ↓
工作包 A：Xugu Driver/DB 探测    Phase 1 离线模块开发
           ↓
Phase 0B：SQL Runtime Profile Freeze
  ├── Type Mapping
  ├── Error Mapping
  ├── Cancel / Stop Capability
  ├── Reset / Probe Contract
  └── Adapter Capability Profile
           ↓
Phase 1：单集群 SQL MVP
  Parser → Compiler/Catalog → Selector/Plan → Manifest/Bundle
  → Validator/Result → Admission/Worker → Xugu Integration
  → 第一条真实 JOIN → Coverage → Worker Pool → 四类样板
  → Catalog Verify / CI / Failure Recovery / Benchmark
           ↓
          G1
     ┌─────┼─────────┐
     ↓     ↓         ↓
Phase 2  Phase 3   Phase 4
Coverage Scenario  Multi-cluster
Generator Tx/并发  Agent/Scheduler
Phase 3 Scenario 基础 + G4
           ↓
Phase 5：Backup / Restore / Cluster / HA

G1 → Phase 6：Result DB / Baseline / Delta / Quality Gate
     （发布范围使用 Phase 2–5 的能力时，追加对应验收依赖）
```

Normalizer/Validator 和 Result 的基础接口必须在 Runner 集成前准备好。业务结果应在 Step 完成时验证，随后进行 Cleanup → Reset → Probe，最终再裁决 Attempt / CaseExecution。
工作包 A 可从前置环境就绪时与 Phase 0A 并行；G0B 只阻塞真实运行时集成，不阻塞 Phase 1 离线模块。Phase 5 的具体 Scenario 依赖见第 11 节。

---

## 2. 前置条件

### 2.1 必须落实的信息

| 编号 | 前置条件 | 具体内容 / 交付物 | 最晚落实时间 |
|---|---|---|---|
| PRE-01 | 设计基线 | 冻结实施起点 Git commit，确认总架构及 02–13 文档版本一致 | P0A 开始前 |
| PRE-02 | 开发环境 | Python 版本、OS/Arch、依赖管理、锁文件、CI 运行方式 | P0A |
| PRE-03 | Xugu 精确版本 | 产品版本/build、兼容模式、拓扑、字符集、时区、关键配置 | A-01 |
| PRE-04 | Python Driver | 名称、版本、安装来源、Python/OS 支持、连接参数、已知限制 | A-01 |
| PRE-05 | 独立测试环境 | 地址/端口、可达性、可分配 DB/Schema、连接上限、恢复方式 | A-01 |
| PRE-06 | 测试账号权限 | DDL/DML、事务、状态查询、必要时取消 Session 的权限 | A-01 |
| PRE-07 | 凭据管理 | Secret 引用方式；Git/Bundle/Result/Log 禁止保存明文秘密 | 首次连接前 |
| PRE-08 | Oracle 依据 | 小数据、人工推导/规范依据、错误码来源、审查责任 | Case active 前 |
| PRE-09 | 集成验证入口 | 可访问测试环境的位置、Artifact 路径、失败清理责任 | 第一条真实 SQL 前 |

“待确认”不阻止 Registry、Model、Parser、Catalog 等离线工作，但阻止对应真实能力被标记为 `VERIFIED`。

### 2.2 技术选型冻结原则

第一阶段沿用：

```text
Python Core
Pydantic Strict Model
Registry YAML
Derived JSON Schema
SQLite Catalog
JSONL Result/Event
Local Artifact
```

要求：

- YAML 解码器必须支持 YAML 1.2 Core 规则并拒绝重复键；
- Pydantic 不替代解码层重复键检查；
- CLI、YAML、依赖管理、测试框架各选一套，不允许各模块引入重复技术栈；
- HTTP/JSON 到 Phase 4 才成为远程协议依赖；
- gRPC、对象存储、复杂 UI、K8s 不作为 G1 前置。

### 2.3 工作包状态

统一状态：

```text
NOT_STARTED
IN_PROGRESS
BLOCKED
ACCEPTED
```

每个工作包必须记录：

```text
负责人
依赖
实现 commit
验证命令
验证环境
证据位置
已知限制
下一步依赖
```

没有验收证据不能标记 `ACCEPTED`。

---

## 3. Phase 0A：工程骨架与 Core Contract Freeze

### 3.1 工作包

| 步骤 | 依赖 | 实施内容 | 交付与验收 |
|---|---|---|---|
| P0A-01 冻结设计基线 | PRE-01 | 记录设计 commit；确认 SQL MVP 范围与未支持能力 | 关键契约均可定位到权威规范 |
| P0A-02 工程骨架 | P0A-01/PRE-02 | `pyproject`、包结构、CLI、framework tests、基础 CI | 干净环境可安装、导入、执行测试 |
| P0A-03 最小 Registry | P0A-02 | Feature、Capability、Level、状态命名空间、Failure Type、Isolation Scope、Resource Access Mode | 枚举单一源；未知 key 拒绝 |
| P0A-04 共享 Core Model | P0A-03 | 建立 SQL MVP 所需结构模型 | 所有消费方复用同一模型 |
| P0A-05 Schema / Static Validator | P0A-04 | 从 Core Model 导出 Schema；实现解码/结构/静态语义分层校验 | 导出可复现，错误码/字段路径稳定 |
| P0A-06 基础 Golden Vector | P0A-04/05 | Metadata、Registry、XGC1、XGMJ1、基础状态规则 | 精确字节/Hash/错误原因经独立审定 |
| P0A-07 Core Contract Freeze | P0A-03–06 | 发布 `contract_set_id`（阶段内亦称 core_contract_set_id，见 12 §2.1） | Parser/Compiler/Catalog 不再自建 DTO/枚举 |

### 3.2 P0A-04 必须包含的共享模型

#### Asset / Identity

```text
RawMetadata
EffectiveMetadata
UnifiedCase
Step / SqlStep / QueryStep
FixtureRef
CoverageClaim
CoverageReview
SourceInfo
ComparisonProfile
```

#### Planning

```text
TestPlan
Target
EnvironmentRequirement
ExpectedExecution
ResourceRequest
Manifest
BundleRef
```

#### Execution / Result

```text
Run
CaseExecution
Attempt
StepResult
ArtifactRef
ResultEvent
```

这里只冻结结构和核心含义，不要求 Phase 0A 已实现完整 Result 投影、远程 Event Replay 或 Resource Admission。

### 3.3 Phase 0A Golden Vector 的边界

#### P0A 必须可执行

```text
Registry
Metadata / Schema
XGC1 基础 Canonical
XGMJ1 Manifest Canonical Encoding
基础纯函数状态迁移（如已实现）
```

#### P0A 只要求“定义完成”，执行验收后置

```text
完整 Result Event Replay
Coverage Execution Projection
Resource Admission 并发冲突
Lease / Fencing
Agent WAL
分布式 Chaos
```

以上向量可以在 Phase 0A 定义输入/预期不变量，但不能为了通过 G0A 提前实现 Phase 1/4 全部代码。

### 3.4 G0A：Core Contract Gate

满足：

- 工程可安装；
- Registry / Core Model / Schema 可生成和验证；
- XGC1 / XGMJ1 基础向量可执行；
- SQL MVP 的身份、字段、默认值、核心状态不再由消费方自行定义；
- Event/Admission 等后续向量即使尚未可执行，也有明确版本和预期不变量。

G0A 通过后，Parser、Compiler、Catalog、Result Core、Admission Core 可以并行开发。

---

## 4. 工作包 A：Xugu 环境、Driver 与运行时能力探测

该工作包与 Phase 0A 并行。

| 步骤 | 依赖 | 实施内容 | 证据与通过标准 |
|---|---|---|---|
| A-01 环境建档 | PRE-03–07 | DB/Driver/OS/build/模式、资源额度、连接权限 | 可复现且脱敏 |
| A-02 类型读取 | A-01 | NULL/int/decimal/float/string/time/binary | 原始 Driver 类型、列元数据、值与精度明确 |
| A-03 事务行为 | A-01 | BEGIN/COMMIT/ROLLBACK/autocommit/DDL 行为 | 不假设 PG/MySQL 语义 |
| A-04 错误归类 | A-01 | 非法 SQL、约束、权限、连接中断 | SQL 错误与网络错误可区分 |
| A-05 Timeout / Cancel / Stop | A-03/04 | 长查询、锁等待、Driver cancel、服务端状态观察 | cancel 成功不等于服务端已停止 |
| A-06 Reset / Probe | A-02–05 | 事务、角色、Schema、临时对象、会话参数、句柄、锁 | 可证明清洁，或明确必须销毁连接/隔离资源 |
| A-07 Adapter Profile | A-02–06 | 固化 Xugu type/error/cancel/reset/probe 能力 Profile | 每项能力有 VERIFIED/UNSUPPORTED/UNKNOWN 及证据 |

能力探测状态：

```text
VERIFIED
UNSUPPORTED
UNKNOWN
FAILED
```

缺权限或不可观察必须记 `UNKNOWN`，不能伪装成 `UNSUPPORTED` 或 `VERIFIED`。

---

## 5. Phase 0B：SQL Runtime Profile Freeze

### 5.1 为什么需要第二次冻结

Core Contract 不应等待所有 Driver 实测才能开始；但 Runtime Contract 又不能在 Driver 行为未知时过早冻结。

因此分为：

```text
G0A：Core Contract Freeze
G0B：SQL Runtime Profile Freeze
```

### 5.2 工作包

| 步骤 | 依赖 | 内容 | 验收 |
|---|---|---|---|
| P0B-01 Type Mapping | A-02/G0A | Driver Value → Canonical Type | 无静默 string 化/截断 |
| P0B-02 Error Mapping | A-04/G0A | Xugu 错误 → Failure/Error Model | 数据库错误与 Infra 分开 |
| P0B-03 Cancel Profile | A-05 | cancel、timeout、stop proof 能力 | 能明确回答“是否确认停止” |
| P0B-04 Reset Contract | A-06 | worker/session reset/probe 能力 | 不可验证项明确要求销毁/隔离 |
| P0B-05 Adapter Capability Profile | P0B-01–04 | 发布 Adapter Profile Version | Runtime 行为有证据 |
| P0B-06 SQL Runtime Contract Freeze | P0B-01–05 | 发布 `sql_runtime_profile_id` | Phase 1 Integration 使用固定 Profile |

按 [12 §2.1](12_Machine_Contracts_and_Engineering_Validation.md#21-核心契约与运行时-profile-的发布身份)，核心契约集合的正式字段仍为 `contract_set_id`；`core_contract_set_id` 是 G0A 工作包中的同义称呼，不新增第二个协议字段。正式 Run 通过 Manifest 冻结：

```text
runtime_versions.contract_set_id
target_entries[].sql_runtime_profile_id
```

每个 SQL Target 固定一个 Profile，Profile 必须引用该 Run 的 contract_set_id；多个 Target 可以使用不同 Profile。Profile 内容、哈希输入、证据引用与兼容检查以 12 为准，Manifest 字段以 11 为准。
已发布核心契约和 Profile 均不得原地改写；规则需要调整时发布新版本和新身份，再重新校准相关 Profile，不能用 Driver 特例绕过核心规则。

---

## 6. 工作包 B：首批 SQL / Oracle / Cleanup / Coverage 资产

### 6.1 分三步建设样板

不在第一条闭环前一次性投入约 20 条完整用例。

#### B0：第一批 1–3 条 JOIN

用于验证：

```text
DSL
Compiler
Catalog
Manifest
Adapter
Canonical
Cleanup
Result
```

要求结果人工可核对。
B0 从 draft 开始，使用显式诊断选择进行 Trial Run；正式 Release 仍只选择 active。通过 Trial Run、Oracle 审查及当前 Claim 的有效 Review 后才能进入 active。draft/review 的证据可用于诊断，不贡献正式 Available/Selected/Executed/Passed Coverage。

#### B1：约 20 条手写种子

第一条真实 JOIN 闭环稳定后，再扩展：

| 功能 | 建议种子 |
|---|---:|
| JOIN | 6 |
| UNION | 4 |
| DDL TABLE | 5 |
| STRING FUNCTION | 5 |

种子用于暴露模型/Runner/Adapter 边界问题。

#### B2：四类正式 MVP 样板

G1 前扩展为每类约 10–50 条，总计约 40–200 条。

每条 Case 至少具有：

```text
稳定 Case ID
Feature/Level
小型 Setup 数据
Expected / Expected Error
可信 Oracle
Isolation / Resource / Timeout
Idempotency / Reset Contract
Cleanup
Coverage Claim
Assertion Refs
Coverage Review Evidence
```

不能把“第一次实测输出”直接保存成 Expected 后自动认定为 Oracle。

---

## 7. Phase 1：单集群 SQL MVP

### 7.1 可以并行的实现流

G0A 后允许并行：

```text
流 A：Parser / Compiler / Catalog
流 B：Canonical / Validator
流 C：Result Core
流 D：Generic Admission / Worker / Fixture
流 E：Xugu Driver Probe / Adapter Profile
```

G0B 后进入真实集成。

### 7.2 工作包

| 步骤 | 前置依赖 | 实施内容 | 交付与验收 |
|---|---|---|---|
| P1-01 解码与 XGT Parser | G0A | Header、显式块边界、JSON Expected、稳定 Step ID、SourceSpan | 正反例通过；不连接数据库 |
| P1-02 Metadata Resolver / Compiler | P1-01 | Suite 继承、Registry 校验、Unified Case、资源下限、Claim 静态校验、Hash | 确定性编译；非法引用拒绝 |
| P1-03 Catalog 2 | P1-02 | Schema、索引、依赖失效、事务提交、增量/全量 | 编译失败不提交半新半旧索引 |
| P1-04 Selector / Plan / Target | P1-03 | Feature/Level/Issue/Status 选择，冻结逻辑 Target 和 ExpectedExecution | UNSUPPORTED/NO_ENV 等不隐式消失 |
| P1-05 Manifest / Bundle | P1-04 | XGMJ1、Bundle、依赖内容、源漂移保护 | Runner 不重新读工作区最新内容 |
| P1-06 Canonical / Validator | G0A + A-02/04 校准 | Exact/RowSort/Expected Error、类型映射、重复行、大结果边界 | Golden Vector + Driver Value 验收 |
| P1-07 Local Result Core | G0A | Run/CaseExecution/Attempt/StepResult、JSONL、Artifact、状态裁决 | 重放可恢复；Cleanup Failure 保留 primary_status |
| P1-08A Generic Resource Admission | G0A | Resource ID/Scope/Access Mode、容量、原子准入 | 同物理资源冲突可判定 |
| P1-08B Fixture / Worker Lifecycle | G0A | Fixture Scope、Connection/Schema 生命周期、单 Worker | 生命周期确定，未清洁不复用 |
| P1-08C Xugu Reset / Probe Integration | G0B、P1-08B/G | 将 A-06 Profile 经真实 Adapter 接入 Worker | 不可确认清洁时销毁/隔离 |
| P1-08G 最小 Xugu Adapter 实现 | G0A；真实接口验收需 G0B | connect/close、execute、流式 fetch、列元数据、事务、错误转换、cancel、reset/probe；消费固定 Profile | 使用真实 Driver 验证正常、异常与资源关闭路径；Profile 不等于可执行 Adapter |
| P1-08D Timeout / Cancel / Stop Proof | G0B、P1-07、P1-08A/B/C/G | Deadline、Driver Cancel、服务端停止确认、Cleanup Budget | TIMEOUT/CANCEL 后资源不可误复用 |
| P1-08E Secret Redaction / Safe Logging | PRE-07/P1-07 | 日志、Artifact、ResultEvent 脱敏 | 密码/token/连接秘密不得泄露 |
| P1-08F Minimal Observability | P1-07、P1-08A/B/E | Structured Log、case duration、worker/resource 基础指标 | 能区分 DB 慢与 Framework 慢 |
| P1-09 第一条真实 JOIN 闭环 | P1-05/06/07、P1-08A–G、G0B、B0 | 完整纵向链 | 第 7.4 节的结果、崩溃恢复及源漂移验收 |
| P1-10 Minimal Coverage Engine / Review | P1-02/05/07、B0；真实投影验收需 P1-09，可与 Worker Pool 并行 | 消费冻结模型/策略/目标、资产及 Review、Plan/Manifest 与执行证据；all-values / mandatory-combination 五阶段投影 | 固定分母；Runner 不自行计算 Coverage；draft 试跑不贡献正式覆盖 |
| P1-11 Worker Pool + B1/B2 样板扩展 | P1-09 | 多 Worker、Fixture/Schema 复用、四类样板 | 重复/变序/并发一致 |
| P1-12 Catalog Verify / Report / CI | P1-03/10/11 | Catalog Verify、JUnit、摘要、自动契约检查 | CORRUPT/STALE/UNVERIFIABLE 可区分 |
| P1-13 Failure Recovery / Performance | P1-09–12 | Restart、重复/迟到 Event、污染注入、Catalog/Compiler/Runner/Canonical Benchmark | 正确性开启时测性能 |

P1-08G 可先按 G0A 接口开发，待 G0B 完成后实测；P1-08C 的真实集成还依赖 P1-08G。编号保留以便追踪，实施依赖以表格为准，不按字母顺序串行。秘密脱敏规则在探测脚本中从首次连接前执行，P1-08E 负责接入框架的统一日志与事件路径。

### 7.3 第一条真实 JOIN 的正确闭环

```text
.xgt + Suite
→ decode / validate
→ compile / index
→ select / plan / target
→ freeze Manifest + Bundle
→ create CaseExecution / Attempt
→ Resource Admission
→ Prepare / Setup
→ execute JOIN
→ Canonical + Validator
→ emit assertion execution evidence
→ Cleanup
→ Reset
→ Probe
→ commit final ResultEvent durably
→ project Attempt / CaseExecution final status
→ release reusable resource
```

这里**不要求 P1-09 直接生成 Coverage Snapshot**。
过程事件从 Attempt 建立起持续写入单写 JSONL，写完并 fsync 后才确认接收；Artifact 在引用前完成写入及内容校验。终态也必须先可靠提交再确认完成，不能等整条 Case 结束才集中保存历史事件。投影可由日志重建；Setup 后崩溃或恢复证据不完整的资源保持隔离，不能因为进程重启就自动复用。具体持久化与裁决遵循 [07 §34](07_Result_Model_Design.md#34-jsonl-mvp-的持久化等价实现)。

P1-09 只必须保存：

```text
case_id
claim_id
assertion_ref
assertion executed/passed evidence
case final status
target_id
attempt_id
```

上述字段是业务证据要素，仍须携带统一 ResultEvent 的运行身份、事件序列及 Manifest 关联，不能定义独立的简化事件协议。

P1-10 Coverage Engine 使用以下冻结输入，不能读取工作区当前版本重算历史：

| 输入 | 用途 |
|---|---|
| Model/version/hash、策略、覆盖计划要求与目标集合 | 建立 Designed 集合 D，包括没有任何 Case 的覆盖点 |
| Catalog/资产快照、Case status、Claim、有效 Review | 计算 Available，排除 draft、UNMAPPED 和 UNREVIEWED |
| Plan、Manifest、ExpectedExecution、适用性及原因 | 计算 Selected；UNSUPPORTED/NO_ENV 不缩小 D |
| 同一有效 Attempt 的完整断言证据、恢复结果、CaseExecution 终态 | 计算 Executed/Passed，不拼接失败重试中的断言 |

依照 [08 §17–18](08_Test_Model_and_Coverage_Design.md#17-覆盖点与分母算法)，五阶段共用同一 D，Snapshot 保留 manifest_hash、模型与 D 的身份及可恢复输入引用：

```text
Designed
Available
Selected
Executed
Passed
```

Runner 不能自己维护另一套 Coverage 逻辑。

### 7.4 P1-09 至少验收

1. 正常 PASS；
2. 故意修改 Expected → FAIL；
3. Setup/业务阶段中断仍执行 Cleanup；
4. Cleanup/Reset/Probe 无法恢复 → ERROR / QUARANTINED 或对应本地隔离；
5. 修改 index 后源文件 → 拒绝漂移或继续执行原 Bundle；
6. Timeout/Cancel 后若不能证明服务端 SQL 停止 → 资源不可复用。
7. Setup 后进程崩溃，以及终态已持久化但确认未返回 → 日志重放不丢失已提交证据、不重复裁决；未完成恢复的资源保持隔离。

通过后再扩大 Worker Pool。

### 7.5 G1：单集群 SQL MVP

- 四类样板各 10–50 条；
- Oracle、生命周期、Coverage Review 有效；
- 精确 Selector、不可变输入、真实 Xugu Adapter、Canonical/Validator 完整；
- 单 Worker、多 Worker、重复、变序均可复现；
- FAIL/TIMEOUT/CANCEL 后能证明恢复或隔离；
- Catalog 全量/增量等价，`catalog verify` 有效；
- Minimal Coverage Snapshot 正确，UNMAPPED/UNREVIEWED/UNSUPPORTED 单列；
- JSONL 重启与基础 Event Replay 不错误回退终态；
- `INFRA_RECOVERED` 独立统计；
- Secret Redaction 基础验收通过；
- 具备 Phase 1 Benchmark/Limit Report。

G1 不要求：

```text
Remote Agent
Global Lease Renewal
Backup/Restore
HA
完整 Baseline/Delta
完整 Quality Gate
Web UI
```

---

## 8. Phase 2：Coverage 扩展与 Generator

前置：G1。

| 步骤 | 内容 | 验收 |
|---|---|---|
| P2-01 | Model/Constraint 完整校验 | 不可满足模型/不可达值明确报告 |
| P2-02 | Pairwise / Boundary / Negative / Interaction | 每种策略独立 Golden Vector |
| P2-03 | Deterministic Template Generator | 相同输入生成相同候选 |
| P2-04 | Dedup / Static Validate / Trial Run / Review | 不误删不同目的 Case |
| P2-05 | Coverage Gap → Candidate → Active → Snapshot | Gap 补齐可追踪 |

G2：至少一个真实 Feature 完成覆盖缺口驱动生成闭环。

Phase 2 不是 Phase 3/4 的强制前置；如果业务优先级更高，可以在 G1 后并行推进。

---

## 9. Phase 3：Scenario / Transaction / Concurrency

前置：G1。Phase 2 非强制依赖。

| 步骤 | 内容 | 验收 |
|---|---|---|
| P3-01 | Scenario Model/Parser、Step Tree、静态资源检查 | 未知动作、非法引用提前拒绝 |
| P3-02 | Session Manager / Transaction | autocommit/isolation 明确，Session 不串扰 |
| P3-03 | parallel/barrier/signal/wait/condition | 作用域、预算、取消传播明确 |
| P3-04 | 可见性/阻塞/死锁 Validator | 用条件观察，不靠 sleep 猜时序 |
| P3-05 | Branch Failure/Barrier Timeout/Cancel/Cleanup Timeout | 有界结束；未停止则隔离 |

G3：正常与异常并发都有确定结果及恢复证据。

---

## 10. Phase 4：Agent / Multi-cluster / Scheduler

### 10.1 前置条件修正

**G1 是强制前置。**

只有当 Phase 4 要直接支持“分布式执行 Scenario/Transaction Case”时，才额外要求 G3。

因此允许：

```text
G1
├→ Phase 2
├→ Phase 3
└→ Phase 4（SQL multi-cluster）
```

而不是强制：

```text
G1 → G2 → G3 → G4
```

### 10.2 工作包

| 步骤 | 内容 | 验收 |
|---|---|---|
| P4-01 | Target / Environment Registry / Capability Match | target_id 与 environment_id 分离 |
| P4-02 | Controller State / Global Admission / Lease/Fencing | 原子准入、epoch/token、资源冲突 |
| P4-08 | TLS/Auth/Secret Distribution；在 P4-03 真实通信前完成 | 验证对端身份与任务权限；未认证 Agent 不接收任务或秘密，Bundle 只含秘密引用 |
| P4-03 | Agent Register/Heartbeat/Bundle/ACK/Reconcile；依赖 P4-02/08 | 旧 assignment 不复活 |
| P4-04 | Shard / Matrix / Weighted LPT / Local Planner | Shard 级下发，无每 SQL RPC |
| P4-05 | Agent WAL / Durable ACK / Backpressure | Controller 短暂故障可恢复 |
| P4-06 | Agent Lost / Retry Migration / QUARANTINED Recovery | 无停止证明不重新授权 |
| P4-07 | Network Partition / ACK Loss / Restart / Old Agent Return | 无双持有者；迟到 PASS 不覆盖 LOST |
| P4-09 | Controller/Agent Observability | Heartbeat、Lease、Queue、WAL、Worker 指标可观察 |

G4：Shard/Matrix 正常和故障迁移均可审计；同 target 下 A LOST → B PASS 仍为一个 CaseExecution、两个 Attempt。

---

## 11. Phase 5：Backup / Restore / Cluster / HA

前置：G4 加上 P3-01 的 Scenario 解析/Step Tree、P3-02 的会话执行基础，以及 P3-05 中与所用动作相关的取消、异常退出和清理恢复验收。系统动作沿用 Scenario DSL，SQL-only 的 G4 不能替代这些能力。涉及并发事务、Barrier 或分支协调的系统场景还需 P3-03/04 和完整 G3；不使用 Generator 的场景不依赖 G2。准备专用可恢复环境和破坏性操作授权。

| 步骤 | 内容 | 验收 |
|---|---|---|
| P5-01 | Admin/System/Backup/Cluster Adapter | Metadata 不可降低动作最低 destructive/isolation/resource |
| P5-02 | Node Start/Stop/Config/Script | 路径与节点目标受控 |
| P5-03 | Backup / Restore | 不只看命令成功，要验证数据/对象状态 |
| P5-04 | Failover / Rejoin / Replication / Consistency | 状态断言证明结果 |
| P5-05 | Partial Failure / Cancel / Cleanup Failure | 隔离、证据、恢复流程有效 |

G5：每个正式声明支持的系统动作都有成功和失败恢复证据。

---

## 12. Phase 6：Release Quality / Result DB / Baseline

前置：至少 G1 的可信结果；具体发布计划若包含 G2–G5 能力，则对应阶段必须完成。

| 步骤 | 内容 | 验收 |
|---|---|---|
| P6-01 | Result DB Projection / Query / Artifact Index | Event Truth 可重建投影 |
| P6-02 | Baseline Lock / Target Mapping | 歧义拒绝，迟到事件不改锁定快照 |
| P6-03 | Membership/Case/Context/Outcome Delta | 不可比样本不冒充产品回归 |
| P6-04 | Failure Signature / Flaky / Coverage History | Signature 只作聚类候选 |
| P6-05 | Absolute/Delta Quality Gate + INFRA_RECOVERED Gate | 固定分母；INDETERMINATE 不默认放行 |
| P6-06 | API / Dashboard / Allure | 展示不重新计算核心语义 |
| P6-07 | Change Impact（可选，Post-v1 增强） | 有代码→Feature 证据后再启用 |

**P6-07 不作为 G6 核心完成条件。**

G6 的核心是：

```text
可信 Result
Baseline
Comparable Delta
Coverage Delta
Quality Gate
CLI/CI Release Decision
```

Dashboard 可以后续增强，Change Impact 明确为可选扩展。

---

## 13. 阻塞与并行策略

| 条件 | 可以继续 | 不得验收 |
|---|---|---|
| 无 Xugu 环境 | Registry/Model/Schema/Parser/Compiler/Catalog/Manifest/纯 Vector | Adapter/G0B/真实 JOIN/G1 |
| 无 Cancel 权限 | 类型、普通 SQL、离线模块 | Stop Proof / Safe Connection Reuse |
| Oracle 未确认 | Case Draft、结构、其他已确认 Case | 该 Case active/Coverage Contribution |
| 只有一个环境 | G1、Phase 2/3 | Multi-environment Migration/Matrix |
| G3 未完成 | SQL Multi-cluster Phase 4 | Distributed Scenario Execution |
| HA 恢复方式未知 | 普通 Agent/Scheduler | 对应破坏性 HA Capability |

并行开发必须建立在共享契约已冻结的前提下，不允许“为了并行”让各 Agent 自定义 DTO、状态枚举或 Hash 规则。

---

## 14. 第一轮实际开工任务

建议实际按以下顺序创建 Issue/Task：

1. 冻结 PRE-01/02，记录工程起点；
2. P0A-02：建立 Python 工程骨架和 CI；
3. P0A-03：建立最小 Registry；
4. P0A-04：建立完整 SQL MVP Core Model；
5. P0A-05/06：Schema、Static Validator、XGC1/XGMJ1 Golden Vector；
6. 通过 G0A，发布 `contract_set_id`；
7. A-01–06 Xugu Driver/DB 探测从环境就绪时即可与 P0A 并行，无需等待 G0A；
8. 并行启动 P1-01/02/03、P1-06、P1-07、P1-08A/B；
9. 完成 P0B-01–06，发布 `sql_runtime_profile_id`；
10. 选定 B0 的 1–3 条 draft JOIN，完成 P1-08G 真实 Adapter 验收，再完成 P1-08C/D；P1-08E/F 可独立推进；
11. P1-09：打通第一条真实 JOIN；
12. P1-10 Coverage Engine 与 P1-11 Worker Pool/B1/B2 并行推进；
13. 完成 P1-12/13，评审 G1；
14. G1 后按业务优先级并行启动 Phase 2/3/4。

每个任务交付必须包含：

```text
实现范围
引用规范
关键技术选择
验证命令
验证环境
证据位置
已知限制
下一步依赖
```

---

## 15. 本次修订摘要

本修订相对上一版实施文档，重点修正：

1. **明确向量定义与执行验收的阶段边界**：Phase 0A 区分“向量定义完成”和“向量必须可执行”，避免误将后续实现作为 G0 前置；
2. **契约冻结拆为 G0A / G0B**：Core Contract 不等待 Driver，Runtime Profile 不在 Driver 未知时冻结；
3. **补全 P0 Core Model 范围**：加入 TestPlan、ExpectedExecution、Run、CaseExecution、StepResult、ArtifactRef、ResourceRequest 等；
4. **修正第一条 JOIN 的 Coverage 边界**：P1-09 只产生 assertion execution evidence，P1-10 才生成 Coverage Snapshot；
5. **拆分 Admission/Worker/Xugu Reset/Cancel**，减少无意义串行依赖；
6. **Coverage Engine 与 Worker Pool 可并行**；
7. **Phase 4 改为 G1 必需、G3 条件依赖**；
8. **新增 Secret Redaction、安全日志、TLS/Auth、Observability 的明确实施节点**；
9. **第一批 Case 改为 1–3 JOIN → 约 20 种子 → 四类 40–200 条**，降低前期返工；
10. **Change Impact 明确为 Post-v1 可选增强，不阻塞 G6**。
11. **补齐执行依赖与证据链**：明确最小 Adapter 编码、Phase 5 的 Scenario 前置、Coverage 冻结输入和过程事件持续持久化；契约身份同步到 11/12。

---

## 16. 规范索引

实施时仍以各专项文档为权威定义：

```text
总架构                         → 架构边界 / Phase 范围
02 XGT                         → SQL DSL
03 Scenario                    → 多 Session / 并发 DSL
04 Metadata                    → Metadata / Registry 映射
05 Catalog                     → Catalog / Verify
06 Scheduler                   → Target / Environment / Lease / Fencing
07 Result                      → Result / Event / State
08 Coverage                    → Test Model / Claim / Coverage
09 Lifecycle                   → Case Lifecycle / Generator / Review
10 Baseline/Delta              → Release Comparison / Quality Gate
11 Execution Consistency       → Manifest / Bundle / Canonical / Reset/Probe
12 Machine Contracts           → Registry / Core Model / Schema / Golden Vector
13 本文                         → 实施依赖、工作包和 Gate
```

如果实施中发现契约需要变化：

```text
先修改权威规范
→ 更新 Contract/Golden Vector
→ 更新 Core Model/Registry
→ 再修改消费方实现
```

禁止只修改实施顺序文档来掩盖契约语义变化。
