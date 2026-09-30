# 98570cf 审核意见修复记录：v13

日期：2026-09-30。依据：`XG_DB_Test_Latest_Implementation_Quality_Audit_98570cf.md`。
本记录描述 v13 工作区与制品状态；是否已提交应以 Git 状态为准。原审核文档保留不变。

## 1. 当前结论

- JOIN 技术证据刷新完成，冻结包完整性 PASS；Readiness 为 WAITING_APPROVAL。
- 正式验收仍为 HOLD：21 条真实候选没有本轮人工评审记录或受信任人工签名，尚未执行晋级及真实 post-promotion 验收。
- GitHub CI 按此前用户指示继续跳过；该决定不自动构成正式发布的 CI 豁免。
- 平台与 AI 控制面仍未完成，不能把本轮基础修复解释为全模块测试平台验收。

## 2. 本轮已完成的修复

| 审核风险 | 修复与证据 | 边界 |
| --- | --- | --- |
| Contract 过宽 | descriptor v2 拆成 runtime、comparison、execution_schema、design、generator、governance、control_plane、suite；执行身份只由前三层组成，冻结包另绑定设计/生成器/治理身份 | 同文件内的 QueryCaseInput/loader 校验仍保守归入执行依赖，尚未完全拆开治理模型实现 |
| 旧身份迁移 | 保存 v12 descriptor 原件，并保留 v1 校验算法；新旧 ID 不互换。刷新 v13 Profile、Mutation、Trial 与回归 | 历史 capability 探针明确保留来源；本轮重新观察 build，未把历史类型探针说成本轮新运行 |
| 外围 JOIN 硬编码 | AcceptanceScope 统一候选/Active/模型路径与覆盖策略；Package、Review、Promotion、Post verifier、Web 通过 Scope/Plugin 路由；CLI 支持 scope-file；导出 Scope 与 QueryExecutable Schema | 仍只有 JOIN 插件；不宣称新增 Filter/Aggregate 功能。完整 Generate/Trial/Coverage 应用服务层尚待后续 |
| 发布过程中读取半批次 | 同项目跨进程发布锁与读取锁；Loader、冻结包、计划、验证器共享锁。中断 journal 阻止读取，恢复完成后开放；Windows 跨进程等待与中断读取检查通过 | 这是目录协议的一致读取补救，仍标记 RECOVERABLE_BATCH；尚未实现版本化 ActiveManifest 与原子指针 |
| Approval 撤销未接入 | ApprovalService 统一签名/时间/撤销验证；CLI 的 verify-package、preflight、promote-batch、post verifier 接入 revoked；每条发布前再次验证 | 配置撤销文件后，缺失或格式错误均拒绝；正式信任库/撤销文件由操作员提供，当前没有真实批准 |
| CI 状态硬编码 | governance-policy.json 记录已授权的 DEFERRED_BY_USER；冻结策略内容与字节 SHA，修改策略使旧包失效 | CI_PASS 声明没有独立 CI 制品不能放行；默认 allow_release_with_ci_exception=false |
| 计数歧义 | 分开 case_verified_count、case_failed_count 与 package_error_count；有全局错误时不把所有用例错误地计为失败 | 兼容保留旧计数字段；必须结合 package_integrity 阅读 |
| Post Acceptance 缺失 | freeze-post-package / verify-post-package：绑定 Manifest、Receipt、Approval、Profile、回归；验证收据完整性、Active 增量、源文件移除、每条治理证据与行哈希、全量回归 ID/步骤/源哈希、Active 覆盖 | 单元检查使用明确标记的合成评审/签名，不作为真实人工批准；真实 post 包仍不存在 |
| 回归 build 复现依据 | 有 DB build 的 Profile 要求 post 包携带 regression-build；核验回归前后 SHOW 值相同且观测时间包围回归时间 | 在正式晋级后必须重新运行全量回归及 build 观测；现有 30 条回归是晋级前基线 |
| Final 手工汇总 | generate-final 重新调用 verifier；框架/前端退出状态、原始日志、JUnit、源码身份均绑定；从 JUnit 推导通过/跳过计数，保存 source_state_id 与输入字节绑定 | 不相信旧 final-acceptance.json 的 PASS；没有 post 包时生成 HOLD；CI 豁免仍需单独明确配置 |
| 原始制品无法携带 | ArtifactStore Protocol + ArtifactRef；LocalStore 支持硬链接不支持时的加锁原子替换；完整 ZIP bundle 导出/导入，先验 SHA/长度/范围再写入 | 尚无 S3/MinIO 实现或远端存储配置；本地包不会自动上传 |
| Codec 平台一致性 | 冻结 XGR1/XGC1 字节和哈希向量；NULL、Decimal、负零、NaN、Infinity、Unicode、日期/时区与二进制在 Windows、WSL Linux 核对通过 | 没有把 NUMERIC 驱动返回 float 的精度问题改称支持；其既有能力限制保留 |
| 过时进度文字 | v12 记录改为按基线提交说明；本文件明确区分实现、真实证据与待授权门禁 | 历史报告不改写成 v13 实测 |

## 3. 本轮实测结果

- 框架：232 passed、1 skipped、0 failed。跳过的是 Windows 缺少原生 Xugu 驱动的集成项；真实 DB 验证另在 WSL 完成。
- 前端：`npm run build` PASS；原有约 1.5 MB chunk 告警保留，本轮未宣称完成 bundle 拆分。
- 静态候选：21/21；真实双跑：21/21 PASS，每次执行完整行保留。
- Mutation：5 KILLED、16 NOT_APPLICABLE，适用项保留原始执行依据。
- 现有 Active 回归：30/30 PASS，前后 build 均为 `2026-05-18 12:11:00 BETA-11679_11665`。
- Active Pairwise：17/137，缺 120；provisional：137/137。
- [包验证](../acceptance/query-generation-mvp/package-verification-v13.json)：21 个用例验证成功，0 用例失败，0 全局包错误。
- [预检](../acceptance/query-generation-mvp/promotion-preflight-v13.json)：被缺少逐例人工评审阻止。
- [机器生成 Final](../acceptance/query-generation-mvp/final-acceptance.json)：HOLD；缺真实 post 包、CI 门禁未完成。不是数据库执行失败。
- 本地 API/UI 已重新拉起；HTTP health、Profile、21 条候选和前端入口均返回 200，候选 Trial 标记 verified，review_recorded=false。

### 当前身份

- Execution Contract：`46e6ceacf0503a315ab844929f3a287184461faa1a7c57ccbfd583d3f76d1ead`。
- Runtime Profile：`5fbbe255381418c934372a11107f4ce628b7c492726ed64926f32389d548ef02`，本地 `artifacts/runtime-profile-v13.json`。
- Manifest：`217a0ad9a300b4b9ddce671f139d48bf3c60277f73758f56e27381a859a2508f`。
- 未审批 PromotionPlan：`3ab6c67a0580b35affdc666f0610559cdb40796c8d2393b1303a03f4782911f1`。人工评审记录改变 YAML 后必须重新冻结与生成计划。
- Final source_state_id：`614b9cf3126964cdb58ab0db934ab6ecac54d38efaa139c9bc152fa959b3f90c`。

## 4. 制品携带

`artifacts/bundles/query-join-v13.zip` 已导出 62 个原始文件，含 Trial、Mutation、Profile、build 观测、回归、索引、验证输出、框架/前端日志与 JUnit；另携带原路径映射对象。

Bundle SHA-256：`10fbb7558e1c796cb011d6893cf72d1aab370e01699b440f1e51d914bb55b653`。

已导入独立空 LocalStore，逐个验证完整字节一致。`portable-evidence-v13.json` 记录包摘要；ZIP 仍遵循既有 artifacts Git 忽略策略，不能仅推送索引就宣称其他机器可独立复核。

API：`export_artifact_bundle(store, references, output)` 与 `import_artifact_bundle(store, source)`。导入保持内容寻址 URI；恢复到原 Trial/Mutation/Profile 位置时，调用者须按原路径映射校验项目范围。本轮只验证空内容存储迁移，不声称完成远端部署恢复演练。

## 5. 后续执行顺序

1. 人工逐例复核 21 条候选及覆盖声明，提供真实 reviewer/reference/coverage-reference。不得以本轮单元测试中的合成引用代替。
2. 对实际通过项运行 candidate review，重新 freeze-package、verify-package，生成新的 PromotionPlan。
3. 操作员配置受信任 allowed-signers 与撤销文件，用本人密钥签署最终 Manifest/Plan；签名 namespace 为 xgtest-promotion。
4. verify-package --preflight 与 promote-batch 均传 --approval、--allowed-signers、--revoked。审批过期/撤销/输入变化必须重新审批。
5. 保存真实 Receipt；按实际 Active 全量运行回归，保存回归前后 SHOW build_time。验证 Active 覆盖确为 137/137。
6. 冻结并验证 post 包，再运行 generate-final。CI 继续跳过时，正式发布是否允许豁免需另有明确决定；本轮保持默认 HOLD 策略。
7. 后续平台工作：版本化 ActiveManifest、远端 ArtifactStore、完整应用服务层和控制面结构化状态 API。
8. 通过上述验收后，再推进 AI 编排、query.full_test、Filter/Aggregate 插件；本轮未提前开始这些新功能。

### Post CLI 示例

以下路径是人工晋级后的真实输入占位，必须替换为实际文件，不可直接当成本轮已存在的证据：

```powershell
.venv/Scripts/xgtest.exe acceptance freeze-post-package --candidate-manifest acceptance/query-generation-mvp/package-manifest.json --receipt <真实Receipt> --regression <晋级后全量回归> --regression-build <回归前后build观测> --runtime-profile artifacts/runtime-profile-v13.json --approval <真实签名Approval> --output acceptance/query-generation-mvp/post-package-v13.json
.venv/Scripts/xgtest.exe acceptance verify-post-package --package acceptance/query-generation-mvp/post-package-v13.json --allowed-signers <TrustFile> --revoked <RevocationsFile>
```

若执行、比较或执行 Schema 身份改变，应建立新的 Runtime Profile 并重跑；若只改评审/治理，执行身份可保持，但旧 Manifest/Plan/Approval 仍需重新冻结与校验。
