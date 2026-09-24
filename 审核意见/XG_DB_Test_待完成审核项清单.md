# XG DB Test 待完成审核项清单

> 来源：`XG_DB_Test_Current_Code_Issues_and_Fixes.md`
> 更新日期：2026-09-15
> 说明：以下事项尚未达到原审核意见的完整验收条件，不应标记为 G0A 已冻结。

## P0：冻结前仍需收口

| 原审核项 | 待完成内容 | 完成条件 |
|---|---|---|
| Core Model 职责拆分 | 当前模型仍集中在 `models.py`，尚未拆为 asset/planning/execution/result/resource 等模块。 | 模块拆分完成，导入边界稳定，Parser/Compiler/Catalog 不再自建 DTO。 |
| Target Identity | 已实现基础 Target Identity Projection、target_id 自动校验和正反向向量；仍需重复环境识别及完整 Environment/Target 注册表。 | 实现 Target 身份投影、Golden Vector 与重复环境识别测试。 |
| Manifest 1 | 已实现 Plan/Manifest 基础身份投影、集合排序和 Plan Hash 校验，并提供 Source/Bundle Drift 校验工具；仍需正式 Manifest 发布流程、Bundle Descriptor、依赖快照和 Runner 强制接入。 | 实现 Manifest identity projection、Descriptor、向量与拒绝规则。 |
| YAML Golden Vector | 已补科学计数、下划线数字、`.nan`、Unicode、null 和非法时间值；仍需独立向量目录、nested duplicate、超大输入和跨 Loader 审核。 | 建立 `framework_tests/contract/yaml/` 标准向量并跨 Loader 审核。 |
| G0A Contract Test 覆盖 | 已补 Runtime Profile、Typed Expected、Admission 和真实 Driver 元数据样本，生成可复算候选描述符；当前 G0A 验收仍为 HOLD。 | 数据库恢复可写后完成表往返探测与四类 MVP 复验，审定完整支持类型集合并记录 Freeze Git 提交。 |

## P1：运行时与适配层

| 原审核项 | 待完成内容 | 外部依赖或验收条件 |
|---|---|---|
| Xugu Adapter | execute、query、事务、列元数据、错误提取、cancel、close 和 bounded fetchmany 已具备；仍需完整 reset 与真实 cancel/stop 证明。 | Adapter 单元测试与真实集成测试均覆盖。 |
| Runtime Profile Builder | 已形成 v0.2 identity + evidence hash 的 Profile Builder，并有 `RuntimeProfile` Schema；仍需证据引用和人工审查流程。 | 定义 Profile Schema、身份投影、证据引用和人工审查流程。 |
| Runtime Profile Identity | 已改为稳定白名单 Projection，并拆为严格 Pydantic Target/Driver/Capabilities 子模型；仍需补采 DB exact build、OS、arch、compatibility mode 与关键配置。 | Profile 能精确绑定真实运行环境。 |
| Cancel / Stop | 尚未执行有界长 SQL 的取消与服务端停止观察。 | 明确 Driver cancel 或连接隔离/关闭替代策略并实测。 |
| Session Reset | 尚未覆盖 schema、autocommit、事务、锁、临时对象和会话参数恢复。 | 形成 reset_probe 与失败隔离策略。 |
| Extended Type Mapping | 真实只读样本取得 21/22 组元数据：NUMERIC 返回 float、时间戳返回非 Canonical 字符串且 TZ 元数据退化、BINARY/RAW 返回 VARCHAR；本轮数据库只读，表往返证据仍缺。 | 在可写环境逐类型完成 operation/mapping/canonical 三层验收，冻结正式支持集合。 |
| Python × Driver 矩阵 | 只完成 Python 3.14 + Driver 2.3.9 的真实验证。 | 对 3.11、3.12、3.13、3.14 分别执行 import/connect/query/type/transaction 验证。 |
| Real Integration CI | 仅声明 marker，尚无受控内网/本地真实虚谷任务。 | 增加不可公开凭据的集成任务、环境选择与制品脱敏策略。 |
| Driver 制品治理 | Driver ZIP 仍在 Git。 | 提供 Nexus/Artifactory/MinIO/内部制品库地址后迁移为 artifact_ref + SHA-256 + 安装脚本。 |
| 可复现依赖锁定 | `requirements.lock` 仍是 freeze 结果。 | 选择并接入 uv、pip-tools 或 Poetry 之一。 |

## P1/P2：语义与质量深化

| 原审核项 | 待完成内容 | 完成条件 |
|---|---|---|
| ComparisonProfile | Runner 已消费 mode，仍未实现 error/normalization/float/timestamp/resource profile 的统一解析与执行策略。 | Profile 被 Compiler、Runner、Comparator 共同消费。 |
| Typed Expected | Bootstrap Runner 已完成 ExpectedRows/Hash/Error/Statement typed dispatch；正式 DSL/Compiler/Catalog 仍需接入同一模型。 | 不再允许业务 Expected 以任意结构绕过验证。 |
| MVP Report Target | MVP Target 已改为 `MvpTargetReport`；正式 Runner 仍需使用完整 Target/Environment 模型并关联 Manifest。 | 报告 Target 与正式 Target/Environment 身份统一。 |
| Resource Conflict Matrix | 已实现纯函数 READ/WRITE/EXCLUSIVE 矩阵、直接父资源重叠和同 Attempt 豁免；仍需容量、资源树多级展开、原子持久化 Lease/Fencing 与并发测试。 | 建立完整资源树、容量和原子准入测试。 |
| SourceSpan | YAML 重复键错误已提供真实文件、行、列；Parser/Compiler 尚未提供字段路径和完整 SourceSpan 贯穿。 | DSL 错误能定位文件、行、列、字段路径。 |
| Canonical 向量覆盖 | 已补部分 Temporal 语义边界；仍缺重复行、空结果、零列、极大整数、Decimal exponent、timezone、错误 Canonical 等。 | 形成版本化完整 Golden Vector 集。 |

## 建议执行顺序

1. Target/Manifest Identity 与 YAML/Canonical 完整 Golden Vector。
2. Runtime Profile Schema 与 Profile Builder。
3. 最小 Xugu Adapter、cancel/reset 探测与真实 Integration CI。
4. Python × Driver 兼容矩阵与依赖/Driver 制品治理。
5. G0A Review 通过后，再进入 Parser、Compiler 与 Catalog。
