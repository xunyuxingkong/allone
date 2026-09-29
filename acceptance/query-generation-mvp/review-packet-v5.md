# JOIN v4 候选评审包（v5 原始行证据）

状态：**等待独立人工评审**。21 条候选已完成静态校验、真实变异验证、真实双跑及 AI 技术评审，均处于 `review`。

- Model / Template / Generator：2 / 4 / 4。
- Contract Set：`8679333f86bfce91ce4812c61d0ebddafbe842305656566ee1f4aede1e65b400`。
- Runtime Profile：`9161277ed4161237ff1804e505bad5071c9a73eca884ec92d88d55976f6afc54`；能力探针临时表清理 VERIFIED，能力证据复用自 v4。
- `<= → <` Mutation：适用 5 条，KILLED 5 条；[索引](mutation-validation-index.json)。
- 真实 Xugu 双跑：21/21 PASS；两次执行的原始返回行、列名、类型、行数和结果哈希均保存在 `artifacts/trial-runs/`；[制品索引](trial-run-index.json)含每份制品路径和 SHA-256。
- 精确整数类型：4 条 `datatype=int` 候选的两个输出键均实测为 `INTEGER`；探针哈希 `a987b266b440e751df7ad7951cfaeab0256a77b55ec25adaa68ba9e46c8a49c0`。
- Active 查询回归：30/30 PASS；本地原始制品 `artifacts/runs/query-v5-active.json`。
- Pairwise：Active 17/137；候选全部晋级后的 provisional 137/137；[覆盖摘要](coverage-summary.json)。
- [AI 技术复核](../../审核意见/XG_DB_Test_JOIN_v5_AI_Technical_Review.md)：原始行证据问题已关闭；数据库精确 build 仍交人工确认。外连接的全匹配和未匹配两类场景均有候选覆盖。

人工评审时逐条确认用例目标、SQL/Expected、覆盖 Claim、变异和双跑证据；打开 `artifacts/trial-runs/` 下对应 JSON，可直接查看 `run1.steps[].result_rows` 与 `run2.steps[].result_rows`。确认后通过 `xgtest candidate review` 记录评审引用。之后再晋级、运行晋级后完整回归并生成最终覆盖快照。本评审包不构成人工评审结论。
