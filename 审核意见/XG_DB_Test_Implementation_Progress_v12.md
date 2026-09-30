---
document_type: implementation_progress
updated_on: 2026-09-30
source_plan: XG_DB_Test_Optimized_Review_and_Implementation_Plan_fce7854.md
implementation_status: in_progress
ci_disposition: DEFERRED_BY_USER
---

# 实施进度与剩余事项：v12

本文对应优化实施计划，记录实际实现和未完成边界，不将整份路线标记为完成。原评审文档保留历史基线。

## 本轮已实现

| 范围 | 实现与证据 |
|---|---|
| A02 字节稳定 | Trial/Mutation/Acceptance JSON 及冻结清单引用的 Query YAML 固定 LF；仅规范化相关 Active YAML 的行尾 |
| A03 Trial Gate | Writer、Acceptance、Promotion、Web 共用校验；严格 Profile 加载；空/子集/错误结构的 Index 拒绝 |
| A04 原始行 | XGR1 可逆 JSON 编码与 XGC1 重算；保留物理顺序，双跑/Mutation 按 comparison 比较；rowsort 保留重复次数 |
| A05 Mutation | 跨 case、缺哈希、未知策略及错误适用性拒绝；KILLED 必须重验两次 baseline 和两次 mutated 的原始行/SQL/摘要/Build |
| A06 晋级前包 | Manifest 固定候选集合和 SHA；核对索引、原始 probe、覆盖；完整性与审批状态分离；只读 Preflight |
| A07 存储/恢复 | 本地内容寻址制品不可变；原子 Writer；OS 锁、输入快照、日志、Receipt 与幂等恢复；明确 RECOVERABLE_BATCH |
| A08 批次入口 | SSH 签名绑定确切 manifest/plan/principal/有效期；允许 signer 校验；旧 CLI 单例 promote 拒绝正式晋级 |
| A09 评审界面 | 逐步 SQL/Expected/实际行、完整 Trial/Mutation 下载、Oracle/评审绑定状态；启动脚本固定 8001 API 与 5173 UI；修复窄屏覆盖表溢出及异步旧页面结果回填 |
| A10/A11 本轮验证 | 新 Contract/Profile、真实 Mutation/双跑/现有 Active 回归、框架、前端构建与包验证完成并留档 |
| C02 的兼容准备 | QueryExecutable/Compiler 已接入隔离 Worker；Worker 接收 ID、timeout、steps，不接收治理/评审/覆盖字段；旧 YAML 兼容加载 |
| C03 的兼容准备 | JOIN 适用性、变异 SQL、候选 ID 抽入 FeaturePlugin/Registry；Lifecycle 不含 JOIN ID 前缀或 predicate 分支；完整 Generator/Validator 服务迁移尚未结束 |

这不代表 A01–A11 的全部设计细节都已封闭：独立 AcceptanceScope DTO、post-promotion 完整验证、统一最终摘要生成、完整原子 Active 发布及审批服务统一仍有剩余工作。

## v12 可复核结果

| 检查 | 实际结果 |
|---|---|
| 真实 Trial | 21/21 PASS，两次原始行完整 |
| 真实 Mutation | 5 KILLED、16 NOT_APPLICABLE；KILLED 保存 4 次执行报告 |
| 当前 Active 回归 | 30/30 PASS；不是晋级后回归 |
| Framework | 209 passed、1 skipped；`artifacts/runs/framework-tests-v12.xml` |
| Schema / Contract | 导出完成，`CONTRACT_DESCRIPTOR_OK` |
| 前端构建 | PASS；已有大于 500 kB 的 chunk 警告尚在 |
| Package | 21/21，Integrity PASS，Readiness WAITING_APPROVAL |
| Promotion Preflight | BLOCKED，21 条缺少正式 Review/Coverage Evidence；没有执行晋级 |
| 覆盖 | Active 17/137；provisional 137/137 |
| 正式验收 | HOLD；PR/CI 为 DEFERRED_BY_USER |

Contract：`2f37cd4c97ddcf53407cbd985fb9dc68dc21ccd18626b199da9aaf54a3ff4a75`。

Profile：`dd656644fc3e87223cc25d9eb94cfc26e025d90d9256d2bcd9ac2d8315f67493`。

Manifest：`3986441afbf95625ccc195734ffa62262b1197ac256660d7f63236d03a588a82`。

未审批 Plan：`9ce4ff687d99b30081ae076e34e6ddda73bf4e4f101ff8af6e7c45d944cb7fab`。

DB Build：`2026-05-18 12:11:00 BETA-11679_11665`。

当前 [评审包](../acceptance/query-generation-mvp/review-packet.md)、[包验证](../acceptance/query-generation-mvp/package-verification-v12.json)、[预检](../acceptance/query-generation-mvp/promotion-preflight-v12.json)、[验收摘要](../acceptance/query-generation-mvp/final-acceptance.json) 已更新。v9/v10/v11 历史证据和候选备份保留，本轮 v12 是真实重执行，不是替换旧制品 ID。

## 浏览器验证

环境：`http://127.0.0.1:5173`，API `http://127.0.0.1:8001`。Browser plugin/skill 未提供；使用现有 Playwright 和已安装 Edge，无新增浏览器依赖。

验证路径：候选详情 → 查看已核验及两次完整结果 → 点击 Trial 下载 → 返回候选列表。桌面 1440×1000 和窄屏 390×844 均检查；页面非空、无框架错误覆盖层、无相关 console/pageerror。窄屏覆盖表导致的整页横向溢出已修复。

`QUERY.JOIN.203908E1` 下载 SHA：`dceefec72a0602667a2bb11b5fadd8346167a777fa650708e3702611f83c43bc`，与 Index 一致；run1/run2 各 5 行。该页面 Trial 已核验、Review 待评审。没有以页面字段存在冒充人工批准。

本轮未逐一做 21 条候选的人工业务复核；页面浏览不等于 B01 人工批准。没有验证跨 50 行的真实分页场景，本批样本未达到该行数。

## 尚待执行的顺序

1. 补齐 A06 的 post-promotion verifier、Final Summary 派生及独立 Scope；A07 完整发布点/更多恢复边界；A08 统一应用服务中的审批消费及撤销配置入口。保留当前受限批处理声明。
2. 按 B01，由人工对稳定评审输入作出逐例决定，提供评审引用和受信任签名身份。记录 Review 后 YAML 字节改变，要重新 Freeze/Plan/签名，不能沿用上方计划。
3. B02–B07：可信批准绑定、全包预检、批次晋级、实际 Active 全量回归、post-promotion 137/137 和最终验收。当前全部未完成，不能自动补造批准。
4. C01：先实现 Execution/Design/Governance/Suite 分层与旧 ID 迁移。当前仍使用保守单一 Contract；测试和 CLI 改动仍会使其变化。
5. C02/C03：完成 Asset/Executable schema 导出与服务接入；扩齐插件的生成、静态验证、覆盖和变异接口，再移除 Candidate/Package 等剩余 JOIN 耦合。
6. C04/C05：CLI/Web 共用 Application Services；ModuleTestSpec、Inspect、Unified Preflight，未建模 Feature 明确显示。
7. D01–D05：Action/Policy/Intent、确定性 Planner、持久 Job/Event Log、幂等 Orchestrator/Recovery/Completion、Agent API 和 Job UI。
8. D06：真实 full_test 到 WAITING_APPROVAL；人工签名后继续执行并核对 Completion。
9. D07：Filter，再 Aggregate，各自独立 Model/Constraint/Mutation/Coverage，通过通用插件接口接入。

后续平台工作未完成的原因是尚未实施；不能全部归因于人工门禁。按原计划，人工批准缺失期间可继续做验证器、评审界面和下一阶段设计准备。

## 发布与存储边界

- 当前 Loader 扫目录，批次中间状态可能可见；没有宣称事务原子性。
- 断点恢复测试覆盖写 Active 后、删候选后中断及重复恢复，另覆盖日志目标篡改和额外 Active 文件。锁竞争、全部崩溃位置、发布后回归失败回退尚未全部测试。
- 签名验证测试使用临时测试密钥，不是正式人工批准。未创建/配置用户正式密钥、未签署本批次。
- 同一系统用户持有仓库和信任库全部写权限，不在签名防伪边界内；底层函数不是外部授权 API。Application Services 统一授权尚待 C04。
- 内容寻址原始制品仍在本地 ArtifactStore；保留此前的 Git 忽略策略。共享/迁移需携带引用的原件，仅提交索引无法复核本地未提交原件。
- 本轮未提交或推送，工作区更新待用户审阅。
