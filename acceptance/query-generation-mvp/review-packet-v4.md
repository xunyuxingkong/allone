# JOIN v4 候选评审包

状态：**等待独立人工评审**。21 条候选已完成静态校验、真实变异验证、真实双跑及 AI 技术评审，均处于 `review`。

- Model / Template / Generator：2 / 4 / 4。
- Contract Set：`3541e2217dabc75ec9e32ad42f6d55b63e935d11dd7b759a6c59f1edf7268db8`。
- Runtime Profile：`45e7e9b320a9bc24503d214a97223018b659f24b1e0fa68e736d979bd8be4b78`；能力探针临时表清理 VERIFIED。
- `<= → <` Mutation：适用 5 条，KILLED 5 条；[索引](mutation-validation-index.json)。
- 真实 Xugu 双跑：21/21 PASS；[制品索引](trial-run-index.json)。
- 精确整数类型：4 条 `datatype=int` 候选的两个输出键均实测为 `INTEGER`；探针哈希 `a987b266b440e751df7ad7951cfaeab0256a77b55ec25adaa68ba9e46c8a49c0`。
- Active 查询回归：30/30 PASS；本地原始制品 `artifacts/runs/query-v4-active.json`。
- Pairwise：Active 17/137；候选全部晋级后的 provisional 137/137；[覆盖摘要](coverage-summary.json)。
- [AI 技术评审](../../审核意见/XG_DB_Test_JOIN_v4_AI_Technical_Review.md)：21 条按现行模型口径通过，2 项证据边界交人工确认；外连接的全匹配和未匹配两类场景均有候选覆盖。

人工评审时逐条确认用例目标、SQL/Expected、覆盖 Claim、变异和双跑证据；确认后通过 `xgtest candidate review` 记录评审引用。之后再晋级、运行晋级后完整回归并生成最终覆盖快照。本评审包不构成人工评审结论。
