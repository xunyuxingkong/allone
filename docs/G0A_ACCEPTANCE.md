# G0A 验收候选快照

状态：**HOLD，尚未 Freeze**（2026-09-28）。本轮已解除数据库只读阻塞，并重新完成真实 Driver 探测和查询回归。正式 Freeze 仍需在代码与契约定稿后记录 `freeze_git_commit`、发布正式 `contract_set_id`；当前 [候选描述符](g0a/contract-descriptor-candidate.json) 的 ID `ff9fad1b73c500e67e782c180ef5190102605a48bb1e29cdd7e6df953040b596` 不应作为已发布 ID 使用。

| 检查 | 本轮结果 | 证据与边界 |
|---|---|---|
| Registry / Schema / Contract | PASS | `registry validate`、`schema export`、`contract verify` 已执行；候选描述符与当前源码、Schema 一致。 |
| Framework Tests | PASS | Python 环境中 170 passed、1 个真实数据库集成用例按标记排除。 |
| 真实 Xugu Driver 能力探针 | PASS | 连接、写入、提交、回滚、SQL 错误映射通过，随机临时表清理 `VERIFIED`；脱敏记录见 `artifacts/capabilities/runtime-profile-evidence.json`。 |
| 表往返类型探针 | PASS（限定支持集合） | 22 种声明类型中 21 种读回；全部探针临时表清理 PASS。`VARBINARY(8)` 因语法错误未读回；`NUMERIC/DECIMAL/NUMBER` 精度映射不满足 Canonical，时间戳类仍有歧义。原始记录见 `artifacts/capabilities/xugu_driver_type_mapping_v1.json`。 |
| SQL Runtime Profile | PASS（候选） | ID `474c848b8b28264c73838e337dcad3a056ad8df295504e976dc4ccc7fd237bac` 绑定本轮候选 Contract Set。摘要见 [runtime-profile-summary.json](../acceptance/query-generation-mvp/runtime-profile-summary.json)。 |
| 现有查询用例真实回归 | PASS | 30/30；包含 JOIN、UNION、字符串和其他查询功能。详情见本地 `artifacts/real-acceptance/query-regression-v2.json`。 |
| JOIN v2 新候选真实试运行 | PASS，技术评审 HOLD | 21/21 均在同一 Runtime Profile 下双跑通过；[独立技术评审](../审核意见/XG_DB_Test_JOIN_v2_AI_Technical_Review.md)发现 5 条 `less_equal` 候选未验证等值边界。人工评审与晋级尚未完成，不计入 Active Coverage。 |
| Cancel / Reset 能力 | UNKNOWN | 本轮能力探针未验证服务端停止与完整会话重置；不声明这些能力可用。 |

当前 G0A HOLD 的剩余动作是固定本轮源码与生成 Schema，复核候选描述符，记录正式 Freeze Git 提交并发布其 Contract Set。JOIN 候选的人工评审与晋级属于 Query Generation 验收门禁，状态见 [final-acceptance.json](../acceptance/query-generation-mvp/final-acceptance.json)。
