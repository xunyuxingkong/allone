# JOIN v3 候选评审包

状态：**等待独立人工评审**。21 条候选已完成静态校验、真实变异验证、真实双跑及 AI 技术评审，均处于 `review`。

- Model / Template / Generator：2 / 3 / 3。
- Contract Set：`00cc4ed20a97e6f84a24137744534d414870cb4bad905dc118af472d10ce8adb`。
- Runtime Profile：`310d95205a3b6c68c014e5b19e25a70879bc60ab0411c0ecc2d0d5b17da998fb`；能力探针临时表清理 VERIFIED。
- `<= → <` Mutation：适用 5 条，KILLED 5 条；[索引](mutation-validation-index.json)。
- 真实 Xugu 双跑：21/21 PASS；[制品索引](trial-run-index.json)。
- Active 查询回归：30/30 PASS；本地原始制品 `artifacts/runs/query-v3-active.json`。
- Pairwise：Active 17/137；候选全部晋级后的 provisional 137/137；[覆盖摘要](coverage-summary.json)。
- [AI 技术评审](../../审核意见/XG_DB_Test_JOIN_v3_AI_Technical_Review.md)：21 条按现行模型口径通过，4 项口径与证据限制交人工确认。

人工评审时逐条确认用例目标、SQL/Expected、覆盖 Claim、变异和双跑证据；确认后通过 `xgtest candidate review` 记录评审引用。之后再晋级、运行晋级后完整回归并生成最终覆盖快照。本评审包不构成人工评审结论。

本评审包对应已归档的 v3 候选。精确 INTEGER 类型修复后的当前评审包为 [review-packet.md](review-packet.md)。
