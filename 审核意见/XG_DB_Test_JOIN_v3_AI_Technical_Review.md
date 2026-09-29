# JOIN v3 候选 AI 技术评审

评审日期：2026-09-29。评审者：Codex（AI 技术评审）。本报告不等于独立人工评审，未写入候选的 `review_evidence` 或 `coverage_review`。

## 结论

- 21 条 Template v3 候选按当前 JOIN v2 模型口径技术通过，均已完成真实 Xugu 双跑；21 份 Trial Artifact 的 SHA-256、Contract/Profile、两次 PASS、行数与结果哈希一致。
- 5 条 `less_equal` 候选在真实 Xugu 上均杀死 `<= → <` 变异，另外 16 条不适用该变异。
- 使用 SQLite 3.53.1 独立执行 21 条 SQL，日期字面量改写为等价 ISO 字符串；21 条输出均与 Expected 一致。此核对独立于生成器的 Expected 计算。
- 30 条 Active 查询在新 Runtime Profile 下真实回归 PASS。Active pairwise 为 17/137；加入 21 条候选后可达 137/137，但在晋级前仍属于 provisional。每条候选至少贡献 1 个其它候选不能替代的 pairwise 要求。
- 本轮 Contract Set 为 `00cc4ed20a97e6f84a24137744534d414870cb4bad905dc118af472d10ce8adb`，Runtime Profile 为 `310d95205a3b6c68c014e5b19e25a70879bc60ab0411c0ecc2d0d5b17da998fb`。变异与 Trial 索引位于 [接受材料](../acceptance/query-generation-mvp/)。

## 逐条结论

| 候选 | JOIN / predicate / datatype / null_side / interaction | 独有 pairwise 要求数 | Mutation | 双跑 |
|---|---|---:|---|---|
| [QUERY.JOIN.06CC8C44](../candidates/archive/query/join-v3/QUERY.JOIN.06CC8C44.yaml) | full / less_equal / int / both / subquery | 5 | KILLED | PASS |
| [QUERY.JOIN.0CEA7F38](../candidates/archive/query/join-v3/QUERY.JOIN.0CEA7F38.yaml) | full / less_equal / int / left / group_by | 4 | KILLED | PASS |
| [QUERY.JOIN.1BF2E9E6](../candidates/archive/query/join-v3/QUERY.JOIN.1BF2E9E6.yaml) | inner / equality / date / none / subquery | 1 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.391DEC9F](../candidates/archive/query/join-v3/QUERY.JOIN.391DEC9F.yaml) | cross / none / date / none / group_by | 4 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.3D46651F](../candidates/archive/query/join-v3/QUERY.JOIN.3D46651F.yaml) | inner / less_equal / date / none / where | 3 | KILLED | PASS |
| [QUERY.JOIN.3F35E684](../candidates/archive/query/join-v3/QUERY.JOIN.3F35E684.yaml) | right / equality / date / none / group_by | 2 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.5022BD6B](../candidates/archive/query/join-v3/QUERY.JOIN.5022BD6B.yaml) | cross / none / int / none / none | 4 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.519D0056](../candidates/archive/query/join-v3/QUERY.JOIN.519D0056.yaml) | full / equality / date / none / group_by | 1 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.60A8D1C6](../candidates/archive/query/join-v3/QUERY.JOIN.60A8D1C6.yaml) | cross / none / varchar / none / where | 4 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.65C4B2F2](../candidates/archive/query/join-v3/QUERY.JOIN.65C4B2F2.yaml) | right / equality / date / left / subquery | 4 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.75B2EB65](../candidates/archive/query/join-v3/QUERY.JOIN.75B2EB65.yaml) | right / inequality / int / left / where | 8 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.88A0F362](../candidates/archive/query/join-v3/QUERY.JOIN.88A0F362.yaml) | left / inequality / varchar / none / subquery | 5 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.932B7B84](../candidates/archive/query/join-v3/QUERY.JOIN.932B7B84.yaml) | right / less_equal / varchar / left / none | 8 | KILLED | PASS |
| [QUERY.JOIN.97BB9073](../candidates/archive/query/join-v3/QUERY.JOIN.97BB9073.yaml) | inner / inequality / varchar / none / group_by | 3 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.AD2143B2](../candidates/archive/query/join-v3/QUERY.JOIN.AD2143B2.yaml) | left / equality / date / none / group_by | 1 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.BDFD053A](../candidates/archive/query/join-v3/QUERY.JOIN.BDFD053A.yaml) | full / inequality / date / both / none | 6 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.BE2862D7](../candidates/archive/query/join-v3/QUERY.JOIN.BE2862D7.yaml) | left / less_equal / date / right / where | 4 | KILLED | PASS |
| [QUERY.JOIN.CCF4F60C](../candidates/archive/query/join-v3/QUERY.JOIN.CCF4F60C.yaml) | full / equality / date / right / subquery | 1 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.D44F96D7](../candidates/archive/query/join-v3/QUERY.JOIN.D44F96D7.yaml) | full / equality / varchar / both / where | 5 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.DC20BEC4](../candidates/archive/query/join-v3/QUERY.JOIN.DC20BEC4.yaml) | full / equality / date / both / group_by | 1 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.E4191101](../candidates/archive/query/join-v3/QUERY.JOIN.E4191101.yaml) | full / inequality / varchar / right / group_by | 3 | NOT_APPLICABLE | PASS |

## 交人工评审确认

1. `datatype=int` 对应逻辑整数覆盖；常量表达式在 Xugu Trial 中可能报告为 `TINYINT`。若要求精确 SQL `INT` 类型，需要重新设计数据构造。当前按模型的逻辑类型口径技术通过。
2. `null_side=none` 的 LEFT/RIGHT/FULL 用例只有匹配行，其输出不单独证明外连接的 NULL 扩展；当前模型只要求对应 JOIN 操作符，故按现行语义技术通过。
3. Trial Artifact 保留两次执行状态、行数和结果哈希，未保存 Xugu 原始结果行；独立 SQL 核对与真实 Runner PASS 支持本轮技术结论。需要直接观察 Xugu 行值时，应在只读会话中重跑。
4. 当前 Runtime Profile 没有精确数据库 build，无法用本轮证据证明 DB build 未漂移。若正式验收要求 build 级复现，应先补采版本信息。

## 门禁状态

AI 技术评审通过。独立人工评审、Review Evidence 记录、晋级、晋级后完整回归与最终覆盖快照仍待完成。未将这份 AI 报告冒充人工签字。

本报告对应已归档的 Template v3 候选；精确 INTEGER 类型修复后的 v4 候选须按新 Contract/Profile 重新验收。
