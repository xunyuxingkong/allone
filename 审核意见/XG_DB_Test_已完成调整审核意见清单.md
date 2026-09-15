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
