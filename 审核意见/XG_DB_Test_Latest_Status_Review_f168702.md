# XG DB Test 最新提交审核：f168702

## 1. 当前基线

- 仓库：`xunyuxingkong/allone`
- 分支：`codex/join-model-v2`
- HEAD：`f1687021967712fca0573d099881a5728c2a243d`
- 提交：`feat: complete approval and smoke workflow`
- 父提交：`297942a3d56dce0224de2f1fb719a897d7519767`
- Branch Protection：OFF
- Commit：unsigned
- GitHub Commit Status：无
- GitHub Workflow Runs：无

## 2. 总体结论

这次主要完成两条主线：Smoke workflow 与 Human Approval 产品化。上一轮的 Smoke 重复生成风险、审批没有操作入口，都得到实质改善。当前 Product MVP 约 90~92%。

## 3. 已解决：Smoke 重复生成

新增累计 generation progress：`budget / generated_total / remaining_budget / stalled`。Smoke 总预算 30，不会每轮重新获得 30。Candidate Generator 也会读取已有 candidate，排除已占用 deterministic ID，连续有限批次不会重复返回同一批。

## 4. 已解决：Completion 前显式记录 feature.coverage

Regression PASS 后不再静默完成；必须真正执行并记录 `feature.coverage`，再根据 `active_missing` 完成 Job。这样 Job Event、Mission covered_scope、Completion 更一致。

## 5. 已解决：单 Feature 校验错误语义

已去掉 `Field(max_length=1)`，由业务 validator 负责 `MISSION_FEATURE_DUPLICATE` 与 `MISSION_FEATURE_SCOPE_MUST_BE_SINGLE_UNTIL_ORCHESTRATION`。

## 6. Human Approval 已开始真正落地

新增：

```text
xgtest approval signer-init
xgtest approval prepare
xgtest approval sign
xgtest approval verify
```

私钥必须放项目外，Allowed Signers 只登记公钥；Approval Payload 绑定 Manifest ID 与 Plan Hash，并带有效期；Core 最终仍由 ApprovalService 校验签名、Signer、过期、撤销与 stale input。AI/MCP 仍没有签名动作。

## 7. Approval UX 明显改善

Mission Detail 已展示 Manifest、Promotion Plan、候选数、Runtime Profile、DB Build、Execution Contract、Regression、Trial、Mutation、Coverage、AI Technical Review，并给出本地 Operator CLI 步骤。

## 8. 新 P0：Smoke Completion 在 Promotion 后会反向失效

当前 `smoke_completion()` 用 `CandidateService.readiness()` 判断本 Job 生成的 candidate 是否仍存在且证据有效。但 `promote_candidate()` 晋升成功后会把 candidate 写入 active root，然后 `path.unlink()` 删除 candidate 文件。

因此完整成功流程：

```text
Generate → Validate → Mutation → Trial → Review → Sign → Promote
```

之后再次打开 Mission，`readiness()` 不再包含这些已晋升 candidate，可能导致：

```text
generated_cases_valid = false
smoke_complete = false
```

建议不要从“当前 candidate 目录”动态重算历史 Strategy Completion。应在进入 Acceptance 前冻结不可变 `strategy_completion` Evidence，或至少把已晋升到 active root 的同 ID 视为已完成。优先级 P0。

## 9. Smoke Completion 还会被历史 BLOCKED 永久污染

当前 `no_blocking_failure` 检查整个历史 ActionResult 是否出现过 FAIL/BLOCKED。一次临时 DB 网络失败即使之后 resume 并全部 PASS，历史 BLOCKED 仍会让 Smoke 永远显示未完成。

建议基于当前状态与各语义阶段的 latest effective result 判断，而不是 `any historical failure`。

## 10. 新 P0/P1：Smoke 30 条预算只限制“生成”，没限制“实际处理”

`CandidateService.readiness()` 仍遍历整个 `candidates/query/<feature>/`，Controller 会处理 readiness 返回的所有 candidate，AcceptanceService.freeze() 也遍历整个 Candidate Root。

如果历史上残留 50 条 candidate，新 Smoke 虽只生成 30 条，仍可能处理旧 50 + 新 30，实际工作量超过 UI 声明。

建议给 Job 冻结 `candidate_scope_ids`，之后 validate/mutation/trial/review/freeze 只作用于该 Job Selected Candidate Set。产品不应依赖人工清理 candidate 目录。

## 11. Approval Operator 新封装还缺真正端到端测试

Core 已有真实 OpenSSH crypto test，但本次新增的 `initialize_local_signer / prepare / sign / verify` wrapper 测试目前主要只覆盖 prepare。

建议新增：

```text
test_operator_approval_full_local_flow
```

真实串：`signer-init → prepare → sign → verify`，再覆盖 wrong key、stale plan、revocation、expiry。

## 12. Approval 页面 APPROVED 可能是 stale UI 状态

当前 `_approval_review()` 只要历史最新 `acceptance.preflight == PASS` 就显示 APPROVED；打开页面时不会重新验证当前 approval/manifest/plan/allowed-signers/revocation/expiry。Core Promotion 会再次校验，所以安全 Gate 没被绕过，但 UI 可能展示陈旧批准状态。

建议增加 `APPROVED_CURRENT / APPROVED_STALE`，或页面读取时调用纯只读 current verify。

## 13. Runtime Profile 默认已切 v15

JobController、CLI acceptance 默认与 `dev-api.ps1` 已改为 `artifacts/runtime-profile-v15.json`。Execution Contract 当前仍是：

```text
663374ea6b647f4f7f27a706bc8d1a3e2c6a0c725052e8cb3c7bb10ca6f7dba6
```

真实 E2E 前仍需确认 v15 Profile 是真实 Probe 产物，Evidence、Contract ID、DB Build 都匹配。

## 14. GitHub 独立 CI 仍没有

当前仍是 Branch Protection OFF、Statuses 空、Workflow Runs 空、Commit unsigned。本次新增测试没有远端独立 CI 证据。

## 15. 当前评分

| 维度 | 评分 |
|---|---:|
| Deterministic Core | 9.0 |
| Evidence / Acceptance | 9.1 |
| AI Control | 8.7 |
| Product Layer | 8.4 |
| Frontend UX | 8.0 |
| Human Approval UX | 7.8 |
| Strategy Semantics | 7.8 |
| Active Case Scale | 5.0 |
| AI Exploratory | 5.5 |
| Real Xugu E2E | 未完成 |

## 16. 下一提交优先级

```text
P0-1 持久化 Strategy Completion Evidence
P0-2 Job-owned Candidate Set
P1-1 Operator Approval Full Integration Test
P1-2 Approval Current Validity Projection
P1-3 Runtime Profile v15 Real Probe
P1-4 Active Case Pack 扩到 180~300 Standard Cases
```

## 17. 最终判断

`f168702` 是一笔方向正确、质量不错的提交。Smoke 生成与本地 Human Signer 都真正向前走了一步，而且没有为了体验拆掉 Human Gate。

下一步最重要的是把 **Strategy Completion** 和 **Candidate Selection** 也变成 Job 自己的不可变事实，然后再跑真实 Smoke / Standard / Human Sign / Promotion / Post Regression / Post Acceptance E2E。
