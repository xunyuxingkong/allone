# XG DB Test 当前代码实现问题与修正方案清单（最新整理版）

> 仓库：`xunyuxingkong/allone`  
> 当前 `main` 最新提交：`242dd99db360b94679cdfb9e70eb032e27bc784e`  
> 最新提交：`feat: build SQL runtime profiles from probes`  
> 上一轮评审基线：`3d0f71a333a856bfc51808c668998ea3e2303006`  
> 更新日期：2026-09-16  
> 目的：在原问题清单基础上重新整理——已解决项明确标记“已解决”；未解决、部分解决和最新代码中新发现的问题统一保留，并给出原因、风险、修正方案和验收标准。

---

# 1. 总体结论

本轮代码相较上一轮已经有明显进展，已经新增或完善：

```text
RegistryEntry 元数据
Registry Enum 单一事实源
Enum 名称碰撞检查
Core Model 大幅扩充
ResultEvent 完整身份字段
Target / ResourceRequest / Manifest 扩充
YAML 1.2 Core 风格 Resolver
Schema 全目录重建与 Contract Identity
Python 版本范围调整
XuguSession
SQL MVP Diagnostic Runner
类型化 MVP Report
SQL Comparator
Runtime Profile Builder
四类 MVP Bootstrap Case
DECIMAL / Transaction Probe 修正
Extended Type Probe 状态拆分
```

当前已经从：

```text
Phase 0A 基础骨架
```

推进到了：

```text
Phase 0A 后半段
+
部分 Phase 1 Diagnostic Vertical Slice
```

但最新代码也暴露了一个新的核心风险：

> **可运行 Runner / Comparator / Runtime Profile 的实现速度，已经开始超过正式 Contract / Canonical / Manifest 主链的落地速度。**

因此当前最优先事项不是继续增加更多 Case、Worker 或功能，而是先把执行正确性、Contract 一致性、Canonical 一致性、Runtime Profile 身份稳定性和 Runner 生命周期语义收紧。

---

# 2. 状态与优先级说明

状态：

```text
✅ 已解决
🟡 部分解决 / 仍需收口
❌ 未解决
🆕 新发现
```

优先级：

```text
P0：继续推进正式 Parser / Compiler / Catalog 前应修正
P1：Phase 1 早期必须修正
P2：G1 前处理
```

---

# 3. 原问题清单最新状态总览

| 编号 | 原问题 | 当前状态 | 最新判断 |
|---|---|---|---|
| 1 | Core Model 过薄 | 🟡 部分解决 | 已大幅扩充，但正式 Runner 尚未使用 |
| 2 | ResultEvent 过薄 | ✅ 已解决 | 核心身份字段已补齐 |
| 3 | Target 过薄 | ✅ 结构已解决 | 但 Diagnostic Runner 未使用正式 Target |
| 4 | Manifest 过薄 | 🟡 部分解决 | 结构扩充，但执行链尚未使用 Manifest/Bundle |
| 5 | Python 3.14 锁死 | ✅ 已解决 | 已改为 `>=3.11,<3.15` |
| 6 | YAML 1.2 Core 不完整 | 🟡 基本解决 | Resolver 已重构，Golden Vector 仍需补齐 |
| 7 | Enum 名称碰撞风险 | ✅ 已解决 | 已加 `REGISTRY_ENUM_NAME_COLLISION` |
| 8 | Registry 丢失 Entry 元数据 | ✅ 已解决 | 已增加 `RegistryEntry.metadata` |
| 9 | Registry 与 Literal 双真源 | 🟡 基本解决 | 核心状态已改用生成 Enum，仍有自由字符串 |
| 10 | Schema stale 文件无法发现 | ✅ 已解决 | 已采用临时目录整体重建 |
| 11 | Schema 缺契约身份 | ✅ 已解决 | 已加入 `$id` 和 contract version |
| 12 | DECIMAL Probe 写死 FAILED | ✅ 已解决 | 已按实际 Driver Python 类型动态判断 |
| 13 | Transaction Probe observer 快照污染 | ✅ 已解决 | 已改用 fresh observer connection |
| 14 | Extended Type `VERIFIED` 语义过宽 | 🟡 基本解决 | 已拆 operation/mapping/canonical，但判定仍偏粗 |
| 15 | Probe Artifact 暴露 host | 🟡 部分解决 | 改成 host_hash，但无盐 Hash 仍有问题 |
| 16 | Canonical Golden Vector 不足 | 🟡 部分解决 | 已补 Decimal/NaN/±0/Temporal/Bytes，仍不完整 |
| 17 | Temporal 只按 `str` 编码 | 🟡 部分解决 | 已校验格式形状，但未校验真实日期/时区语义 |
| 18 | NaN / ±0 Golden Vector 不足 | ✅ 基础问题已解决 | 已有对应一致性测试 |
| 19 | ComparisonProfile 太简化 | 🟡 基本解决 | 已增加 error/normalization/float/timestamp policy |
| 20 | `expected: Any` 过宽 | 🟡 模型已解决 | Core Model 已类型化，但 Runner 尚未使用它 |
| 21 | Resource access mode 不完整 | ✅ 已解决 | 已支持 `shared_read/shared_write/exclusive` |
| 22 | ResourceRequest 缺 resource_type/impact | ✅ 基本解决 | 已加入 type/impact/parent/quantity |
| 23 | Generated Enum 类名可读性差 | ✅ 已解决 | 已增加显式 Enum Class Name 映射 |
| 24 | ContractError 信息不足 | 🟡 部分解决 | 仍需 SourceSpan / line / column |
| 25 | Xugu Adapter 只有 connect/smoke | 🟡 部分解决 | 已增加 XuguSession，但 reset/probe/cancel 仍未完成 |
| 26 | Probe 没有 Runtime Profile | 🟡 已开始解决 | 已新增 Profile Builder，但还不是正式 Contract Model |
| 27 | Runtime Profile Identity 信息不足 | ❌ 未解决 | 当前仍缺正式身份投影和稳定性 |
| 28 | CI 没有 Real Xugu Integration 分层 | 🟡 部分解决 | 已有 marker，但不等于已有真实 Integration CI |
| 29 | Driver ZIP 直接提交 Git | ❌ 未解决 | 建议迁移制品仓库 |
| 30 | `requirements.lock` 机制不清 | ❌ 未解决 | 仍需确定正式 lock 工具 |
| 31 | Contract Test 数量不足 | 🟡 部分解决 | 数量已增加，但还不足以完整 Freeze |

---

# 4. 已解决项

## 4.1 ✅ ResultEvent 核心结构已补齐

现在已经包含：

```text
schema_version
event_id
run_id
case_id
attempt_id
target_id
environment_id
producer_epoch
assignment_epoch
sequence
fencing_token
timestamp
event_type
payload
```

原“ResultEvent 太薄”的结构性问题已解决。

后续属于 Result Engine 实现的问题包括：

```text
event_id 唯一规则
duplicate event
conflicting duplicate
sequence gap
late event
terminal state immutable
durable ACK
```

---

## 4.2 ✅ Target Model 结构已基本补齐

当前已有：

```text
database_product
database_version
db_build
driver_name
driver_version
os
arch
topology
mode
configuration_fingerprint
dataset_fingerprint
sql_runtime_profile_id
target_id
```

Target 结构层面的原问题已解决。

后续只需固定唯一算法：

```text
Target Identity Projection
→ XGMJ1
→ SHA-256
→ target_id
```

不能允许 `target_id` 由调用方自由拼接。

---

## 4.3 ✅ Registry Entry 元数据已保留

当前 `RegistryEntry` 已保存：

```text
key
metadata
```

不再静默丢弃 `phase` 等属性。

---

## 4.4 ✅ Registry Enum Collision 已解决

现在已对多个 Registry Key 规范化为同一 Python Enum Member 的情况做冲突检测，并抛出：

```text
REGISTRY_ENUM_NAME_COLLISION
```

---

## 4.5 ✅ Generated Enum 类名已改进

现在有显式类名：

```text
FeatureKey
CapabilityKey
FailureType
IsolationScope
ResourceAccessMode
CaseAssetStatus
CaseExecutionStatus
AttemptStatus
StepStatus
```

---

## 4.6 ✅ Python 3.14 单版本锁死已解决

已调整为：

```text
Python >=3.11,<3.15
```

并增加 `xugu_integration` pytest marker。

后续仍应生成真实：

```text
Python Version × Xugu Driver Version
```

兼容矩阵，但原问题已解决。

---

## 4.7 ✅ Schema stale 文件问题已解决

Schema 现在采用：

```text
临时空目录生成
→ 删除旧 Schema 目录
→ 整体替换
```

不会继续残留已删除 Model 的旧 Schema。

---

## 4.8 ✅ Schema Contract Identity 已解决

生成 Schema 已加入：

```text
$id
x-xg-contract-version
```

---

## 4.9 ✅ DECIMAL Probe 写死 FAILED 已解决

现在已按实际 Driver 返回类型判断：

```text
decimal.Decimal
→ EXACT
→ Canonical VERIFIED

其他类型，例如 float
→ LOSSY
→ Canonical FAILED
```

---

## 4.10 ✅ Transaction Probe observer 污染已解决

现在每次事务可见性检查通过 fresh observer connection 查询，避免旧 observer transaction snapshot 导致误判。

---

## 4.11 ✅ Resource Access Mode 基础结构已解决

当前 Registry 已定义：

```text
shared_read
shared_write
exclusive
```

---

## 4.12 ✅ ResourceRequest 主要字段已补齐

当前已有：

```text
resource_type
resource_id
scope
access_mode
quantity
impact_scope
parent_identity
```

---

# 5. 部分解决但仍需继续收口的问题

## 5.1 P0：Core Model 已扩充，但正式执行链并未使用

### 已完成

当前 Raw/Effective Metadata 已增加：

```text
metadata_version
subfeature
scenario
complexity
execution_class
parallel
idempotency
retry
reset_contract
cleanup_timeout
requirements
resources
owner
since
until
generated_by
disabled_reason
replaced_by
```

Status / Feature / Level / Isolation 也已使用 Registry Enum。

### 剩余问题

最新 Runner 仍然：

```text
load_yaml()
→ dict
→ case.get()
→ step.get()
→ 直接执行数据库
```

即：

```text
Core Model 很严格
Runner 却完全绕过 Core Model
```

当前 `cases/mvp/*.yaml` 也并不满足完整 `EffectiveMetadata` 所要求的字段。

### 风险

会出现：

```text
Schema/Contract 判非法
但 Runner 仍然能执行
```

### 优化方案

短期先增加：

```text
BootstrapCaseInput / MvpCaseInput
```

并要求：

```text
raw YAML
→ Pydantic model_validate
→ Runner
```

正式实现再切到：

```text
DSL
→ Parser/Resolver
→ UnifiedCase
→ Runner
```

### 验收标准

Runner 不再通过 `dict.get()` 读取核心执行字段。

---

## 5.2 P0：Manifest 结构已扩充，但执行链未使用

### 已完成

Manifest 已加入：

```text
git_commit
dirty
source_snapshot_hash
catalog_snapshot_id
plan_hash
case_entries
target_entries
runtime_versions
```

### 未完成

当前 `xgtest run` 仍是：

```text
case_dir
→ glob YAML
→ 直接读取工作区
→ 执行
```

缺少：

```text
Selector
Plan
Target Expansion
Manifest Freeze
Bundle
Source Drift Verify
```

### 优化方案

当前 Runner 明确定位为：

```text
bootstrap / diagnostic runner
```

正式 Runner 只接受：

```text
Frozen Manifest + Bundle
```

---

## 5.3 P1：YAML 1.2 Resolver 基本完成，但 Contract Vector 仍不足

建议至少固定以下输入：

```yaml
a: 0123
b: 0o123
c: 0x10
d: .inf
e: -.inf
f: .nan
g: 1_000
h: 2026-09-16
i: yes
j: no
k: ON
l: Null
```

并增加：

```text
1__0
0o_1
nested duplicate
unhashable mapping key
深层嵌套
超大输入
```

建议建立固定 `framework_tests/contract/yaml/` Golden Vector 数据集。

---

## 5.4 P1：Extended Type Probe 已拆状态，但语义判定仍偏粗

### 已完成

已有：

```text
operation_status
mapping_status
canonical_compatibility
status
```

### 当前不足

主要还是用：

```text
type(fetched) is type(input)
```

判断 EXACT。

这不能发现：

```text
datetime 精度截断
timezone 丢失
binary 长度变化
BLOB 内容截断
```

### 优化方案

每种类型至少验证：

```text
type equality
value equality
precision equality
scale equality
length equality
timezone equality
round-trip equality
```

再得出：

```text
EXACT
LOSSY
STRINGIFIED
UNSUPPORTED
UNKNOWN
```

---

## 5.5 P1：Probe 隐私处理改善，但 host_hash 仍不够安全

当前已从原始 Host 改成：

```text
SHA256(host)
```

但 IP/短主机名属于低熵值，可枚举反查。

### 优化方案

优先不保存 Host，只保留：

```text
environment_id
target_ref
```

如确实需要关联，使用：

```text
HMAC-SHA256(secret_salt, host)
```

而不是无盐 SHA-256。

`database_alias` 同样需要评估是否属于内部敏感信息。

---

## 5.6 P1：Canonical Golden Vector 已补充，但仍不完整

目前已有：

```text
Decimal 1.00 == 1
NaN canonicalization
+0.0 / -0.0
date format
bytes 00/FF
```

仍建议补：

```text
大整数
负大整数
极小 Decimal
Decimal exponent
Decimal 0E-N
float +Inf/-Inf
多个不同 NaN payload
empty string
trailing spaces
Unicode combining form
isolated surrogate
NULL vs "NULL"
empty result
duplicate rows
zero-column result
time
timestamp
timestamp_tz
timezone offset edge
```

---

## 5.7 P1：Temporal 已做格式检查，但缺真正语义校验

当前 Regex 可以验证“长得像”：

```text
YYYY-MM-DD
HH:MM:SS
Timestamp
Timestamp TZ
```

但例如：

```text
2026-99-99
25:99:99
+99:99
```

仍可能通过形状检查。

### 优化方案

用真正解析器验证：

```text
date.fromisoformat
time.fromisoformat
datetime.fromisoformat
```

再重新编码成 Canonical 文本。

对 `timestamp_tz` 还必须明确：

```text
保留 offset
```

还是：

```text
统一转换 UTC/Z
```

并用 Golden Vector 固定。

---

## 5.8 P1：ComparisonProfile 已扩展，但策略仍为自由字符串

当前已有：

```text
error_profile
normalization_profile
float_policy
timestamp_policy
```

后续稳定后建议建立 Registry：

```text
comparison_modes
normalization_profiles
float_policies
timestamp_policies
```

不用立即全部 Enum 化，但正式 Release Case 前应冻结。

---

## 5.9 P1：Expected Model 已类型化，但 Runner 未使用

Core Model 已有：

```text
ExpectedRows
ExpectedHash
ExpectedError
ExpectedStatement
```

但 Runner 仍传递自由 `dict/Any` 给 Comparator。

### 优化方案

严格 Dispatch：

```text
ExpectedRows      -> compare_rows
ExpectedHash      -> compare_hash
ExpectedError     -> compare_error
ExpectedStatement -> compare_affected_rows
```

Comparator 不再根据字典 key 猜 Expected 类型。

---

## 5.10 P1：ContractError 仍需 SourceSpan

正式 Parser/Compiler 阶段建议支持：

```text
file
line
column
field_path
code
message
details
cause
```

---

## 5.11 P1：XuguSession 基础能力已有，但 Reset / Probe 尚未成立

当前已有：

```text
open
execute
query
begin
commit
rollback
cancel
reset
close
```

但现在：

```text
reset() = rollback()
```

这不是完整 Session Reset。

真正 Reset 至少涉及：

```text
transaction
autocommit
isolation
schema
role
timezone
session parameter
temporary object
prepared handle
cursor
lock
```

### 优化方案

当前 `reset()` 先改名为：

```text
rollback_transaction()
```

等 A-06 验证后再实现真正：

```text
reset()
probe()
```

无法证明 clean 时必须销毁连接。

---

## 5.12 P1：Real Xugu Integration CI 仍未真正完成

虽然已有 `xugu_integration` marker，但 marker 只是测试分类，不等于真实 CI。

还需要：

```text
内网 Runner
真实 Driver
真实 Xugu
独立凭据
Integration Artifact
```

建议独立命令：

```bash
pytest -m xugu_integration
```

与公共 Contract CI 分开。

---

## 5.13 P1：Driver ZIP 仍不建议长期留 Git

建议迁移到：

```text
Nexus
Artifactory
MinIO
Internal Package Registry
```

Git 只保存：

```yaml
driver_version:
sha256:
artifact_ref:
```

---

## 5.14 P1：依赖锁文件机制仍需明确

建议正式选择：

```text
uv.lock
pip-tools
Poetry lock
```

不要长期让 `requirements.lock` 只是一次普通 `pip freeze`。

---

# 6. 最新代码中新发现的 P0 问题

## N1. P0 Critical：普通 SQL 报错可能被 `compare_error()` 误判为 PASS

### 当前逻辑

Runner 对任何异常都会调用：

```text
compare_error(error, step.expected)
```

而 `compare_error()` 在 expected 没有：

```text
code
sqlstate
message_pattern
```

时最终可能返回 `True`。

例如正常 Query：

```yaml
expected:
  rows:
    - [2, two, 20]
```

实际 SQL 却报：

```text
table not found
```

此时 `expected` 并不是 ExpectedError，但当前 Comparator 仍可能把这个异常判成 PASS。

### 风险

这是严重测试正确性问题：

```text
SQL 真失败
→ 测试框架报告 PASS
```

### 原因

Comparator 根据自由 Dict 猜 Expected 类型，而不是通过类型系统显式 Dispatch。

### 修正方案

只有 `ExpectedError` 才允许异常比较：

```text
ExpectedError:
    没报错 -> FAIL
    报错 -> compare_error()

ExpectedRows / ExpectedHash / ExpectedStatement:
    报错 -> ERROR
```

Comparator 改成只接收 `ExpectedError`，不能再接收 `Any`。

### 必须增加测试

```text
ExpectedRows + DB Exception -> ERROR
ExpectedStatement + DB Exception -> ERROR
ExpectedError + matching Exception -> PASS
ExpectedError + wrong code -> FAIL
ExpectedError + no exception -> FAIL
```

---

## N2. P0：Runner 绕过所有 Core Contract / Parser / Compiler

当前路径：

```text
YAML
→ load_yaml()
→ dict.get()
→ XuguSession
```

而正式设计是：

```text
DSL
→ Decoder
→ Parser
→ Metadata Resolver
→ UnifiedCase
→ Compiler
→ Catalog
→ Selector
→ Manifest
→ Bundle
→ Runner
```

### 风险

形成两套世界：

```text
Core Contract：严格
Diagnostic Runner：宽松
```

### 修正方案

短期：

```text
BootstrapCaseInput.model_validate(raw)
```

正式：

```text
Runner 只接受 UnifiedCase / CompiledCase
```

后续正式执行只接受：

```text
Manifest + Bundle 中的 Compiled Case
```

当前 `cases/mvp/*.yaml` 必须明确标注为 Bootstrap Asset，而不是正式 Test Asset。

---

## N3. P0：Comparator 完全绕过 XGC1 Canonical

当前 SQL Rows Hash 使用：

```text
json.dumps(..., default=str)
→ SHA256
```

这与已有：

```text
CanonicalCell
XGC1
typed framing
```

构成第二套 Canonical 实现。

### 风险 1：逻辑类型丢失

例如：

```text
Decimal("1.0")
"1.0"
date(...)
datetime(...)
bytes(...)
```

可能全部被 `default=str` 转换。

### 风险 2：Hash 与正式 Contract 不一致

测试资产 Expected Hash 和 Runner Actual Hash 可能使用不同算法。

### 风险 3：rowsort 不稳定

当前直接：

```python
sorted(actual)
```

混合：

```text
None
int
str
Decimal
```

可能直接抛 `TypeError`。

### 修正方案

唯一主链：

```text
Driver Value
→ Runtime Type Mapping
→ CanonicalCell
→ XGC1
```

Exact：

```text
Canonical Row Frame 按原顺序比较
```

RowSort：

```text
Canonical Row Frame bytes 排序
```

Hash：

```text
XGC1 stream
→ SHA256
```

删除 SQL Result Hash 中 `json.dumps(default=str)` 方案。

---

## N4. P0：Runtime Profile ID 当前不是稳定语义身份

### 当前实现

```text
evidence_hash = SHA256(整个 Probe Evidence)
profile_body 包含 evidence_sha256
profile_id = SHA256(profile_body)
```

但 Probe Evidence 中包含：

```text
started_at
finished_at
随机 table 名
运行期字段
```

因此同一个环境重复 Probe 两次，也可能产生不同 `sql_runtime_profile_id`。

### 问题本质

Profile ID 应表示：

```text
Runtime Semantics Identity
```

而不是：

```text
某次 Probe Run Identity
```

### 修正方案

拆分：

```text
ProbeEvidence
RuntimeProfile
```

ProbeEvidence 可以包含时间、随机表名、Artifact 等运行期数据。

Runtime Profile Identity Projection 只包含：

```text
profile_schema_version
contract_set_id
db exact build
driver exact version
os
arch
mode
configuration fingerprint
type mapping
error mapping
cancel semantics
reset/probe semantics
capability limitations
```

然后：

```text
XGMJ1(ProfileIdentityProjection)
→ SHA256
→ sql_runtime_profile_id
```

`evidence_sha256` 只用于审计，不参与 Profile ID。

---

## N5. P0：Runtime Profile 把物理 Host 上下文混入语义身份

当前 Profile target 保留：

```text
host_hash
database_alias
```

这属于 Environment Evidence，不属于 Runtime Semantic Identity。

### 风险

同版本、同配置的 Cluster A / Cluster B 可能只因为 Host 不同就产生不同 Profile ID，破坏：

```text
Target / Environment 分离
```

### 修正方案

Runtime Profile 分：

```text
identity
evidence_context
```

identity：

```text
DB build
Driver
OS/arch
mode
configuration fingerprint
mapping/cancel/reset semantics
```

evidence_context：

```text
environment_id
host_hash（如必须）
database_alias
probe_run_id
```

后者不进入 `sql_runtime_profile_id`。

---

## N6. P0 Bug：`xgtest registry validate` 可能无法序列化 `RegistryEntry`

当前 Registry 值已经是：

```text
tuple[RegistryEntry]
```

CLI 却直接：

```text
json.dumps(list(values))
```

标准 JSON 不会自动序列化 dataclass。

### 可能结果

```text
TypeError: Object of type RegistryEntry is not JSON serializable
```

### 修正方案

显式：

```python
[
    {"key": entry.key, **entry.metadata}
    for entry in entries
]
```

或者给 Registry 提供 `to_dict()`。

### 验收标准

CI 必须真实执行：

```bash
xgtest registry validate
```

而不是只通过 Loader 单测间接验证。

---

## N7. P0：Setup / Main / Cleanup 没有真正分阶段执行

当前 Runner 把：

```text
setup
statement
query
cleanup
```

放在同一个循环中。

异常被捕获后继续执行下一 Step。

### 问题场景

```text
setup_left FAIL
↓
insert_left 继续执行
↓
query 继续执行
↓
制造级联错误
↓
cleanup
```

### 正确语义

```text
Prepare
↓
Setup
    失败 -> Main 不执行
↓
Main
↓
Cleanup（无论 Main 成败都执行）
↓
Reset
↓
Probe
```

### 修正方案

至少拆：

```text
run_setup()
run_main()
run_cleanup()
```

Cleanup 必须进入独立 finally 生命周期。

### 必测

```text
Setup FAIL -> Main 不执行，Cleanup 执行
Main FAIL -> Cleanup 执行
Cleanup FAIL -> primary_status 保留 + cleanup failure 单独记录
```

---

# 7. 最新代码中新发现的 P1 问题

## N8. P1：`XuguSession.reset()` 名称具有误导性

当前：

```text
reset() = rollback()
```

完整 Reset 应包含事务、autocommit、isolation、schema、role、timezone、session parameter、temp object、prepared handle、cursor、lock 等。

### 修正方案

当前先改名为：

```text
rollback_transaction()
```

只有 A-06 验证完成后才提供真正 `reset()` / `probe()`。

不能证明 clean 时销毁连接。

---

## N9. P1：Query 使用 `fetchall()`，与大结果目标冲突

当前：

```text
cursor.fetchall()
→ tuple(rows)
```

MVP 小数据没问题，但不能固化成正式 Adapter API。

### 修正方案

正式 Query API 支持：

```text
fetchmany(batch_size)
row iterator
streaming canonicalizer
incremental hash
external rowsort
```

---

## N10. P1：当前 MVP YAML Case 不是正式 XGT DSL

新增的：

```text
cases/mvp/join.yaml
union.yaml
ddl_table.yaml
string_function.yaml
```

非常适合作为纵向验证资产，但正式 SQL DSL 是 `.xgt`。

### 风险

YAML Runner 越完善，后续越容易偏离正式 XGT 设计。

### 修正方案

把这些文件明确标为：

```text
bootstrap / diagnostic assets
```

建议放：

```text
framework_tests/integration/assets/sql_mvp/
```

或：

```text
cases/bootstrap/
```

正式资产继续使用：

```text
tests/query/.../*.xgt
```

---

## N11. P1：MVP Report 又硬编码了一套 Status

Core 已有：

```text
StepStatus
CaseExecutionStatus
AttemptStatus
```

但 MVP Report 又用：

```text
Literal["PASS", "FAIL", "ERROR"]
```

### 修正方案

统一使用 Registry Enum。

并补：

```text
RunStatus Registry
```

不要形成第二套状态源。

---

## N12. P1：MVP Run Report 的 Target 又退化成自由 Dict

正式 `Target` 已经结构化，但 `MvpRunReport` 又定义：

```text
target: dict[str, str]
```

### 修正方案

改用：

```text
TargetSnapshot
```

或最小：

```text
TargetRef:
  target_id
  sql_runtime_profile_id
  environment_id
```

---

## N13. P1：Runnable Path 没有 Manifest / Bundle / Source Drift Protection

当前：

```text
glob *.yaml
→ 读取当前文件
→ 执行
```

选例和真正执行之间没有 Freeze。

### 修正方案

当前 CLI 建议明确叫：

```text
xgtest bootstrap-run
```

正式 `xgtest run` 留给：

```text
Plan
→ Manifest
→ Bundle
→ Verify Hash
→ Execute
```

---

## N14. P1：Run ID 仅由开始时间 Hash 截断生成

当前类似：

```text
SHA256(started_at)[:16]
```

作为 Diagnostic ID 可以，但不应成为正式 Run Identity。

### 修正方案

推荐：

```text
UUIDv7
```

或 ULID。

`manifest_hash` 作为单独的不可变输入身份，不能与 Run ID 混用。

---

## N15. P1：PASS Report 保存全部 Rows，不符合长期规模目标

当前 Report 直接存：

```text
rows
columns
column_types
```

### 修正方案

正式模式默认：

PASS：

```text
row_count
result_hash
duration
status
```

FAIL 才保存：

```text
expected
actual sample
diff
artifact URI
```

大结果必须落 Artifact，不塞主 JSONL/Event。

---

## N16. P1：Column Type 只是 `str(driver_type)`，不是 Logical Type

当前直接把 Driver `cursor.description` type code 转字符串。

### 修正方案

增加：

```text
DriverColumnMetadata
→ Runtime Profile Type Mapper
→ LogicalType
```

Comparator 只理解 Logical Type，不理解 Xugu Driver Type Code。

---

## N17. P1：Error Message 尚缺统一脱敏

`extract_error()` 会直接返回 `str(error)`，Runner 再直接写 Report。

数据库错误有可能包含：

```text
SQL
对象名
路径
参数
连接信息
```

### 修正方案

增加统一：

```text
ErrorRedactor
```

在进入：

```text
ResultEvent
Artifact
Report
Log
```

前脱敏。

---

## N18. P1：无盐 `host_hash` 可被枚举反查

与 Probe 隐私问题一致。

优先不要保存 Host；需要关联时使用：

```text
HMAC-SHA256(environment_secret, host)
```

---

# 8. Runtime Profile 专项优化方案

Runtime Profile 是最新提交的重点，建议现在就收口。

## 8.1 建立正式 Pydantic Model

建议定义：

```text
SQLRuntimeProfile
RuntimeTargetIdentity
DriverIdentity
TypeMappingProfile
ErrorMappingProfile
CancelProfile
ResetProfile
CapabilityProfile
EvidenceRef
```

不要长期用自由 `dict[str, Any]`。

---

## 8.2 Profile ID 使用稳定 Identity Projection

推荐：

```text
SQLRuntimeProfile
→ identity_projection()
→ XGMJ1
→ SHA-256
→ sql_runtime_profile_id
```

不得将以下字段加入身份：

```text
started_at
finished_at
random table
artifact path
probe run id
physical host
```

---

## 8.3 Evidence Hash 与 Profile ID 分离

推荐模型：

```text
Runtime Profile
  ├── sql_runtime_profile_id
  └── evidence_refs[]
        ├── evidence_sha256
        ├── probe_run_id
        └── timestamp
```

同一个 Profile 可以拥有多次 Probe Evidence。

---

## 8.4 Profile 绑定 Contract Set

至少记录：

```text
core_contract_set_id
canonical_version
probe_version
profile_schema_version
```

避免旧 Profile 被错误复用于新 Contract。

---

# 9. Comparator 专项重构方案

目标接口建议改成：

```text
compare(
    actual: CanonicalResult,
    expected: TypedExpected,
    profile: ComparisonProfile
) -> ValidationResult
```

不要继续使用：

```text
compare_rows(list, Any, mode)
compare_error(Exception, Any)
```

## Exact

```text
Driver Rows
→ Canonical Cells
→ XGC1 Row Frames
→ 顺序比较
```

## RowSort

```text
Canonical Row Frame
→ bytes lexical sort
→ compare
```

## Hash

```text
XGC1 Canonical Stream
→ SHA256
```

## Expected Error

只有 `ExpectedError` 才能进入 Error Comparator。

返回值建议从 `bool` 升级为：

```text
ValidationResult:
  matched
  reason_code
  expected_summary
  actual_summary
```

方便 Result / Allure / Debug。

---

# 10. 当前推荐修正顺序

## 第一批：必须马上修

```text
1. N1：修复普通 SQL Exception 被误判 PASS
2. N6：修复 registry validate 的 RegistryEntry JSON 序列化
3. N3：Comparator 接入 Canonical/XGC1
4. N2：Runner 至少通过 Typed Bootstrap Model
5. N7：拆 Setup / Main / Cleanup 生命周期
6. N4/N5：重做 Runtime Profile Identity Projection
```

---

## 第二批：G0A / 第一条可信 JOIN 前完成

```text
7. Core Model 剩余字段和 Enum 收口
8. YAML Golden Vector 补齐
9. Canonical Golden Vector 补齐
10. Temporal 真正语义校验
11. Runtime Profile Pydantic Model
12. Target/Profile Identity 使用 XGMJ1
13. Mvp Report Status/Target 去双真源
```

---

## 第三批：Phase 1 正式 Runner 前完成

```text
14. Manifest / Bundle / Source Drift
15. Adapter Logical Type Mapping
16. Reset / Probe
17. Timeout / Cancel / Stop Proof
18. Streaming fetchmany / incremental hash
19. Error Redaction
20. PASS Report 极简化
21. Real Xugu Integration CI
```

---

# 11. 建议当前工作包状态

| 工作包 | 建议状态 |
|---|---|
| P0A-02 工程骨架 | ✅ ACCEPTED |
| P0A-03 Registry | 🟡 接近 ACCEPTED |
| P0A-04 Core Model | 🟡 IN_PROGRESS |
| P0A-05 Schema / Validation | 🟡 接近 ACCEPTED |
| P0A-06 Golden Vector | 🟡 IN_PROGRESS |
| G0A Core Contract Gate | 🟡 NOT READY |
| A-01 Environment / Driver | 🟡 IN_PROGRESS |
| A-02 Type Mapping | 🟡 IN_PROGRESS |
| A-03 Transaction | ✅ 基础 Probe 已具备 |
| A-04 Error Mapping | 🟡 IN_PROGRESS |
| A-05 Cancel / Stop Proof | ❌ UNKNOWN |
| A-06 Reset / Probe | ❌ UNKNOWN |
| A-07 Runtime Profile | 🟡 IN_PROGRESS |
| P1 Diagnostic Runner | 🟡 已有 Bootstrap 实现 |
| P1 Formal Runner | ❌ 尚未成立 |
| P1 Comparator | 🟡 已有初版，但需 Canonical 重构 |

---

# 12. G0A 是否可以冻结

当前仍不建议立刻 Freeze。

主要阻塞已经不是“模型数量太少”，而是以下契约一致性问题：

```text
Runner 绕过 Model
Comparator 绕过 Canonical
Runtime Profile ID 不稳定
Registry Validate 存在具体实现 Bug
```

G0A Freeze 前建议最低要求：

```text
[ ] Registry validate 可真实执行
[ ] Core Model / Registry Enum 一致
[ ] YAML 核心 Vector 稳定
[ ] XGMJ1 / XGC1 Vector 稳定
[ ] Comparator 不再维护第二套 Canonical
[ ] Runtime Profile Identity Projection 固定
```

---

# 13. 对当前 Bootstrap Runner 的定位建议

当前 Runner 很有价值，因为它能快速验证：

```text
Driver
真实数据库
SQL
Expected
Report
```

不要删除。

但建议明确定位：

```text
Bootstrap / Diagnostic Runner
```

它的目的：

```text
提前发现 Driver / DB / Oracle 问题
```

而不是代替正式 XG DB Test Runner。

正式 Runner 仍应遵循：

```text
XGT
→ Parse
→ Compile
→ Catalog
→ Select
→ Manifest
→ Bundle
→ Resource Admission
→ Execute
→ Canonical Validate
→ Cleanup
→ Reset
→ Probe
→ Result Event
```

---

# 14. 最终判断

本轮已经有大量问题被正确修复，特别是：

```text
Registry
Core Model
Target
ResultEvent
Schema
DECIMAL Probe
Transaction Probe
YAML Resolver
```

当前最需要防止的是：

> **为了尽快得到“能跑 SQL”的 MVP，在正式架构旁边形成一条永久存在的简化执行链。**

下一阶段应把 Bootstrap Runner 中验证有效的能力逐步接回正式架构：

```text
Typed Contract
Canonical
Runtime Profile
Manifest
Result Model
```

而不是继续让：

```text
raw YAML dict
JSON default=str hash
自由 dict Profile
```

扩散。

先处理本文件列出的 P0 问题，再继续 Parser / Compiler / Catalog，会显著降低后续多 Agent 并行开发的返工成本。
