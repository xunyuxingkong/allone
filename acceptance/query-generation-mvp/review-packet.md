# JOIN 候选评审包：v14

21 条候选保持 review；Package Integrity=PASS，Readiness=WAITING_APPROVAL，Final=HOLD。

## 当前输入

- Execution Contract：`f7589aabf3714f1897cf8bd84eb9de7fdc0f19acadf881be4548d2a4ca172680`。
- Runtime Profile：`15f80cc0258cd008d4b70accdc6b0cc89e17a6ff369a61b1d572cd25da05a7ea`；`artifacts/runtime-profile-v14.json`。
- Manifest：`bccf05ed22a97384a3ebbc4626db67eedde8dfec01ffd718e311241ce410e615`。
- 尚未审批的 [完整 PromotionPlan](promotion-plan-v14.json)。
- [Trial 索引](trial-run-index.json)：21/21 双跑 PASS，完整原始行。
- [Mutation 索引](mutation-validation-index.json)：5 KILLED、16 NOT_APPLICABLE。
- 现有 Active 回归 30/30 PASS；Active 覆盖 17/137，provisional 137/137。
- 框架 239 passed、1 skipped；前端独立 `npm ci` 后构建 PASS，环境/依赖快照可复核。
- CI=DEFERRED_BY_USER，正式发布豁免未开启。

## 人工评审与签名

1. 在 [候选页面](http://127.0.0.1:5173/candidates)逐例核对 SQL、Expected、Comparison、Oracle、Coverage Claim、run1/run2 全部行及 Mutation。
2. 对通过项留存真实评审引用，再执行 `xgtest candidate review CASE_ID --reviewer PRINCIPAL --reference REVIEW_REF --coverage-reference COVERAGE_REF`。历史 AI 技术复核不替代本轮人工批准。
3. YAML 改变后重新 freeze-package、verify-package、生成 PromotionPlan；本页计划即失效。
4. 操作员使用本人受信任 SSH 密钥，对最终 Manifest/Plan 签名；namespace=xgtest-promotion。TrustFile 与 RevocationsFile 由操作员配置。
5. Preflight/Batch/Post 均传 approval、allowed-signers、revoked，批量发布前每条再次核验。
6. 晋级后按 Receipt 的实际 Active 集全量回归，保存前后 build 观测；freeze-post-package、verify-post-package、generate-final。

## 本轮边界

读取锁阻止正在晋级或中断批次的部分可见状态；仍为 RECOVERABLE_BATCH，版本化 ActiveManifest 尚未完成。Post verifier 与派生 Final 已实现，真实 post 验收尚未执行。

[完整修复、证据与后续步骤](../../审核意见/XG_DB_Test_Quality_Audit_153ba26_Progress_v14.md)。本包是评审输入，不是人工批准记录。

现有前端/API 可访问，但自动审批检查拒绝了 API 重启命令，运行服务仍加载 v13 Profile。须停止旧 API 后运行更新的 `dev-api.ps1`，才能在页面中复核 v14 身份。
