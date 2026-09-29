# JOIN v4 候选 AI 技术评审

评审日期：2026-09-29。评审者：Codex（AI 技术评审）。本报告不等于独立人工评审，未写入候选的 `review_evidence` 或 `coverage_review`。

## 结论

- 21 条 Template v4 候选按当前 JOIN v2 模型口径技术通过，均已完成真实 Xugu 双跑；21 份 Trial Artifact 的 SHA-256、Contract/Profile、两次 PASS、行数与结果哈希一致。
- 5 条 `less_equal` 候选在真实 Xugu 上均杀死 `<= → <` 变异，另外 16 条不适用该变异。
- 实际系统表 `SYSDBA.SYS_DATATYPES` 显示 TINYINT/SMALLINT/INTEGER/BIGINT 的 TYPE_ID 分别为 3/4/5/6；裸小整数 JOIN 键元数据为 TINYINT，显式 `CAST(... AS INTEGER)` 后为 INTEGER。系统表只读探针 SHA-256 为 `1e30a3ecbe165579cc9e5350e015d61b8fb9ba50b233c438ddac8907c7ce255f`；4 条 `datatype=int` 候选的左右输出键均实测为 INTEGER，候选只读探针 SHA-256 为 `a987b266b440e751df7ad7951cfaeab0256a77b55ec25adaa68ba9e46c8a49c0`。原始探针分别位于 `artifacts/wsl-runtime/integer-type-system-probe-v4.jsonl` 和 `artifacts/wsl-runtime/integer-cast-probe-v4.jsonl`。
- 使用 SQLite 3.53.1 独立执行 21 条 SQL，日期字面量改写为等价 ISO 字符串；21 条输出均与 Expected 一致。此核对独立于生成器的 Expected 计算。
- 30 条 Active 查询在新 Runtime Profile 下真实回归 PASS。Active pairwise 为 17/137；加入 21 条候选后可达 137/137，但在晋级前仍属于 provisional。每条候选至少贡献 1 个其它候选不能替代的 pairwise 要求。
- 外连接的两种场景都在候选集中：全部匹配的 LEFT/RIGHT/FULL 用例覆盖对应 JOIN 类型与无 NULL 扩展结果；另有 LEFT 的 right-null、RIGHT 的 left-null，以及 FULL 的 left-null、right-null、both 用例验证未匹配行保留和 NULL 扩展。因此 `null_side=none` 用例不单独承担外连接 NULL 扩展验证。
- 本轮 Contract Set 为 `3541e2217dabc75ec9e32ad42f6d55b63e935d11dd7b759a6c59f1edf7268db8`，Runtime Profile 为 `45e7e9b320a9bc24503d214a97223018b659f24b1e0fa68e736d979bd8be4b78`。变异与 Trial 索引位于 [接受材料](../acceptance/query-generation-mvp/)。

## 逐条结论

| 候选 | JOIN / predicate / datatype / null_side / interaction | 独有 pairwise 要求数 | Mutation | 双跑 |
|---|---|---:|---|---|
| [QUERY.JOIN.0D0BBF8C](../candidates/query/join/QUERY.JOIN.0D0BBF8C.yaml) | cross / none / date / none / group_by | 4 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.203908E1](../candidates/query/join/QUERY.JOIN.203908E1.yaml) | left / less_equal / date / right / where | 4 | KILLED | PASS |
| [QUERY.JOIN.23229486](../candidates/query/join/QUERY.JOIN.23229486.yaml) | full / equality / date / both / group_by | 1 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.244FDDA1](../candidates/query/join/QUERY.JOIN.244FDDA1.yaml) | full / equality / varchar / both / where | 5 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.26B774DD](../candidates/query/join/QUERY.JOIN.26B774DD.yaml) | cross / none / varchar / none / where | 4 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.274C0E9A](../candidates/query/join/QUERY.JOIN.274C0E9A.yaml) | full / inequality / date / both / none | 6 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.2833D345](../candidates/query/join/QUERY.JOIN.2833D345.yaml) | full / less_equal / int / left / group_by | 4 | KILLED | PASS |
| [QUERY.JOIN.3B332CE4](../candidates/query/join/QUERY.JOIN.3B332CE4.yaml) | right / less_equal / varchar / left / none | 8 | KILLED | PASS |
| [QUERY.JOIN.4CEF656C](../candidates/query/join/QUERY.JOIN.4CEF656C.yaml) | full / less_equal / int / both / subquery | 5 | KILLED | PASS |
| [QUERY.JOIN.593A35D9](../candidates/query/join/QUERY.JOIN.593A35D9.yaml) | full / equality / date / none / group_by | 1 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.5C2BA314](../candidates/query/join/QUERY.JOIN.5C2BA314.yaml) | right / equality / date / left / subquery | 4 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.5F6BFA55](../candidates/query/join/QUERY.JOIN.5F6BFA55.yaml) | full / equality / date / right / subquery | 1 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.66220C62](../candidates/query/join/QUERY.JOIN.66220C62.yaml) | right / equality / date / none / group_by | 2 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.79CE12B8](../candidates/query/join/QUERY.JOIN.79CE12B8.yaml) | left / equality / date / none / group_by | 1 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.94E99B87](../candidates/query/join/QUERY.JOIN.94E99B87.yaml) | cross / none / int / none / none | 4 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.9AD85025](../candidates/query/join/QUERY.JOIN.9AD85025.yaml) | full / inequality / varchar / right / group_by | 3 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.CD4C9BF1](../candidates/query/join/QUERY.JOIN.CD4C9BF1.yaml) | left / inequality / varchar / none / subquery | 5 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.D398430A](../candidates/query/join/QUERY.JOIN.D398430A.yaml) | inner / inequality / varchar / none / group_by | 3 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.D9F1ECD9](../candidates/query/join/QUERY.JOIN.D9F1ECD9.yaml) | inner / equality / date / none / subquery | 1 | NOT_APPLICABLE | PASS |
| [QUERY.JOIN.DF308258](../candidates/query/join/QUERY.JOIN.DF308258.yaml) | inner / less_equal / date / none / where | 3 | KILLED | PASS |
| [QUERY.JOIN.E3E11FE7](../candidates/query/join/QUERY.JOIN.E3E11FE7.yaml) | right / inequality / int / left / where | 8 | NOT_APPLICABLE | PASS |

## 交人工评审确认

1. Trial Artifact 保留两次执行状态、行数和结果哈希，未保存 Xugu 原始结果行；独立 SQL 核对与真实 Runner PASS 支持本轮技术结论。需要直接观察 Xugu 行值时，应在只读会话中重跑。
2. 当前 Runtime Profile 没有精确数据库 build，无法用本轮证据证明 DB build 未漂移。若正式验收要求 build 级复现，应先补采版本信息。

## 门禁状态

AI 技术评审通过。独立人工评审、Review Evidence 记录、晋级、晋级后完整回归与最终覆盖快照仍待完成。未将这份 AI 报告冒充人工签字。
