# XG DB Test 问题修复记录

> 记录范围：依据 `XG_DB_Test_Current_Code_Issues_and_Fixes.md` 完成的最近几轮代码与契约修复  
> 记录日期：2026-09-16  
> 当前状态：Bootstrap/Diagnostic Runner 可在真实虚谷环境运行；G0A 尚未宣布冻结

## 1. 记录目的

本文件记录审核问题从发现到修复、验证和提交的闭环结果。原始审核意见作为问题来源，已完成与待完成清单作为当前状态索引；本文件不替代这些权威文档。

修复遵循以下边界：

- 只修改审核意见明确涉及的代码、测试、Schema 和状态清单。
- 用户修改的原始审核文档不覆盖、不自动混入代码提交。
- 真实虚谷验证使用项目隔离 Python 环境，不修改 237 的系统 Python。
- 未具备真实 Driver/数据库证据的能力保留为待办，不标记为已完成。

## 2. 按提交记录的修复批次

| 提交 | 批次 | 主要内容 |
|---|---|---|
| `1ae2735` | 审核 P0 执行正确性收口 | 修复普通异常误判 PASS、Typed Bootstrap 解码、Setup/Main/Cleanup 分阶段、XGC1 行比较、Runtime Profile 稳定身份、Registry 校验序列化、rollback/reset 语义、UUID run_id、错误信息脱敏。 |
| `23923d2` | Target / Manifest 基础身份 | 新增 Target Identity Projection、`target_id` 自动校验、Plan/Manifest Identity Projection、稳定集合排序、Plan Hash 校验、YAML 与 Temporal Golden Vector。 |
| `09d5317` | Profile 与结果流式基础 | 新增 `RuntimeProfile` Pydantic 契约和 Schema；Adapter 增加 Driver Type → Logical Type 映射、bounded `fetchmany` 和 `iter_query_rows()`。 |
| `5b59f53` | 发布输入漂移保护 | 新增 Source Snapshot 与 Bundle 内容/大小校验工具；将 MVP Report Target 类型化，补充 `MvpTargetReport` Schema 和漂移测试；同步更新审核完成/待完成清单。 |

本轮后续边界收口代码已在本次提交完成，具体包括 Comparator 类型单一来源、Expected 非空约束和 Profile Identity 白名单化。

本轮继续完成第二优先级中的状态与身份收口：`MvpStepReport.status` 接入 `StepStatus`，Case Report 显式保留业务、清理和恢复状态，Runtime Profile Identity 拆为严格 Pydantic 子模型，并扩展错误凭据脱敏范围。

本轮继续补充可在当前工程闭环验证的基础能力：Adapter 与 Comparator 共用 Logical Type 映射，YAML 重复键错误保留 SourceSpan，并加入纯函数 Resource Conflict Matrix；正式 Parser/Compiler、持久化 Lease 与外部环境准入仍未宣称完成。

## 3. 问题与修复对应关系

### 3.1 已修复的新发现问题

| 问题 | 修复结果 | 主要落点 |
|---|---|---|
| N1 普通 SQL 异常被误判为 PASS | 只有显式 `ExpectedError` 才允许异常比较；Rows/Hash/Statement 预期遇到异常为 ERROR，错误预期不匹配为 FAIL。 | `src/xgtest/runtime/comparator.py`、`src/xgtest/runtime/runner.py` |
| N2 Runner 绕过 Core Model | Bootstrap YAML 先解码为 `BootstrapCaseInput`、`EffectiveMetadata`、`SqlStep` 和 typed Expected。 | `src/xgtest/core/models.py`、`src/xgtest/runtime/runner.py` |
| N3 Comparator 绕过 XGC1 | 删除 JSON `default=str` 行 Hash；Exact、Rowsort 和 Hash 统一使用 XGC1 typed framing。 | `src/xgtest/core/canonical.py`、`src/xgtest/runtime/comparator.py` |
| N4 Profile ID 不稳定 | Profile ID 只由语义 identity 计算；探测时间、随机表名和运行期证据不参与身份。 | `src/xgtest/runtime/profile.py` |
| N5 Host 混入语义 Profile 身份 | Profile 拆分 semantic identity 与物理 target context；Host 不参与语义 Profile ID。 | `src/xgtest/runtime/profile.py` |
| N6 Registry Entry 无法 JSON 序列化 | CLI 将 Entry 序列化为 `key + metadata` 对象。 | `src/xgtest/cli.py` |
| N7 Setup/Main/Cleanup 混在单循环 | Setup 失败跳过 Main，Cleanup 始终运行，并输出 `SKIPPED`。 | `src/xgtest/runtime/runner.py`、`registry/statuses.yaml` |
| N8 `reset()` 名称误导 | 增加 `rollback_transaction()`；完整 reset 未验证时显式抛出 `NotImplementedError`。 | `src/xgtest/adapter/xugu.py` |
| N11 MVP Report 状态双真源 | Step/Case/Run 状态接入 Registry 生成 Enum；新增 `SKIPPED`。 | `src/xgtest/core/models.py`、`src/xgtest/generated/registry_enums.py` |
| N12 MVP Target 自由 Dict | 新增 `MvpTargetReport`，Run Report 使用类型化 Target。 | `src/xgtest/core/models.py`、`src/xgtest/runtime/runner.py` |
| N14 Run ID 截断碰撞 | 改用 UUID4 运行 ID。 | `src/xgtest/runtime/runner.py` |
| N17 错误信息缺少脱敏 | 对 password 参数和连接 URL 凭据统一替换为 `<redacted>`。 | `src/xgtest/adapter/xugu.py` |

### 3.2 已完成的契约与输入保护

| 问题 | 修复结果 | 主要落点 |
|---|---|---|
| Target Identity 缺少稳定算法 | 语义字段经 XGMJ1 + SHA-256 生成 `target_id`，模型构造时自动校验。 | `src/xgtest/core/identity.py`、`src/xgtest/core/models.py` |
| Plan/Manifest 缺少稳定基础身份 | Plan/Manifest 投影对目标、Bundle、Case 等集合按语义键排序，并提供 SHA-256 计算。 | `src/xgtest/core/identity.py` |
| Runtime Profile 缺少正式模型 | 新增 v0.2 `RuntimeProfile` 模型、identity 校验和 JSON Schema。 | `src/xgtest/core/models.py`、`src/xgtest/runtime/profile.py`、`schemas/RuntimeProfile.schema.json` |
| Source/Bundle 漂移未校验 | 对相对路径、文件存在性、内容 Hash、Bundle 大小执行校验；越界和漂移会拒绝。 | `src/xgtest/core/manifest.py` |
| Driver 类型只有原始字符串 | 增加 INTEGER、NUMERIC、DOUBLE、DATE、TIMESTAMP、BINARY、VARCHAR 等到 Logical Type 的显式映射。 | `src/xgtest/adapter/xugu.py` |
| 大结果集只有 fetchall | 查询优先按 1000 行批次使用 `fetchmany`，并提供 `iter_query_rows()` 流式接口；MVP 报告仍会收集结果用于兼容现有输出。 | `src/xgtest/adapter/xugu.py` |
| YAML/Temporal 边界向量不足 | 增加科学计数、下划线数字、NaN、null、Unicode 以及非法日期/时间值测试；Temporal 由格式检查升级为真实解析校验。 | `framework_tests/contract/`、`src/xgtest/core/canonical.py` |

### 3.3 Issues_and_Fixes2.md 本轮 P0 边界修复

| 问题 | 修复结果 | 主要落点 | 验证证据 |
|---|---|---|---|
| N18 Comparator timestamp/time substring bug | Comparator 采用精确类型别名和最长匹配；`timestamp`、`timestamp_tz`、`time`、`datetime` 分别得到正确 Logical Type。 | `src/xgtest/runtime/comparator.py` | 类型反向测试、237 全量测试。 |
| N19 ExpectedError 空对象歧义 | `ExpectedError` 至少包含一个 `code`、`sqlstate` 或 `message_pattern`；`ExpectedStatement.affected_rows` 改为必填。 | `src/xgtest/core/models.py` | 空模型拒绝测试、Schema 重新生成。 |
| N20 Profile Identity 黑名单风险 | 只对白名单 capability、type mapping、事务可见性、错误类别/代码和取消/Reset 状态建身份；原始 message、对象名、观测值不参与 ID。 | `src/xgtest/runtime/profile.py` | 随机表名、时间和随机错误消息变化的 Profile ID 稳定测试；Profile 真实执行 PASS。 |

### 3.4 Issues_and_Fixes2.md 第二优先级收口

| 问题 | 修复结果 | 主要落点 | 验证证据 |
|---|---|---|---|
| N11 MvpStepReport 状态双真源 | `MvpStepReport.status` 改用 Registry `StepStatus`，Schema 与 Runner 同步。 | `src/xgtest/core/models.py`、`src/xgtest/runtime/runner.py` | 生命周期测试、Schema 重新导出。 |
| N21 Cleanup Failure 未保留 primary_status | Case Report 增加 `primary_status`、`cleanup_status`、`recovery_status`、`failure_type`；清理失败会将最终状态置为 ERROR，同时保留业务主状态。 | `src/xgtest/core/models.py`、`src/xgtest/runtime/runner.py` | Setup/Cleanup 失败反向测试、真实 MVP 回归。 |
| O3 RuntimeProfile Identity 内部自由字典 | Identity 拆为 Target、Driver、Capabilities 及类型/事务/错误子模型，未注册嵌套字段会被拒绝。 | `src/xgtest/core/models.py`、`src/xgtest/runtime/profile.py` | 嵌套字段拒绝测试、真实 Profile 构建与执行 PASS。 |
| N17 Error Redaction 覆盖不足 | 增加 token、secret、authorization、api-key、access-token 和 Bearer 形式脱敏，同时保留 URL 凭据脱敏。 | `src/xgtest/adapter/xugu.py` | Adapter 脱敏反向测试。 |

### 3.5 当前工程可闭环的基础能力补充

| 问题 | 修复结果 | 主要落点 | 验证证据 |
|---|---|---|---|
| O5 Logical Type Mapping 重复实现 | Adapter 与 Comparator 使用同一 Core 映射函数，精确处理 timestamp/time 和带参数类型。 | `src/xgtest/core/logical_types.py`、`src/xgtest/adapter/xugu.py`、`src/xgtest/runtime/comparator.py` | 类型边界测试。 |
| SourceSpan 未贯穿 YAML 重复键错误 | DuplicateKeyError 增加源文件、行、列，保持稳定错误代码。 | `src/xgtest/core/errors.py`、`src/xgtest/core/yaml_loader.py` | YAML SourceSpan 测试。 |
| Resource Conflict Matrix 缺少共享实现 | 新增纯函数冲突判定，READ/READ 共享，其他重叠模式冲突，父资源与子资源正确展开，同 Attempt 可豁免。 | `src/xgtest/core/admission.py` | Admission 矩阵测试。 |

## 4. 验证记录

验证环境为 237 项目目录中的隔离 `.venv`，Python 3.14.7，xgcondb Driver 2.3.9；未修改系统 Python。

已完成验证：

- 框架测试：**47 passed**。
- 真实虚谷四个 MVP Case（JOIN、UNION、DDL TABLE、STRING FUNCTION）：**PASS**。
- 带 v0.2 Runtime Profile 的真实执行：**PASS**。
- `xgtest registry validate`：可输出包含 Entry 元数据的 JSON。
- `xgtest schema export`：重新生成 RuntimeProfile、MvpTargetReport 及相关 Schema。
- Source Snapshot / Bundle 漂移、Target ID、Plan/Manifest 排序和 Temporal 反向用例：通过。
- Logical Type 映射、YAML SourceSpan、Resource Conflict Matrix 反向用例：通过。
- 数据库测试对象均执行清理，未在目标库留下本轮 MVP 表。

## 5. 当前仍待完成

以下事项没有在本轮伪造为完成状态：

- Core Model 拆分为 asset/planning/execution/result/resource 模块。
- 正式 XGT DSL、Parser、Compiler、Catalog，以及 Manifest/Bundle 强制接入正式 Runner。
- 完整 Target/Environment Registry、DB exact build、OS/arch 和配置采集闭环。
- Xugu `cancel/stop` 有界长 SQL 证明，以及 schema、锁、临时对象、会话参数的完整 reset probe。
- DATE/TIME/DATETIME/BLOB 的最终三层 Type Mapping 与 Canonical 冻结。
- 完整 YAML/Canonical Golden Vector 目录、Resource Conflict Matrix 和 SourceSpan 贯穿 Parser/Compiler。
- Python 3.11～3.14 × Driver 兼容矩阵、真实 Integration CI、Driver 制品仓库和正式依赖锁定。
- `host_hash` 的无盐枚举风险（N18）；当前仅完成 Host 不进入语义 Profile ID，尚未完成 HMAC 或完全移除物理引用。

这些事项继续列在 `XG_DB_Test_待完成审核项清单.md` 中，完成前不应宣布 G0A Freeze。

## 6. 提交与文件状态

本修复记录随本文件一起提交。相关代码已推送到 GitHub `main`。

用户后续修改的原始文件 `XG_DB_Test_Current_Code_Issues_and_Fixes.md` 保留在工作区未提交状态，以避免覆盖用户内容；完成清单和待完成清单的状态更新已随代码提交。
