# JOIN 候选评审包：v13

21 条候选保持 review；Package Integrity=PASS，Readiness=WAITING_APPROVAL，Final=HOLD。

## 当前输入

- Execution Contract：`46e6ceacf0503a315ab844929f3a287184461faa1a7c57ccbfd583d3f76d1ead`。
- Runtime Profile：`5fbbe255381418c934372a11107f4ce628b7c492726ed64926f32389d548ef02`；`artifacts/runtime-profile-v13.json`。
- Manifest：`217a0ad9a300b4b9ddce671f139d48bf3c60277f73758f56e27381a859a2508f`。
- 尚未审批的 PromotionPlan：`3ab6c67a0580b35affdc666f0610559cdb40796c8d2393b1303a03f4782911f1`；[完整计划](promotion-plan-v13.json)。
- [Trial 索引](trial-run-index.json)：21/21 双跑 PASS，完整原始行。
- [Mutation 索引](mutation-validation-index.json)：5 KILLED、16 NOT_APPLICABLE。
- 现有 Active 回归 30/30 PASS；Active 覆盖 17/137，provisional 137/137。
- 框架 232 passed、1 skipped；前端构建 PASS。
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

[完整修复、证据与后续步骤](../../审核意见/XG_DB_Test_Quality_Audit_Fix_Progress_v13.md)。本包是评审输入，不是人工批准记录。
