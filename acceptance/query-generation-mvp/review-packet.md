# JOIN 候选评审包：v12

状态：21 条候选保持 `review`，Package Integrity 为 PASS，Readiness 为 WAITING_APPROVAL，Final Acceptance 为 HOLD。

## 本轮输入

- Contract：`2f37cd4c97ddcf53407cbd985fb9dc68dc21ccd18626b199da9aaf54a3ff4a75`。
- Runtime Profile：`dd656644fc3e87223cc25d9eb94cfc26e025d90d9256d2bcd9ac2d8315f67493`，文件 `artifacts/runtime-profile-v12.json`。
- Manifest：`3986441afbf95625ccc195734ffa62262b1197ac256660d7f63236d03a588a82`。
- 当前未审批计划：`9ce4ff687d99b30081ae076e34e6ddda73bf4e4f101ff8af6e7c45d944cb7fab`。
- DB build：`2026-05-18 12:11:00 BETA-11679_11665`。每次 Trial/适用 Mutation 均保存任务开始和结束的只读 `SHOW build_time;` 观测。
- [Trial 索引](trial-run-index.json)：21/21 真实双跑 PASS，原始返回行完整留存；步骤哈希由行内容重算。
- [Mutation 索引](mutation-validation-index.json)：5 KILLED、16 NOT_APPLICABLE；适用项有 baseline×2、mutated×2、SQL 摘要和原始行。
- 现有 Active 真实回归：30/30 PASS，`artifacts/runs/query-active-regression-v12.json`。
- 框架：209 passed、1 skipped。Windows 驱动集成项跳过；上述真实执行另在 WSL 使用 xgcondb 完成。
- Active Pairwise：17/137，缺 120。候选全部晋级后的 provisional 为 137/137，不属于当前 Active 结果。
- PR/GitHub CI：DEFERRED_BY_USER。

## 人工复核步骤

1. 在 [候选页面](http://127.0.0.1:5173/candidates)逐例核对用例目标、SQL、每步 Expected、comparison、Coverage Claim、Oracle。
2. 对照 run1/run2 原始结果和 Mutation。下载完整 Trial/Mutation JSON 可查看全部行；分页仅影响页面展示。
3. 对每条作出明确通过/退回结论并留下原始评审引用。历史 AI 技术复核不构成本轮人工批准。
4. 通过 `xgtest candidate review CASE_ID --reviewer PRINCIPAL --reference REVIEW_REF --coverage-reference COVERAGE_REF` 记录通过项。本命令记录评审意见，不签发正式晋级批准。
5. 记录评审会改变 YAML 字节，必须重新 freeze-package、verify-package，并重新生成 PromotionPlan；上方未审批计划仅用于当前快照复核，不能在评审改写后沿用。
6. 人工操作员对最终计划的 Approval Payload 使用本人受信任的 SSH 签名密钥签署，namespace 为 `xgtest-promotion`。普通 AI/只读 Web 不提供签发接口。受信任 principal、公钥及 allowed-signers 由操作员提供，当前未配置正式密钥或签名。
7. 通过签名批准后，执行 `xgtest acceptance promote-batch --approval APPROVAL_JSON --allowed-signers TRUST_FILE`。旧单例 promote 入口拒绝正式晋级。
8. 按 Receipt 的实际 Active 集运行全量回归，再生成 post-promotion 验收与覆盖。当前该部分仍待实现/执行，不能仅将 provisional 改名为 Active。

## 已知边界

批次发布明确标记 RECOVERABLE_BATCH：可断点恢复，当前目录 Loader 仍可能看到批次中间状态。尚未实现单一 Active Manifest 原子发布。
签名验证能够核对计划、身份、过期与撤销；它不抵御同时拥有整个仓库和信任库写权限的同一系统用户。

本包是技术证据与评审输入，不是批准记录。
