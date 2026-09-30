# XG DB Test 最新提交实现质量审核与后续计划

## 审核基线

- 仓库：`xunyuxingkong/allone`
- 分支：`codex/join-model-v2`
- 当前远端 HEAD：`98570cfdff7e3215210a5dd1132baf4e8b920ae2`
- 提交：`feat: harden evidence gates and rebuild v12 review package`
- 父提交：`fce78543822423df9bfea9b898088627e7d032ee`
- 提交时间：`2026-09-30T02:34:42Z`
- 审核日期：2026-09-30
- Commit URL：`https://github.com/xunyuxingkong/allone/commit/98570cfdff7e3215210a5dd1132baf4e8b920ae2`

本次提交相对 `fce7854`：

```text
79 files changed
+7291 additions
-604 deletions

src/                     17 files
framework_tests/          8 files
acceptance/              22 files
candidates/              21 files
docs / 审核意见            4 files
```

当前远端 GitHub 状态：

```text
Branch protection: OFF
Required status checks: OFF
Commit status checks: none
PR workflow runs for commit: none
Commit signature: unsigned
```

因此，本文区分两类证据：

```text
1. 仓库内已提交的实现、测试报告、Acceptance Evidence
2. GitHub 远端独立 CI / Branch Governance
```

前者已经明显增强；后者目前仍未建立。

---

# 1. 总体结论

这次 `98570cf` 不是普通补丁，而是一次比较完整的 **Evidence Gate / Promotion Governance / Recovery / Runtime Boundary 加固提交**。

相比上一版 `6e044b7 / fce7854`，此前提出的多项关键问题已经真正进入代码：

```text
MutationValidationResult
严格 Mutation Applicability
完整 Trial Raw Row 重验
XGR1 / XGC1 行编码与语义哈希
Content-addressed Local ArtifactStore
Acceptance Package Manifest
Package Integrity Verify
Promotion Preflight
Promotion Plan
SSH Signed Approval
Recoverable Batch Promotion
QueryExecutable / Compiler
FeaturePlugin 初步抽取
Review UI Evidence 展示
LF Byte Stability
```

所以本次实现质量是明显上升的。

我的当前评价：

| 维度 | 评价 |
|---|---:|
| Evidence / Gate 严谨度 | **9.1 / 10** |
| Mutation / Trial 可信度 | **9.2 / 10** |
| Promotion / Recovery | **8.5 / 10** |
| 测试设计 | **8.8 / 10** |
| 通用架构程度 | **7.2 / 10** |
| AI Control Plane 就绪度 | **6.5 / 10** |
| GitHub / Release Governance | **5.5 / 10** |
| **综合实现质量** | **8.7 / 10** |

结论不是“可以直接 Freeze”，而是：

> **JOIN 的技术证据链已经达到较高质量，当前真正的主线应从继续补 JOIN 功能，转向完成正式人工批准、晋级后验收，以及把仍然 JOIN-specific 的外围流程抽象成平台能力。**

当前 G0A 状态继续保持：

```text
HOLD
```

是正确的。

---

# 2. 本次提交真正修好的问题

## 2.1 Mutation Evidence 从“结果字段”升级为可重新验证的执行证据

新增严格模型：

```text
MutationValidationResult
MutationCheck
MutationEvidence
```

其中 `MutationCheck` 已经约束：

```text
KILLED:
original_hash 必须存在
mutated_hash 必须存在
original_hash != mutated_hash

NOT_APPLICABLE:
不得携带 original_hash / mutated_hash
```

`record_candidate_mutation_evidence()` 现在还会检查：

```text
case_id 是否匹配 Candidate
mutation_id 是否属于 Feature Plugin
Applicability 与状态是否一致
KILLED 是否带完整执行证据
Runtime Profile 是否有效
Contract Set 是否当前
```

这基本解决了上一轮指出的“Evidence Writer 过度信任调用方”等问题。

---

## 2.2 Mutation KILLED 不再只相信 Hash，而是重新验证 4 次真实执行

适用 Mutation 当前会执行：

```text
Baseline Run 1
Baseline Run 2
Mutated Run 1
Mutated Run 2
```

并保存：

```text
原始 SQL Hash
变异 SQL Hash
完整 Result Rows
Result SHA256
Build Observation
```

`_validate_mutation_execution()` 会重新计算：

```text
Raw Rows
→ decode XGR1
→ XGC1 Semantic Hash
→ Baseline Determinism
→ Mutated Determinism
→ original != mutated
```

同时要求：

```text
baseline 状态 PASS
mutated 状态只能 PASS / FAIL
ERROR / TIMEOUT 不可冒充 KILLED
```

这是本次非常关键的提升。

---

## 2.3 NOT_APPLICABLE Gate 已严格化

上一版非 Applicable 状态仍有宽松空间，本次已经改成：

```text
FeaturePlugin.mutation_applies(case) == True
→ 必须 KILLED

FeaturePlugin.mutation_applies(case) == False
→ 必须 NOT_APPLICABLE
```

Acceptance Package 和 Promotion Gate 都会重新检查，语义正确。

---

## 2.4 Trial Artifact 已真正做到 Raw Rows 可重算

新增：

```text
src/xgtest/core/row_codec.py
```

提供 XGR1 可逆编码，目前覆盖：

```text
None
str
int
bool
finite float
NaN / +/-Inf
bytes
Decimal
datetime
date
time
```

Trial 验证不再只相信 `result_sha256`，而是：

```text
result_rows
→ decode_rows()
→ rows_sha256()
→ rows_semantic_sha256()
→ 与存储 hash 比较
```

Evidence 中的 Result Hash 因此可以由原始结果重新计算。

---

## 2.5 rowsort 已正确区分物理结果和语义结果

当前验证同时保留：

```text
Physical Result Hash
Semantic Result Hash
```

对于：

```text
comparison.mode = rowsort
```

双跑允许顺序不同，但重复行数量仍必须保持一致。

新增测试已经覆盖：

```text
rowsort reorder
duplicate count
```

这个设计正确。

---

## 2.6 Trial Index 不再允许“子集冒充全量”

`verify_trial_artifact_index()` 会重新枚举：

```text
candidates/query/join/*.yaml
status = review
```

得到真实 Scope，再核对：

```text
missing candidate
extra candidate
duplicate candidate
candidate_count
```

因此：

```text
20/21
```

不能再伪装为：

```text
20/20 PASS
```

对应测试 `test_subset_is_not_whole_scope` 很有价值。

---

## 2.7 verified_count 统计已经改善

当前已经拆出：

```text
verified_count
failed_count
failed_cases
global_errors
errors
```

未来 AI 可以得到：

```text
20 verified
1 failed
```

而不是遇到一条失败就只能得到模糊的总 FAIL。

---

## 2.8 ArtifactStore 已从普通路径文件开始转为内容寻址

新增：

```text
LocalArtifactStore
```

使用：

```text
SHA256(content)
→ objects/<前2位>/<sha256>.json
```

并具有：

```text
已存在对象重新 verify
禁止 absolute / ..
读取时验证 size + SHA256
临时文件写入
flush + fsync
再发布
```

这已经明显优于可覆盖的普通 Artifact 路径。

---

## 2.9 `.gitattributes` 解决 Byte Hash 的跨平台行尾问题

新增：

```text
artifacts/**/*.json text eol=lf
acceptance/**/*.json text eol=lf
candidates/query/**/*.yaml text eol=lf
cases/query/**/*.yaml text eol=lf
```

当前 Evidence Gate 大量依赖 byte SHA-256，因此 Windows checkout 的 CRLF 风险必须处理。本次方向正确。

---

## 2.10 Acceptance Package 已经从“散文件”进化成冻结包

新增：

```text
package-manifest.json
package-verification-v12.json
promotion-plan-v12.json
promotion-preflight-v12.json
```

Manifest 会冻结：

```text
Runtime Profile
Runtime Profile Evidence
Trial Index
Mutation Index
Coverage Summary
Candidate Set
Candidate SHA
Semantic Hash
Trial Artifact SHA
Mutation Artifact SHA
```

并通过：

```text
manifest_id = hash(manifest projection)
```

绑定成一个整体。

这已经非常接近未来 AI 需要的结构化 `AcceptanceState`。

---

## 2.11 Package Integrity 与 Promotion Readiness 已分离

当前真实结果：

```text
Package Integrity : PASS
Readiness         : WAITING_APPROVAL
Preflight         : BLOCKED
```

即使：

```text
21/21 Trial PASS
5 KILLED
16 NOT_APPLICABLE
```

也不会被错误解释成“已经允许自动晋级”。

这一点正确。

---

## 2.12 PromotionPlan 已绑定 Active Snapshot

`build_promotion_plan()` 当前把：

```text
manifest_id
Active 全部 YAML 路径 + SHA
待晋级 Candidate + SHA
Governance Policy Version
```

一起计算 `plan_hash`。

所以 Approval 签署的是：

```text
Candidate 集合
+
Active 基线
+
Manifest
```

而不是模糊的“批准这21条”。

---

## 2.13 Human Approval 已经升级为真实签名 Gate

新增：

```text
src/xgtest/generator/approval.py
```

Approval Payload 绑定：

```text
principal
decision
manifest_id
plan_hash
issued_at
expires_at
governance_policy_version
```

并使用：

```text
ssh-keygen -Y verify
namespace = xgtest-promotion
```

验证受信任 principal、签名、有效期、Manifest 和 Promotion Plan。

因此 AI 即使能记录 Review，也无法单靠自由字符串完成正式 Promotion。

---

## 2.14 单 Candidate Promote 已被限制

CLI 已要求正式晋级使用：

```text
acceptance promote-batch
+
frozen manifest
+
signed approval
+
allowed-signers trust store
```

这能防止人工单条 promote 绕过 Scope / Plan / Approval。

---

## 2.15 Batch Promotion 已具有 Resume / Journal / Receipt

新增：

```text
promotion journal
promotion receipt
OS lock
resume validation
active snapshot validation
input drift detection
destination conflict detection
```

能够处理：

```text
Active 写成功但 Candidate 未删
Candidate 已删但 Journal 未更新
重复 resume
Journal 被篡改
额外 Active 文件出现
```

当前代码将语义明确标为：

```text
RECOVERABLE_BATCH
```

而没有误称为原子事务，这是合理的。

---

## 2.16 Runtime 已开始与 Governance Asset 分离

新增：

```text
QueryExecutable
compile_query_asset()
```

Worker 接收：

```text
id
timeout
steps
```

而不再接收：

```text
coverage
generation
oracle
mutation_evidence
review_evidence
coverage_review
```

这已经落实了上一轮建议的：

```text
Asset
↓ compile
Runtime DTO
↓ Worker
```

方向。

---

## 2.17 Lifecycle 的 JOIN 硬编码明显减少

新增：

```text
FeaturePlugin
PluginRegistry
JoinPlugin
```

目前至少将：

```text
mutation applicability
mutation SQL rewrite
candidate expected ID
```

从 Lifecycle 抽出。

`lifecycle.py` 已不再直接判断 `predicate == less_equal`，也不直接拼 `QUERY.JOIN.`。

---

# 3. 当前真实 Acceptance 状态

最新 `final-acceptance.json`：

```text
Contract:
2f37cd4c97ddcf53407cbd985fb9dc68dc21ccd18626b199da9aaf54a3ff4a75

Runtime Profile:
dd656644fc3e87223cc25d9eb94cfc26e025d90d9256d2bcd9ac2d8315f67493

Manifest:
3986441afbf95625ccc195734ffa62262b1197ac256660d7f63236d03a588a82

Promotion Plan:
9ce4ff687d99b30081ae076e34e6ddda73bf4e4f101ff8af6e7c45d944cb7fab
```

提交内记录的验证结果：

```text
Framework Tests:
209 passed
1 skipped

Frontend Build:
PASS

Current Active Regression:
30 / 30 PASS

Real Xugu Double Trial:
21 / 21 PASS

Mutation:
5 KILLED
16 NOT_APPLICABLE

Package Integrity:
PASS

Candidate Human Review:
PENDING

Promotion:
PENDING_HUMAN_APPROVAL

Post-Promotion Regression:
PENDING

Current Active Pairwise:
17 / 137

Provisional after promotion:
137 / 137

Final:
HOLD
```

必须继续强调：

> **当前 Active 仍然只有 17/137。**

`provisional 137/137` 不能写成 `active 137/137`。当前仓库这一点处理正确。

另外，GitHub 当前没有 status check / workflow run，因此 `209 passed` 和 Frontend PASS 属于提交内证据，不是远端 CI 独立验证。

---

# 4. 当前仍存在的关键问题

## P0：正式 Human Review 尚未完成

当前 21 条 Candidate 仍缺：

```text
ReviewEvidence
CoverageReview
```

所以 Promotion Preflight：

```text
BLOCKED
promotable_count = 0
```

21 条均返回：

```text
CANDIDATE_PROMOTION_EVIDENCE_REQUIRED
```

这不是代码 Bug，而是 Gate 正常工作。

正确下一步：

```text
逐例 Human Review
→ record review
→ Candidate bytes 改变
→ 重新 Freeze Package
→ Verify Package
→ 重新生成 PromotionPlan
→ Human Sign 新 Plan
```

注意：

> 当前 `9ce4ff...` Plan 在 Review 写入后会失效，不能直接签署继续用。

---

## P0：Post-Promotion Verifier 尚未闭环

当前完整 verifier 仍集中于：

```text
pre_promotion
```

晋级后还缺统一：

```text
Promotion Receipt Verify
Active Set Verify
Full Regression Verify
137/137 Active Coverage Verify
Post-Promotion Package Verify
Final Acceptance Derivation
```

因此系统现在已经可以较可靠地证明：

```text
“这些 Candidate 的准入证据完整”
```

但还不能自动证明：

```text
“晋级后整个 Query 模块正式完成”
```

所以现在仍不能 G0A Freeze。

---

## P1：Batch Promotion 可恢复，但不是原子可见

当前 Promotion 是逐条写 Active，再通过 Journal 保证恢复。

它解决：

```text
Durability / Recovery
```

但还没有完全解决：

```text
Visibility Atomicity
```

项目 v12 文档也承认：

```text
Loader 扫目录
批次中间状态可能可见
```

未来 AI / Scheduler 如果在 Promotion 中途启动 Regression，可能读取到部分晋级状态。

### 推荐最终方案

```text
cases/query/.versions/<version_id>/
```

先构造完整新版本：

```text
Build
→ Verify
→ Atomic switch active-manifest.json
```

Runner 永远通过 Active Manifest 读取固定版本。

如果短期不做版本目录，至少增加：

```text
Promotion global write lock
+
Runner/Loader read lock
```

---

## P1：Contract Set Identity 仍然过度耦合

当前 Contract Descriptor 仍包含：

```text
src/xgtest/core
src/xgtest/query
src/xgtest/design
src/xgtest/generator
framework_tests/contract
framework_tests/design
framework_tests/generator
models
generators
src/xgtest/cli.py
runtime/profile.py
runtime/comparator.py
adapter/xugu.py
```

这意味着：

> 改一个 Framework Test 都可能改变 Contract Set ID。

随后会产生：

```text
Contract ID changed
→ Runtime Profile stale
→ Trial stale
→ Mutation stale
→ Review stale
→ Package stale
```

这正是短期内不断出现 v9/v10/v11/v12 Evidence 重建的重要原因。

### AI Control Plane 前必须拆分

建议至少：

```text
Runtime Contract ID
Comparison Contract ID
Execution Schema ID
Design Model ID
Generator Identity
Governance Contract ID
Control Plane Version
```

特别是：

```text
Framework Test Code
CLI implementation
Web implementation
```

不应进入 Runtime Profile Identity。

---

## P1：FeaturePlugin 只完成第一层抽取

本次 `lifecycle.py` 已明显改善，但 JOIN-specific 逻辑只是向其他文件迁移，还未从平台链路消失。

### `review.py`

仍然直接使用：

```text
QUERY.JOIN.
TEMPLATE_ID
TEMPLATE_VERSION
candidate_signature()
```

### `package.py`

仍然硬编码：

```text
candidates/query/join
scope = query.join.review
models/query/join.yaml
```

### `promotion_batch.py`

仍然硬编码：

```text
cases/query/join
candidates/query/join
models/query/join.yaml
```

### Web Read Service

仍然存在：

```text
_join_model()
candidates/query/join
```

所以当前应定义为：

```text
Lifecycle Pluginized
```

而不是：

```text
Platform Pluginized
```

下一版 Plugin / Scope 应提供：

```text
model_path
candidate_root
active_root
scope_id
expected_candidate_id
mutation_policy
coverage_strategy
review_policy
```

在 Filter Plugin 开始前，这项应完成。

---

## P1：Review Evidence 仍然是自由文本身份

正式 Promotion 已要求 SSH Signed Approval，这是巨大进步。

但：

```text
record_review(
  reviewer,
  review_reference,
  coverage_reference
)
```

仍接受自由字符串。

因此 `ReviewEvidence` 自身无法证明：

```text
reviewer 确实是对应真人
reference 确实存在
reference 状态确实 Approved
```

当前安全边界主要由最终 Signed PromotionApproval 兜底，短期可以接受。

长期建议明确：

```text
TechnicalReviewEvidence
PromotionApproval
```

如果接 GitHub Review，可绑定：

```text
PR number
review id
review state
reviewer login
commit SHA
```

---

## P1：Approval Revocation 有底层参数，但尚未接入实际流程

`verify_promotion_approval()` 支持：

```text
revoked_path
```

但当前 Package Verify / Promotion Batch 主要调用没有真正注入 Revocation Store。

所以撤销能力现在属于：

```text
底层预留
```

还不是：

```text
完整 Governance Workflow
```

建议后续集中到：

```text
ApprovalService
```

统一注入：

```text
TrustStore
RevocationStore
Clock
SignerVerifier
Policy
```

---

## P1：`ci_disposition = DEFERRED_BY_USER` 被硬编码

`freeze_pre_promotion_manifest()` 当前直接写：

```python
"ci_disposition": "DEFERRED_BY_USER"
```

这对本次状态可以成立，但对通用平台不成立。

未来真实状态可能是：

```text
CI_REQUIRED
CI_PASS
CI_FAIL
CI_NOT_CONFIGURED
DEFERRED_BY_POLICY
DEFERRED_BY_USER
```

所以该值应来自：

```text
Policy / Project State
```

而不是 Package Builder 写死。

这是一个典型 Truth Source 问题。

---

## P1：当前 Package Integrity 还不是“完整最终验收包”

Manifest 当前主要绑定：

```text
Trial
Mutation
Coverage
Runtime Profile
Candidate
```

但 Final Acceptance 还报告：

```text
Framework 209 passed
Frontend PASS
Current Active Regression 30/30
CI disposition
```

这些并没有全部进入统一可验证的 Final Acceptance Package。

因此当前：

```text
package_integrity = PASS
```

准确语义应该是：

```text
Pre-Promotion Candidate Package PASS
```

而不是：

```text
整个项目最终验收包 PASS
```

后续建议分成：

```text
CandidateAcceptancePackage
PromotionPackage
PostPromotionPackage
ReleaseAcceptancePackage
```

最终 Summary 只能由这些 verifier 派生。

---

## P1：Final Acceptance JSON 仍可能人工漂移

当前 `final-acceptance.json` 含大量状态字段，但尚未看到统一：

```text
generate_final_acceptance()
```

从所有 Evidence 确定性生成。

项目自己的 v12 Progress 也明确说明：

```text
统一最终摘要生成仍未完成
```

未来 AI 不应直接相信某个 JSON 内手填的 `PASS`。

正确流程：

```text
Structured Evidence
↓
Verifier
↓
Derived AcceptanceState
↓
render final-acceptance.json
```

---

## P1：LocalArtifactStore 还不是完整 ArtifactStore 接口

新增 LocalArtifactStore 的方向很好，但还缺：

```text
ArtifactStore Protocol
MinIOArtifactStore
S3ArtifactStore
ArtifactBundleExporter
```

目前 Raw Artifact 仍是本机状态。

Review Packet 自己也指出：

```text
仅提交索引无法复核本地未提交原件
```

这对未来：

```text
AI Worker
CI Worker
另一台测试机
Web Server
```

会成为限制。

建议统一：

```text
ArtifactStore.put()
ArtifactStore.get()
ArtifactStore.verify()
ArtifactStore.exists()
```

并支持：

```text
local
minio
s3
bundle export
```

---

## P1：GitHub CI / Branch Protection 仍然没有建立

当前远端事实：

```text
branch protected = false
required checks = none
statuses = []
workflow runs = []
```

因此仓库中的：

```text
209 passed
frontend PASS
```

仍属于本地/提交内 Evidence，不是不可绕过的远端 Merge Gate。

正式进入：

```text
main
release
24h Agent
Auto Promotion
```

前应增加：

```text
GitHub Actions
Protected Branch
Required Checks
PR Review
```

---

# 5. 本次新增的中低优先级问题

## P2：Implementation Progress 文档又出现状态陈旧

最新提交中的：

```text
审核意见/XG_DB_Test_Implementation_Progress_v12.md
```

末尾仍写：

```text
“本轮未提交或推送，工作区更新待用户审阅。”
```

但它现在已经：

```text
提交
+
推送
+
成为远端 HEAD
```

这再次证明：

> **Markdown 不能作为 Truth Source。**

建议状态文档绑定：

```yaml
as_of_commit:
generated_at:
source_state_id:
status:
```

并避免长期保存：

```text
未推送
工作区干净
服务正在运行
```

这类瞬时状态。

---

## P2：Package Verify 的 verified_count 在 Global Error 场景可能容易误读

如果只有 Package-level global error，而没有具体 Case Error，可能出现：

```text
package_integrity = FAIL
verified_count = 21
```

技术上可解释为“21 条 Case 验证成功，但包级规则失败”，但对 UI / AI 容易误解。

建议拆：

```text
case_verified_count
case_failed_count
package_error_count
```

---

## P2：LocalArtifactStore hard-link 发布应补文件系统兼容策略

当前使用：

```python
os.link(temp, destination)
```

NTFS/ext4 一般没问题，但未来放到网络盘、某些 Volume/NAS 时 hard-link 可能不可用。

建议增加：

```text
Capability Probe
```

或：

```text
O_EXCL / atomic rename fallback
```

并在 Windows/Linux CI 中覆盖。

---

## P2：XGR1/XGC1 需要正式跨平台 Test Vector

建议冻结：

```text
NULL
-0.0
NaN
+Inf
-Inf
Decimal scale
timezone datetime
binary
unicode
duplicate rows
```

并要求：

```text
Windows Python
Linux Python
未来 Java/Go Worker
```

结果完全一致。

---

## P2：前端仍有 >500KB Chunk Warning

当前 Frontend Build PASS，但 v12 文档记录了大 chunk 警告。

不阻塞主线，后续再做：

```text
route lazy loading
vendor split
```

即可。

---

# 6. 与上一轮审核逐项对照

| 上一轮意见 | 本次状态 |
|---|---|
| Mutation Result 不应接受任意 dict | **基本解决**：增加 `MutationValidationResult` |
| 非 Applicable 必须严格 NOT_APPLICABLE | **解决** |
| Acceptance 应统一 Package Verify | **大幅解决**：已有 Pre-Promotion Package |
| verified_count 失败即归零 | **解决** |
| Raw Rows 应重算 result hash | **解决** |
| QueryCase Asset / Runtime DTO 应拆 | **部分解决**：新增 QueryExecutable Compiler |
| Lifecycle JOIN-specific | **部分解决**：Lifecycle 已插件化，外围仍 JOIN-specific |
| Artifact Store 抽象 | **部分解决**：LocalArtifactStore 已落地 |
| Batch Promotion Preflight | **解决** |
| Batch Promotion 事务/恢复 | **大幅改善**：Recoverable Batch；仍非原子可见 |
| Technical Review / Human Approval 分离 | **大幅解决**：Signed Promotion Approval |
| Contract Identity 过宽 | **未解决** |
| GitHub CI / Branch Protection | **未解决** |
| Markdown 不是 Truth Source | **理念正确，但仍出现陈旧状态文本** |
| Final Acceptance machine-derived | **未解决** |
| AI Control Plane | **尚未开始，当前选择合理** |

整体来看：

> **本次提交没有继续盲目扩功能，而是在提升系统可信度，这个方向正确。**

---

# 7. 现在是否应该进入 AI Control Plane？

当前不建议直接开始：

```text
Planner / Orchestrator
```

但相比上一轮，已经明显更接近平台化阶段。

正式进入 AI Control Plane 前，建议先完成 6 个基础问题：

```text
1. JOIN 正式收口
2. Contract Identity 分层
3. Generic Acceptance Scope / FeaturePlugin
4. Atomic Active State
5. ArtifactStore Interface / Portable Evidence
6. Derived Acceptance State
```

这六项完成后，再做：

```text
TestIntent
Planner
Job
Orchestrator
```

返工概率会低很多。

---

# 8. 推荐后续实施顺序

## 阶段 A：把 v12 JOIN 真正收口

### A01 Human Review 21 Candidate

逐条核对：

```text
SQL
Expected
Comparison Mode
Coverage Assignment
Oracle
Trial Run 1
Trial Run 2
Mutation
```

记录 ReviewEvidence / CoverageReview。

### A02 重新 Freeze

Review 会改变 Candidate YAML 字节，因此必须重新：

```text
freeze-package
```

获得新的 manifest_id。

### A03 Verify Package

要求：

```text
Package Integrity PASS
21/21 verified
No global error
```

### A04 Build New PromotionPlan

重新绑定：

```text
Active Snapshot
Candidate SHA
Manifest ID
Plan Hash
```

### A05 Human Signed Approval

签署新：

```text
manifest_id
plan_hash
principal
expires_at
```

旧 `9ce4ff...` 不再沿用。

### A06 Promotion Preflight

要求：

```text
readiness = READY
blockers = []
promotable_count = 21
```

### A07 Batch Promotion

执行正式批次 Promotion，生成 Receipt，要求 21 completed。

### A08 Post-Promotion Full Regression

必须对整个 Active Query Suite 跑，而不是只跑新增 21 条。

### A09 Active Coverage

只有此时才能正式报告：

```text
Active Pairwise = 137 / 137
```

### A10 Post-Promotion Acceptance

新增正式 verifier，验证：

```text
Receipt
Active Set
Regression
Coverage
Runtime Profile
Contract
```

### A11 Final Acceptance

由代码确定性生成 FinalAcceptanceState，再决定 G0A HOLD / FREEZE。

---

# 9. 阶段 B：AI Control Plane 前置架构

## B01 Contract Identity 分层

目标：

```text
修改测试实现
不应自动导致 Runtime Profile 失效
```

建议拆：

```text
Execution Contract
Comparison Contract
Runtime Capability Contract
Design Model Identity
Generator Identity
Governance Contract
```

## B02 AcceptanceScope DTO

不要再硬编码：

```text
query.join.review
candidates/query/join
```

定义结构化：

```text
module
feature
candidate_root
active_root
model_ref
coverage_strategy
```

## B03 FeaturePlugin v2

扩展 Plugin：

```text
candidate_id()
candidate_root()
active_root()
model()
generate()
static_validate()
coverage()
mutation_specs()
review_policy()
```

让 `review.py / package.py / promotion_batch.py / web/service.py` 全部不再知道 JOIN。

## B04 Active Manifest / Atomic Publish

Runner 应读取：

```text
active-manifest.json
```

而不是实时扫描目录推断 Active State。

## B05 ArtifactStore Interface

从 LocalArtifactStore 升级为真正 Protocol，支持 Local / MinIO / S3 / Bundle。

## B06 Acceptance State Derivation

建立：

```text
CandidateAcceptanceState
PromotionState
PostPromotionState
FinalAcceptanceState
```

全部 Derived，不允许人工填写 PASS。

---

# 10. 阶段 C：Application Service

完成 B 阶段后，将：

```text
CLI
Web
AI
```

统一到 Application Services：

```text
ProjectService
ModuleService
CandidateService
AcceptanceService
PromotionService
```

原则：

```text
CLI != Business Logic
Web != Business Logic
AI != Business Logic
```

---

# 11. 阶段 D：AI Control Plane

再实现：

```text
ProjectState
ModuleState
ModuleTestSpec
PreflightResult
TestIntent
Action
ActionResult
Policy
TestJob
JobEvent
Planner
Orchestrator
Recovery
CompletionEvaluator
```

第一条真实工作流仍然建议：

```text
query.full_test
```

流程：

```text
inspect
→ plan
→ run
→ verify
→ generate missing coverage
→ mutation
→ trial
→ technical review
→ WAITING_APPROVAL
```

人工签名后：

```text
resume
→ promotion
→ full regression
→ coverage
→ acceptance
→ completion
```

---

# 12. 阶段 E：扩 Feature

JOIN 作为 Reference Plugin，然后依次：

```text
Filter
Aggregate
Subquery
CTE
Window
Set Operation
```

必须坚持：

> 新 Feature 只能新增 Plugin / Model / Template / Mutation Policy，不应往通用 Lifecycle、Package、Promotion 里继续增加 `if feature == ...`。

---

# 13. 当前不建议继续做的事情

暂时不要优先：

```text
JOIN v5 / v6 / v7 Template
更多 JOIN Predicate
Multi-Agent
LLM 直接改 SQL
AI 自动代替人工批准
复杂分布式 Scheduler
只有界面没有 Core State 的 AI 控制台
```

目前价值最高的是把：

```text
Truth
Evidence
State
Policy
Promotion
```

做成通用平台边界。

---

# 14. 下一轮提交建议拆分

`98570cf` 一次包含 79 个文件、7291 行新增，作为阶段性大提交可以理解。

后续建议拆成：

```text
Commit 1
contract identity refactor

Commit 2
generic acceptance scope + plugin v2

Commit 3
active manifest / atomic publish

Commit 4
artifact store protocol

Commit 5
post-promotion verifier

Commit 6
application services

Commit 7
AI control state model
```

每个 Commit 尽量只包含：

```text
代码
+
针对性测试
+
必要 Schema
```

Evidence Refresh 单独提交，方便 Review。

---

# 15. GitHub 工程治理建议

正式合并主分支前增加：

```text
GitHub Actions
```

至少：

```text
framework-tests
schema-contract
frontend-build
package-static-check
```

然后：

```text
Protect main
Require PR
Require checks
```

`codex/*` 工作分支仍可以高频迭代，但进入 main / release 时应有不可绕过 Gate。

---

# 16. 本次提交最终判断

`98570cf` 是目前项目中非常重要的一次质量提升。

项目已经从：

```text
“有测试生成 + 有证据文件”
```

推进到：

```text
“Evidence 可以重算
Gate 可以校验
Promotion 可以冻结
Approval 可以签名
失败可以恢复”
```

几个关键边界已经开始成立：

```text
Evidence ≠ 声明
Approval ≠ 字符串
Promotion ≠ 单文件复制
Runtime Input ≠ Governance Asset
Artifact ≠ 可随意覆盖文件
```

但仍不能宣布平台阶段完成。

最关键的剩余问题：

```text
Contract Identity 仍过宽
外围 Package/Review/Promotion 仍 JOIN-specific
Active 发布还非原子可见
Artifact Store 仍仅本地
Final Acceptance 尚未完全机器派生
GitHub CI / Branch Protection 未建立
Human Review / Signed Approval 未执行
Post-Promotion Acceptance 未闭环
```

当前最准确的项目状态：

```text
JOIN Evidence Pipeline:
接近完成

JOIN Formal Acceptance:
尚未完成

Generic Test Platform:
进入重构准备阶段

AI Control Plane:
尚未正式进入
```

---

# 17. 推荐最终路线

```text
现在
│
├─ Human Review 21
├─ Re-Freeze Package
├─ Verify Package
├─ New PromotionPlan
├─ Signed Human Approval
├─ Promotion Preflight
├─ Recoverable Batch Promotion
├─ Full Active Regression
├─ Active 137/137
├─ Post-Promotion Verify
└─ Final Acceptance
        │
        ▼
Contract Identity Split
        │
        ▼
AcceptanceScope + FeaturePlugin v2
        │
        ▼
Atomic Active Manifest
        │
        ▼
ArtifactStore Interface
        │
        ▼
Derived Acceptance State
        │
        ▼
Application Services
        │
        ▼
AI Control Plane
        │
        ▼
query.full_test
        │
        ▼
Filter Plugin
        │
        ▼
Aggregate Plugin
```

---

# 18. 长期架构原则

继续坚持：

```text
AI 决定下一步做什么
Deterministic Core 决定事实是什么
```

进一步明确：

```text
Markdown 不是 Truth Source
Final JSON 不是 Truth Source
AI 不是 Truth Source
CLI 不是 Truth Source
Web 不是 Truth Source

Verifier + Evidence + Structured State
才是 Truth Source
```

最终目标应是：

```text
任何人
任何 CLI
任何 Web
任何 AI
```

面对同一个：

```text
Project State + Evidence
```

都只能得到同一个：

```text
Acceptance Result
```

这才是后续平台真正的核心价值。
