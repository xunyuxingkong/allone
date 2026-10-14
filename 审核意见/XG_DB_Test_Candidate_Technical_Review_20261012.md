# XG DB Test 候选用例技术复核记录（2026-10-12）

## 1. 复核范围与结论

本记录承接 `XG_DB_Test_Latest_Status_Review_7a576bf_Product_Ready_Roadmap.md` 的候选用例门禁。本轮核查了 `candidates/query` 下 131 条候选，其中 121 条处于 `review`，10 条仍为 `draft`。

**结论：121 条候选的现有静态、真实双跑、原始行和 Mutation 证据完整且相互一致，可进入独立人工评审；不代表人工评审、签名批准、Promotion 或正式验收已完成。** `review` 是候选队列状态，不是批准状态。本记录是技术证据复核，不是外部 DeepSeek 评审，也不冒充人工签名。

## 2. 检查依据

- 121 条 `review` 候选均有静态验证证据、Trial Artifact 引用和 SHA-256。
- 逐条读取 Trial Artifact 并核对其 SHA-256 与候选 YAML 一致；试跑和两次独立执行均为 `PASS`。
- 两次执行的每个 SQL 步骤均保留 `result_rows` 字段，可从制品查看当时返回的原始行；本轮核对到 run1 与 run2 各 121 个结果行字段。
- 121 条制品均记录本次目标 build：`SHOW build_time;` 原始值为 `2026-10-08 12:11:05 BETA-Beta`，解析版本为 `BETA-Beta`，驱动版本为 `2.3.9`。
- 逐条核对 Mutation Artifact SHA、候选语义哈希和运行时 profile 标识；总计 18 项 `KILLED`、103 项 `NOT_APPLICABLE`。`NOT_APPLICABLE` 表示当前 Mutation 规则不适用于该 SQL，不等于变异被杀死。
- 对候选及现有 `cases/query` 执行重复分类：0 个无效候选、0 个重复/冲突组。

复核脚本输出：

```text
review candidates: 121
Trial run1/run2 PASS: 121 / 121
raw result_rows fields: 121 / 121 runs for each
current build observations: 121 / 121
artifact/hash/profile consistency issues: 0
Mutation: KILLED 18, NOT_APPLICABLE 103
duplicate groups: 0
```

## 3. 按功能分类

| 功能 | 已具备真实证据、待人工评审 | 仍为 draft、试跑受阻 |
|---|---:|---:|
| JOIN | 21 | 0 |
| Filter | 44 | 0 |
| Aggregate | 17 | 10 |
| Subquery | 27 | 0 |
| Sort/Limit | 12 | 0 |
| **合计** | **121** | **10** |

## 4. 需继续处理的 10 条聚合候选

### 4.1 Runtime Profile 暂不支持精确保真的 NUMERIC 返回（7 条）

这些候选的输出是 `SUM` 或 `AVG`，Xugu/当前 `xgcondb` 驱动将结果类型报告为 `NUMERIC`，但返回 Python `float`。Runtime Profile 将其标记为 lossy/unsupported，因此试跑被安全阻断。不能仅为让候选变绿而放宽类型检查。

| 候选 ID | 组合要点 |
|---|---|
| `QUERY.AGGREGATE.282E922B` | SUM / int / GROUP BY + HAVING / 有 NULL |
| `QUERY.AGGREGATE.4BC35FE0` | AVG / int / GROUP BY + HAVING |
| `QUERY.AGGREGATE.61816D89` | AVG / int / 多组全 NULL |
| `QUERY.AGGREGATE.6C89B408` | AVG / int / 空输入 |
| `QUERY.AGGREGATE.985B570B` | SUM / int / 多组全 NULL |
| `QUERY.AGGREGATE.E8082868` | SUM / int / 空分组输入 |
| `QUERY.AGGREGATE.ED52680A` | AVG / int / 单组全 NULL |

**只读诊断结果：**在当前集群直接查询 `SUM(9007199254740993, 2)` 时，数据库列类型为 `NUMERIC`，驱动返回 `float 9007199254740996.0`，而精确和应为 `9007199254740995`；SQL 端 `CAST(SUM(...) AS VARCHAR(100))` 返回精确文本 `'9007199254740995'`，`CAST(AVG(...) AS VARCHAR(100))` 返回 `'11.5'`。这证明字符串投影可保留值，但结果类型变成 `VARCHAR`，不能再证明原生 NUMERIC 返回类型。

**后续步骤：**需决定聚合用例是否只验证精确数值、允许将结果投影为精确字符串，还是必须同时验证 Xugu 原生 NUMERIC 类型。前者可通过明确版本化的模板与预期值变更实现，并重新生成/静态校验、双跑、保存原始结果和执行 Mutation；后者必须先获得驱动的精确 Decimal 映射能力。未有该设计决定前继续保持 `draft`，不放宽 Runtime Profile。

### 4.2 Xugu 对部分 NULL 的统计函数返回 E17091（3 条）

当前驱动将 `E17091: 统计函数忽略了部分空值` 作为异常抛出，Runner 因而不能把结果作为成功查询行采集。只读查询已分别复现：`MAX` 混合 NULL、`COUNT(expr)` 混合 NULL、`SUM` 全 NULL 都会报该错误。不能在没有明确产品语义的情况下把该异常忽略或伪装为 PASS。执行前过滤 NULL 虽可能得到相同部分结果，却会绕开用例所声明的 NULL 聚合语义，不能算作覆盖该行为。

| 候选 ID | 组合要点 |
|---|---|
| `QUERY.AGGREGATE.3922075B` | MAX / varchar / 重复值并含 NULL |
| `QUERY.AGGREGATE.425E5676` | SUM / int / 单组全 NULL |
| `QUERY.AGGREGATE.AAB98386` | COUNT(expr) / int / 非 NULL 与 NULL 混合 |

**后续步骤：**确认 E17091 是可配置的警告、服务端错误还是驱动的错误映射；通过只读会话保存原始异常与版本信息。若数据库执行语义可接受但驱动将警告升级为异常，应针对驱动告警映射制定修复与回归；若属于数据库规定错误，则把受影响组合明确标为不支持并调整覆盖策略。

## 5. Case Library 规模与待过门禁

- 当前正式 `cases/query` 共 30 条；没有将本轮候选计为 Active。
- 121 条候选通过证据复核后即使全部经人工审核、签名批准并 Promotion，累计也为 151 条，仍低于路线图 180 条的最低目标；至少还需 29 条非重复且完成全门禁的有效用例。
- 10 条 Aggregate 候选需先解决上节所列阻塞，不能计入已验证覆盖。
- 尚未完成的治理门禁：逐条人工评审（本轮结论可作为评审材料）、Operator 签名批准、Promotion、Promotion 后回归、正式 Acceptance/Final Report。不得将本报告或 `review` 状态当作其中任一门禁的替代。
- 本轮没有实际创建人工签名、改变 Candidate 状态、Promotion 到 Active Case Library，也没有提交或推送。

## 6. 推荐执行顺序

1. 由人工评审 121 条候选及其 Trial 原始行，优先核对 NULL/外连接边界、日期/类型表示、排序默认 NULL 顺序、子查询三值逻辑等边界结果。
2. 对 18 个 `KILLED` Mutation 查看变异前后 SQL 与结果；对 103 个 `NOT_APPLICABLE` 确认当前策略确实无可适用变异。
3. 按组织实际 signer 流程生成签名批准并验证当前 Manifest、Candidate Scope 和签名信任链。
4. 完成 Promotion、Promotion 后回归及 Acceptance；成功后再统计 Active Case 数与覆盖率。
5. 单独解决 10 条 Aggregate 阻塞，并补足至少 29 条完成全部门禁的非重复用例，使有效 Case Library 达到 180 条最低线。

## 7. 本轮技术结论的边界

本轮确认的是：候选内容与已记录的静态模型、真实 Xugu 双跑和 Mutation 制品相符，且制品可复核。它不等价于逐条由人确认业务预期，也不证明所有 Xugu 数据类型、build 或执行路径都已覆盖。真实数据库证据仅对应记录的 `BETA-Beta` build 与 `xgcondb 2.3.9`。
