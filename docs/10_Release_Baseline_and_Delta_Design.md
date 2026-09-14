# Release Baseline & Delta Analysis Design

> Version 1.1

## 1. 目标

数据库发布测试不能只输出：

```text
10000 PASS
20 FAIL
```

更重要的是回答：

```text
相比上一版本，发生了什么变化？
```

---

## 2. Baseline

每个 Release Plan 可以声明：

```yaml
baseline:
  run_id: release-5.0.3-final
```

或：

```yaml
baseline:
  version: 5.0.3
  selector: latest_successful_release
```

---

## 3. Delta 分类

差异使用正交字段，不强制一个枚举覆盖所有信息：

| 维度 | 枚举 |
|---|---|
| membership_delta | COMMON / NEW_CASE / REMOVED_CASE / NEWLY_SELECTED / NOT_SELECTED / TARGET_ADDED / TARGET_REMOVED |
| case_delta | UNCHANGED / METADATA_CHANGED / CASE_CHANGED |
| context_delta | COMPARABLE / ENVIRONMENT_CHANGED / RUNTIME_CHANGED / MODEL_CHANGED / UNKNOWN |
| outcome_delta | NEW_FAILURE / FIXED / PERSISTENT_FAILURE / UNCHANGED_PASS / FLAKY_CHANGED / UNSUPPORTED_CHANGED / INCOMPLETE_CHANGED / NOT_COMPARABLE |

NEW_CASE/REMOVED_CASE 依据冻结的资产清单判定，不能仅因某次没有选中就推断新增/删除。
CASE_CHANGED 或不可比上下文的样本默认 outcome_delta=NOT_COMPARABLE，保留原始前后状态；不计严格 NEW_FAILURE。
如显式批准变更维度进行比较（例如数据库版本升级），须在 Plan.allow_changes 声明并记录比较策略。

---

## 4. New Failure

在 COMMON、语义未变且上下文可比的集合内，Baseline PASS/INFRA_RECOVERED，Current FAIL/ERROR/TIMEOUT → NEW_FAILURE。
同时按 failure_type 分开 product_failure（TEST_*）、infrastructure_failure（INFRA_*）和 framework_failure（FRAMEWORK_*/FIXTURE_*）；不得把网络故障直接解释为数据库回归。
Baseline FLAKY 或 Current INCOMPLETE 不进入严格新增失败，分别归入稳定性/完整性差异并影响门禁。

---

## 5. Fixed

可比集合中，Baseline FAIL/ERROR/TIMEOUT，Current PASS/INFRA_RECOVERED → FIXED；按前次 failure_type 区分产品修复与环境/框架恢复。
Baseline 不可比、缺结果或 FLAKY 不能算确定修复。

---

## 6. Persistent Failure

可比集合中前后均 FAIL/ERROR/TIMEOUT → PERSISTENT_FAILURE。
Failure Signature 相同仅说明候选相似失败，不证明同一根因；保存 signature_changed、主失败与 Cleanup 失败明细。

---

## 7. New Case

当前资产清单有、Baseline 资产清单无为 NEW_CASE。可由新增 Feature/Regression、补覆盖或 Generator 产生。
同一资产先前存在但没被选择，应记 NEWLY_SELECTED；不能通过选例差异夸大新增用例数。

---

## 8. Removed Case

Baseline 资产清单有、当前资产清单无为 REMOVED_CASE；保留删除/替代原因。
仍在资产库但 deprecated/disabled、selector excluded 或 version unsupported，分别记录 lifecycle_delta、NOT_SELECTED 或 UNSUPPORTED_CHANGED。
资产清单缺失时 membership_delta 不做新增/删除推断，并将相应分析置为 UNKNOWN。

---

## 9. Case Version

先按稳定 case_id 配对，再比较 semantic_hash 与 compiled_hash：

- semantic_hash 相同且 compiled_hash 相同：UNCHANGED。
- semantic_hash 相同而 compiled_hash 不同：检查有效 Metadata/工具差异，通常为 METADATA_CHANGED；运行上下文变化仍须单独校验。
- semantic_hash 不同：CASE_CHANGED，默认不作为产品回归可比样本。

不能因标题变化丢失所有对比，也不能因 Case ID 不变忽略 Oracle/Fixture 已改变。Hash 定义见 [11](11_Execution_Consistency_and_Validation_Contract.md)。

---

## 10. Environment Normalization

跨 Run 不能依靠物理 environment_id 或任意“最近 Run”配对。
采用逻辑目标的 comparison_key：OS/arch/topology/mode/storage profile/配置及数据集指纹，并核对 DB build、Driver/Adapter/Runner/Canonical 版本。
发布升级通常仅允许 database_version/database_build 作为实验变更维度，其余变化需显式 allow_changes 或标为 NOT_COMPARABLE。
每个 Baseline target 至多匹配一个 Current target；歧义或属性缺失不得任意选一个，要求显式 target mapping 或记 UNKNOWN。
环境探测值和声明不一致时，拒绝执行或标明环境漂移，不允许更新快照掩盖差异。

---

## 11. Matrix Delta

例如：

| Case | 5.0 x86 | 5.1 x86 | 5.1 ARM |
|---|---|---|---|
| JOIN.001 | PASS | FAIL | PASS |

可以直接发现：

```text
版本差异
架构差异
```

---

## 12. Release Summary

报告先显示门禁、完整性和可比性，再显示结果数量。

```text
Expected CaseExecution  100000
Executed                 99890
PASS                     99700
INFRA_RECOVERED              40
FAIL                       100
ERROR                       20
TIMEOUT                     20
FLAKY                       10
SKIP                        50
INCOMPLETE                  60
CANCELLED                    0
```

上述状态计数合计 100000；Executed 中 ERROR 是否计入由第 21 节定义，本例 20 ERROR 均具有有效业务阶段结论。
Delta 报告另列 comparable_count、CASE_CHANGED、context_changed、New Failure（按类别）、Fixed、Persistent Failure、New/Removed/Not Selected；不同维度不能直接相加当总数。

---

## 13. Quality Gate

阈值为结构化数据；比率 value 在 0..1，计数为非负整数，op 为 eq/lt/lte/gt/gte：

```yaml
quality_gate:
  p0_execution_rate: {op: gte, value: 1.0}
  p0_pass_rate: {op: gte, value: 1.0}
  new_failure: {op: eq, value: 0}
  max_flaky: {op: lte, value: 5}
  unsupported_rate: {op: lt, value: 0.01}
```

每个门禁结果为 PASS/FAIL/INDETERMINATE/NOT_APPLICABLE，附实际分子、分母、阈值、样本范围和原因。
发布仅在 Run=COMPLETED 且所有必需门禁 PASS 时通过。零分母为 NOT_APPLICABLE，必需门禁的 N/A 不自动通过。
INCOMPLETE 或基线/模型证据不足不能靠 new_failure=0 放行；发布要求完整性门禁和可比性检查同时有效。

---

## 14. Coverage Delta

同模型 hash、策略、目标映射和分母范围可直接比较覆盖率百分点差异。
模型变化时标 MODEL_CHANGED，并分别报告共同覆盖点的变化、新增设计点、移除设计点、未映射声明；禁止直接用新旧不同分母做“覆盖提升”结论。
Coverage 五阶段定义与点去重规则统一使用 [08](08_Test_Model_and_Coverage_Design.md)，本模块不实现第二套计算。

---

## 15. Failure Signature

用于判断：

```text
Persistent Failure
```

是否为相似失败候选，根因仍需证据确认。

Signature 应基于：

```text
failure_type
error_code
normalized_message
failing_step
normalized_stack
```

---

## 16. Baseline 选择规则

优先级：显式 run_id > 显式 version/selector > 同分支且符合比较目标的最近锁定 Release > 同环境最近锁定成功 Full Regression。
显式选择无效时直接报错，不静默换基线。自动选择必须唯一、已定稿锁定、Run 收敛且必需质量门禁通过，并记录选择理由。
初次发布没有 Baseline 时仍可运行测试和绝对门禁；Delta 为 NOT_APPLICABLE，Plan 必须显式声明首次发布策略，不能伪造“新增失败为零”。

---

## 17. Baseline 不可变

作为 Release Baseline 的 Run：

```text
必须锁定
```

禁止后续重写快照、统计分母与门禁。原始迟到事件可追加到审计区，但不更新锁定投影。需要纠正时生成新的 Run/发布快照，显式关联 supersedes。

---

## 18. Delta API

后续可提供：

```text
GET /runs/{run}/delta/{baseline}
```

用于：

```text
Web
CI
Release Dashboard
```

---

## 19. 发布报告重点

最终 Release Dashboard 首页应该优先展示：

```text
New Failure
P0/P1 Quality Gate
Coverage Delta
Persistent Failure
Flaky
Environment Health
```

而不是只展示总通过率。

---

## 20. 最终原则

> Release Test 的价值不只是告诉我们“这次是否通过”，更重要的是告诉我们“相比上一版本，产品质量发生了什么变化”。

## 21. 统计口径与防止分母漂移

Plan 首先定义发布必需范围（Feature/level/model/targets），再记录 Case 选择与合法排除。范围变化必须与 Baseline 报告 scope_delta；不能把排除 P0 当作测试通过。
对每个级别 l，N_l 为能力过滤、环境分配之前冻结的 expected_executions 数量。环境不支持、缺环境、取消和未执行都保留在 N_l。
Executed_l 是有一次业务测试阶段有效完成结论的 CaseExecution 数；包括 PASS/FAIL/TEST_TIMEOUT，以及 primary_status 为业务有效结论但 Cleanup 失败导致的 ERROR；仅连接失败、Fixture Setup 失败、LOST 或未开始不计。
Passed_l 仅计最终 PASS/INFRA_RECOVERED 且全部业务断言通过与资源恢复成功的 CaseExecution；FLAKY、Cleanup ERROR 和 INCOMPLETE 不计。

```text
execution_rate_l = Executed_l / N_l
pass_rate_l = Passed_l / N_l
unsupported_rate = SKIP(reason=UNSUPPORTED) / N_all
```

可另显示 Passed/Executed 作为执行后通过率，但必须注明 conditional_pass_rate，不能代替发布 pass_rate。
重试只影响 Attempt 数，不增加 N 或执行/通过次数。max_flaky 可作为额外限制，不覆盖 P0 100% 的严格通过要求。
例：100 个 P0、20 unsupported、80 PASS → execution_rate=80%、pass_rate=80%、unsupported_rate=20%；即使执行后通过率 100%，P0 门禁仍 FAIL。

## 22. 不可比与完整性门禁

new_failure 仅在完整可比样本中计算。缺基线、事件未收齐、目标匹配歧义或要求范围内存在未裁决差异时，该门禁不能 PASS。
Case/环境/模型变化不自动代表失败，但必须给出经审查的变更归类或豁免证据并冻结到 Plan；否则相关必需比较门禁 INDETERMINATE。
INCOMPLETE>0、Run FAILED/CANCELLED 或必要资产缺失时发布阻断。豁免必须有范围、原因、责任人、有效期和引用，报告仍展示原始失败/缺测，不修改分母或原始结果。

## 23. INFRA_RECOVERED 独立门禁

采用可配置基础设施健康门禁，避免大量基础设施失败重试后通过被产品通过率掩盖。两个字段均可使用，同时配置时都必须通过；未配置则只报告指标，不隐式采用零容忍策略。

```yaml
quality_gate:
  max_infra_recovered: {op: lte, value: 5}
  infra_recovered_rate: {op: lt, value: 0.01}
```

上述阈值为配置示例，不是所有项目的默认值。零容忍发布可显式将 max_infra_recovered.value 设为 0。
R = 最终 INFRA_RECOVERED 的 CaseExecution 数，N = 第 21 节过滤前冻结的 expected_executions 数。infra_recovered_rate = R/N；max_infra_recovered 的实际值为 R。重试次数不会重复增加 R。
同时报告各 target 的 R/N、INFRA_* Attempt 总数及未恢复数量；单一总比例可能掩盖某个目标环境不稳定，若 Plan 要求目标级门禁，使用该目标自己的冻结分母。
N=0 的比例为 NOT_APPLICABLE；结果缺失或 Run 未收敛时为 INDETERMINATE；均不能让必需门禁自动通过。
INFRA_RECOVERED 继续计入既有 Passed 分子；基础设施门禁独立决定发布是否允许，两者不覆盖对方。例：1000 个目标执行最终全部通过、其中 20 个 INFRA_RECOVERED，产品通过率 100%，基础设施恢复率 2%，示例中的两个基础设施门禁均 FAIL。
不能靠扩大未执行集合稀释恢复率：execution_rate、完整性与基础设施门禁需同时检查。基础统计从 Phase 1 保存，完整发布门禁按既定 Phase 6 实现。
