---
document_type: code_review_and_implementation_design
as_of_commit: fce78543822423df9bfea9b898088627e7d032ee
implementation_commit: 6e044b7bbc49d75fa90124997bf0d27e28af08f9
reviewed_on: 2026-09-29
document_status: proposed
source_review: XG_DB_Test_Latest_Review_and_Next_Plan_fce7854.md
supersedes: null
implementation_status: not_started_by_this_document
ci_disposition: deferred_by_user
---

# XG DB Test 复核意见与优化实施设计

## 1. 结论和适用范围

最新评审对 Mutation Evidence、Review Hash、JOIN 耦合及平台化方向的判断大体成立；但“技术层已经足够，只剩人工评审和晋级”需要修正。当前真实样本有效，不代表准入校验已经覆盖所有错误输入。正式晋级前应先修复下面已经复现的证据校验缺口。

本文件给出设计和实施顺序，不代表已经实现。此次仅审查代码、读取现有证据并在临时目录复核错误路径，没有修改正式候选、记录真实人工审批或执行正式晋级。原评审文档保持原样。

沿用用户已经给出的决定：本轮暂缓 PR/GitHub CI，后续可执行工作无需再等待 PR。记录为 `DEFERRED_BY_USER`，不把 CI 写成 PASS；人工评审并未因此豁免。

### 1.1 基线事实

| 项目 | 当前结果 | 证据与边界 |
|---|---|---|
| Git HEAD | `fce7854` | 本轮通过 Git 实际读取；该提交仅增加原路线文档 |
| 实际代码提交 | `6e044b7` | Mutation Evidence、Promotion Gate、Trial Index Verifier 已存在 |
| Contract Set | `b60dfa9c8aaacbb0f435053efaff95501e3ed2078773fbcc47d2f87d00244d6c` | 本轮重新计算与索引一致 |
| Runtime Profile | `45b562cd11cd74e08bc0d389f334b738c2a9dec475a8bb6c3add1ae973dd2079` | `artifacts/runtime-profile-v9.json` |
| 真实候选 | 21 条 `review` | 不是 Active，也没有正式 Human Review |
| Trial Index | 当前校验器 21/21 PASS | 本轮执行；只证明现有校验规则通过 |
| 原始结果行 | 42 个 Trial 步骤全部重算哈希一致 | 本轮从 JSON 读取，调用当前 `rows_sha256` 重算，0 差异、0 解码错误 |
| Mutation | 5 KILLED、16 NOT_APPLICABLE | 已存证据的结果，本轮没有重新连接数据库执行 Mutation |
| Active Coverage | 17/137，缺 120 | 当前结构化覆盖记录；候选加入后的暂定值为 137/137 |
| Framework / 前端构建 | 172 passed、1 deselected；构建 PASS | 前一轮记录，本轮没有重跑整套测试或构建 |
| Active 真实回归 | 30/30 PASS | 已存 v9 报告，本轮没有重新执行数据库回归 |
| Final Acceptance | HOLD | `acceptance/query-generation-mvp/final-acceptance.json` |
| Git 制品规模 | 77 个文件、226,616 字节，约 221 KiB | 本轮统计 Git 已跟踪的 `artifacts/` 工作区文件；不是全部 Git 历史或全部被忽略文件的体积 |

不能从“存在 build 字段”推出“每次执行都实时确认了数据库 build 没有变化”；也不能从“已存 172 项测试通过”推出新 Gate 的错误路径已经有覆盖。

## 2. 对最新评审 13 项建议的校准

| 原章节 | 核实结论 | 优化后的处理意见 |
|---|---|---|
| 3.1 文档落后 | 成立 | 加基线与历史状态；可生成的状态从结构化检查输出，不手工维护多份 PASS |
| 3.2 Lifecycle JOIN 耦合 | 成立 | 当前可作为 JOIN 实现；扩第二个 Feature 前抽接口，不要求先迁移所有目录 |
| 3.3 Mutation JOIN 硬编码 | 成立 | 先落实适用性、结果模型和证据验证，再抽通用 Executor；不能只把字符串替换规则搬到 YAML |
| 3.4 非适用 KILLED 可过 | 成立 | 适用性与结果状态严格配对；未知或重复 mutation_id 均拒绝 |
| 3.5 Writer 信任调用方 | 成立且比描述更严重 | 实测外来 case_id、缺失两个结果哈希的 KILLED 能写入并在隔离样本中晋级；严格 DTO 本身也不能证明真实执行 |
| 3.6 完整 Acceptance Gate 缺失 | 成立 | 提前到正式晋级之前；补集合完整性、阶段、Manifest 和统一校验，不仅拼接多个索引 |
| 3.7 失败统计归零 | 成立 | 分别输出通过用例数、失败用例数、全局错误；全局失败不能掩盖逐例结果 |
| 3.8 原始行重算哈希 | 成立 | 当前 42 步实际一致，但 Verifier 未强制检查；需复用 XGC1，明确有序与无序语义 |
| 3.9 Asset/Runtime DTO 拆分 | 方向成立 | 渐进引入 Compiler 和兼容 Loader，避免一次性重写全部资产和 Worker 协议 |
| 3.10 人工评审软门禁 | 成立 | 定义批准者和可信签发入口；`approval_type=human` 或 PR 字符串本身不是身份验证 |
| 3.11 Contract 耦合过重 | 成立 | 连测试文件和 CLI 改动也能使 Profile 过期；要设计依赖清单与迁移，不能靠减少哈希字段掩盖失效 |
| 3.12 Artifact 全进 Git | 增长风险成立，当前紧迫性被高估 | 先解决字节稳定、不可变引用和本地存储接口；暂不部署 MinIO/S3，不删除既有证据 |
| 3.13 Batch Promotion | 成立 | Preflight 只能降低中途失败，不能提供事务性；另需锁、快照校验、发布点和恢复日志 |

原文顺序还有三处矛盾：

1. 一方面指出 Gate 仍可能接受错误 Evidence，另一方面建议立即做 Human Review/Promotion。应该先修 Gate、重建最后一轮证据，再请人审稳定快照。
2. 将 Human Approval Contract、Policy Engine 放在 Orchestrator 之后。批准边界、允许动作和失败状态必须先定义，执行器从第一版就服从它们。
3. 先 G0A Freeze，再立刻拆 Contract Identity。若已计划近期改变契约，应先保持候选状态完成分层；若已 Freeze，则以新版本迁移，不能修改已发布契约的含义。

## 3. 本轮新增或进一步确认的问题

以下 P0 表示“正式准入前应修复”，不是说已经观察到数据库结果错误。临时样本中重新计算外层哈希，是为了检查 Gate 的内容规则；不意味着哈希机制能够抵御拥有全部仓库写权限的攻击者。

### F01 · P0：Windows 检出可能破坏制品字节哈希

证据：仓库未发现 `.gitattributes`，本机 `core.autocrlf=true`。Trial/Mutation 的 SHA256 是对实际文件字节计算的，见 [lifecycle.py](../src/xgtest/generator/lifecycle.py) 137–141、262–266 行。

对首个已提交 Trial 执行只读 `git cat-file --filters HEAD:<artifact-path>`，模拟 Git 检出过滤后，内容出现 CRLF，SHA256 不再等于 Index。当前工作区直接运行校验仍 PASS，因而日常本机测试不会自动发现此问题。

修复设计：

- 对需要按字节校验的 JSON 制品明确固定 UTF-8/LF，配套 `.gitattributes` 和所有 Writer 的显式字节序列化。
- 明确 Byte SHA256 与 Semantic Hash 的不同用途；不能在读取时任意归一化字节后仍称为“原始文件 SHA256”。
- 加 Windows `autocrlf=true` 与 Linux 检出验证。只对受影响路径处理，禁止顺手重写全仓库行尾。
- 若规范化改变了正式制品字节，必须重新生成绑定链和使旧审批过期。比较原始 blob 后再决定哪些无需变更，不能一概声称不影响证据。

### F02 · P0：Trial Index 缺少被验收集合的约束

证据：[acceptance.py](../src/xgtest/generator/acceptance.py) 65–83、160–167 行。当前仅检查 `candidate_count == len(entries)`，随后循环索引中的条目。

实测：将索引中的 candidates 清空并把两个计数设为 0，返回 PASS；保留 1 条、同时调整计数，也返回 PASS。当前 21 条完整记录没有错误，但函数不能证明“整批 21 条都被验证”。

修复设计：使用 `AcceptanceScope` 或 Manifest 固定被验收的 `case_id + semantic_hash` 集合，与 Index 做集合等值比较。报告 missing、extra、duplicate。不能永久硬编码 21；允许明示的单例检查，但输出必须带 `scope=single_case`，不得被当作整包通过。

### F03 · P0：Profile 只读 JSON，没有验证其自身身份

证据：[acceptance.py](../src/xgtest/generator/acceptance.py) 59–80 行直接 `json.loads` 并读取 ID；已有的 [models.py](../src/xgtest/core/models.py) 526–546 行能够验证 Profile Identity，当前函数没有调用它。

实测：在临时 Profile 中把 `identity.driver.version` 改成 `[99,99,99]`、保留旧 ID，Verifier 返回 PASS；对同一临时文件调用 `load_profile()` 会失败。

修复设计：统一使用 `load_profile()`；验证 Probe 引用及其 SHA，要求本验收范围规定的 DB version/build 字段非空。顶层 JSON 为 `[]` 等合法 JSON 但错误结构时应返回结构化 FAIL；当前实测抛出 `AttributeError`。所有错误输入都不得导致“异常退出代替失败报告”。

### F04 · P0：Trial 的 Writer、Acceptance、Promotion、Web 规则不一致

证据：[lifecycle.py](../src/xgtest/generator/lifecycle.py) 281–397 行；[acceptance.py](../src/xgtest/generator/acceptance.py)；[service.py](../src/xgtest/web/service.py) 60–118 行。三处重复维护 Trial 投影。Promotion 重算外层哈希，但没有独立要求两次报告都 PASS、投影相等和原始行存在。

隔离复现：复制真实候选/制品到临时目录，修改 run2 为 FAIL，重算其外层绑定并使用明确标注为测试的评审引用，`promote_candidate()` 仍接受。两个 run 的原始行删除后重算绑定，也能被接受。正式候选未变动。

修复设计：抽 `validate_trial_evidence()` 纯函数，由所有入口共用。校验身份、步骤集合与候选一致、每步状态、双跑语义一致、原始行完整度、结果哈希、Profile 和 Contract。Promotion 必须亲自调用，不能依赖调用者事先运行 Verifier。

Trial 路径在 Promotion 中还只有词法检查；对齐 Acceptance/Web 的 resolve 后根目录包含检查，处理符号链接/junction 越界。错误 JSON/报告结构使用严格模型，避免 KeyError/AttributeError 泄漏为不明失败。

### F05 · P0：原始行与步骤 result_sha256 未交叉校验

证据：[acceptance.py](../src/xgtest/generator/acceptance.py) 135–158 行校验行数与外层投影哈希，没有把原始行编码后重算步骤哈希。

隔离复现：同时修改两个 run 的一行值，保留旧 `result_sha256`，更新外层 SHA/Trial Hash/引用，Verifier 返回 PASS，Promotion 也接受。说明两个字段各自被保留，却没有验证它们表达同一个结果。

修复设计：复用 [comparator.py](../src/xgtest/runtime/comparator.py) 的 XGC1 编码规则。定义版本化 Typed Row Codec，明确 DATE/TIMESTAMP、Decimal、Bytes、NULL、非有限浮点的可逆表示；禁止用 `str(value)` 或另一个 JSON 哈希代替执行器的规范编码。

现有 JOIN 的 42 个步骤可直接用当前编码器重算，均一致。其他类型是否可直接由 JSON 恢复必须逐类验证，不能从这 42 步推断全部类型已支持。

### F06 · P0：Mutation 结果跨候选误绑定，且 KILLED 缺乏内容约束

证据：[lifecycle.py](../src/xgtest/generator/lifecycle.py) 228–278、336–371 行；[models.py](../src/xgtest/core/models.py) 308–325 行。

实测：对复制的 less_equal 候选传入 `case_id=FOREIGN.CASE`、`status=KILLED` 且没有 original/mutated 哈希，Writer 用目标候选 ID 重写了制品并接受；临时样本随后可晋级。非适用候选也允许 KILLED；Gate 未严格约束唯一 mutation_id 集合，Mutation Artifact 的 policy_version 也未与 Evidence 逐项比较。

修复设计：

1. 定义严格 `MutationValidationResult`，在写盘前验证 case_id、semantic_hash、执行上下文、策略版本和适用性。
2. applicable 必须符合策略；本轮 required mutation 为 KILLED，not applicable 必须是 NOT_APPLICABLE。
3. 对本轮 `must_change_result` 策略，KILLED 要求原始和变异结果摘要完整，且按同一比较语义存在差异；缺失、重复、未知 mutation_id 均拒绝。
4. 保存 baseline×2、mutated×2 的执行状态、结果摘要、变异前后 SQL 摘要及底层制品引用，使判断可重算。当前两条 hash 和字符串状态不足以独立复核如何得到 KILLED。
5. 通用 Writer 接受经验证结果，但仍不把类型检查当作执行真实性证明。AI 只调用执行服务，由该服务产生结果和执行记录；已有全仓库写权限的本地用户不在防伪边界之内。

### F07 · P1：覆盖和验收没有区分晋级前后阶段

当前 Verifier 硬性要求候选路径存在且状态是 `review`（acceptance.py 90、109 行），Promotion 会把它移入 Active 并删除原文件。原索引因此不能直接承担晋级后的最终验收。

设计 `phase=pre_promotion|post_promotion`：前者验证固定候选快照；后者通过不可变 Asset Revision 和 Promotion Receipt 定位 Active 资产，验证全量回归扫描集合与该 Active 快照相同。旧审查快照继续可读，不能靠改旧文件路径冒充同一包。

Final Acceptance、Mutation Index、Coverage Summary 和运行报告应有统一 Manifest。校验内容一致性与流程就绪度分开：包完整可以 PASS，但 Human Review 缺失时 readiness 必须 WAITING_APPROVAL，最终不能写 PASS。

### F08 · P1：同语义重试覆盖旧制品，文件晋级缺乏可恢复发布点

Trial/Mutation 当前以 `<case_id>/<semantic_hash>.json` 作为路径，每次 write_bytes 会覆盖。即使 SQL 不变，执行环境或证据变化也可能让旧审批指向的内容消失。

Promotion 当前是先写 Active 文件，再 unlink 原候选（lifecycle.py 391–396 行），没有整批发布事务。预检完后内容变化、目标冲突、进程中断都可能产生部分完成或两个路径并存。

先实现不可变本地 ArtifactStore 与原子文件 Writer；再为批量准入引入锁、快照复验、事务日志、Active Set Manifest 发布点和幂等恢复。单靠“预检 21/21 PASS”不能称为事务实现。

### F09 · P1：DB Build 记录不等于运行时漂移检测

`trial_candidate()` 从传入 Profile 复制 build/version；`validate_profile()`（runtime/profile.py 171 行起）检查目标地址哈希、数据库别名、driver 和 contract，没有读取当前数据库 build。

这不是否定已有 `SHOW build_time;` 记录。需要区分“已采集的 build”与“本次执行实时观测的 build”。在真实执行任务开始时执行只读 build probe，形成带采集时间和原始值的 ExecutionContext；按任务/连接边界复验，漂移时 BLOCKED。历史证据验收不应因数据库后来升级而失去历史可验证性。

### F10 · P1：rowsort 语义与双跑/Mutation 的顺序敏感哈希冲突

模板输出使用 `comparison.mode=rowsort` 且没有保证 ORDER BY，但双跑比较原始行数组，步骤结果 SHA 也保留行顺序。相同行集顺序变化可能被判为不稳定，Mutation 比较也可能受到影响。该项来自静态审查，本轮没有复现真实数据库行序漂移。

保留原始观测顺序供人工看；另计算受 comparison mode 控制的语义摘要。rowsort 按规范单行编码构建保留重复次数的 multiset 摘要，不能转换成 set。rows 模式保持顺序敏感。双跑与 Mutation 按策略使用语义摘要，物理制品 SHA 继续保护完整原件。

### F11 · P1：前端尚不能完整承担人工评审

证据：[service.py](../src/xgtest/web/service.py) 202–235 行的 Candidate Detail 没有返回 Oracle、Mutation Evidence、原始 Trial 行或完整 Review Evidence；[CandidateDetailView.vue](../webui/src/views/CandidateDetailView.vue) 只展示 SQL、首步 Expected、覆盖和摘要哈希。`review_recorded` 仅表示字段存在，不表示评审仍有效。

原始行已经在文件中可直接核对，用户要求的“制品保留每一行”在现有样本中成立；缺的是前端直接访问这些证据和准确展示新鲜度。应补只读证据视图、分页原始行、完整制品下载、Mutation/Oracle/审批快照与过期原因。首步 Expected 改为逐步骤对应，保持 SQL/Expected/实际结果可比。

上一轮启动记录显示前端使用 5173、当前工作区 API 使用 8001，8000 是旧服务。环境变量仅对启动进程生效，重启时容易连回旧服务。增加项目内启动入口，明确根目录、Profile、API 目标，启动后检查实际 Contract/Profile。禁止单凭首页 200 就宣称最新数据已部署。

### F12 · P1：新 Gate 缺少针对性反例覆盖

检索 framework_tests，当前有 Mutation 执行逻辑测试及 Lifecycle 的成功链、语义漂移、Profile/Contract/Trial SHA 错误测试；没有找到 Trial Index Verifier 的专门测试，也缺少上述新 Mutation Gate 的错误适用性、缺失哈希、跨用例结果等测试。现有成功链还使用无原始行的 Fake Trial Report。

应把 F01–F06 的复现转为失败路径测试，并修改成功 Fixture，使其满足正式证据模型。测试注入 runner 可以免连数据库，但最终准入验证规则不应因为测试路径而放松。

## 4. 隔离复核记录与可重现方法

所有修改仅发生在临时文件和候选副本中，临时目录已由上下文管理器清理。Mutation/Promotion 的 synthetic review 标记明确写为测试引用，不属于真实 Human Review。没有连接真实数据库、没有改动正式 YAML。

| 编号 | 操作 | 当前实际输出 | 修复后期望 |
|---|---|---|---|
| R01 | 原始索引、原始 v9 Profile | PASS，verified_count=21 | 保持 PASS |
| R02 | 索引清空，两个计数均改为 0 | PASS | 批次集合不匹配 FAIL |
| R03 | 索引只留 1 条，两个计数均改为 1 | PASS，verified_count=1 | 完整验收 FAIL；明确单例模式可通过 |
| R04 | 索引顶层替换为 `[]` | AttributeError | INDEX_SCHEMA_INVALID，结构化 FAIL |
| R05 | Profile identity.driver.version 改为 `[99,99,99]`，旧 ID 不变 | Verifier PASS；load_profile 拒绝 | Verifier 同样拒绝 |
| R06 | `git cat-file --filters HEAD:<trial-artifact>` | CRLF=true，SHA 与 Index 不等 | 检出字节 SHA 与 Index 相等 |
| R07 | 当前 21 制品、双跑 42 步原始行重算步骤 SHA | 42 一致、0 差异、0 解码错误 | 保持成立并成为 Gate |
| R08 | 临时候选传入外来 case_id 的 KILLED，无结果哈希 | Writer 接受；临时 Promotion 接受 | Writer 在写盘前拒绝 |
| R09 | 临时 Trial run2 改 FAIL，重算外层绑定 | 临时 Promotion 接受 | TRIAL_RUN_NOT_PASS |
| R10 | 临时 Trial 双跑 result_rows 改 null，重算外层绑定 | 临时 Promotion 接受 | RAW_ROWS_REQUIRED |
| R11 | 双跑原始行改同一值，保留步骤旧 SHA，更新外层绑定 | Verifier PASS；临时 Promotion 接受 | RESULT_ROWS_HASH_MISMATCH |

R02/R03 的复现只需用临时 Index 调用 `verify_trial_artifact_index(root, temp_index, original_profile)`。R09–R11 需要复制 Candidate/Artifact、调整对应字段、重算 Artifact SHA 和 Trial 投影摘要，再在临时目录调用 `record_review()` 和 `promote_candidate()`。这用于证明准入函数缺少内容验证，不是要求生产流程重新签署修改过的证据。

建议新增测试文件：`framework_tests/generator/test_acceptance.py`、`test_mutation_evidence.py`、`test_promotion_preflight.py`。测试分别验证可接受边界和拒绝原因；不得只重复实现逻辑后比较同一公式。

## 5. 核心设计：先收敛事实校验，再扩平台

### 5.1 共用 Evidence Validator

新增概念接口（本文件中的接口和后续 CLI 均为设计，尚不存在）：

```python
validate_trial_evidence(asset, trial, profile, context) -> EvidenceValidation
validate_mutation_evidence(asset, evidence, policy, context) -> EvidenceValidation
verify_acceptance_package(manifest, phase) -> AcceptanceVerification
preflight_promotion(plan) -> PromotionPreflight
```

要求这些检查是只读操作，可被 CLI、Web、Promotion、Application Service 和以后 AI 调用。校验失败返回明确路径、case_id、step_id、expected/actual 和错误码；不边检查边修改候选，不自动补造缺失证据。

`AcceptanceVerification` 至少返回 `schema_version`、`scope_id`、`phase`、`package_integrity`、`readiness`、`expected_count`、`observed_count`、`verified_count`、`failed_count`、`failed_cases`、`global_errors`、`waivers`。用例计数与错误条数不同；一个用例十条错误仍只计一个 failed_case。

包验证覆盖：

- Scope、Candidate/Active Revision、Trial Index、Mutation Index 的集合相等和唯一性。
- Contract Descriptor 自身摘要、Profile 自身摘要及原始 Probe 引用。
- 每个 Artifact Byte SHA、语义身份、步骤集合、原始行完整性和结果摘要。
- Mutation policy/applicability、底层执行证据和汇总一致性。
- Review/Approval 与确切输入绑定，不能只检查字段存在。
- 当前 Coverage 必须从冻结资产快照重算；Final Acceptance 必须从这些结果派生。
- `post_promotion` 额外要求 Promotion Receipt、实际 Active 集合和完整回归报告集合一致，0 缺失、0 未声明额外用例。

Manifest 列出不可变成员及其摘要，自身 ID 从不含自身 ID 的规范投影计算；Final Summary 引用该 Manifest ID。禁止 Manifest 哈希包含引用自己的 Final Summary，形成无法计算的自引用循环。

### 5.2 ArtifactStore 与完整原始行

第一版仅实现 LocalArtifactStore：`put(bytes, media_type) -> ArtifactRef`、`get(ref)`、`verify(ref)`。引用包含 `uri`、`sha256`、`size_bytes`、`media_type`、`schema_version`。内容以 SHA 寻址，同内容幂等、不同内容永不覆盖。

写盘顺序为模型校验 → 规范序列化 → 临时文件 → 原子发布 → 更新引用。读路径必须限制 store 根目录且拒绝越界；预检只读取本地已配置 store，不自动下载任意 URI。

Raw Rows 必须完整留存：可分块存储并为整套分块建立摘要，Web 按页展示；分页不等于截断证据。若超过资源上限，应明确 BLOCKED/CAPTURE_INCOMPLETE，不能只保存前 N 行仍标 PASS。针对其他类型引入版本化 codec；脱敏或只保留摘要的策略不得自动套用到用户要求的完整 Xugu 行证据。

旧路径通过只读兼容 Adapter 接入；迁移时校验每个旧引用，保留历史索引和原始制品。Git 暂存少量验收样本与 Manifest，何时迁移远程 store 由实际体积、频率和共享需求决定。

### 5.3 技术评审与正式批准

`TechnicalReview` 保存执行者类型、发现、结论和被审证据摘要；AI 可以生成。`PromotionApproval` 保存可信 principal、决策、签发时间、到期/撤销状态、scope/plan hash、evidence set hash、策略版本和原始批准引用。

本轮没有 PR，不应把“创建 GitHub Review”重新变成唯一批准入口。可先采用本机受信任操作者入口，把用户对具体快照的批准记录为可核对的审计事件；以后再提供 GitHub Review Provider。无论哪个入口，都不得由 AI 自填 reviewer 字符串或 `human` 枚举证明真人身份。

批准必须针对实际可审的完整包。PR/CI 暂缓已有用户指令，无需重复确认；候选人工评审没有完成，不能由这条暂缓指令推导出候选通过。

威胁边界要写清：MVP 防止普通 API/AI 调用误写审批，不承诺抵御能修改源码、证据及信任配置的同一系统用户。若未来要求抗此类修改，必须把签发服务或密钥放到独立权限域，不能仅靠多算一个 hash。

### 5.4 PromotionPlan、批量发布与恢复

PromotionPlan 在批准前生成，包含固定 Candidate Revision 集合、证据集合、当前 Active Snapshot、目标覆盖、Contract/Profile、策略版本和目标冲突检查。plan_hash 不包含随后生成且引用自己的 Approval，避免循环依赖。

Preflight 不写文件，逐条返回 promotable/blockers，并检查全量集合的重复 ID、重复语义、目标冲突和相对当前 Active 的覆盖贡献。

执行阶段：取得项目内发布锁 → 复核 plan_hash 和输入摘要未变 → 检查批准有效 → 写不可变目标资产和事务日志 → 一次原子替换 Active Set Manifest → 写 Receipt → 完成候选状态投影及恢复标记。

所有正式执行读取同一 Active Set Manifest，才能声称批次具有单一可见发布点。如果仍然直接扫描 `cases/query/`，必须标注为可恢复批处理，而不是事务性晋级；暂停并发 Reader 只能作为有明确范围的临时措施。

恢复按 transaction_id 幂等执行，不能重复插入；失败发生在发布前不改变 Active Snapshot，发布后依据日志恢复附属状态。发生回归失败时保留失败记录，通过审计化回退到旧 Manifest 撤销新 Active 集，不能删除失败证据后宣称成功。

### 5.5 Contract Identity 分层及证据迁移

先写依赖矩阵，再分层。当前 `_SOURCE_DIRS` 把测试、Generator、Model、CLI 都算入单一 ID，确实会造成大范围证据过期。

| 身份 | 主要输入 | 应影响的证据 |
|---|---|---|
| Runtime Contract ID | Driver 适配、类型映射、执行会话/超时能力规则、Profile Schema | Runtime Profile、执行上下文 |
| Comparison Contract ID | XGC1 编码、Typed Row Codec、Comparison Policy | Trial/Mutation 结果摘要、回归结果 |
| Generator Contract ID | 渲染器、Expected 生成规则、Mutation Policy、插件版本 | 新生成资产及其生成来源 |
| Model Hash / Template Hash | 维度、约束、覆盖策略、模板 | Coverage Claim、生成输入、评审关联 |
| Governance Policy ID | Evidence Gate、审批、准入规则 | Approval 与 Promotion readiness |
| Source Snapshot Hash | 精确代码/测试输入清单 | 执行可追溯性；不把每次文档修改自动当作运行能力失效 |

清单必须显式覆盖依赖并有“改变一个组件，只失效预期下游”的测试。Runtime/Comparison 修改仍应触发相关重验证；将它们移出大 ID 后不能漏掉真实行为变化。

采用 Schema 版本升级与旧 ID 只读兼容；旧 Evidence 保留原 ID。可证明只是元数据/展示变化时生成迁移/再验证凭据；无法证明兼容时重跑。禁止直接把旧 Artifact 的 ID 改成新值让其重新通过。

### 5.6 Asset、FeaturePlugin 与 Application Service

`QueryCaseAsset` 承担 Coverage、Generation、Oracle 和治理引用，`ExecutableQueryCase` 承担 metadata、steps 与运行所需限制。Compiler 负责验证和显式转换，保留 source revision 以关联结果；Worker 仅接收执行 DTO。

第一阶段保持现有 YAML 可加载，旧 `QueryCaseInput` 通过适配入口过渡。不要同时改变 YAML 格式、比较算法、模板和 Worker 协议。注册表/Schema/回归报告有版本兼容测试后再切换默认路径。

FeaturePlugin 初版只把 JOIN 现有实现包在稳定接口后：模型、assignment 校验、渲染/Expected、Candidate ID、MutationSpec 和 Coverage Strategies。通用 Lifecycle 不再识别 `QUERY.JOIN.` 或 `less_equal`。插件由显式注册表加载；数据文件不能任意导入 Python 模块。

Application Service 统一协调 ArtifactStore、Validators、Runner 和 Lifecycle。可先用薄 facade 迁移 CLI，再迁移 Web，不要求先搬迁全部目录。Core 保持同步、确定性函数；任务调度和授权只在 Application/Control 边界组织。

### 5.7 AI Control Plane 的必要约束

1. ModuleTestSpec 先声明 query.basic/join/filter/aggregate 等是否必需、是否有模型、完成阈值。JOIN 137/137 仅表示当前 JOIN pairwise 范围覆盖，不能称为数据库查询功能全覆盖。
2. Inspect 输出结构化 Project/Module State，附快照 ID 和状态来源。Markdown 可用于解释，但不能单独证明项目通过验收。
3. ActionResult/ActionError、Policy、TechnicalReview/Approval 先于 Planner/Orchestrator；不要出现默认允许任意动作的中间版本。
4. Planner 是确定性函数，输入 TestIntent+State+Policy，输出动作依赖和 plan_hash；相同输入相同计划。
5. TestJob 记录 job_id、action_id、attempt_id、输入/输出摘要、幂等键、事件序号和策略版本。恢复前验证输入未漂移。
6. Orchestrator 初版顺序执行，WAITING_APPROVAL 持久化后停止有副作用步骤；恢复必须检查新审批，不得把超时视为批准。
7. Recovery 按依赖图修复 stale；限制次数和成本。人工拒绝、审批缺失、数据权限错误不能无限重试。
8. CompletionEvaluator 区分 DEFINED_SCOPE_COMPLETE、MODULE_FULL_INCOMPLETE、MODULE_FULL_COMPLETE，并列出未建模的必需 Feature。
9. Agent Semantic API 暴露结构化动作；授权层不得给 AI 的普通调用发放 Approval 签发权限。只限制工具名称而仍共享审批写入口，不算隔离完成。

## 6. 优化后的分步实施计划

### 阶段 A：正式晋级前修复事实校验

| 步骤 | 实施内容与主要位置 | 依赖 | 验收标准 |
|---|---|---|---|
| A01 | 标注新旧文档基线，定义 AcceptanceScope、阶段与 CI 暂缓记录格式 | 无 | 当前状态与历史意见不混淆；CI 不再阻塞本轮开发，也不显示 PASS |
| A02 | `.gitattributes` 固定证据字节，统一 Writer | A01 | Windows/Linux 检出后相同制品 SHA 一致，F01 反例消失 |
| A03 | 统一 Trial Validator、Profile 严格加载、输入结构错误报告 | A02 | F02/F03/F04 全部被拒绝；现有正确样本保持通过 |
| A04 | Raw Row Codec/XGC1 重算、双跑语义摘要 | A03 | F05 被拒绝；乱序、重复行、空结果、NULL、类型边界各有明确结果 |
| A05 | 严格 MutationValidationResult、Policy、Writer/Gate 共用校验 | A03/A04 | 外来 case_id、缺少哈希、未知/重复 Mutation、错误适用性均失败；正常 5+16 通过 |
| A06 | 统一 Package Verifier、只读 Promotion Preflight、逐例统计 | A03–A05 | Scope 全集验证；完整包结构正确而审批缺失时显示 WAITING_APPROVAL |
| A07 | LocalArtifactStore、不可变快照、PromotionPlan/事务日志/发布点 | A06 | 同语义重跑不覆盖旧证据；断点恢复和输入漂移测试通过 |
| A08 | 最小 Approval Contract 与受信任签发边界 | A06/A07 | AI 技术评审不能自升格；批准绑定计划及证据集合，撤销/过期可拒绝 |
| A09 | Web/API 评审详情、原始行浏览/下载、Gate 状态；项目启动入口 | A06–A08 | 原始完整制品可取；陈旧 Review 明确显示；启动可核对来源与 Profile |
| A10 | 跑针对性测试和完整框架检查，生成最终候选 Contract/Profile | A02–A09 | 框架与生成文件一致；把实际结果留档，不能沿用旧 172 项统计冒充新结果 |
| A11 | 在冻结代码快照下重建需要更新的证据，执行 Package Verify | A10 | Active 回归、Mutation、21 条双跑与 Raw Rows 全部绑定一致；人工审批输入不再变化 |

这些修复多数会改变当前单一 Contract ID。A02–A09 完成前不逐次要求重跑真实数据库；先完成本地确定性测试，再在 A10/A11 统一固化和执行一次必要的真实证据更新。若某次代码修改影响真实结果，按实际依赖补跑，不以“减少重跑”为理由沿用失效证据。

### 阶段 B：完成 JOIN 正式准入

| 步骤 | 实施内容 | 验收标准 |
|---|---|---|
| B01 | 导出稳定评审包并由人工评审、明确决定 | 决策对应确切 plan/evidence hash；所有 21 条有可追溯结论；有拒绝项时不宣称整批通过 |
| B02 | 从可信批准记录生成 Review/Coverage/Approval Evidence | 使用正式服务；不手改 YAML；重新 Verify 后不存在 stale 绑定 |
| B03 | 对整个 PromotionPlan 执行 Preflight | 计划所选集合逐例通过；Active 快照和目标仍一致 |
| B04 | 执行批次晋级并生成 Receipt | 单一可见发布点或明确标注受限批处理；中断恢复不重复、不丢候选 |
| B05 | 扫描正式 Loader 的全部 Active 集，运行真实全量回归 | 实际用例集合与 Receipt 中 Active Snapshot 相同；不得硬编码 51 或其他推算数量 |
| B06 | 重算 Active Coverage 与 post-promotion Package | 本模型 required=137、active_covered=137、active_missing=0；不能拿 provisional 值替代 |
| B07 | 生成最终验收、记录例外与 G0A 决策 | 所有要求由规则计算；CI 暂缓如被最终策略允许则显式 PASS_WITH_EXCEPTION，严格原策略仍未全满足 |

若 B01 未完成，可继续准备评审界面、验证器和下阶段设计；不能伪造 B02–B07 已完成。G0A 决策是对目标契约版本的判断：若马上进行 C01，建议该版本保持候选，待依赖身份定型后发布；并非要求把全部 AI 功能做完才能 Freeze。

### 阶段 C：平台基础边界，避免一次性重写

| 步骤 | 实施内容 | 验收/兼容要求 |
|---|---|---|
| C01 | Contract 分层及失效矩阵 | 文档/控制面展示修改不使 Runtime Profile 过期；执行/比较规则修改仍正确失效；保留旧 ID 解释能力 |
| C02 | Asset/Executable DTO 与 Compiler | 旧 YAML 经兼容 Loader 可用；执行含义和结果不变；治理字段不进入 Worker 输入 |
| C03 | JOIN Plugin 适配与 Registry | 原 JOIN Goldens 不变；Core Lifecycle 没有 JOIN 前缀/特定 predicate 分支 |
| C04 | Application Services，迁移 CLI/Web 调用 | 同一操作走同一个校验和授权入口；前端不得自行把字段存在判作 Gate PASS |
| C05 | ModuleTestSpec、Inspect、Unified Preflight | 未建模 Feature 被明确列出；结构化状态可重算；不存在读取“Latest.md”判定完成的分支 |

ArtifactStore 接口已在 A07 最小实现，C 阶段扩充导出/导入即可；远程存储按实际需求单独落地。全部步骤保留旧入口适配与回退路径，避免同时修改领域算法、格式、存储和界面。

### 阶段 D：AI 驱动工作流

| 步骤 | 实施内容 | 验收标准 |
|---|---|---|
| D01 | ActionResult/Error、Policy、TestIntent | 明确 PASS/FAIL/BLOCKED/WAITING_APPROVAL/SKIPPED；审批动作不可由普通 AI principal 签发 |
| D02 | Deterministic Planner | 同一快照和 Policy 得同一计划；依赖、动作适用性、计划 hash 可检验 |
| D03 | 持久 TestJob/Event Log 与幂等执行骨架 | 中断可恢复；同动作恢复不重复写制品或晋级 |
| D04 | 顺序 Orchestrator、Recovery、CompletionEvaluator | 批准处停住；陈旧证据按依赖重算；未覆盖模块不能报告 MODULE_FULL_COMPLETE |
| D05 | Agent Semantic API 和 Job Web 页面 | 支持 Inspect/Plan/Start/Get/Resume；UI 看进度、阻塞原因和证据；权限测试证明 AI 不能自批 |
| D06 | 真实 query.full_test 端到端 | 从固定范围执行到 WAITING_APPROVAL，人工批准后继续到可验证 Completion |
| D07 | Filter Plugin，再做 Aggregate Plugin | 每个 Feature 独立 Model/Constraint/Mutation/Coverage；不得为第二个 Feature 改通用 Lifecycle 加 if/else |

## 7. 验收与回退清单

每个实现提交应说明影响的身份/证据、迁移范围和实际验证结果。建议按 A02、A03/A04、A05、A06、A07、A08、A09 分批提交，避免一个提交混入 Core 大重构和新 Feature。

重点测试矩阵：

- 输入：空/子集/额外/重复候选、无效 JSON、错误类型、null 标识、路径越界、大小上限。
- Trial：一步缺失、额外步骤、错误 case_id、run FAIL、step FAIL、空 steps、双跑差异、缺原始行、行宽/行数错误、原始行与摘要不符。
- Mutation：外来 case_id、错误 semantic/profile/contract/policy、未知/重复 mutation_id、不适用却 KILLED、缺哈希、无变化却宣称 KILLED、SQL 执行错误被误当 KILLED。
- Review：旧输入、批准到期/撤销、计划改变、AI 调用签发、仅填写人名/URL、跳过 CI 被误当跳过人工评审。
- 发布：锁竞争、Preflight 后输入变化、写中断、发布前后进程崩溃、重复 resume、目标冲突、回归失败恢复旧 Active 快照。
- 跨平台：Windows/Linux Git 检出字节一致；运行同一 XGC1 测试向量；旧资产和旧 Profile 仍可解释。
- Web：逐步骤 Expected、原始行分页与完整导出、Mutation/Oracle/Approval 展示、陈旧状态、错误提示、API 根目录/版本不匹配。

回退以已发布的 Asset/Artifact/Active Manifest 版本为单位，保留失败记录。旧 API 在兼容窗口内只读可用；不强制迁移全部历史文件，不删除用户已有证据，不修改项目外系统配置。

## 8. 下一轮执行入口

下一轮应从 A01/A02 开始，先修字节稳定和准入验证。Human Review 在 A11 的稳定证据包完成后进行，这样审批输入不会因为连续修 Gate 而反复失效。JOIN 的业务模板维度暂不扩展，后续工作集中在证据可靠性、评审可用性和通用架构边界。

当前已通过的 21 条真实试跑及 42 步原始行重算结果可以继续作为事实记录；不能据此忽略本轮已复现的校验漏洞。当前 `HOLD` 仍合理，但原因应更新为“准入校验加固和人工批准尚未完成”，而不再仅写“等人工评审”。
