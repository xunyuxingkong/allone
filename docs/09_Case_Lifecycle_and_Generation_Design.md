# Case Lifecycle & Generation Pipeline Design

> Version 1.1

## 1. 目标

定义测试用例从“生成/设计”到“正式发布资产”的完整生命周期。

---

## 2. 生命周期

```text
generated
   ↓
draft
   ↓
review
   ↓
active
   ↓
deprecated
   ↓
disabled
```

---

## 3. 状态定义

### generated

Generator 自动产生，尚未进行静态和运行验证。

### draft

已经通过静态校验，可以人工修改。

### review

已完成试跑，等待 Review。

### active

正式测试资产，可进入 Release Regression。

### deprecated

保留历史，但默认不参与执行。

### disabled

临时关闭，必须填写原因。

---

## 4. Generator Pipeline

```text
Test Model
   ↓
Coverage Gap
   ↓
Generation Strategy
   ↓
Candidate Case
   ↓
Deduplicate
   ↓
Static Validate
   ↓
Trial Run
   ↓
Review
   ↓
Active
   ↓
Git
```

---

## 5. Generation Strategy

支持：

```text
manual
template
pairwise
boundary
negative
interaction
bug
import
```

---

## 6. Provenance

自动生成 Case 必须保存：

```yaml
source: pairwise

generated_by:
  generator: join_generator
  generator_version: "1.4"
  model_id: query.join
  model_version: "3"
  seed: 1729
  strategy: pairwise
  generated_at: "2026-09-11"
```

---

## 7. Generator 不直接写 active

自动生成默认：

```text
status = generated
```

通过：

```text
validate
trial-run
review
```

后才能 active。

---

## 8. Deduplicate

至少检查：

```text
Case ID
Normalized SQL
Coverage Signature
Template Parameter Signature
```

后续可以增加语义 SQL Fingerprint。

---

## 9. Trial Run

Candidate Case 应先在指定数据库环境执行：

```text
syntax check
setup check
expected result check
cleanup check
repeatability check
```

---

## 10. Expected Result 来源

允许：

```text
manual
reference database
known result
property
```

但最终 Active Case 必须有明确 Oracle。

---

## 11. Bug Case

Bug 修复时：

```yaml
status: active
source: bug
issue: XGDB-12345
tags:
  - regression
```

并归入正常 Feature Taxonomy。

---

## 12. Disable

```yaml
status: disabled
disable_reason: "Known issue XGDB-10086"
```

禁止无原因 disable。

---

## 13. Deprecate

适用于：

```text
语法废弃
Feature 移除
Case 被更好的 Case 替代
```

建议：

```yaml
status: deprecated
replaced_by:
  - QUERY.JOIN.LEFT.000201
```

---

## 14. Case Review

Review 至少检查：

```text
功能归属
测试目的
覆盖维度
SQL/Scenario 可读性
Expected 是否可信
是否重复
是否可重复执行
Cleanup
Level
Tag
```

---

## 15. Git 工作流

建议：

```text
Generator/Author
→ branch
→ validate
→ trial-run
→ PR
→ review
→ merge
```

Merge 后：

```text
Catalog rebuild/incremental update
```

---

## 16. 生命周期门禁

Release Selector 默认：

```text
status = active
```

Nightly 可选：

```text
active + review
```

generated/draft 不应进入正式发布。

---

## 17. 生命周期统计

Dashboard：

```text
Generated
Draft
Review
Active
Deprecated
Disabled
```

可以发现：

```text
大量 draft 长期没人 review
大量 disabled 未恢复
```

---

## 18. Case Aging

后续可以统计：

```text
last_modified
last_executed
last_pass
last_fail
```

识别多年未执行或长期无效 Case。

---

## 19. Generator 与 Coverage 闭环

```text
Coverage Gap
→ Generator
→ New Case
→ Active
→ Coverage 提升
```

这是生成器存在的主要价值。

## 20. 生命周期迁移与复核失效

手写 Case 从 draft 开始；生成 Case 从 generated 开始。generated → draft 需静态校验，draft → review 需 Trial Run，review → active 需 Review 证据。
active 可直接 disabled 或 deprecated；disabled 恢复必须回到 review，通过当前语义哈希的 Trial Run/Review 后重新 active。deprecated 不自动恢复；替代用例使用 replaced_by 关联。
修改 SQL、Fixture、Oracle 或比较策略导致 semantic_hash 变化时，旧 Review/Trial Run 证据失效；发布校验要求提交匹配新哈希的证据。仅修改标题/Owner 不强制重新试跑。
生成器 seed、模板/模型/生成器版本和输入指纹必须保存；随机值与预期结果在入 Git 前固化。

## 21. Oracle 与去重证据

oracle_provenance.kind 为 manual/reference_database/known_result/property；reference、reviewer 和 evidence_hash 记录确定预期的依据。
reference_database 必须记录产品、版本、模式与已审查的语义差异；不能直接把被测版本输出自动确认为正确答案。
Trial Run 的通过证明可执行性与一致性，不独立证明 Oracle 正确。重复运行、清理恢复和失败注入检查使用 11 的验收场景。
Case ID 冲突必须失败；Normalized SQL/Coverage Signature 相同仅作为候选重复供 Review，不能自动删除具有不同 Fixture、Oracle、参数或缺陷目的的 Case。
active 默认选例由 Catalog.status 实现；generated/draft/review 不得靠遗漏 status 绕过发布门禁。

validation_evidence 的字段与必填规则由 04 §28 定义，随 effective_metadata 写入 Catalog/Bundle；Review 证据绑定语义哈希而非易变的工作区路径。
