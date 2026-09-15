# XG DB Test 待完成审核项清单

> 来源：`XG_DB_Test_Current_Code_Issues_and_Fixes.md`
> 更新日期：2026-09-15
> 说明：以下事项尚未达到原审核意见的完整验收条件，不应标记为 G0A 已冻结。

## P0：冻结前仍需收口

| 原审核项 | 待完成内容 | 完成条件 |
|---|---|---|
| Core Model 职责拆分 | 当前模型仍集中在 `models.py`，尚未拆为 asset/planning/execution/result/resource 等模块。 | 模块拆分完成，导入边界稳定，Parser/Compiler/Catalog 不再自建 DTO。 |
| Target Identity | 已扩展 Target Snapshot 字段，但尚未由稳定 Identity Projection 自动计算和校验 target_id。 | 实现 Target 身份投影、Golden Vector 与重复环境识别测试。 |
| Manifest 1 | 已扩展字段，但 case entry、expected execution、bundle dependency 与 runtime version 仍未形成完整可校验的正式 Manifest 发布流程。 | 实现 Manifest identity projection、Descriptor、向量与拒绝规则。 |
| YAML Golden Vector | 已校准核心标量，但未覆盖 nested duplicate、科学计数、`.nan`、Unicode、null、所有边界格式。 | 建立 `framework_tests/contract/yaml/` 标准向量并跨 Loader 审核。 |
| G0A Contract Test 覆盖 | 现有测试仍不足以冻结 G0A。 | 补全 Registry、Model、Canonical、YAML、Schema 的正反向 Golden Vector。 |

## P1：运行时与适配层

| 原审核项 | 待完成内容 | 外部依赖或验收条件 |
|---|---|---|
| Xugu Adapter | 当前仅具备 connect/smoke；尚未实现 execute、query/fetchmany、事务封装、列元数据、错误提取、cancel、reset、close 等最小 Adapter API。 | Adapter 单元测试与真实集成测试均覆盖。 |
| Runtime Profile Builder | Probe 仍生成原始 JSON，尚未由 Profile Builder 形成不可变 SQLRuntimeProfile。 | 定义 Profile Schema、身份投影、证据引用和人工审查流程。 |
| Runtime Profile Identity | 未完整采集 DB exact build、OS、arch、compatibility mode 与关键配置。 | Profile 能精确绑定真实运行环境。 |
| Cancel / Stop | 尚未执行有界长 SQL 的取消与服务端停止观察。 | 明确 Driver cancel 或连接隔离/关闭替代策略并实测。 |
| Session Reset | 尚未覆盖 schema、autocommit、事务、锁、临时对象和会话参数恢复。 | 形成 reset_probe 与失败隔离策略。 |
| Extended Type Mapping | DATE/TIME/DATETIME 目前可写入读取但返回字符串；BLOB 绑定失败；尚未定义最终 Canonical 映射策略。 | 每种类型完成 operation/mapping/canonical 三层验收。 |
| Python × Driver 矩阵 | 只完成 Python 3.14 + Driver 2.3.9 的真实验证。 | 对 3.11、3.12、3.13、3.14 分别执行 import/connect/query/type/transaction 验证。 |
| Real Integration CI | 仅声明 marker，尚无受控内网/本地真实虚谷任务。 | 增加不可公开凭据的集成任务、环境选择与制品脱敏策略。 |
| Driver 制品治理 | Driver ZIP 仍在 Git。 | 提供 Nexus/Artifactory/MinIO/内部制品库地址后迁移为 artifact_ref + SHA-256 + 安装脚本。 |
| 可复现依赖锁定 | `requirements.lock` 仍是 freeze 结果。 | 选择并接入 uv、pip-tools 或 Poetry 之一。 |

## P1/P2：语义与质量深化

| 原审核项 | 待完成内容 | 完成条件 |
|---|---|---|
| ComparisonProfile | 仅预留部分字段，尚未实现 error/normalization/float/timestamp/resource profile 解析与执行逻辑。 | Profile 被 Compiler、Runner、Comparator 共同消费。 |
| Typed Expected | 已定义数据结构，尚未在 DSL/Compiler/Comparator 落地。 | 不再允许业务 Expected 以任意结构绕过验证。 |
| Resource Conflict Matrix | ResourceRequest 已补字段，尚未实现父子资源冲突、容量与 Admission 判定。 | 建立矩阵与并发测试。 |
| SourceSpan | ContractError 已可携带 SourceSpan，但 YAML/Parser/Compiler 尚未提供真实行列信息。 | DSL 错误能定位文件、行、列、字段路径。 |
| Canonical 向量覆盖 | 已覆盖一部分边界，仍缺重复行、空结果、零列、极大整数、Decimal exponent、timezone、错误 Canonical 等。 | 形成版本化完整 Golden Vector 集。 |

## 建议执行顺序

1. Target/Manifest Identity 与 YAML/Canonical 完整 Golden Vector。
2. Runtime Profile Schema 与 Profile Builder。
3. 最小 Xugu Adapter、cancel/reset 探测与真实 Integration CI。
4. Python × Driver 兼容矩阵与依赖/Driver 制品治理。
5. G0A Review 通过后，再进入 Parser、Compiler 与 Catalog。
