# XG DB Test 最新提交代码审核

## 1. 审核基线

- 仓库：`xunyuxingkong/allone`
- 分支：`codex/join-model-v2`
- HEAD：`6311887d8dffd69c5727d4b6059ce7b9077273fa`
- 提交：`feat: add external agent test jobs and CLI MCP interfaces`
- 父提交：`969f8be6e9698d5b6cbb97ee870ac6963ac9d1b4`
- 提交日期：2026-10-08

本次只比上一基线多 1 个提交，但属于一次较大的 AI 控制面落地：

```text
新增/修改 22 个文件
核心新增：
  src/xgtest/ai/*
  src/xgtest/application/*
  framework_tests/test_ai_jobs.py
  docs/external-agent-jobs.md
  Web Job 列表/详情页
```

远端当前仍没有 GitHub Commit Status / Workflow Run，分支也未启用保护；因此本报告把“仓库内测试记录”和“远端独立 CI”分开看待。

---

# 2. 总体结论

这次提交的**方向是对的，而且终于开始把项目拉回“AI 驱动测试”的主线**。

它不再继续加 Evidence 层，而是实质实现了：

```text
External Agent
    ↓ MCP / CLI
JobController
    ↓ Semantic Action
Application Services
    ↓
Deterministic Core
    ↓
Real Xugu / Evidence / Acceptance
```

当前最重要的进步是：

```text
AI 选择动作
Core 校验动作是否合法
Core 决定 PASS/FAIL
Human Gate 决定 Promotion
```

这与项目最初的 AI 驱动测试本心高度一致。

我的评价：

| 维度 | 评分 |
|---|---:|
| AI / Core 权责边界 | 9.2 |
| Action Contract 安全性 | 9.0 |
| Job 持久化 / 恢复 | 8.7 |
| Application Service 分层 | 8.4 |
| Human Gate | 9.0 |
| MCP / CLI 适配 | 8.8 |
| 测试质量 | 8.7 |
| 多 Job 一致性 | 7.0 |
| 敏感信息处理 | 7.2 |
| 真实 E2E 完成度 | 6.8 |
| **本次提交综合实现质量** | **8.5 / 10** |

结论：

> **AI-Driven MVP 的“骨架”已经成型，但暂时还不能称为“可用 MVP 已完成”。**
>
> 不是因为还缺更多架构，而是因为当前有 2~3 个控制面逻辑问题需要修，并且完整真实 Xugu E2E 还没跑通。

---

# 3. 本次提交做对了什么

## 3.1 外部 Agent，而不是项目内再嵌一个 LLM

现在项目没有强行引入 OpenAI/DeepSeek API Key，而是：

```text
Codex / 外部 Agent
→ MCP / CLI
→ JobController
```

这是非常适合当前 MVP 的选择。

优点：

```text
不重复造 Agent Runtime
不绑定某一家 LLM
项目本身保持 deterministic
AI 能真正选择下一动作
```

这比“项目内写一个固定 LLM Planner”更轻，也更符合 MVP。

---

## 3.2 Semantic Action 白名单落实得不错

当前允许的动作被封闭在：

```text
project.inspect
project.preflight
module.inspect
module.regression
feature.coverage
candidate.generate
candidate.validate
candidate.mutation
candidate.trial
candidate.technical_review
acceptance.inspect
acceptance.preflight
acceptance.promote
acceptance.post_verify
```

没有开放：

```text
shell.execute
filesystem.write
approval.sign
repair.propose
repair.validate
```

而且 Pydantic `extra=forbid` 继续生效。

因此 AI 不能通过 Action Contract 偷带：

```text
任意 shell
任意 SQL
任意 Hash
人工签名
```

这是当前控制面的核心安全边界，设计正确。

---

## 3.3 AI Technical Review 与 Human Approval 仍然分开

技术评审上下文绑定：

```text
Candidate
Trial Raw Rows
Mutation Evidence
Runtime Profile
↓
context_hash
```

提交技术评审时必须携带相同：

```text
review_context_id
```

上下文变化就拒绝。

而 AI Technical Review 不会写入：

```text
ReviewEvidence
CoverageReview
Signed Approval
```

这仍然保证：

```text
AI 可以审
AI 不能批准自己
```

方向非常正确。

---

## 3.4 Job 持久化比普通 state.json 强很多

`JobStore` 采用：

```text
append event
fsync
→ atomic state replace
```

并以 Event Log 为恢复事实来源。

对于进程在写入事件中途死亡：

```text
partial trailing event
```

会被忽略，不会当作有效 Checkpoint。

还增加：

```text
revision
request_id 幂等
job lock
project execution lock
```

这些都非常适合本机单用户 MVP。

---

## 3.5 请求幂等与 Revision 防并发覆盖是亮点

执行 Action 时要求：

```text
request_id
expected_revision
```

同 request_id + 同内容：

```text
允许重放
```

同 request_id + 不同内容：

```text
REQUEST_ID_REUSED
```

旧 Revision：

```text
JOB_REVISION_CONFLICT
```

这比很多早期 Agent Workflow 实现可靠。

---

## 3.6 中断后不会把 RUNNING 当成功

如果 Action 中断：

```text
current_action != None
```

则：

```text
eligible_actions = []
```

必须显式：

```text
resume
```

Promotion 中断则继续委托原 Core Journal 恢复。

这很好地保持了之前 Evidence / Promotion 的可信边界。

---

## 3.7 Application Service 没有重写 Core

新增：

```text
ProjectService
ModuleService
CandidateService
AcceptanceService
```

但真正的测试事实仍调用现有：

```text
Runner
Coverage
Mutation
Trial
Package Verify
Promotion
Post Acceptance
```

没有在 AI 层重新实现一套 PASS/FAIL 规则。

这是正确的分层方式。

---

## 3.8 Real DB Worker 只接受固定 Operation

数据库 Worker 只允许：

```text
preflight
regression
mutation
trial
```

没有接受：

```text
AI 传入任意 SQL
```

这很好地守住了“AI 不能绕过 deterministic core”的原则。

---

# 4. 当前 P0：AI Technical Review 的 FAIL 仍会被当成“已完成评审”

这是本次最重要的代码逻辑问题。

当前 `review_valid()` 只验证：

```text
TechnicalReview Schema 合法
context_hash 当前有效
```

但没有判断：

```text
decision == PASS
```

因此下面这种评审：

```json
{
  "decision": "FAIL",
  "recommendation": "INVESTIGATE"
}
```

仍会让：

```text
technical_review_valid = true
```

随后 Controller 会认为该 Candidate 的 Technical Review 已经完成，继续走到：

```text
acceptance.inspect
```

甚至进入：

```text
WAITING_APPROVAL
```

虽然 Human Gate 最终仍能阻止 Promotion，但 AI 控制面的语义已经错了。

## 应改成两个概念

```text
technical_review_valid
= 上下文和结构没被篡改

technical_review_accepted
= decision == PASS
  && recommendation == READY_FOR_HUMAN_REVIEW
```

Controller 的 Candidate Readiness 必须依赖：

```text
technical_review_accepted
```

如果：

```text
FAIL
```

应该：

```text
Job = BLOCKED
```

如果：

```text
CONCERNS
```

可以：

```text
BLOCKED / NEEDS_HUMAN_CHECK
```

但不能当作正常完成。

### 优先级

```text
P0 — AI MVP Workflow Correctness
```

---

# 5. P1：Job 没有绑定 Control Plane / Source Identity

当前 Preflight 漂移检查主要比较：

```text
execution_contract_id
runtime_profile_id
```

这是测试执行层的身份。

但现在 Job 本身已经依赖大量：

```text
src/xgtest/ai/*
src/xgtest/application/*
```

如果 Job 跑到一半：

```text
修改 controller.py
修改 services.py
重启程序
resume Job
```

只要：

```text
Execution Contract 没变
Runtime Profile 没变
```

旧 Job 就可能继续由**另一版控制逻辑**执行。

这是 Durable Job 中比较危险的语义漂移。

## 建议

在 Job 创建时冻结：

```text
control_plane_id
git_commit
```

或至少：

```text
job_source_state_id
```

每次 Action / Resume 前比较。

策略可以是：

```text
Execution Identity changed
→ 必须重新 Preflight + Evidence Revalidation

Control Plane changed
→ Job BLOCKED: JOB_CONTROL_PLANE_CHANGED
→ 人工确认后 migrate/resume
```

不要让旧 Job 悄悄跨代码版本继续跑。

### 优先级

```text
P1，建议 MVP E2E 前修
```

---

# 6. P1：多个 Job 会共享同一套全局 Candidate State

虽然实现了：

```text
project execution lock
```

但该锁只保证：

```text
两个 Action 不会同时执行
```

没有保证：

```text
两个 Workflow 不会交替修改同一 Candidate 集
```

例如：

```text
Job A: generate
Job B: mutation
Job A: technical review
Job B: acceptance.inspect
```

两者操作的其实都是：

```text
candidates/query/join
```

而不是 Job 私有 Candidate Set。

更明显的是：

```text
AcceptanceService.freeze()
```

会冻结当前全局所有 Candidate，而不是：

```text
只冻结本 Job 生成/选择的 Candidate
```

Technical Review 又是：

```text
per Job 存储
```

所以现在“Job 私有状态”和“项目全局候选状态”存在混合。

## MVP 最简单修法

不要现在做复杂隔离。

直接建立：

```text
Single Mutable Workflow Policy
```

同一 Project 同时只允许一个：

```text
query.full_test / query.join.verify
```

处于：

```text
RUNNING / PLANNED / WAITING_APPROVAL / BLOCKED
```

`query.status` 可以并存。

第二个 Mutating Job 创建时：

```text
MUTABLE_JOB_ALREADY_EXISTS
```

等 MVP 稳定后再做真正：

```text
Candidate Set Snapshot / Job Ownership
```

### 优先级

```text
P1，建议 MVP 前修
```

---

# 7. P1：WSL 数据库凭据当前会进入命令行参数

`DatabaseExecutor` 的 WSL 路径当前构造：

```text
wsl --exec env
XGTEST_DB_HOST=...
XGTEST_DB_USER=...
XGTEST_DB_PASSWORD=...
python3 -m ...
```

虽然没有把密码写进 Job JSON，

但：

```text
PASSWORD=value
```

实际上进入了父进程的命令参数。

在 Windows 进程查看、审计或调试工具里，命令行可能被观察到。

这与文档中：

```text
数据库凭据只通过环境传递
```

的安全意图并不完全一致。

## 建议

优先考虑：

```text
WSLENV
```

让变量通过环境继承到 WSL，避免把值写到 argv。

或者：

```text
受权限保护的临时 credential channel
```

但不要把密码直接放 command line。

### 优先级

```text
P1 Security
```

---

# 8. P1：DB Worker 的原始异常信息仍可能进入 Job Evidence

Controller 自己已经很谨慎：

```text
异常消息只有满足大写错误码格式才直接保留
否则统一 ACTION_EXECUTION_ERROR
```

但 `db_worker.main()` 里：

```text
extract_error(error)["message"]
```

会直接写入：

```text
*.result.json
```

Application Service 再把该结果放进：

```text
ActionResult.outputs / blockers
```

因此原始数据库异常中如果包含：

```text
连接串
路径
SQL 片段
内部对象名
```

就可能进入：

```text
Job Event
Final Report
Web Job Detail
```

## 建议

Worker 返回：

```text
error_code
error_type
safe_message
raw_error_artifact_ref
```

Job 只保存安全投影。

完整原始错误若确实需要：

```text
单独 Artifact
限制 UI 默认展示
```

---

# 9. P2：Event Log 会 O(n²) 增长

每一个 JobEvent 当前保存：

```text
完整 TestJob checkpoint
```

而 TestJob 又保存：

```text
所有 action_results
所有 completed_requests
```

因此 Action 越多：

```text
Event 1: 1 个 Result
Event 2: 2 个 Result
Event 3: 3 个 Result
...
```

长期空间接近：

```text
O(n²)
```

当前 JOIN 21 Candidate 的 MVP 还能接受。

但未来：

```text
24h Agent
几百函数
大量失败结果
```

会非常膨胀。

## MVP 暂不需要大改

先限制：

```text
ActionResult.outputs 大小
Failure steps 投影
最大 explanation 长度
```

MVP 后再改成：

```text
Event Delta + Periodic Snapshot
```

---

# 10. P2：Regression Failure 当前可能把完整 Step 数据塞进 Job

`db_worker` 回归失败会返回：

```text
case_id
failure_type
steps
error
```

`steps` 可能比较大，甚至包含结果数据。

这会进入：

```text
ActionResult.outputs
→ TestJob
→ 每个 Event Checkpoint
```

建议 Failure Output 只保留：

```text
case_id
step_id
status
failure_type
safe_error_code
artifact_ref
```

详细结果仍然放原始 Run Artifact。

这既减少体积，也降低数据泄露面。

---

# 11. `query.join.verify` 与 `query.full_test` 当前几乎同语义

Controller 当前只对：

```text
query.status
```

做特殊流程。

另外两个：

```text
query.join.verify
query.full_test
```

基本走同一条 Eligible Action 逻辑。

而 `TestIntent` 默认：

```text
allow_candidate_generation = true
allow_trial = true
allow_promotion = true
```

所以名称叫：

```text
verify
```

实际上也可能：

```text
generate
trial
promotion
```

当前文档里确实将后二者都定义为 Candidate Workflow，所以这不算隐藏 Bug；但产品语义容易误解。

## 建议

要么：

```text
query.join.verify
默认只允许 inspect/regression/coverage/existing evidence verify
```

要么直接改名：

```text
query.join.full_test
```

避免“verify”实际改变项目状态。

---

# 12. Job COMPLETED 与 Formal Final PASS 分开是正确设计

Controller 在：

```text
acceptance.post_verify PASS
```

后可以把 Job 标为：

```text
COMPLETED
```

即便：

```text
formal_final = HOLD
```

这一点表面上容易疑惑，但当前设计是合理的：

```text
Job COMPLETED
= 这次 Workflow 执行完成

Formal Final PASS
= 正式发布/验收门禁通过
```

当前实现状态文档也明确区分了这两件事。

建议 UI 进一步明确显示：

```text
Workflow: COMPLETED
Formal Acceptance: HOLD
```

不要只显示一个绿色 Completed。

---

# 13. 当前真实验证状态

仓库提交内记录：

```text
Framework:
260 passed
1 skipped

新增控制器测试：
21 项

Frontend:
vue-tsc + vite build PASS

MCP:
stdio handshake PASS
7 tools discovered
list invocation PASS
```

但这属于仓库内实施记录。

当前 GitHub 远端：

```text
Commit Status: none
Workflow Run: none
Branch Protection: OFF
Commit: unsigned
```

因此不能把 260 PASS 解释为独立 CI 的验证结果。

---

# 14. 更重要的是：真实 AI Full-Test E2E 还没有跑通

项目自己的实施记录非常诚实：

```text
query.status
已经跑通
```

但是完整：

```text
query.full_test
```

在真实 Preflight 时因为数据库网络不可达而 BLOCKED。

因此目前已经证明的是：

```text
AI Control Framework
Job Persistence
Action Boundary
Synthetic Workflow
MCP Interface
```

还没有证明：

```text
External Agent
→ live Xugu regression
→ candidate workflow
→ technical review
→ human approval
→ promotion
→ post regression
→ post acceptance
```

整条真实链。

所以当前准确状态应是：

```text
AI-Driven MVP Implementation:
约 80~85%

AI-Driven MVP Real E2E:
未完成
```

---

# 15. 接下来不要再做新的大架构

当前最不应该做的是：

```text
ActiveManifest
Remote ArtifactStore
Filter Plugin
Multi-Agent
Repair Engine
更复杂 Planner
更多 UI
```

先把最新提交里的控制面本身修稳。

---

# 16. 下一提交建议只修 4 件事

## Fix 1 — Technical Review Decision Gate

```text
FAIL / CONCERNS
不能被当成 accepted technical review
```

新增测试：

```text
test_failed_technical_review_blocks_acceptance
test_concerns_review_requires_human_check
```

---

## Fix 2 — Job Source / Control Plane Identity

Job 创建 / Preflight 冻结：

```text
git_commit
control_plane_layer_id
```

Resume / Action 前检查。

新增：

```text
test_control_plane_change_blocks_resume
```

---

## Fix 3 — Single Mutable Job Policy

第一版明确：

```text
同一项目最多一个 mutating test job
```

新增：

```text
test_second_mutating_job_is_rejected
```

避免跨 Job Candidate 污染。

---

## Fix 4 — Credential / Error Redaction

```text
WSL password 不进入 argv
DB Worker 返回安全错误码
Job Event 不保存未经清洗的 raw exception
```

新增：

```text
test_password_not_in_worker_command
test_driver_error_is_redacted
```

---

# 17. 修完以后立刻做真实 E2E

不要再开 v15 大重构。

恢复 Xugu 网络后直接执行：

```text
External Agent
→ create query.full_test
→ project.preflight
→ module.regression
→ coverage
→ candidate workflow
→ 21 AI technical reviews
→ WAITING_APPROVAL
```

然后真实人工：

```text
ReviewEvidence
CoverageReview
Signed Approval
```

再：

```text
resume
→ preflight
→ promotion
→ post regression
→ post verify
→ final report
```

只要这条真实链跑通：

> **就可以正式把当前版本定义为 AI-Driven Usable MVP。**

即便最终：

```text
Formal Final = HOLD
```

因为 GitHub CI 被用户主动延后，也不妨碍：

```text
AI Test MVP = 可用
```

两者是不同概念。

---

# 18. 当前项目阶段判断

```text
Deterministic Test Core:
成熟

Evidence / Acceptance Core:
成熟度较高

External Agent Semantic API:
第一版完成

File-backed Job:
第一版完成

MCP / CLI Adapter:
第一版完成

AI Technical Review:
有 1 个决策 Gate 缺陷

Multi-job Isolation:
不足

Credential Boundary:
需加固

Real Xugu AI E2E:
未完成

Usable AI MVP:
接近完成，但还不能宣布 DONE
```

---

# 19. 最终建议

这次提交总体是**非常关键的一步**。

项目终于从：

```text
“把 Deterministic Test Core 做得越来越完整”
```

转成：

```text
“让外部 AI 真正驱动 Core 完成测试目标”
```

这是正确方向。

接下来应该克制：

```text
不再扩平台
不再补漂亮架构
不再增加 Feature
```

只修：

```text
Technical Review Gate
Job Identity
Single Mutable Job
Secret Redaction
```

然后立即跑一次真实 `query.full_test` E2E。

如果成功，当前阶段就应该宣布：

```text
XG DB Test AI-Driven MVP v1 = DONE
```

然后下一步才进入：

```text
Filter Plugin
Repair Candidate Loop
24h Autonomous Runner
```

这能保证项目不再偏离“AI 驱动数据库测试”的本心。
