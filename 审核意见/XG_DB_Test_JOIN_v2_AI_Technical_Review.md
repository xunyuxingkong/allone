# JOIN v2 候选 AI 技术评审

评审日期：2026-09-28。评审者：Codex（AI 技术评审）。本报告不等于计划要求的真实人工评审；没有写入任何 `review_evidence` 或 `coverage_review`。

## 结论

- 21 条候选中，**16 条按当前 JOIN v2 模型口径技术通过**；**5 条 `less_equal` 候选暂缓晋级**，需要补充 `a.k = b.k` 的边界数据并重新校验、真实双跑。
- 独立组合枚举得到 137 个可行 pairwise 要求；按当前两条 Active Claim 计数，Active 17 个，加入 21 条候选后 137 个。21 条候选无重复 assignment，每条至少有 1 个其它候选不能替代的要求。该结论依赖现有 `join_02_left` Claim 的有效性，见下文口径问题。
- 用 SQLite 独立执行 21 条 SQL，日期字面量仅改为等价的 ISO 字符串以适配 SQLite 语法；21 条输出均与 Expected 一致。此检查独立于生成器的 Expected 计算，也不替代真实 Xugu 双跑。
- 21 份 Xugu Trial Artifact 的 SHA-256、Contract/Profile、两次 PASS、行数与结果哈希逐项吻合。`where`、`group_by`、`subquery` 分别去掉关键过滤或分组后结果发生变化；输出 NULL 扩展侧与声明一致。

## 逐条结论

| 候选 | 维度：JOIN / predicate / datatype / null_side / interaction | 独有 pairwise 要求数 | 技术结论 |
|---|---|---:|---|
| [QUERY.JOIN.1587A38D](../candidates/archive/query/join-v2/QUERY.JOIN.1587A38D.yaml) | right / less_equal / varchar / left / none | 8 | 暂缓：缺等值边界 |
| [QUERY.JOIN.4C8C237C](../candidates/archive/query/join-v2/QUERY.JOIN.4C8C237C.yaml) | left / less_equal / date / right / where | 4 | 暂缓：缺等值边界 |
| [QUERY.JOIN.6D14282A](../candidates/archive/query/join-v2/QUERY.JOIN.6D14282A.yaml) | left / equality / date / none / group_by | 1 | 技术通过 |
| [QUERY.JOIN.6DDD8395](../candidates/archive/query/join-v2/QUERY.JOIN.6DDD8395.yaml) | cross / none / int / none / none | 4 | 技术通过 |
| [QUERY.JOIN.73205D44](../candidates/archive/query/join-v2/QUERY.JOIN.73205D44.yaml) | full / less_equal / int / left / group_by | 4 | 暂缓：缺等值边界 |
| [QUERY.JOIN.7483C7E8](../candidates/archive/query/join-v2/QUERY.JOIN.7483C7E8.yaml) | full / equality / date / both / group_by | 1 | 技术通过 |
| [QUERY.JOIN.844DC9C3](../candidates/archive/query/join-v2/QUERY.JOIN.844DC9C3.yaml) | full / equality / date / right / subquery | 1 | 技术通过 |
| [QUERY.JOIN.90375A83](../candidates/archive/query/join-v2/QUERY.JOIN.90375A83.yaml) | right / equality / date / none / group_by | 2 | 技术通过 |
| [QUERY.JOIN.92E8C7B5](../candidates/archive/query/join-v2/QUERY.JOIN.92E8C7B5.yaml) | full / inequality / varchar / right / group_by | 3 | 技术通过 |
| [QUERY.JOIN.95FF02CF](../candidates/archive/query/join-v2/QUERY.JOIN.95FF02CF.yaml) | full / equality / date / none / group_by | 1 | 技术通过 |
| [QUERY.JOIN.98AAF359](../candidates/archive/query/join-v2/QUERY.JOIN.98AAF359.yaml) | inner / inequality / varchar / none / group_by | 3 | 技术通过 |
| [QUERY.JOIN.9C7749FA](../candidates/archive/query/join-v2/QUERY.JOIN.9C7749FA.yaml) | inner / less_equal / date / none / where | 3 | 暂缓：缺等值边界 |
| [QUERY.JOIN.9D3FFA5C](../candidates/archive/query/join-v2/QUERY.JOIN.9D3FFA5C.yaml) | cross / none / varchar / none / where | 4 | 技术通过 |
| [QUERY.JOIN.A8062588](../candidates/archive/query/join-v2/QUERY.JOIN.A8062588.yaml) | left / inequality / varchar / none / subquery | 5 | 技术通过 |
| [QUERY.JOIN.ACD09E7C](../candidates/archive/query/join-v2/QUERY.JOIN.ACD09E7C.yaml) | full / equality / varchar / both / where | 5 | 技术通过 |
| [QUERY.JOIN.B5FB1A92](../candidates/archive/query/join-v2/QUERY.JOIN.B5FB1A92.yaml) | cross / none / date / none / group_by | 4 | 技术通过 |
| [QUERY.JOIN.D231B777](../candidates/archive/query/join-v2/QUERY.JOIN.D231B777.yaml) | full / inequality / date / both / none | 6 | 技术通过 |
| [QUERY.JOIN.EC3FEEF0](../candidates/archive/query/join-v2/QUERY.JOIN.EC3FEEF0.yaml) | inner / equality / date / none / subquery | 1 | 技术通过 |
| [QUERY.JOIN.ED774CF9](../candidates/archive/query/join-v2/QUERY.JOIN.ED774CF9.yaml) | full / less_equal / int / both / subquery | 5 | 暂缓：缺等值边界 |
| [QUERY.JOIN.F1D5075C](../candidates/archive/query/join-v2/QUERY.JOIN.F1D5075C.yaml) | right / equality / date / left / subquery | 4 | 技术通过 |
| [QUERY.JOIN.F6A1656D](../candidates/archive/query/join-v2/QUERY.JOIN.F6A1656D.yaml) | right / inequality / int / left / where | 8 | 技术通过 |

## 明确需修复

`less_equal` 的模板只构造 `左值 < 右值` 的匹配行，以及 `左值 > 右值` 的不匹配行；没有 `左值 = 右值`。对以下 5 条把 `a.k <= b.k` 改为 `a.k < b.k`，独立执行结果完全不变，因而不能检出 `<` 与 `<=` 的边界错误：

- `QUERY.JOIN.1587A38D`
- `QUERY.JOIN.4C8C237C`
- `QUERY.JOIN.73205D44`
- `QUERY.JOIN.9C7749FA`
- `QUERY.JOIN.ED774CF9`

代码修改应限于 `less_equal` 相关数据与 Expected。由于静态校验会按模板重新渲染候选，修复须升级模板版本并重新生成候选；模板源码属于当前 Contract Set，版本升级后需重建 Runtime Profile，并将全部候选重新绑定新 Contract/Profile 完成真实双跑。现有 21 份 Trial Artifact 只能保留为历史证据，不能用于修改后的晋级。

## 需要确认的覆盖口径与证据边界

1. `datatype=int` 候选在 Xugu Trial 的列元数据中是 `TINYINT`。若 `int` 表示逻辑整数类型，这与 Runtime Profile 一致；若要求精确 SQL `INT`，则需要显式 CAST 或建表数据。涉及 `QUERY.JOIN.6DDD8395`、`QUERY.JOIN.73205D44`、`QUERY.JOIN.ED774CF9`、`QUERY.JOIN.F6A1656D`。
2. `null_side=none` 的 LEFT/RIGHT/FULL 候选只有匹配行，输出与 INNER JOIN 相同。当前语义规格仅要求 SQL 中出现对应 JOIN 操作符，因此按现行模型通过；若评审要求每条用例独立证明外连接行为，需要调整模型定义或测试数据。
3. Trial Artifact 保存两次执行状态、行数和结果哈希，不保存 Xugu 原始结果行。本报告依据 Runner PASS、完整制品哈希和独立 SQL 执行核对 Expected；需要直接观察 Xugu 行值的评审人，应在只读会话中重跑对应 SQL。原始 Trial Artifact 目前只在本机 `artifacts/trial-runs/`，外部评审前需提供可核验副本。
4. 现有 Active `QUERY.JOIN_02_LEFT` 用 `b.label IS NULL` 证明右侧 NULL 扩展，但没有投影右侧连接键 `b.n`。最新计划的建议定义是“输出中右侧为 NULL 的 unmatched row”，按此可接受，因为输入 `b.label` 固定非 NULL；当前 [v2 语义说明](../docs/Query_Generation_JOIN_Model_v2.md)却写成“右键为 NULL”。若坚持键必须投影，该 Active Claim 需修复或暂不计入，当前候选集届时只能覆盖 133/137，缺 4 个 pairwise 要求。建议先统一文字口径，或让 Active Case 显式投影 `b.n` 并重新回归。
5. 21 份 Trial Artifact 的 `database_version` 全为 `null`，当前 Runtime Profile 也未记录精确 DB build；Driver 版本为 2.3.9。因而证据能绑定目标地址的哈希、数据库别名、Contract 和 Driver，但不能证明精确数据库版本未漂移。若正式验收要求 DB build 级复现，应补采版本并在新 Profile 下重跑；若 MVP 接受当前粒度，应在验收记录中明示这一限制。

## 门禁状态

本报告针对已归档的 JOIN v2 候选及其历史 Trial Artifact。v3 模板已补充 `less_equal` 等值边界，v2 候选不能代表 v3 验收；v3 候选需重新静态验证、Mutation Validation、当前 Contract/Profile 下真实双跑，再进入独立人工评审。
