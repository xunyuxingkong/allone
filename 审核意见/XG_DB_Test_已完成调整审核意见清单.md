# XG DB Test 已完成调整审核意见清单

> 来源：`XG_DB_Test_Current_Code_Issues_and_Fixes.md`
> 更新日期：2026-09-15
> 范围：本清单仅记录已实际修改并完成验证的审核项；未完成或只完成部分的事项见同目录的待完成清单。

## 已完成调整

| 原审核项 | 调整结果 | 落点 | 验证证据 |
|---|---|---|---|
| P0 Core Model 基础字段不足 | 扩展 RawMetadata、EffectiveMetadata、Target、Manifest、ResourceRequest、ResultEvent、ComparisonProfile 及 Typed Expected，补入 SQL MVP 所需的关键身份、资源、运行时与元数据字段。 | `src/xgtest/core/models.py`、`schemas/` | Python 3.14 环境通过模型与 Schema 相关测试；Schema 已重新导出。 |
| ResultEvent 过于简化 | 增加 schema_version、event_id、run/case/target/environment identity、assignment_epoch、fencing_token、timestamp。 | `src/xgtest/core/models.py` | 生成 `ResultEvent.schema.json`。 |
| Registry 丢弃元数据 | 新增 `RegistryEntry`，保留 key 之外的元数据；Enum 只消费 entry.key。 | `src/xgtest/core/registry.py` | Registry 测试断言 `phase: sql_mvp` 被保留。 |
| Registry Enum 命名碰撞 | 在生成前检查规范化成员名，碰撞时报 `REGISTRY_ENUM_NAME_COLLISION`。 | `src/xgtest/core/registry.py` | 新增碰撞测试。 |
| Registry 与模型双真源 | 模型的 feature、level、status、isolation、resource access mode 改用 Registry 生成的 Enum。 | `src/xgtest/core/models.py`、`src/xgtest/generated/registry_enums.py` | 生成 Enum 与模型测试通过。 |
| Lifecycle 缺少 generated | `case_asset` Registry 增加 `generated`。 | `registry/statuses.yaml` | 生成 `CaseAssetStatus.GENERATED`。 |
| Resource access mode 不完整 | 增加 `shared_write`。 | `registry/resource_access_modes.yaml` | 生成 `ResourceAccessMode.SHARED_WRITE`。 |
| YAML 1.2 Core 校准不足 | 移除 SafeLoader 遗留的 bool/int/float/null/timestamp 隐式规则，显式注册 Core 规则；保留重复键拒绝。 | `src/xgtest/core/yaml_loader.py` | 覆盖 `0123`、`0o123`、`0x10`、`.inf`、时间戳样式文本与 on/off。 |
| Schema stale 检查失效 | Schema 先导出到空临时目录，再原子替换 generator-managed 输出目录。 | `src/xgtest/cli.py` | 237 上执行 schema export，Schema 文件集重新生成。 |
| Schema 缺少稳定身份 | 每份 Schema 注入 `$id` 与 `x-xg-contract-version`。 | `src/xgtest/cli.py`、`schemas/` | 已重新导出全部 Schema。 |
| DECIMAL Probe 结论写死 | 根据真实 Python 返回类型计算 EXACT/LOSSY 与 Canonical 兼容性。 | `tools/probes/xugu_capability_probe.py` | 真实 Driver 2.3.9 返回 float，报告为 `LOSSY / FAILED`。 |
| 事务 observer 快照污染 | 每次可见性检查均使用 fresh observer connection。 | `tools/probes/xugu_capability_probe.py` | 真实探测得到 rollback=0、commit=1。 |
| Probe Artifact 暴露连接信息 | 默认仅保存 host SHA-256 与 database alias，不写 host/port。 | `tools/probes/xugu_capability_probe.py` | 真实探测产物已验证输出脱敏 target。 |
| Extended Type VERIFIED 语义过宽 | 分离 operation_status、mapping_status、canonical_compatibility。 | `tools/probes/xugu_extended_types_probe.py` | Probe 输出结构已更新。 |
| Canonical Golden Vector 不足 | 增加 Decimal、NaN、正负零、bytes 与日期格式向量。 | `framework_tests/contract/test_canonical.py` | Python 3.14 契约测试通过。 |
| 日期时间仅检查 str | date/time/timestamp/timestamp_tz 增加 Canonical 格式校验。 | `src/xgtest/core/canonical.py` | 新增非法日期格式拒绝测试。 |
| ContractError 定位信息不足 | 增加可选 SourceSpan、details、cause 字段。 | `src/xgtest/core/errors.py` | Python 语法与契约测试通过。 |
| Python 3.14 被过早独占锁定 | 项目支持范围改为 `>=3.11,<3.15`，仍以真实 Python 3.14 Driver 环境作为当前实测基线。 | `pyproject.toml`、CI | 237 Python 3.14 + xgcondb 2.3.9 的真实探测通过。 |
| CI 未区分真实集成测试 | Contract CI 显式排除 `xugu_integration`，项目声明该 marker。 | `pyproject.toml`、`.github/workflows/contract.yml` | CI 配置已更新。 |

## 验证汇总

- 237 项目隔离 Python 3.14：`15 passed`。
- Registry Enum、JSON Schema 已重新生成。
- 真实虚谷连接、基础读取、事务提交/回滚、错误映射与清理均已复测。
- 本次没有修改系统 Python 或持久化数据库凭据。

## 本轮依据最新问题清单完成

| 原审核项 | 调整结果 | 落点 | 验证证据 |
|---|---|---|---|
| N1 普通异常误判 PASS | 只有显式 `ExpectedError` 才允许异常比较通过；Rows/Hash/Statement 预期遇到异常报告 ERROR，错误预期不匹配报告 FAIL。 | `src/xgtest/runtime/comparator.py`、`src/xgtest/runtime/runner.py` | Comparator 单元测试、237 全量测试与真实 MVP 回归。 |
| N2 Runner 绕过 Core Model | Bootstrap YAML 先解码为 `BootstrapCaseInput`、`EffectiveMetadata`、`SqlStep` 和 typed Expected，再进入执行阶段。 | `src/xgtest/core/models.py`、`src/xgtest/runtime/runner.py` | Typed bootstrap 测试与真实四用例回归。 |
| N3 Comparator 绕过 XGC1 | SQL 行比较和 Hash 统一使用 XGC1 typed framing；rowsort 按规范化行帧排序，支持 NULL 与混合类型。 | `src/xgtest/core/canonical.py`、`src/xgtest/runtime/comparator.py` | XGC1 comparator 测试、真实 JOIN/UNION/DDL/字符串函数回归。 |
| N4/N5 Runtime Profile 身份不稳定 | Profile 拆分 semantic identity 与物理 target context；时间、随机表名、host 等证据字段不参与 profile ID，身份使用 XGMJ1。 | `src/xgtest/runtime/profile.py` | Profile invariance 测试、237 重新构建 v0.2 Profile 并带 Profile 执行 PASS。 |
| N6 Registry validate 序列化失败 | CLI 将 `RegistryEntry` 序列化为 key 与 metadata，而不是直接 JSON 编码 dataclass。 | `src/xgtest/cli.py` | CLI 断言测试、237 `xgtest registry validate` 实测。 |
| N7 生命周期混在单循环 | 执行拆为 Setup/Main/Cleanup；Setup 失败跳过 Main，Cleanup 始终执行并报告 SKIPPED。 | `src/xgtest/runtime/runner.py`、`registry/statuses.yaml` | Setup failure 生命周期测试、真实 MVP Cleanup 回归。 |
| N8 reset 名称误导 | `rollback_transaction()` 明确表示已验证能力；未验证完整会话 reset 时 `reset()` 显式抛出 NotImplementedError。 | `src/xgtest/adapter/xugu.py` | Adapter 测试与真实 MVP 回滚收尾。 |
| N14 run_id 截断碰撞风险 | 使用 UUID4 生成运行 ID，避免时间戳摘要截断导致碰撞。 | `src/xgtest/runtime/runner.py` | 237 真实运行产物检查。 |
| N17 错误信息缺少脱敏 | 错误提取对 password 参数和连接 URL 凭据执行统一脱敏。 | `src/xgtest/adapter/xugu.py` | Adapter 脱敏测试。 |
| Target Identity Projection | Target ID 由语义字段经 XGMJ1 + SHA-256 自动计算并在模型构造时校验；Host 等物理上下文不参与 Target 语义 ID。 | `src/xgtest/core/identity.py`、`src/xgtest/core/models.py` | Target 正反向校验与语义投影测试。 |
| Manifest / Plan Identity 基础规则 | Plan/Manifest 身份投影提供稳定集合排序、XGMJ1 编码和 SHA-256 计算；Manifest 校验 Plan Hash 与 Target ID。 | `src/xgtest/core/identity.py`、`src/xgtest/core/models.py` | 目标重排、Bundle/Case 重排和 Run 变化测试。 |
| YAML / Temporal Golden Vector 增补 | 增加科学计数、下划线数字、NaN、null、Unicode 以及非法日期/时间值的契约向量。 | `framework_tests/contract/test_registry.py`、`src/xgtest/core/canonical.py` | 237 契约测试通过。 |
| Runtime Profile Pydantic 契约 | 新增 `RuntimeProfile` 模型和 Schema，Profile 加载时执行字段及 identity 校验。 | `src/xgtest/core/models.py`、`src/xgtest/runtime/profile.py`、`schemas/RuntimeProfile.schema.json` | 237 全量测试与 Profile 执行通过。 |
| Adapter Logical Type / fetchmany 基础能力 | 增加 Driver 类型到 Logical Type 的明确映射；查询优先使用 bounded `fetchmany`，并提供 `iter_query_rows()` 流式接口。 | `src/xgtest/adapter/xugu.py`、`src/xgtest/runtime/runner.py` | Adapter 测试、真实 MVP 回归通过。 |
| N12 MVP Target 类型化 | MVP Run Report 的 target 改为 `MvpTargetReport` 模型，避免继续使用自由字典。 | `src/xgtest/core/models.py`、`src/xgtest/runtime/runner.py` | Schema 生成与真实运行报告校验通过。 |
| Source / Bundle Drift 校验基础能力 | 新增按相对路径和内容哈希校验 Source Snapshot、按大小和 SHA-256 校验 Bundle 的公共工具。 | `src/xgtest/core/manifest.py` | 漂移、缺失和越界测试通过。 |
