# XG DB Test 当前代码实现问题与修正方案清单（2026-09-16 最新整理版）

> 仓库：`xunyuxingkong/allone`  
> 当前 `main` 最新提交：`96b2f27eed5a047c17f1b37378b9a0d1e5b4bf13`  
> 最新提交：`docs: add audit fix history`  
> 本次代码修复区间：`242dd99d` → `96b2f27e`  
> 更新日期：2026-09-16  
> 目的：在上一版审核问题清单基础上，统一整理已经修复的问题、仍未完全解决的问题，以及本轮新发现的问题，并为每项给出原因、风险、优化修正方案和建议验收标准。

---

## 1. 总体结论

本轮修复质量总体较高。实际修复集中在：

```text
1ae2735  fix: close audit gaps in MVP execution path
23923d2  feat: add target and manifest identity projections
09d5317  feat: formalize runtime profile and streaming query types
5b59f53  feat: validate source bundles and type report targets
96b2f27  docs: add audit fix history
```

已经解决了上一版多数 P0 正确性问题，尤其包括：

```text
普通 SQL 异常误判 PASS
Bootstrap Runner 绕过 Typed Model
Comparator 绕过 XGC1
Setup/Main/Cleanup 混跑
Registry Entry 序列化
Target Identity
Plan/Manifest Identity
Runtime Profile ID 基础稳定化
Source / Bundle Drift Protection
MVP Report Target 类型化
Temporal 真实值校验
XuguSession reset 语义误导
```

当前整体状态可概括为：

```text
Phase 0A 接近冻结
+
Bootstrap / Diagnostic SQL MVP 可真实运行
+
正式 Phase 1 主链尚未完全接入
```

当前剩余问题主要集中在：

```text
少数协议边界
Runtime Profile Identity 最后收口
Comparator 类型解释重复
Expected 类型边界
正式 Manifest/Bundle 执行链尚未接入
Reset / Cancel / Stop Proof 未完成
```

整体修复质量评价：

```text
8.8 / 10
```

---

## 2. 状态说明

```text
✅ 已解决
🟡 部分解决 / 仍需收口
❌ 未解决
🆕 本轮新发现
```

优先级：

```text
P0：G0A Freeze 前建议修复
P1：Phase 1 早期必须处理
P2：G1 前处理
```

---

## 3. 已解决问题总览

| 编号 | 问题 | 当前状态 | 修复质量 |
|---|---|---:|---:|
| N1 | 普通 SQL 异常被误判为 PASS | ✅ 已解决 | 9.5/10 |
| N2 | Runner 绕过 Core Model | ✅ Bootstrap 路径已解决 | 9/10 |
| N3 | Comparator 绕过 XGC1 | ✅ 已解决 | 9/10 |
| N4 | Runtime Profile ID 被时间/随机表影响 | 🟡 基本解决 | 8/10 |
| N5 | Host 混入语义 Profile Identity | ✅ 基础问题已解决 | 9/10 |
| N6 | RegistryEntry 无法 JSON 序列化 | ✅ 已解决 | 10/10 |
| N7 | Setup/Main/Cleanup 同循环执行 | ✅ 已解决 | 9/10 |
| N8 | `reset()` 名称误导 | ✅ 已解决 | 10/10 |
| N11 | MVP Report 状态双真源 | ✅ 基本解决 | 9/10 |
| N12 | MVP Target 使用自由 Dict | ✅ 已解决 | 9/10 |
| N14 | Run ID 由时间 Hash 截断 | ✅ 已解决 | 10/10 |
| N17 | 错误信息未脱敏 | ✅ 基础解决 | 8.5/10 |
| O1 | Target Identity 缺稳定算法 | ✅ 已解决 | 9/10 |
| O2 | Plan / Manifest Identity 缺基础算法 | ✅ 已解决 | 8.5/10 |
| O3 | Runtime Profile 缺正式 Model | ✅ 基础解决 | 8/10 |
| O4 | Source / Bundle Drift 未校验 | ✅ 能力已实现 | 9/10 |
| O5 | Adapter 无 Logical Type Mapping | ✅ 基础解决 | 8.5/10 |
| O6 | Query 只有 fetchall | 🟡 已有 streaming 基础 | 7.5/10 |
| O7 | Temporal 只有 Regex 校验 | ✅ 已升级真实解析 | 9/10 |

---

## 4. ✅ 已解决：普通 SQL 异常误判 PASS

### 原问题

旧逻辑在任何 SQL Step 抛异常后都会调用 `compare_error()`，即使 Expected 是正常 Rows/Hash/Statement，也有机会被误判为 PASS。

### 当前修复

现在行为已经明确：

```text
ExpectedRows / ExpectedHash / ExpectedStatement + DB Exception -> ERROR
ExpectedError + matching exception -> PASS
ExpectedError + mismatch -> FAIL
ExpectedError + SQL 正常成功 -> FAIL
```

并通过 `is_expected_error()` 防止普通结果预期进入错误比较。

### 修复质量

```text
9.5 / 10
```

### 后续建议

继续补：

```text
ExpectedError(all None)
expected: {}
```

反向测试，详见新问题 N19。

---

## 5. ✅ 已解决：Bootstrap Runner 已接 Typed Core Model

旧路径：

```text
YAML -> dict.get() -> DB
```

已经改为：

```text
YAML
→ RawMetadata
→ EffectiveMetadata
→ SqlStep
→ ExpectedRows / ExpectedHash / ExpectedError / ExpectedStatement
→ BootstrapCaseInput
→ Runner
```

### 修复质量

```text
9 / 10
```

### 剩余边界

这只是 Bootstrap / Diagnostic Runner，正式链路仍应是：

```text
XGT
→ Parser
→ Compiler
→ Catalog
→ Manifest
→ Bundle
→ Runner
```

---

## 6. ✅ 已解决：Comparator 已统一使用 XGC1

旧实现：

```text
json.dumps(default=str)
→ SHA256
```

现在已经统一为：

```text
Driver Value
→ Logical Type
→ CanonicalCell
→ XGC1
→ Exact / RowSort / Hash
```

Rowsort 也改为按 Canonical Row Frame bytes 排序。

### 修复质量

```text
9 / 10
```

### 剩余问题

Comparator 仍维护一套 `_TYPE_HINTS`，存在 timestamp/time substring bug，详见 N18。

---

## 7. ✅ 已解决：Setup / Main / Cleanup 生命周期拆分

当前已经实现：

```text
Setup
↓
Main
↓
Cleanup
↓
Rollback Transaction
↓
Close
```

Setup 失败时：

```text
剩余 Setup -> SKIPPED
Main -> SKIPPED
Cleanup -> 仍执行
```

### 修复质量

```text
9 / 10
```

### 仍需补

正式 Result Core 阶段要显式保留：

```text
primary_status
cleanup_status
recovery_status
failure_type
```

---

## 8. ✅ 已解决：`reset()` 名称误导

当前：

```text
rollback_transaction()
```

只表达事务回滚。

完整：

```text
reset()
```

在未验证前直接抛 `NotImplementedError`。

### 修复质量

```text
10 / 10
```

---

## 9. ✅ 已解决：Target Identity

当前已经有：

```text
target_identity_projection()
compute_target_id()
validate_target_id()
```

算法：

```text
Target Semantic Fields
→ XGMJ1
→ SHA-256
→ target_id
```

并在模型构造时自动校验。

### 修复质量

```text
9 / 10
```

---

## 10. ✅ 已解决：Plan / Manifest 基础 Identity

当前已有：

```text
plan_identity_projection()
compute_plan_hash()
manifest_identity_projection()
compute_manifest_hash()
```

集合排序和 Identity Projection 基础已经具备。

### 修复质量

```text
8.5 / 10
```

### 剩余问题

正式 Runner 还没有强制走：

```text
Manifest
→ Bundle
→ Verify
→ Execute
```

---

## 11. ✅ 已解决：Source / Bundle Drift Protection 基础能力

当前已覆盖：

```text
SOURCE_PATH_OUTSIDE_ROOT
SOURCE_MISSING
SOURCE_DRIFT
BUNDLE_MISSING
BUNDLE_SIZE_MISMATCH
BUNDLE_DRIFT
```

### 修复质量

```text
能力实现：9 / 10
架构接入：4 / 10
```

原因是目前这些能力还没有被正式 Runner 强制调用。

---

## 12. ✅ 已解决：Temporal 从 Regex 升级为真实值校验

当前已经使用：

```text
date.fromisoformat()
time.fromisoformat()
datetime.fromisoformat()
```

并区分：

```text
timestamp -> timezone-naive
timestamp_tz -> 带时区
```

### 修复质量

```text
9 / 10
```

---

## 13. 🟡 部分解决：Runtime Profile Identity

### 已修复

当前已经排除很多明显运行期字段：

```text
started_at
finished_at
run_id
probe_run_id
random_table
host_hash
database_alias
artifact
duration
```

同时 Host/Database Alias 不再参与语义 Profile ID。

### 剩余风险

当前仍采用：

```text
完整 capabilities
→ 删除已知 runtime-only key
→ 剩余作为 identity
```

这是“黑名单式排除”。

如果某个随机值出现在字段值内部，例如错误消息：

```text
table XGT_CAP_A123_MISSING does not exist
```

第二次 Probe 变成：

```text
table XGT_CAP_B456_MISSING does not exist
```

那么 Profile ID 仍可能变化。

### 优化方案

改成严格白名单 Projection：

```text
RuntimeProfileIdentity
├── database_identity
├── driver_identity
├── platform
├── mode
├── configuration_fingerprint
├── type_mapping
├── transaction_semantics
├── error_mapping
├── cancel_semantics
└── reset_semantics
```

Error Mapping Identity 只保留稳定语义，例如：

```text
error code availability
sqlstate availability
exception category
stable error class
```

不要保留具体 message。

### 验收标准

同一 DB Build / Driver / 配置下：

```text
随机表名不同
时间不同
Host 不同
Probe Run ID 不同
错误消息中的对象名不同
```

必须得到相同 `sql_runtime_profile_id`。

---

## 14. 🟡 部分解决：RuntimeProfile 已有 Model，但内部仍过于自由

当前：

```python
identity: dict[str, Any]
target: dict[str, str]
driver: dict[str, Any]
```

只能验证 Envelope，无法约束内部语义。

### 优化方案

拆成：

```text
RuntimeProfile
RuntimeProfileIdentity
RuntimeTargetIdentity
RuntimeDriverIdentity
TypeMappingProfile
ErrorMappingProfile
CancelProfile
ResetProfile
EvidenceContext
```

至少在 G0A 前把 `RuntimeProfileIdentity` 结构化。

---

## 15. 🟡 部分解决：Streaming 基础能力已有，但正式 Runner 仍不是 Streaming

Adapter 已有：

```text
fetchmany()
iter_query_rows()
```

但 `query()` 仍会收集全部 rows，Runner 也继续使用 `query()`。

### 优化方案

正式 Runner：

```text
iter_query_rows()
→ Canonical Row Frame
→ Incremental Hash
```

Rowsort 则：

```text
bounded memory
→ temp file
→ external merge sort
```

---

## 16. 🟡 部分解决：MVP Report 状态仍有轻微双定义

Case/Run 已使用 Registry Enum，但 `MvpStepReport.status` 仍是 Literal。

### 优化方案

直接改为：

```python
status: StepStatus
```

避免后续状态 Registry 与 Literal 漂移。

---

## 17. 🟡 部分解决：Error Redaction

当前已能脱敏：

```text
password=
passwd=
pwd=
URL user:password@
```

### 剩余风险

还可能遗漏：

```text
token=
secret=
authorization=
JDBC-style properties
其他连接串格式
```

### 优化方案

抽成统一：

```text
SecretRedactor / ErrorRedactor
```

供：

```text
Log
Artifact
ResultEvent
Report
```

共同使用。

---

## 18. 🆕 P0：Comparator 存在 timestamp / time substring 类型映射 Bug

### 当前逻辑

Comparator 内部：

```python
_TYPE_HINTS = {
    "date": "date",
    "time": "time",
    "timestamp_tz": "timestamp_tz",
    "timestamptz": "timestamp_tz",
    "timestamp": "timestamp",
}
```

然后通过：

```python
if token in value:
```

判断。

### Bug

因为：

```text
"time" in "timestamp" == True
```

所以 `timestamp` / `timestamp_tz` 有可能被先判成 `time`。

### 为什么严重

会直接影响：

```text
Logical Type
XGC1 Header
Exact Compare
Hash
```

属于结果正确性问题。

### 最佳修正方案

Comparator 不应再次解释 Driver Type。

正式链应该只有：

```text
Adapter
→ Runtime Profile Type Mapping
→ Logical Type
→ Comparator
```

Comparator 只接收框架 Logical Type。

### 临时修法

如果短期必须保留 fallback：

```text
exact normalized type match
```

或最长 token 优先，不要 substring。

### 验收测试

```text
timestamp -> timestamp
timestamp_tz -> timestamp_tz
timestamptz -> timestamp_tz
time -> time
datetime -> timestamp
```

---

## 19. 🆕 P0：ExpectedError 空对象存在歧义

### 当前问题

`ExpectedError` 的：

```text
code
sqlstate
message_pattern
```

都允许 None。

因此：

```yaml
expected: {}
```

理论上可能被 Union 匹配成一个空的 `ExpectedError`。

### 风险

一旦被识别为 ExpectedError，任意数据库错误都有可能被错误当成“预期错误”。

### 修正方案

给 `ExpectedError` 增加 validator：

```text
code / sqlstate / message_pattern
至少一个非 None
```

`ExpectedStatement` 的 `affected_rows` 也应设为必填而不是可选 None。

### 长期方案

正式 DSL 使用明确 discriminator，例如：

```yaml
expected:
  kind: error
  code: E5021
```

### 验收测试

```text
expected: {} -> reject
ExpectedError(all None) -> reject
ExpectedStatement(None) -> reject
```

---

## 20. 🆕 P0：Runtime Profile Identity 应改为白名单 Projection

当前策略是：

```text
完整 Evidence
→ 删除若干 runtime-only 字段
→ 剩余作为 Identity
```

这属于黑名单式设计。

### 风险

未来 Probe 新增：

```text
sql_text
object_name
message
server_pid
session_id
elapsed
```

只要忘记加入黑名单，就会污染 Identity。

### 正确方案

只选择明确属于 Runtime Semantics 的字段：

```text
RuntimeProfileIdentity
├── profile_schema_version
├── contract_set_id
├── database_identity
├── driver_identity
├── platform
├── mode
├── configuration_fingerprint
├── type_mapping
├── transaction_semantics
├── error_mapping
├── cancel_semantics
└── reset_semantics
```

其余都属于 EvidenceContext。

---

## 21. 🟡 新发现：Cleanup Failure 没有显式保留 primary_status

正式设计要求：

```text
业务 FAIL
+
Cleanup FAIL
→ 最终 ERROR / FIXTURE_CLEANUP
```

但同时要保留：

```text
primary_status = FAIL
```

当前 MvpCaseReport 还没有这些字段。

### 优化方案

增加：

```text
primary_status
cleanup_status
recovery_status
failure_type
```

### 优先级

P1，暂不阻塞 G0A。

---

## 22. 🟡 新发现：Runtime Profile validate 仍绑定物理 Host

虽然 Host 已不参与 Profile ID，但 `validate_profile()` 仍要求：

```text
host_hash 相同
database_alias 相同
```

### 当前阶段判断

Bootstrap 阶段属于安全且保守的实现，可以接受。

### 未来优化

Multi-cluster 时拆：

```text
Semantic Compatibility
```

与：

```text
Evidence Environment Binding
```

不能把物理 Host 当成 Runtime Semantic Compatibility 的必要条件。

---

## 23. 🟡 新发现：Manifest / Source / Bundle 能力尚未强制接入 Runner

目前已经有：

```text
compute_manifest_hash
verify_source_snapshot
verify_bundle
```

但 Diagnostic Runner 仍是：

```text
case_dir
→ glob yaml
→ 执行当前工作区内容
```

### 优化方案

正式 Runner 应迁移为：

```text
run_manifest(manifest, bundle)
```

执行前强制：

```text
verify_manifest
verify_bundle
verify_source_snapshot
verify_runtime_profile
```

---

## 24. 仍未解决的问题

本轮没有伪装成完成，保留待办是正确的：

```text
Core Model 模块拆分
正式 XGT Parser / Compiler / Catalog
Xugu Cancel / Stop Proof
完整 Reset / Probe
Resource Conflict Matrix
SourceSpan
Python × Driver Compatibility Matrix
Real Integration CI
Driver ZIP 制品管理
正式 Dependency Lock
```

---

## 25. 当前推荐优先修正顺序

### 第一优先级：下一提交建议只修 3 个

```text
1. Comparator timestamp/time 类型解析重复与 substring Bug
2. Runtime Profile Identity 改成严格白名单 Projection
3. ExpectedError / ExpectedStatement 非空约束
```

这三个属于 G0A Freeze 前最后的 Contract 正确性问题。

### 第二优先级

```text
4. MvpStepReport.status 改用 StepStatus
5. RuntimeProfileIdentity 拆正式 Pydantic 子模型
6. Cleanup Failure 显式保留 primary_status
7. Canonical Golden Vector 再补完整
8. YAML Golden Vector 独立目录
```

### 第三优先级：进入正式 Phase 1

```text
9. XGT Parser
10. Metadata Resolver
11. Compiler
12. Catalog 2
13. Selector / Test Plan
14. Manifest / Bundle Publisher
15. Runner 强制 Manifest / Bundle Verify
16. Coverage Minimal Engine
17. Reset / Probe
18. Worker Pool
```

---

## 26. 当前建议工作包状态

| 工作包 | 当前建议状态 |
|---|---|
| P0A-02 工程骨架 | ✅ ACCEPTED |
| P0A-03 Registry | ✅ 接近 ACCEPTED |
| P0A-04 Core Model | 🟡 接近 ACCEPTED |
| P0A-05 Schema / Validation | ✅ 接近 ACCEPTED |
| P0A-06 Golden Vector | 🟡 IN_PROGRESS |
| G0A Core Contract Freeze | 🟡 VERY CLOSE / NOT YET |
| A-01 Xugu Environment | ✅ 基础完成 |
| A-02 Type Probe | 🟡 基础完成，最终映射仍需收口 |
| A-03 Transaction Probe | ✅ 基础完成 |
| A-04 Error Mapping | 🟡 基础完成 |
| A-05 Cancel / Stop Proof | ❌ 未完成 |
| A-06 Reset / Probe | ❌ 未完成 |
| A-07 Runtime Profile | 🟡 约 80% |
| Bootstrap Runner | ✅ 可真实运行 |
| Formal Runner | ❌ 尚未成立 |
| Comparator | 🟡 约 90% |
| Target Identity | ✅ 基本完成 |
| Manifest Identity | 🟡 基础完成 |
| Source/Bundle Drift | ✅ 工具完成，主链接入未完成 |

---

## 27. 是否可以 G0A Freeze

当前建议：

```text
暂不 Freeze
```

但已经非常接近。

建议最后补齐：

```text
[ ] Comparator Logical Type 单一来源
[ ] Runtime Profile Identity 白名单化
[ ] ExpectedError / ExpectedStatement 非空约束
[ ] 相关 Golden Vector 通过
```

以上完成后，再做一次 G0A Contract Review。如果没有新的结构性问题，就可以正式冻结：

```text
core_contract_set_id
```

---

## 28. 最终结论

本轮修复整体质量较高，不是表面按审核清单打勾。

尤其：

```text
普通异常误判 PASS
XGC1 Comparator
Typed Bootstrap Runner
Setup/Main/Cleanup 生命周期
Target Identity
Manifest Identity
Runtime Profile 基础稳定化
Source/Bundle Drift
Temporal 真实解析
```

已经明显提升框架可信度。

当前剩余问题已经高度集中：

> Comparator Logical Type 单一来源、Runtime Profile Identity 白名单化、Expected 类型边界。

这三个问题修完后，Phase 0A 就非常接近真正可以 Freeze。

建议下一阶段：

```text
先完成 G0A 最后三个边界问题
↓
正式 Freeze Core Contract
↓
再进入 XGT Parser / Compiler / Catalog 主线开发
```
