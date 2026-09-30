# XG DB Test 最新提交实现质量审核与后续计划

## 审核基线

- 仓库：`xunyuxingkong/allone`
- 分支：`codex/join-model-v2`
- 当前远端 HEAD：`153ba266b05934306ee217d33be3834d5f076f69`
- 提交：`feat: address quality audit and refresh v13 acceptance evidence`
- 父提交：`98570cfdff7e3215210a5dd1132baf4e8b920ae2`
- 审核日期：2026-09-30

相对上一基线：

```text
68 files changed
+5266 additions
-653 deletions

src/              16 files
framework_tests/  11 files
acceptance/       12 files
candidates/       21 files
schemas/           2 files
```

GitHub 远端仍然：

```text
Branch protection: OFF
Required checks: OFF
Commit statuses: none
Workflow runs: none
Commit signature: unsigned
```

因此本文继续区分“仓库内技术证据”和“GitHub 独立 CI / Merge Governance”。

---

# 1. 总体结论

`153ba26` 对上一轮审核意见的响应质量较高。最重要的几项——Contract Identity 分层、AcceptanceScope、跨进程 Active 读取锁、Approval Revocation、Post-Promotion Acceptance、机器派生 Final、Release Check Evidence、ArtifactStore Protocol——都已经出现实质实现。

当前项目已经从：

```text
JOIN 证据链可靠
```

推进到：

```text
证据链 + 晋级治理 + Post Acceptance + Identity 分层
开始形成平台骨架
```

当前评价：

| 维度 | 评价 |
|---|---:|
| Evidence / Gate 严谨度 | 9.4 / 10 |
| Trial / Mutation 可复核性 | 9.3 / 10 |
| Promotion / Recovery | 9.0 / 10 |
| Post-Promotion Acceptance | 8.8 / 10 |
| Contract / Identity | 8.4 / 10 |
| Generic / Plugin 架构 | 8.0 / 10 |
| Artifact Portability | 8.1 / 10 |
| AI Control Plane 就绪度 | 7.5 / 10 |
| GitHub / Release Governance | 5.8 / 10 |
| **综合实现质量** | **8.9 / 10** |

当前 G0A 继续保持：

```text
HOLD
```

是正确的。现在的主线不应再是继续扩 JOIN，而应是完成真实 Human Review → Promotion → Post Acceptance，并继续收敛平台边界。

---

# 2. 本次真正修好的关键问题

## 2.1 Contract Identity 分层已经落地

`contract_set.py` 升级到 descriptor v2，并拆出：

```text
runtime
comparison
execution_schema
design
generator
governance
control_plane
suite
```

真正决定 Runtime Execution Contract 的只有：

```text
runtime + comparison + execution_schema
```

因此：

```text
CLI / Web / Framework Test / Governance 改动
```

不再自动导致 Runtime Profile 失效。

这解决了之前频繁出现的：

```text
改治理代码
→ Contract ID 变化
→ Profile stale
→ Trial / Mutation / Review 全部重跑
```

问题。

同时保留 v1 historical descriptor 校验，旧证据不会被“重新解释”。这一点设计正确。

---

## 2.2 AcceptanceScope 已经成为正式抽象

新增：

```text
AcceptanceScope
```

统一描述：

```text
module
feature
candidate_root
active_root
active_suite_root
model_ref
coverage_strategy
```

JOIN 当前定义为：

```text
query.join
candidates/query/join
cases/query/join
cases/query
models/query/join.yaml
```

Package、Promotion、Post Acceptance、Web 等开始通过 Scope / Plugin 路由，不再全部硬编码 JOIN 路径。

这是从“JOIN Pipeline”走向“Feature-Aware Platform”的关键一步。

---

## 2.3 FeaturePlugin 继续扩展

当前 Plugin 已经拥有：

```text
scope
generate()
static_validate()
mutation_applies()
mutated_sql()
expected_id()
```

Review 层也已经改成调用：

```text
FEATURE_PLUGINS.for_model(...).expected_id(...)
```

而不再自己拼 `QUERY.JOIN.*`。

说明通用生命周期正在真正抽离 Feature-specific 逻辑。

---

## 2.4 Promotion 中间态可见问题得到有效补救

新增：

```text
src/xgtest/core/asset_lock.py
```

实现：

```text
Publisher exclusive lock
Reader cooperating lock
```

如果 Promotion Journal 不是 COMPLETE：

```text
ACTIVE_PUBLICATION_INCOMPLETE
```

Reader 会直接拒绝加载，而不是读到半批次。

测试覆盖：

```text
跨进程 Reader 等 Publisher
Reader 等 Batch Publisher
中断 Batch 后 Loader 拒绝读取
```

当前仍是 `RECOVERABLE_BATCH`，不是原子版本切换，但一致读取能力已经显著提高。

---

## 2.5 Approval Revocation 已真正接入

新增：

```text
ApprovalService
```

统一封装：

```text
TrustStore
RevocationStore
Clock
Signature Verify
```

并接入：

```text
verify-package
preflight
promote-batch
post verifier
```

Promotion Batch 甚至会在每条 Candidate 前再次验证 Approval。

因此：

```text
Approval 中途被撤销
```

后续晋级不会继续。

这是治理层的重要增强。

---

## 2.6 CI disposition 不再写死

新增：

```text
governance-policy.json
```

当前状态：

```text
ci_disposition = DEFERRED_BY_USER
allow_release_with_ci_exception = false
```

Freeze Package 会绑定：

```text
Policy 内容
Policy byte SHA
CI disposition
```

策略发生变化会使旧 Package 失效。

这比把 `DEFERRED_BY_USER` 写死在业务代码中正确很多。

---

## 2.7 Post-Promotion Acceptance 已实现第一版

新增：

```text
post_acceptance.py
```

Post Package 绑定：

```text
Candidate Manifest
Promotion Receipt
Regression Report
Runtime Profile
Approval
Regression Build Observation
```

并验证：

```text
Manifest / Receipt / Plan Identity
Selected / Completed Candidate Set
Signed Approval
Source Candidate 已移除
Active 文件 SHA
Active Snapshot Delta
Regression Contract / Profile / Target
Regression Scope
Case Source Hash
Step IDs
所有 Step PASS
DB Build 前后观测
Active Coverage
```

这已经形成真正的 Post-Promotion Gate，而不是简单“晋级后再跑一下”。

---

## 2.8 Post Regression 已绑定数据库 Build

如果 Runtime Profile 有 DB Build，则 Post Package 必须包含：

```text
before SHOW build_time
regression
after SHOW build_time
```

并满足：

```text
before_time <= regression.started
regression.finished <= after_time
```

同时前后 Build 值一致。

这有效避免了：

```text
Profile 是 Build A
Regression 实际跑 Build B
```

的证据漂移。

---

## 2.9 Final Acceptance 已开始确定性派生

新增：

```text
generate_final_acceptance()
```

它会重新调用：

```text
verify_post_promotion_package
verify_pre_promotion_package
verify_release_checks
load_governance_policy
```

然后重新生成：

```text
status
blockers
evidence_bindings
source_state_id
```

所以历史 `final-acceptance.json` 即使手改成 PASS，也不能替代真实证据。

这基本实现了：

```text
Final JSON 不是 Truth Source
Verifier 才是 Truth Source
```

---

## 2.10 Release Checks 已升级为可复核证据

新增：

```text
release_checks.py
```

实际运行：

```text
pytest
npm run build
```

并保存：

```text
exit code
stdout/stderr
JUnit
source_snapshot_id
```

Verifier 会检查：

```text
Source 是否变化
Report / Log SHA
JUnit 结构
测试数量
失败数量
Exit Code
```

v13 当前记录：

```text
Framework: 232 passed, 1 skipped
Frontend: PASS
```

这比单纯 Markdown 记录 PASS 可靠很多。

---

## 2.11 ArtifactStore Protocol 正式出现

当前已定义：

```python
ArtifactStore(Protocol)
```

接口：

```text
put
get
verify
exists
```

LocalArtifactStore 还增加了：

```text
hard-link fallback
publish lock
atomic replace
```

上一轮“只有 Local 实现，没有抽象”的问题已经解决。

---

## 2.12 Artifact Bundle 已支持安全导入导出

新增：

```text
export_artifact_bundle()
import_artifact_bundle()
```

Import 会检查：

```text
总大小限制
Entry 数量限制
重复 Entry
Manifest
Object SHA
Object Size
Unexpected Entry
```

而且先完整验证，再写入 ArtifactStore。

本轮实际导出：

```text
62 files
bundle SHA256:
10fbb7558e1c796cb011d6893cf72d1aab370e01699b440f1e51d914bb55b653
```

并在空 Store 中做了 Roundtrip Verify。

---

## 2.13 XGR1 / XGC1 Frozen Vector 已补齐

新增固定测试向量，覆盖：

```text
NULL
Decimal
-0.0
NaN
Infinity
Unicode
Date/Time
Timezone
Binary
```

这是未来跨 Windows/Linux、甚至 Java/Go Worker 保持结果 Hash 一致的重要基础。

---

# 3. 当前 v13 真实状态

最新身份：

```text
Execution Contract:
46e6ceacf0503a315ab844929f3a287184461faa1a7c57ccbfd583d3f76d1ead

Runtime Profile:
5fbbe255381418c934372a11107f4ce628b7c492726ed64926f32389d548ef02

Manifest:
217a0ad9a300b4b9ddce671f139d48bf3c60277f73758f56e27381a859a2508f

Promotion Plan:
3ab6c67a0580b35affdc666f0610559cdb40796c8d2393b1303a03f4782911f1

Final source_state_id:
614b9cf3126964cdb58ab0db934ab6ecac54d38efaa139c9bc152fa959b3f90c
```

当前提交内状态：

```text
Framework:
232 passed / 1 skipped

Frontend:
PASS

Pre-Promotion Package:
21 / 21 verified
0 failed
0 global error
PASS

Real Trial:
21 / 21 PASS

Mutation:
5 KILLED
16 NOT_APPLICABLE

Current Active Regression:
30 / 30 PASS

Current Active Coverage:
17 / 137

Provisional:
137 / 137

Human Review:
PENDING

Promotion Preflight:
BLOCKED

Promotion:
PENDING

Post Package:
NOT EXIST

Final:
HOLD
```

当前 Final Blocker：

```text
POST_PACKAGE_INVALID
FINAL_CI_GATE_INCOMPLETE
```

与真实项目状态一致。

---

# 4. 上一轮问题修复对照

| 上一轮问题 | v13 状态 |
|---|---|
| Contract Identity 过宽 | **大幅改善** |
| CLI/Test 改动污染 Runtime Contract | **解决** |
| 外围 JOIN 硬编码 | **部分解决，明显改善** |
| Promotion 中间态可见 | **大幅改善** |
| ArtifactStore 无 Protocol | **解决** |
| Artifact 无 Bundle | **解决第一版** |
| Post verifier 缺失 | **解决第一版** |
| Final 手工汇总 | **大幅解决** |
| CI disposition 写死 | **解决** |
| Revocation 未接入 | **解决** |
| Release Checks 只是声明 | **大幅解决** |
| Cross-platform codec vector | **解决第一版** |
| GitHub CI / protection | **未解决** |
| Human Review / Promotion | **未执行** |
| Atomic ActiveManifest | **未实现** |
| Remote ArtifactStore | **未实现** |

---

# 5. 当前最重要的剩余问题

## P0：现在应该做真实 Human Review，而不是继续无限刷新证据

当前技术 Gate 已经相对稳定：

```text
21/21 Package PASS
Trial PASS
Mutation PASS
Release Check PASS
```

真正阻塞的是：

```text
ReviewEvidence
CoverageReview
Signed Approval
```

所以现在如果继续：

```text
v14 Trial
v15 Mutation
v16 Package
```

却不做 Human Review，项目会陷入“技术证据无限迭代”。

推荐当前直接进入：

```text
Human Review 21
```

然后完成第一条真正的 Formal Acceptance 闭环。

---

## P0：当前 PromotionPlan 不能直接签

当前 Plan：

```text
3ab6c67...
```

仍然是未审批快照。

Human Review 写入 YAML 后：

```text
Candidate byte SHA 改
→ Manifest ID 改
→ Promotion Plan 改
```

因此必须严格：

```text
Review
→ Re-Freeze
→ Verify
→ Build New Plan
→ Sign
```

不能签当前旧 Plan。

---

# 6. Contract 分层已经正确，但 execution_schema 仍偏粗

虽然 v2 已经解决了最大问题，但：

```text
execution_schema
```

仍包含整个：

```text
src/xgtest/core
registry
```

而 `core` 里同时存在：

```text
Execution Model
Governance Model
Manifest
Admission
Asset Lock
Evidence Model
```

所以未来改一个纯 Governance Model，只要它仍在 `core/models.py`，仍可能影响 Execution Contract。

建议下一阶段做物理拆分：

```text
core/execution_models.py
core/evidence_models.py
core/governance_models.py
core/control_models.py
```

让 Execution Contract 真正只绑定 Worker 必需类型。

该问题已经从以前的 P0 降为 P1，但还没有完全结束。

---

# 7. 新发现：多 Feature 后 Coverage Scope 会出问题

这是本次审核最重要的新架构发现之一。

当前 Scope：

```text
active_root       = cases/query/join
active_suite_root = cases/query
```

Post Acceptance 对：

```text
cases/query
```

跑全量回归，这是正确的。

但 Coverage 当前也会把：

```text
整个 cases/query 的 CoverageClaim
```

交给：

```text
JOIN model
```

现在只有 JOIN，所以没问题。

未来：

```text
JOIN
FILTER
AGGREGATE
```

同时存在后，会出现：

```text
coverage_gap(join_model, join + filter + aggregate claims)
```

可能造成 Coverage 统计错误或 Assignment 不匹配。

### 正确模型应该拆成

```text
Feature Coverage Scope
Module Regression Scope
```

例如：

```text
feature_active_root = cases/query/join
module_regression_root = cases/query
```

然后：

```text
Coverage:
只看当前 Feature

Regression:
跑整个 Module
```

这件事必须在 Filter Plugin 前修。

---

# 8. Mutation Plugin 仍假设一个 Feature 只有一个 Mutation

当前 Plugin 仍是：

```text
mutation_id: str
```

JOIN 现在只有：

```text
replace_le_with_lt
```

所以没问题。

但未来 Filter 很可能需要：

```text
eq_to_ne
and_to_or
is_null_to_not_null
```

Aggregate 也可能有多个变异规则。

因此下一版建议改成：

```text
MutationSpec[]
MutationPolicy
```

例如：

```text
plugin.mutation_specs()
```

而不是单一：

```text
plugin.mutation_id
```

这是新增第二个 Feature 前必须处理的问题。

---

# 9. Active Lock 是有效过渡，但最终仍需要 ActiveManifest

当前锁方案解决了 cooperating readers 的半批次可见。

但真实 Active State 仍由：

```text
cases/query/*.yaml
```

目录状态决定。

理想方案仍然是：

```text
ActiveManifest
```

例如：

```text
active-manifest.json
```

绑定：

```text
version
case set
case SHA
source manifest
promotion receipt
```

发布流程：

```text
构建完整新版本
→ 验证
→ 原子切换 ActiveManifest
```

Runner 永远读取一个明确版本。

这样才是真正的原子可见状态。

---

# 10. 当前 Lock 依赖所有 Reader 合作

`asset_lock.py` 已明确称为：

```text
cooperating readers
```

只要未来某处代码直接：

```python
Path("cases/query").rglob(...)
```

绕过 Loader / Repository，就仍可能读取中间状态。

所以平台层最好新增：

```text
ActiveCaseRepository / SuiteRepository
```

规定：

```text
CLI
Web
Acceptance
Runner
AI
```

都不能直接读 Active 文件系统。

---

# 11. Final Acceptance 目前没有普通 PASS 路径

当前逻辑非常安全：

```text
CI_PASS
```

不会因为 Policy 写了 PASS 就直接放行，而会继续要求：

```text
FINAL_CI_EVIDENCE_REQUIRED
```

问题是现在 `generate_final_acceptance()` 还没有真正的：

```text
CiEvidence
```

输入。

所以当前实际上：

```text
CI_PASS
→ HOLD

DEFERRED + no exception
→ HOLD

DEFERRED + explicit exception
→ PASS_WITH_EXCEPTION
```

没有：

```text
PASS
```

的正常路径。

### 建议增加 CiEvidence

至少：

```text
provider
repository
commit_sha
workflow
run_id
status
completed_at
source_snapshot_id
artifact_refs
```

只有：

```text
CI_PASS
+
Independent CI Evidence PASS
+
Source identity match
```

才允许：

```text
Final = PASS
```

---

# 12. Release Check 还缺环境身份

现在 Release Evidence 绑定：

```text
Source Snapshot
Exit Code
Log
JUnit
```

已经不错。

但还没有绑定：

```text
Python Version
Python Dependency Set
OS / Arch
Node Version
npm Version
实际 node_modules dependency tree
```

尤其前端当前执行：

```text
npm run build
```

而不是：

```text
npm ci
npm run build
```

所以本地 `node_modules` 可能与 lockfile 存在差异。

建议 Release Evidence 增加：

```text
command
cwd
python_version
dependency_snapshot
node_version
npm_version
package_lock_sha
environment_id
```

正式前端 Build 最好在干净环境：

```text
npm ci
npm run build
```

后再留 Evidence。

---

# 13. Artifact Bundle 目前只是“本地可搬运”

虽然 v13 已经成功：

```text
export bundle
fresh store import
verify
```

但 Bundle 本体：

```text
artifacts/bundles/query-join-v13.zip
```

仍在 Git Ignore 范围。

另一个开发者 `git clone` 后只会知道：

```text
Bundle 应存在
Bundle SHA 是什么
```

但拿不到文件。

所以现在的 Portable Evidence 更准确应叫：

```text
Local Portable Evidence
```

后续至少需要一个远端后端：

```text
MinIO
S3
GitHub Release Artifact
CI Artifact
```

---

# 14. Bundle Import 建议增加 Expected Bundle Identity

当前 Import 会校验包内部自洽性，但一个“自洽但不是目标版本”的 Bundle 也能被成功导入。

真正判断：

```text
这是不是 v13 指定 Bundle
```

目前依赖调用者额外比对：

```text
bundle_sha256
```

建议接口支持：

```text
expected_bundle_sha256
```

或者 Bundle Manifest 自带：

```text
bundle_manifest_id
```

并让 Acceptance Package 绑定它。

---

# 15. Governance Policy 仍缺强身份授权

当前：

```text
governance-policy.json
```

已经结构化，但：

```text
ci_decision_reference
```

仍只是字符串。

现在：

```text
allow_release_with_ci_exception = false
```

所以没直接风险。

未来如果允许：

```text
CI exception
```

建议也采用签名治理：

```text
GovernanceExceptionApproval
principal
scope
reason
source_state
expires_at
signature
```

让：

```text
Promotion Approval
CI Exception Approval
```

都属于统一 Governance 模型。

---

# 16. Post Acceptance 要区分 Feature Complete 与 Module Complete

当前：

```text
JOIN provisional 137/137
```

未来只能表示：

```text
JOIN Feature defined scope complete
```

不能直接表示：

```text
Query Module complete
```

因为 Query Module 后面还有：

```text
Filter
Aggregate
Subquery
Window
CTE
Set Operation
```

未来 CompletionEvaluator 应能输出：

```text
Feature JOIN:
DEFINED_SCOPE_COMPLETE

Query Module:
MODULE_FULL_INCOMPLETE
```

而不是看到 JOIN 137/137 就宣布整个 Query 模块完成。

---

# 17. 测试质量继续上升

本轮新增的测试很有价值：

```text
active visibility
post acceptance
portable artifacts
release checks
scope
contract layer invalidation
row codec frozen vector
```

尤其这些测试：

```text
reader waits for publisher
interrupted batch blocks loader
tampered regression fails
CI exception must be explicit
bundle corruption rejected
CLI/tests do not change runtime contract
```

都属于“攻击 Evidence / State”的测试，而不是只测试 Happy Path。

这是目前项目测试质量提升最明显的部分之一。

---

# 18. GitHub Governance 仍是明显短板

远端当前仍：

```text
protected = false
required checks = none
statuses = []
workflow runs = []
unsigned commit
```

所以出现一个明显不对称：

```text
Test Asset Promotion Governance:
越来越严格

Git Source Promotion Governance:
仍然宽松
```

正式进入：

```text
24h AI Agent
自动修复
自动 PR
```

前必须补：

```text
GitHub Actions
Protected Main
Required Checks
PR Review
```

否则 AI 可以绕过仓库 Gate 直接改源码。

---

# 19. 现在是否应该开始 Human Review？

建议：**现在就开始。**

前几轮 Evidence Contract 一直变化，Review 容易反复 stale，所以延后合理。

但 v13 已经把：

```text
Contract
Package
Promotion
Post Acceptance
Release Check
```

基本稳定下来。

继续做 v14/v15 技术重构而不 Review，收益已经开始下降。

当前正确路线是：

```text
冻结 JOIN 业务语义
→ Human Review
→ Promotion
→ Post Acceptance
```

完成第一个真实 Formal Acceptance 闭环。

---

# 20. Human Review 后哪些需要重建，哪些不需要重跑

Review 写入后必须重建：

```text
Candidate Byte SHA
Package Manifest
Manifest ID
Package Verify
Promotion Plan
Plan Hash
Signed Approval
Preflight
```

但如果没有修改：

```text
SQL
Expected
Coverage Assignment
Mutation
Execution Contract
```

则原则上不必重新跑：

```text
Real Trial
Mutation Execution
Runtime Capability Probe
```

这正是 Contract 分层后最大的收益。

---

# 21. 推荐下一阶段执行顺序

## 阶段 A：完成 JOIN Formal Acceptance

```text
A01 Human Review 21
A02 Record Review Evidence
A03 Re-Freeze Package
A04 Verify Package
A05 Build New PromotionPlan
A06 Human Signed Approval
A07 Promotion Preflight
A08 Batch Promotion
A09 Full Query Active Regression
A10 Regression Build Observation
A11 Confirm Active JOIN Coverage 137/137
A12 Freeze Post Package
A13 Verify Post Package
A14 Generate Final
```

如果 CI 仍 Deferred 且没有正式 Exception：

```text
Final 继续 HOLD
```

这是正确结果。

---

# 22. 阶段 B：AI Control Plane 前最后一轮底座

建议依次：

```text
B01 Execution Model 物理拆分
B02 Feature Coverage Scope / Module Regression Scope
B03 MutationSpec[] / MutationPolicy
B04 ActiveManifest
B05 ActiveCaseRepository
B06 Remote ArtifactStore
B07 CiEvidence
B08 Governance Exception Approval
```

---

# 23. 阶段 C：Application Services

之后再建立：

```text
ProjectService
ModuleService
FeatureService
CandidateService
AcceptanceService
PromotionService
ArtifactService
```

所有入口：

```text
CLI
Web
AI
```

统一调用 Application Service。

---

# 24. 阶段 D：AI Control Plane

然后实现：

```text
ProjectState
ModuleState
FeatureState
ModuleTestSpec
TestIntent
PreflightResult
Action
ActionResult
TestJob
JobEvent
Policy
Planner
Orchestrator
Recovery
CompletionEvaluator
```

第一条真实工作流仍建议：

```text
query.full_test
```

---

# 25. 当前最重要的三个下一步

如果只保留三件事：

```text
1. Human Review + JOIN Formal Acceptance

2. Feature Coverage Scope / Module Regression Scope
   + MutationSpec[]

3. ActiveManifest + Application Service
```

完成后再上：

```text
Planner / Orchestrator / query.full_test
```

最稳妥。

---

# 26. 最终评价

`153ba26` 比上一提交又明显前进了一步。

这次新增的：

```text
Layered Contract Identity
AcceptanceScope
Cross-process Asset Lock
ApprovalService
Post Acceptance
Derived Final State
Release Evidence
Artifact Bundle
Frozen Codec Vector
```

都属于真正的平台基础设施，而不是只为了当前 JOIN 21 条 Candidate 打补丁。

当前项目已经开始从：

```text
JOIN Test Tool
```

向：

```text
AI-operable Test Platform
```

转换。

但还不能宣布平台完成。

当前阶段判断：

```text
JOIN Test Generation:
完成度高

JOIN Evidence Pipeline:
基本完成

JOIN Formal Acceptance:
待 Human Review / Promotion / Post

Generic Feature Platform:
第一阶段完成

Application Service:
尚未完成

AI Control Plane:
尚未正式开始

Multi-Feature Query Platform:
尚未实际验证
```

---

# 27. 长期原则

继续坚持：

```text
AI 决定下一步做什么
Deterministic Core 决定事实是什么
```

并进一步明确：

```text
Markdown 不是 Truth Source
Final JSON 本身不是 Truth Source
AI 不是 Truth Source
CLI 不是 Truth Source
Web 不是 Truth Source
```

真正的 Truth 应该来自：

```text
Structured State
+
Immutable Evidence
+
Deterministic Verifier
+
Signed Governance Decision
```

最终应保证：

```text
同一个 Project State
同一组 Evidence
同一个 Policy
```

无论是人、CLI、Web、CI 还是 AI Agent，都只能得到同一个 Acceptance Result。
