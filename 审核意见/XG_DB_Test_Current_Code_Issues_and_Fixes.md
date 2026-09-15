# XG DB Test 当前代码实现问题与修正方案清单

> 评审对象：`xunyuxingkong/allone` 当前 `main` 分支最新提交  
> 最新提交：`3d0f71a333a856bfc51808c668998ea3e2303006`  
> 提交说明：`feat: add contract framework and Xugu adapter probes`  
> 评审日期：2026-09-15  
> 目的：汇总当前已提交代码中需要修正、补齐或继续收口的问题，并明确每项问题的原因、风险、修正方案、优先级和验收标准。

---

## 1. 总体结论

当前实现方向正确，已经开始落地：

```text
Python 工程骨架
Registry
Pydantic Strict Core Model
JSON Schema 导出
XGMJ1 / XGC1 Canonical 编码
framework_tests
Xugu Adapter Smoke Probe
Xugu Capability Probe
CI Contract Verification
```

但现在还不适合直接大规模推进 Parser / Compiler / Catalog / Runner。原因是最底层的：

```text
Core Model
Registry
YAML Decoder
Canonical Contract
Schema 生成
Xugu Probe
```

仍有一些基础契约问题。如果不先修正，后续模块会建立在不稳定模型上，容易形成较大的契约债务和返工。

优先级约定：

```text
P0：进入 Parser / Compiler / Catalog 之前必须修正
P1：Phase 1 早期必须修正
P2：可以稍后补齐，但 G1 前必须解决
```

---

# 2. P0：Core Model 与正式 SQL MVP 契约不完整

## 当前问题

`src/xgtest/core/models.py` 已经定义：

```text
RawMetadata
EffectiveMetadata
UnifiedCase
Target
ResourceRequest
TestPlan
Manifest
Run
CaseExecution
Attempt
StepResult
ArtifactRef
ResultEvent
```

方向正确，但目前多数还是最小骨架。

例如 `EffectiveMetadata` 只有：

```text
id
title
module
feature
level
status
tags
timeout
isolation
destructive
```

而正式设计中 SQL MVP 还需要考虑：

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
fixtures
source
oracle
issue
owner
since
until
generated_by
disabled_reason
replaced_by
```

Case Lifecycle 里也缺少 `generated` 等正式状态。

## 原因与风险

如果现在直接继续实现 Parser / Compiler / Catalog：

```text
当前简化模型
→ Parser
→ Compiler
→ Catalog Schema
```

后续补字段会导致：

```text
Parser Header 重构
Metadata Resolver 重构
Catalog Schema 变更
Compiler Hash 输入变化
Manifest 内容变化
Coverage / Review 逻辑变化
```

这属于典型的基础契约返工。

## 修正方案

建议将 Core Model 按职责拆分：

```text
src/xgtest/core/models/

asset.py
planning.py
execution.py
result.py
coverage.py
resource.py
```

SQL MVP 至少先完整定义：

### Asset / Case

```text
RawMetadata
EffectiveMetadata
SourceInfo
UnifiedCase
SqlStep
QueryStep
FixtureRef
CoverageClaim
CoverageReview
ComparisonProfile
```

### Planning

```text
TestPlan
Target
EnvironmentRequirement
ExpectedExecution
Manifest
BundleRef
```

### Execution

```text
Run
CaseExecution
Attempt
StepResult
```

### Resource

```text
ResourceRequest
ResourceIdentity
ResourceScope
AccessMode
```

### Result

```text
ResultEvent
ArtifactRef
```

不要求所有业务逻辑在 Phase 0 就实现，但结构和语义应先统一。

## 验收标准

- SQL MVP 所需共享字段全部进入 Core Model；
- Parser / Compiler / Catalog 不再自行创建 DTO；
- 字段语义与 Metadata 设计一致；
- Lifecycle 状态统一从 Registry 获取；
- 不使用 `dict[str, Any]` 充当关键业务对象。

当前建议状态：

```text
P0A-04 Core Model = IN_PROGRESS
```

---

# 3. P0：ResultEvent 模型过于简化

## 当前实现

```text
attempt_id
producer_epoch
sequence
event_type
payload
```

## 问题

正式 Result Event 至少要能表达：

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

其中部分字段 Phase 4 才真正强制，但模型应提前区分：

```text
Core Event Identity
Distributed Extension
```

## 风险

后续很容易演变成：

```text
Phase1ResultEvent
Phase4AgentResultEvent
```

两套事件协议，从而导致 Result Store、Event Replay、Projection、Retry 都需要兼容两套模型。

## 修正方案

现在就定义完整结构，允许分布式字段在 Phase 1 可选：

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

Phase 1：

```text
assignment_epoch = null
fencing_token = null
environment_id = local environment id
```

Phase 4 再提高约束。

## 验收标准

- Event 有稳定唯一身份；
- 可进行幂等去重；
- 可按 sequence 重放；
- Late Event 可准确定位 Attempt；
- Phase 4 无需重新定义事件格式。

---

# 4. P0：Target 模型过于简化

## 当前实现

```text
target_id
db_build
driver_version
sql_runtime_profile_id
```

## 问题

Target 表示的是“逻辑测试目标”，不是一个普通连接配置。

建议至少包含：

```text
database product/version/build
driver name/version
os
arch
topology
mode
configuration fingerprint
dataset fingerprint
sql_runtime_profile_id
```

## 风险

Target 信息不足时：

```text
Baseline
Matrix
Retry Migration
Environment Matching
Delta
```

都无法可靠判断两个执行环境是否属于同一个逻辑目标。

## 修正方案

定义结构化 Target Snapshot，并由稳定 Identity Projection 生成 `target_id`，不要让 `target_id` 只是任意字符串。

---

# 5. P0：Manifest 当前只能算骨架，不能冻结为正式 Manifest 1

## 当前实现

```text
run_id
contract_set_id
plan
bundles
```

## 缺失

正式 Manifest 仍需要：

```text
git_commit
dirty
source_snapshot_hash
catalog_snapshot_id
plan_hash
case_entries
target_entries
expected_executions
runtime_versions
bundle dependency list
```

## 风险

现在就冻结 Manifest 1，后面必然产生协议变更。

## 修正方案

当前结构暂时视为：

```text
ManifestCore
```

只有当 XGMJ1 Identity Projection、Target Entry、Case Entry、Runtime Version 等都落地后，再冻结正式 Manifest 1。

---

# 6. P0：Python 3.14 锁定过早

## 当前实现

`pyproject.toml`：

```toml
requires-python = ">=3.14,<3.15"
```

CI：

```yaml
python-version: "3.14"
```

## 问题

目前没有正式证据证明真实 `xgcondb` Driver 对 Python 3.14 支持稳定。

现有 Adapter 测试使用 monkeypatch 模拟 `xgcondb`，不能证明真实 Driver 可用。

## 风险

可能出现：

```text
Framework CI PASS
真实 xgcondb 在 Python 3.14 无法导入/运行
```

最终整个工程环境被迫回退。

## 修正方案

先建立：

```text
Python 3.11
Python 3.12
Python 3.13
Python 3.14
```

与真实 Driver 的兼容矩阵，至少验证：

```text
import xgcondb
connect
cursor
SELECT 1
basic type read
transaction
```

再冻结正式 Python 范围。

---

# 7. P0：YAML Loader 还不是真正完整的 YAML 1.2 Core

## 当前实现

已经处理：

```text
on/off 不再当 bool
true/false 正常解析
duplicate key reject
```

这是正确的。

## 问题

当前仍复制 PyYAML SafeLoader 的其他 resolver，因此可能保留部分 YAML 1.1 数字解析行为。

需要重点测试：

```yaml
a: 0123
b: 0o123
c: 0x10
d: .inf
e: -.inf
f: .nan
g: 1_000
```

## 风险

不同语言、不同 Loader 对相同 Metadata 产生不同解析结果。

## 修正方案

建立：

```text
framework_tests/contract/yaml/
```

Golden Vector，覆盖：

```text
bool
null
integer
octal
hex
float
scientific
inf/nan
timestamp-looking scalar
on/off/yes/no
unicode
duplicate key
nested duplicate key
```

不能只靠修几个 PyYAML Resolver 来近似 YAML 1.2 Core。

---

# 8. P0：Registry Enum 生成存在成员名碰撞风险

## 当前实现

```python
key.upper().replace(".", "_").replace("-", "_")
```

## 问题

例如：

```text
a-b
a_b
a.b
```

都会生成：

```text
A_B
```

## 修正方案

Enum 生成前建立：

```text
normalized_member_name -> original key
```

映射。

发现冲突直接：

```text
REGISTRY_ENUM_NAME_COLLISION
```

失败。

---

# 9. P0：Registry 只保留 key，其他元信息被静默丢弃

## 当前问题

YAML 已经出现：

```yaml
- key: sql.execute
  phase: sql_mvp
```

但加载器只留下：

```text
sql.execute
```

`phase` 被丢弃。

## 风险

Registry 无法真正成为 Single Source of Truth。

后续可能需要：

```text
phase
description
category
introduced_version
deprecated_version
retry_policy
resource_scope
owner
```

## 修正方案

定义：

```python
RegistryEntry
```

包含：

```text
key
phase
description
metadata
```

Registry 保存 Entry，而不是 tuple[str]。

Enum 生成只读取 `entry.key`。

---

# 10. P0：Registry 与 Pydantic Literal 形成双真源

## 当前问题

模型中：

```python
status: Literal["draft", "review", "active", ...]
```

同时 Registry 里也维护状态。

## 风险

Registry 新增状态，例如：

```text
generated
```

但模型 Literal 忘记同步，就出现两套定义。

## 修正方案

模型直接使用生成 Enum：

```python
status: CaseAssetStatus
level: Level
isolation: IsolationScope
```

同样适用于：

```text
FailureType
ResourceAccessMode
Capability
```

---

# 11. P0：Schema Export 无法发现 stale schema

## 当前流程

```bash
xgtest schema export
git diff --exit-code -- schemas
```

## 问题

如果一个 Model 已从 `MODEL_EXPORTS` 删除，旧的：

```text
OldModel.schema.json
```

仍会留在目录中，export 不会删除，Git Diff 也可能仍然干净。

## 修正方案

推荐：

```text
生成到临时空目录
→ 比较文件集合
→ 比较文件内容
```

或者清理所有 generator-managed schema 后重新生成。

---

# 12. P0：Schema 缺少稳定契约身份

## 问题

当前自动导出的 Schema 缺少明确：

```text
$id
schema version
contract version
```

## 修正方案

生成时注入类似：

```json
{
  "$id": "xgtest://schema/1.1/EffectiveMetadata",
  "x-xg-contract-version": "1.1"
}
```

并在 Core Contract Descriptor 中记录：

```text
schema file
sha256
contract_set_id
```

---

# 13. P1：DECIMAL Probe 被硬编码为 FAILED

## 当前问题

Capability Probe 中 decimal 状态直接写死为 FAILED，而不是根据 Driver 实际返回类型判断。

## 风险

未来 Driver 行为改变后，Probe 仍会输出旧结论。

## 修正方案

按真实值判断：

```text
Decimal -> VERIFIED
float -> LOSSY/FAILED
other -> UNKNOWN/FAILED
```

最好拆：

```text
operation_status
mapping_status
canonical_compatibility
```

---

# 14. P1：事务可见性 Probe 可能受 observer 自身事务快照污染

## 当前逻辑

同一个 `second_connection` 先验证 rollback，再继续验证 commit。

## 风险

第一次 SELECT 可能已经建立事务快照，第二次 SELECT 看不到主连接刚提交的数据。

此时：

```text
commit_visible_count == 0
```

并不能证明主连接 COMMIT 失败。

## 修正方案

每次 visibility check 使用 fresh observer connection，或显式重置 observer transaction。

推荐封装：

```text
fresh_count(...)
```

每次新连接进行验证。

---

# 15. P1：Extended Type Probe 的 VERIFIED 语义过宽

## 当前逻辑

只要：

```text
INSERT 成功
SELECT 成功
```

就标记 VERIFIED。

## 问题

SQL 操作成功和 Driver Mapping 正确不是一回事。

例如：

```text
DATE 输入 date
返回 str
```

不能直接认为满足 Canonical 要求。

## 修正方案

拆成：

```text
operation_status
mapping_status
canonical_compatibility
```

mapping 可以使用：

```text
EXACT
LOSSY
STRINGIFIED
UNSUPPORTED
UNKNOWN
```

---

# 16. P1：Probe Artifact 默认包含 host / port / database

## 风险

Artifacts 如果被上传到 CI 或共享位置，会暴露内部网络和数据库命名信息。

## 修正方案

默认 Artifact 建议只保存：

```text
environment_id
target_ref
host_hash
database_alias
```

完整连接信息仅允许本地 debug 模式。

---

# 17. P1：Canonical Golden Vector 覆盖不足

当前测试只覆盖很少的 Canonical 情况。

至少补充：

```text
int +0/-0
大整数
Decimal 1/1.0/1.00
Decimal exponent
极小 Decimal
float +0/-0
多种 NaN payload
+Inf/-Inf
空字符串
尾空格
Unicode
bytes 00/FF
NULL vs "NULL"
重复行
空结果
零列/零行
date/time/timestamp
timestamp_tz
```

---

# 18. P1：date/time/timestamp 当前只检查 str，不检查语义格式

## 当前问题

`date/time/timestamp/timestamp_tz` 只要求 Python 类型是 `str`。

因此：

```text
"abc"
"yesterday"
```

也可能被编码。

## 修正方案

明确 Canonical 格式：

```text
date        YYYY-MM-DD
time        HH:MM:SS[.fraction]
timestamp   YYYY-MM-DDTHH:MM:SS[.fraction]
timestamp_tz 明确统一 offset/UTC canonical rule
```

并严格验证。

---

# 19. P1：Float NaN / ±0 需要完整跨平台 Golden Vector

当前 NaN 统一为固定 bit pattern，方向正确。

需要增加：

```text
多个 NaN payload -> 同一 Canonical NaN
+0.0
-0.0
```

确保不同平台结果完全一致。

---

# 20. P1：ComparisonProfile 过于简化

当前：

```text
mode
canonical_version
```

后续还需要承载：

```text
error profile
normalization profile
float policy
timestamp policy
error code/sqlstate/message rule
resource limit
```

建议现在就预留结构，避免未来完全替换模型。

---

# 21. P1：SqlStep.expected 使用 Any 过宽

## 当前问题

```python
expected: Any | None
```

使 Expected 基本没有 Schema 约束。

## 修正方案

尽早定义类型化 Expected：

```text
ExpectedRows
ExpectedHash
ExpectedError
ExpectedStatement
```

这也与 XGT Typed Expected 设计一致。

---

# 22. P1：ResourceRequest access_mode 不完整

当前只有：

```text
shared_read
exclusive
```

资源模型后续至少需要：

```text
read
write
exclusive
```

或：

```text
shared_read
shared_write
exclusive
```

必须与 Resource Conflict Matrix 保持一致。

---

# 23. P1：ResourceRequest 缺 resource_type / impact_scope

当前：

```text
resource_id
scope
access_mode
capacity
```

建议补：

```text
resource_type
resource_id
access_mode
quantity
impact_scope
parent/ancestor identity
```

否则 Admission 逻辑无法准确表达父子资源冲突。

---

# 24. P1：Generated Enum 类名可读性一般

自动生成：

```text
StatusesCaseAsset
Capabilities
Features
```

能工作，但业务代码可读性较差。

建议建立 Registry 名称到 Enum Class Name 的显式映射：

```text
CaseAssetStatus
AttemptStatus
RunStatus
FeatureKey
CapabilityKey
FailureType
IsolationScope
ResourceAccessMode
```

---

# 25. P1：ContractError 还需要 SourceSpan / details

当前：

```text
code
path
message
```

方向正确。

后续 Parser/Compiler 错误还应该支持：

```text
source file
line
column
field path
details
cause
```

否则真实 DSL 报错定位体验会较差。

---

# 26. P1：当前 Xugu Adapter 只能算 connection bootstrap

现在主要是：

```text
connect
smoke_probe
```

不能把 A-07 视为完成。

真正最小 Adapter 仍需：

```text
execute
query/fetchmany
begin
commit
rollback
autocommit
column metadata
error extraction
cancel
reset
probe
close
```

---

# 27. P1：Capability Probe 应生成 Runtime Profile，而不只是孤立 JSON

建议流程：

```text
Raw Probe Evidence
        ↓
Profile Builder
        ↓
SQLRuntimeProfile
```

将“观察结果”和“正式能力判定”分开。

这样可保留原始证据，又可以通过规则/人工审查形成正式 Profile。

---

# 28. P1：Probe 缺少完整 Profile Identity 信息

Runtime Profile 应至少绑定：

```text
DB exact build
Driver version
OS
arch
compatibility mode
关键配置
```

当前报告信息还不足以成为正式 Runtime Profile Identity。

---

# 29. P1：CI 需要区分 Contract CI 与 Real Xugu Integration CI

公共/普通 CI 可以继续只做：

```text
pytest
registry
schema generation
contract vectors
```

另外增加内网/本地真实环境任务：

```text
pytest -m xugu_integration
```

两者不能混为一谈。

Mock Adapter PASS 不能作为真实 Xugu 能力 VERIFIED 的证据。

---

# 30. P1：厂商 Driver ZIP 不建议长期放 Git

当前仓库包含 Driver ZIP。

长期建议迁移到：

```text
Nexus
Artifactory
MinIO
内部 Package Registry
```

Git 中只保存：

```text
driver version
sha256
artifact_ref
install script
```

这样更适合版本治理，也避免仓库膨胀和分发边界问题。

---

# 31. P1：requirements.lock 需要正式可复现生成机制

应明确使用：

```text
uv lock
pip-tools
poetry lock
```

等一种正式方式。

不要把普通 `pip freeze` 结果长期当完整可复现锁文件。

---

# 32. P2：当前 Contract Test 数量不足，不足以 G0A Freeze

目前测试主要覆盖：

```text
unknown field
strict bool
Registry deterministic
duplicate YAML key
on/off
一个 XGMJ1 Hash
基础 XGC1 frame
Xugu smoke mock
```

G0A 前至少补：

### Registry

```text
duplicate registry key
unknown registry
enum name collision
malformed entry
metadata preservation
```

### YAML

```text
nested duplicate
octal/hex
float
nan/inf
timestamp-looking scalar
null
boolean
```

### Core Model

```text
invalid id
invalid timeout
missing required
invalid lifecycle
target identity
resource identity
manifest identity
```

### Canonical

按前述完整 Golden Vector 补齐。

---

# 33. 推荐修正顺序

建议下一阶段按下面顺序，而不是直接开始 Parser：

```text
1. Registry 真正成为单一事实源
2. Core Model 补全
3. Pydantic Literal 改用 Registry Enum
4. YAML 1.2 Core 行为校准
5. Schema stale 检查
6. Schema 契约身份
7. Canonical Golden Vector 补齐
8. 修 DECIMAL Probe
9. 修事务 observer Probe
10. Extended Type Probe 状态拆分
11. Runtime Profile Builder
12. Python × Driver 兼容矩阵
13. G0A Review
14. 再进入 XGT Parser / Compiler / Catalog
```

---

# 34. 当前建议状态

| 工作包 | 当前建议状态 |
|---|---|
| P0A-02 工程骨架 | ACCEPTED / 接近 ACCEPTED |
| P0A-03 Registry | IN_PROGRESS |
| P0A-04 Core Model | IN_PROGRESS |
| P0A-05 Schema / Validation | IN_PROGRESS |
| P0A-06 Golden Vector | IN_PROGRESS |
| G0A | NOT READY |
| A-01 Xugu Environment | IN_PROGRESS |
| A-02 Type Probe | IN_PROGRESS |
| A-03 Transaction Probe | IN_PROGRESS |
| A-04 Error Probe | IN_PROGRESS |
| A-05 Cancel/Stop | NOT VERIFIED |
| A-06 Reset/Probe | NOT VERIFIED |
| A-07 Runtime Profile | NOT READY |

---

# 35. 下一提交最应该处理的 8 项

如果只看最优先事项：

```text
1. 补全 SQL MVP Core Model
2. 补全 ResultEvent / Target / Manifest 核心身份
3. Registry Entry 保存元数据 + Enum Collision 检查
4. 模型改用 Registry Enum，消除双真源
5. 校准完整 YAML 1.2 Core 行为
6. 修复 DECIMAL Probe 和事务可见性 Probe
7. Schema Export 增加 stale 检查与契约身份
8. 实测真实 xgcondb 的 Python 支持范围
```

---

# 36. 最终判断

当前代码最大的优点：

> 架构思想已经真正进入代码，而不是继续停留在设计文档。

当前最大的风险：

> Core Contract 还没稳定，就继续往 Parser / Compiler / Catalog 推进。

因此当前最合适的路线是：

```text
Registry / Core Model / YAML / Canonical / Probe 修稳
        ↓
完成 G0A
        ↓
冻结 Core Contract
        ↓
Parser / Compiler / Catalog
```

这样后续多个 Agent 并行开发时，基础接口不会频繁漂移，整体返工会明显减少。
