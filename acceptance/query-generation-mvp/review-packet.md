# JOIN v4 候选评审包（v6 原始行与数据库版本证据）

状态：**等待独立人工评审**。21 条候选已完成静态校验、真实变异验证、真实双跑及 AI 技术复核，均处于 `review`。

- Model / Template / Generator：2 / 4 / 4。
- Contract Set：`c1fb2d3586a70dd627f8da950dbe900847837f48cb33ece865c0aa0ae85e911a`。
- Runtime Profile：`5ea8f183395d637fd37366173abe1722b5f6a9744f3ce5c895115dbafd068fd0`；能力探针临时表清理 VERIFIED，能力证据复用自 v5；数据库 build 通过只读 `SHOW build_time;` 记录为 `2026-05-18 12:11:00 BETA-11679_11665`。
- `<= → <` Mutation：适用 5 条，KILLED 5 条；[索引](mutation-validation-index.json)。
- 真实 Xugu 双跑：21/21 PASS；两次执行的原始返回行、列名、类型、行数和结果哈希均保存在 `artifacts/trial-runs/`；[制品索引](trial-run-index.json)含每份制品路径和 SHA-256。
- 精确整数类型：4 条 `datatype=int` 候选的两个输出键均实测为 `INTEGER`；探针哈希 `a987b266b440e751df7ad7951cfaeab0256a77b55ec25adaa68ba9e46c8a49c0`。
- Active 查询回归：30/30 PASS；本地原始制品 `artifacts/runs/query-v6-active.json`。
- Pairwise：Active 17/137；候选全部晋级后的 provisional 137/137；[覆盖摘要](coverage-summary.json)。
- [AI 技术复核](../../审核意见/XG_DB_Test_JOIN_v6_AI_Technical_Review.md)：原始行证据与数据库精确 build 均已记录；独立人工评审仍待完成。外连接的全匹配和未匹配两类场景均有候选覆盖。

人工评审时逐条确认用例目标、SQL/Expected、覆盖 Claim、变异和双跑证据；打开 `artifacts/trial-runs/` 下对应 JSON，可直接查看 `run1.steps[].result_rows` 与 `run2.steps[].result_rows`。确认后通过 `xgtest candidate review` 记录评审引用。之后再晋级、运行晋级后完整回归并生成最终覆盖快照。本评审包不构成人工评审结论。

