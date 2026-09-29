# G0A 验收候选快照

状态：**HOLD，尚未 Freeze**（2026-09-29）。JOIN 模板 v4 对 `datatype=int` 显式使用 `INTEGER`；当前 [候选描述符](g0a/contract-descriptor-candidate.json) 的 ID `c1fb2d3586a70dd627f8da950dbe900847837f48cb33ece865c0aa0ae85e911a` 仍是候选值，尚未正式发布。

| 检查 | 本轮结果 | 证据与边界 |
|---|---|---|
| Registry / Schema / Contract | PASS | 本轮已重新导出 Schema 并生成候选描述符；Framework Tests 未在本轮重跑。 |
| Framework Tests | NOT RUN | 本轮聚焦原始行制品和真实数据库证据刷新。 |
| 真实 Xugu Driver 能力探针 | PASS（复用） | WSL 中使用仓库提供的 Linux Driver 2.3.9；连接、写入、提交、回滚、SQL 错误映射通过，随机临时表清理 `VERIFIED`。能力探针复用 v5，并在本轮单独补采数据库版本，证据见 `artifacts/capabilities/runtime-profile-evidence-v6.json`。 |
| 表往返类型探针 | PASS（限定支持集合） | 同一目标和 Driver 下的 22 种声明类型探针中 21 种读回，全部临时表清理 PASS；`VARBINARY(8)` 因语法错误未读回。原始记录见 `artifacts/capabilities/xugu_driver_type_mapping_v1.json`。 |
| 精确 INTEGER 类型 | PASS | 系统表 `SYSDBA.SYS_DATATYPES` 列出四种整数类型；裸小整数被推断为 `TINYINT`，显式 CAST 后为 `INTEGER`。4 条 v4 `datatype=int` 候选左右连接键实测均为 `INTEGER`；见[JOIN v6 AI 技术复核](../审核意见/XG_DB_Test_JOIN_v6_AI_Technical_Review.md)。 |
| SQL Runtime Profile | REBUILT | 新 ID `5ea8f183395d637fd37366173abe1722b5f6a9744f3ce5c895115dbafd068fd0` 绑定当前 Contract Set、目标地址哈希和 Driver 2.3.9；能力证据复用自 v5；数据库版本记录为 `BETA-11679_11665`，build 时间为 `2026-05-18 12:11:00`，原始查询见 `artifacts/capabilities/xugu-show-build-time-v1.json`。 |
| 现有查询用例真实回归 | PASS | 30/30 在 v6 Profile 下真实回归通过；本地原始制品为 `artifacts/runs/query-v6-active.json`。 |
| JOIN v2 试运行 | 历史 PASS，已过期 | v2 的 21/21 双跑仅作为历史证据；[v2 AI 技术评审](../审核意见/XG_DB_Test_JOIN_v2_AI_Technical_Review.md)及候选已归档。 |
| JOIN v3 试运行 | 历史 PASS，已过期 | v3 的 21/21 双跑和[AI 技术评审](../审核意见/XG_DB_Test_JOIN_v3_AI_Technical_Review.md)仅作历史证据；候选已归档。 |
| JOIN v4 候选（v6 试跑证据） | 技术验证 PASS，人工评审 PENDING | 21 条静态校验、真实双跑、完整 Xugu 返回行与 AI 技术复核通过；5 条适用 `<= → <` 变异均被杀死。21 条仍为 `review`，未记录人工 Review Evidence、未晋级；见[评审包](../acceptance/query-generation-mvp/review-packet.md)。 |
| Cancel / Reset 能力 | UNKNOWN | 本轮能力探针未验证服务端停止与完整会话重置；不声明这些能力可用。 |

数据库精确版本/build 已记录，不再是待确认项。当前 G0A HOLD 的剩余动作是独立人工评审 JOIN 候选并记录 Review Evidence、按门禁晋级、执行晋级后完整回归与最终覆盖快照，随后复核候选描述符、记录正式 Freeze Git 提交并发布 Contract Set。状态见 [final-acceptance.json](../acceptance/query-generation-mvp/final-acceptance.json)。
