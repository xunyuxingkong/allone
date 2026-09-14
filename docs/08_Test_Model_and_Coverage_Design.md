# Test Model & Coverage Model Design

> Version 1.1

## 1. 目标

Test Model 回答：

> 一个数据库 Feature 应该从哪些维度测试？

Coverage Model 回答：

> 当前到底覆盖了哪些维度，还缺什么？

---

## 2. 层级

```text
Domain
 ↓
Feature
 ↓
SubFeature
 ↓
Test Model
 ↓
Dimension
 ↓
Value
 ↓
Constraint
 ↓
Coverage Strategy
```

---

## 3. Test Model 示例：JOIN

```yaml
model_id: query.join
model_version: "1"

module: query
feature: join

dimensions:

  join_type:
    values:
      - inner
      - left
      - right
      - full
      - cross

  table_count:
    values:
      - 2
      - 3
      - many

  predicate:
    values:
      - none
      - equality
      - inequality
      - range
      - expression
      - function

  datatype:
    values:
      - int
      - decimal
      - varchar
      - date
      - timestamp

  null_side:
    values:
      - none
      - left
      - right
      - both

  index:
    values:
      - none
      - left
      - right
      - both

  interaction:
    values:
      - none
      - where
      - group_by
      - subquery
      - union
      - window
```

---

## 4. Constraint

例如：

```yaml
constraints:

  - if:
      join_type: cross
    then:
      predicate: none

  - if:
      join_type: cross
    exclude:
      interaction:
        - subquery
```

---

## 5. Coverage Strategy

支持：

```text
all-values
pairwise
3-wise
boundary
negative
mandatory-combination
interaction
manual
```

---

## 6. Coverage Level

每个 Value 可以声明：

```yaml
level: P0
```

例如：

```text
INNER JOIN → P0
LEFT JOIN  → P0
FULL JOIN  → P1
20-table Join → P3
```

---

## 7. Coverage Signature

作者或 Generator 在 Case 中声明 coverage；Compiler 校验后产生签名，不从 SQL 关键词自动推断测试意图。

```yaml
coverage:
  - claim_id: left-null-1
    model_id: query.join
    model_version: "1"
    assignment:
      join_type: left
      table_count: 2
      predicate: equality
      datatype: varchar
      null_side: right
      index: both
      interaction: subquery
    assertion_refs: [query-3]
```

assignment 必须声明模型全部必需维度，每个值在 Registry 内且满足约束；assertion_refs 是同一 Case 内的断言 Step ID。
一个 Case 可有多个 Claim，支持跨 Feature；claim_id 在 Case 内唯一。手工用例同样要求 Review 证明声明与实际断言对应。
无声明的 Case 为 UNMAPPED，仍可运行但不进入已映射覆盖分子；禁止把 UNMAPPED 自动记为已覆盖。

---

## 8. Coverage 类型

平台至少统计：

```text
Feature Coverage
Dimension Coverage
Value Coverage
Pairwise Coverage
Boundary Coverage
Negative Coverage
Interaction Coverage
Datatype Coverage
Level Coverage
Regression Coverage
Environment Coverage
```

---

## 9. Coverage 五个阶段

必须区分：

```text
Designed Coverage
Available Case Coverage
Selected Coverage
Executed Coverage
Passed Coverage
```

例如：

```text
设计要求 100 个组合
资产库已有 92 个
本次选择 80 个
实际执行 78 个
通过 77 个
```

这五个数字意义完全不同。

---

## 10. Coverage Gap

Gap 示例：

```text
JOIN × TIMESTAMP × NULL
缺少 Case

JOIN × WINDOW
缺少 P1 Case

FULL JOIN × VARCHAR × DUPLICATE
未覆盖
```

Coverage Gap 可以直接输入 Generator。

---

## 11. Coverage 与 Generator

```text
Coverage Gap
   ↓
Generation Strategy
   ↓
Candidate Case
```

而不是：

```text
Generator 随机生产大量 Case
```

---

## 12. Coverage 与 Release

Coverage Gate 使用与 Test Plan 绑定的 model_hash、strategy、level 与 target 范围。阈值是 0..1 的结构化数值：

```yaml
coverage_gate:
  - model_id: query.join
    model_version: "1"
    stage: passed
    strategy: all-values
    level: P0
    op: gte
    value: 1.0
```

模型不存在、约束不可满足或快照缺失为 INDETERMINATE，不是 100%。详细门禁与分母规则见 [10](10_Release_Baseline_and_Delta_Design.md)。

---

## 13. Coverage Snapshot

每个 Release Run 保存：

```text
coverage_snapshot_id
run_id
git_commit
model_version
```

用于比较：

```text
5.0
vs
5.1
```

测试覆盖是否提升或退化。

---

## 14. Test Model Version

model_id 是稳定标识（query.join），model_version 是不可变版本字符串（"1"、"2"）；model_hash 覆盖维度、值、约束、覆盖策略和点级别。
Case Claim 固定引用版本与哈希；禁止原地修改已被发布快照引用的模型。
不同模型版本的覆盖率不直接相减，必须报告 MODEL_CHANGED，并按共同点、新增点和移除点分别统计。

---

## 15. Coverage Dashboard

未来 UI 至少显示：

```text
Feature Tree
Coverage %
Missing Values
Missing Pair
Missing Interaction
P0/P1 Gap
Bug Regression Count
Environment Matrix
```

---

## 16. 最终原则

> Case 数量不是 Coverage。

真正要衡量的是：

```text
测试模型要求的能力空间
vs
测试资产实际覆盖空间
```

## 17. 覆盖点与分母算法

令 V 为所有满足约束的完整 assignment。all-values 的点为 (dimension,value)；pairwise 的点为两个不同维度的值对，仅当至少存在一个 V 中的完整扩展时才有效。
mandatory-combination 为模型明确列出的合法部分或完整 assignment；boundary/negative/interaction 必须引用显式定义的 coverage point，不能按名字猜测。
Compiler 将 Claim 投影到相应策略的点集合 C；不同 Claim/Case 覆盖同一点只计一次。点标识含 model_hash、strategy、规范化 assignment。
值或点可声明 level；组合未显式声明时采用涉及值中的最高优先级，禁止用 Case 数量反推点的要求级别。

对冻结发布目标集合 T，设计集合 D={(point,target) | point 被覆盖计划要求于该 target}。能力过滤、执行失败或缺 Case 都不能缩小 D。

| 阶段 | 分子集合；统一分母为 D |
|---|---|
| Designed | D 本身；同时报告点数量，不把它当完成率 |
| Available | D 中有 active、已审查有效 Claim 的点 |
| Selected | Available 中被本次 Plan 选中 Case 声明的点 |
| Executed | Selected 中至少一个对应 Claim 的全部 assertion_refs 实际完成的点 |
| Passed | Executed 中至少一个对应 Claim 的全部断言通过、资源恢复成功，且 CaseExecution 为 PASS 或 INFRA_RECOVERED 的点 |

同一 Claim 的多条断言必须来自同一有效 Attempt，不能拼接多个失败重试凑出通过。FLAKY 不计 Passed，单列诊断覆盖。
矩阵总分母按 point × target；各 target 另有独立分母，不能用一个平台通过替代另一个平台缺测。
无 Case 的点属于资产缺口；UNSUPPORTED 属于环境缺口；UNMAPPED 属于声明缺口，分别展示。

## 18. 模型校验与快照

校验未知维度/值、重复值、空域、约束引用、不可满足模型、不可达值、Claim 违约束和失效断言引用。约束条件区分 if/then/exclude，不允许任意 eval。
模型示例中 cross 对应 predicate=none；不存在的 blob 不应出现在当前模型约束中。所有模型 YAML 键和枚举使用固定解析规范，null 维度名改为 null_side 避免隐式 YAML 空值。
Snapshot 保存 manifest_hash、每个 model_id/version/hash、策略、D 的哈希与数量、五阶段点集或可恢复引用、UNMAPPED/UNSUPPORTED 明细。
验收例：D=100、Available=92、Selected=80、Executed=78、Passed=77，则分别报告 92%、80%、78%、77%；选中 80 不会把 Passed 改成 77/80 的“总体覆盖率”。
MVP 只实现 all-values 和 mandatory-combination；pairwise 及更复杂策略在 Phase 2 实现，未实现策略明确拒绝。

## 19. Coverage Review 与独立失效条件

显式 Claim 仍可能错误，例如 INNER JOIN 的 SQL 被声明为 LEFT JOIN。Schema/约束通过只说明声明格式合法，不能证明该功能已被实际验证。
Review 必须同时展示 SQL/Scenario、Setup/Fixture、Expected/Oracle、Coverage Assignment、assertion_refs 对应断言和精确 Model 定义；由审查人确认断言能支撑声称的覆盖。

```yaml
coverage_review:
  reviewer: query-team-reviewer
  reviewed_at: "2026-09-11T10:00:00Z"
  review_revision: "git-review-revision"
  evidence_hash: "<review-artifact-sha256>"
  review_input_hash: "<review-input-sha256>"
```

一个 coverage_review 绑定当前 Case 的完整 Claim 集合。review_input_hash = SHA-256(XGMJ1(review_input))，review_input 显式包含执行 semantic_hash、按 claim_id 排序的完整 claims（含 assignment 和 assertion_refs）、各模型的 model_id/version/hash 与 review_contract_version。
assertion_refs 在此为无序引用集合，按 Step ID 排序去重；Step 本身的执行顺序由 semantic_hash 固定。reviewer/时间/证据自身及 compiled_hash 不进入 review_input，避免循环哈希。
SQL/Fixture/Expected、Claim 值、断言引用、模型或审查规则变化均使旧证据失效；只改标题/Owner 不使其失效。不能仅绑定 Git revision 或执行 semantic_hash，否则“只改 Claim”会沿用旧审查。
同一个 PR 可以承载用例审查和覆盖审查，只要证据同时绑定两类输入，不强制再设一套审批系统。

## 20. 审查与覆盖计数的处理

active 且 coverage 非空时，缺失/过期/无法读取的证据在 validate/index/Release plan 阶段报错。统计旧快照时，不能验证的 Claim 标为 UNREVIEWED，不进入 Available/Selected/Executed/Passed 分子，不自动改写 Case 状态或缩小 Designed 分母。
无 Claim 仍为 UNMAPPED；draft/review 可以携带待审 Claim 做试跑，但不得贡献正式 Available Coverage。UNREVIEWED 与 UNMAPPED/UNSUPPORTED 分开展示。
Contract Test 要求：重复 Claim 不提高覆盖；断言引用错误静态失败；仅将 inner 改成 left 而保持 SQL 不变会使 review_input_hash 改变；未审或证据过期无法贡献正式覆盖。未来 Golden Vector 位于 framework_tests/contract/coverage/。
