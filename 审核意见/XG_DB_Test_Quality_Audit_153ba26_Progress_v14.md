# 153ba26 审核意见实施记录：v14

日期：2026-09-30。依据：`XG_DB_Test_Latest_Implementation_Quality_Audit_153ba26.md`。
本记录描述 v14 工作区与制品状态；提交与推送状态以 Git 为准。原审核意见保留原文。

## 1. 执行顺序与当前状态

阶段 A 仍缺少 21 条真实人工逐例评审、覆盖评审和受信任操作员签名。已请求这些输入，尚未收到；没有伪造 reviewer/reference 或签名，也没有执行候选晋升。

推进不依赖人工批准的底座，依序完成 B01、B02、B03，并修复审核文档指出的制品导入身份和发布检查复现信息问题。阶段 B 尚未全部完成，不能宣称 AI 控制面或 Query 全模块完成。

| 步骤 | 实现 | 证据与边界 |
| --- | --- | --- |
| B01 Execution Model 物理拆分 | `model_base`、`execution_models`、`evidence_models`、`governance_models`、`control_models` 分开定义；`core.models` 仅兼容导出；`QueryExecutable` 归执行模型 | Worker 模型、比较和 Profile 使用执行层类型。descriptor v3 的执行身份不再直接包含全体治理模型或 QueryCaseInput Schema；保留 v13 descriptor 原件与历史验证。治理模型变更不改变执行 ID 的检查通过 |
| B02 Feature Coverage / Module Regression | 覆盖只接受 Feature 路径内、对应 model_id/version 的 Active 声明；回归继续覆盖 Module 全部 Active 用例 | 两个历史 JOIN 基线显式登记在 `legacy_feature_assets`；错误放在其他 Feature 路径的 JOIN 声明不计入。Web/Post 输出分别标识 Feature 完成度和 Module 完成度，Module 保持 `MODULE_FULL_INCOMPLETE` |
| B03 MutationSpec[] / MutationPolicy | Plugin 可定义多条规则；逐条执行并验证完整规则集合、适用性、策略/规则版本及各自 SQL/结果证据；CLI 汇总全部结果 | 缺项、重复、未知规则、WEAK、交叉挪用执行证据均拒绝。单规则历史接口兼容；历史 v1 单规则证据按明确兼容条件读取。JOIN 仍保留既有一条规则；多规则验证使用明确标注的合成测试，不冒充多 Feature 实测 |
| Bundle 身份 | 导入可传 `expected_bundle_sha256`，先在同一打开文件上核对 ZIP SHA 再解析和写入 | 内部自洽但整个 ZIP 身份不符时，在写目标存储前拒绝；未声称完成远端存储 |
| Release 环境 | 记录 Python 版本/解释器、真实已安装 Python 包集、OS/arch；记录 Node/npm 版本、lock SHA、`npm ls --all --json` 依赖树，并生成 environment_id | 前端复制到独立临时目录，执行 `npm ci` 后 `npm run build`；安装/构建命令、目录、退出码及日志均绑定。检查源码涵盖前端根配置、public 文件和 Python lock。验证环境身份/依赖哈希，旧 schema 1 报告不能作为本轮 release 证据 |

审核文档中“其他 Feature 声明直接混入 JOIN 覆盖”的判断需要校准：原 `coverage_gap` 已过滤 model_id/version。本轮实际补的是路径归属隔离，不是声称过去将所有模型混算；17/137 的既有基线保持。

## 2. 集中验证结果

- 框架：239 passed、1 skipped、0 failed。跳过的是 Windows 无原生驱动的集成项；真实 Xugu 执行在 WSL 完成。
- 前端：独立目录 `npm ci` 与构建 PASS；Node v22.14.0、npm 10.9.2，Windows/AMD64。原有大 chunk 告警仍存在。
- 21 条候选静态验证与真实双跑 PASS；两次完整 Xugu 原始行保留。
- Mutation：5 KILLED、16 NOT_APPLICABLE；适用项保留两次基线/两次变异执行和 build 观测。
- Module Active 回归：30/30 PASS，执行前后 SHOW build_time 一致。
- DB build：`2026-05-18 12:11:00 BETA-11679_11665`，本轮重新只读查询；历史类型/能力探针明确保留来源，未改称新探针。
- 候选 SQL、Expected、Coverage 的语义哈希与刷新前逐例一致；只更新相关静态/执行/Mutation 证据。
- Active JOIN 覆盖 17/137，provisional 137/137；候选尚未晋升，不把 provisional 当成 Active 完成。
- Trial 索引及冻结包验证 PASS：21 条验证成功，0 用例失败、0 全局包错误；Readiness=WAITING_APPROVAL。
- Preflight 缺真实逐例评审而阻塞；Final=HOLD，缺真实 Post 包且 CI 门禁未完成。

本轮模型物理迁移改变执行身份，因此只做一次集中 v14 真实执行刷新。后续仅改治理/界面时仍需重新冻结相关包，不应机械地产生新执行版本。

## 3. 身份、原始制品与服务

- Execution CID：`f7589aabf3714f1897cf8bd84eb9de7fdc0f19acadf881be4548d2a4ca172680`。
- Runtime Profile：`15f80cc0258cd008d4b70accdc6b0cc89e17a6ff369a61b1d572cd25da05a7ea`，本地 `artifacts/runtime-profile-v14.json`。
- Manifest：`bccf05ed22a97384a3ebbc4626db67eedde8dfec01ffd718e311241ce410e615`。
- 当前机器证据见 `acceptance/query-generation-mvp` 中 v14 Package verification、PromotionPlan、Preflight、Release checks、Portable evidence，以及当前 Trial/Mutation 索引和 Final。
- 本地 `artifacts/bundles/query-join-v14.zip` 携带 66 个原始文件和原路径映射；已传预期 bundle SHA，导入独立空 LocalStore 后逐个核对完整字节。最终摘要以 `portable-evidence-v14.json` 为准。
- 原始制品仍按既有策略由 Git 忽略；仅提交索引不能使其他机器获得这些原始行，需要另行携带 ZIP。
- `dev-api.ps1` 和 CLI 默认 Profile 已切到 v14。自动审批检查拒绝了停止并重启现有 API 的命令，返回 `blocked by policy`，没有更具体原因。
- 现有前端 `http://127.0.0.1:5173` 返回 200、API health 正常，但运行中的 API 仍返回 v13 Profile；不能将其称为已加载 v14。需在原服务终端停止旧 API，再执行 `./dev-api.ps1` 加载本轮代码和 Profile。
- 本轮没有新增前端操作页面；新增完成度字段已经在后端读模型中提供，界面交互设计属于后续应用服务/控制面步骤。

## 4. 后续按序实施

1. 阶段 A：收到真实 reviewer、逐例评审引用与覆盖评审引用后，记录 Review，重新 Freeze/Verify，生成新 PromotionPlan。操作员签名后才 Preflight、Batch、全量回归/build、Post Freeze/Verify、Final。旧未审批计划不能直接复用为已批准计划。
2. B04 ActiveManifest：不可变版本清单、原子 current 指针、明确旧目录迁移/恢复协议；保存稳定 Active 集快照，再替换现有 RECOVERABLE_BATCH 的读取补救。
3. B05 ActiveCaseRepository：让 Coverage、Runner、Web、Package/Post 统一读取同一 Manifest 版本，检查源字节身份与项目路径范围。
4. B06 Remote ArtifactStore：实现远端内容寻址、存在性/完整字节验证、上传失败恢复及真实跨环境恢复。真实远端存储地址/凭据尚未提供，本轮未创建外部存储或系统配置。
5. B07 CiEvidence：CI run、commit、workflow、环境及完整日志/报告身份绑定；裸 `CI_PASS` 仍不能放行。用户此前要求跳过 PR/GitHub CI，真实触发继续遵守该决定。
6. B08 GovernanceExceptionApproval：单独签署范围明确的 CI/发布豁免，核验有效期/撤销和输入身份；当前 `allow_release_with_ci_exception=false`，没有新增豁免批准。
7. 阶段 C：按原审核计划建立 Application Services，统一 CLI/Web 的生成、执行、覆盖、评审、晋升操作及一致错误结果。
8. 阶段 D：结构化状态与行动契约、Planner/Orchestrator、AI 操作及停止/恢复边界；随后按计划验证多 Feature 和 query.full_test，不能先将 JOIN 覆盖等同全模块完成。

上面的未完成项是后续工作清单，不是本轮已实现声明。人工输入未齐不影响继续 B04 等独立底座开发。
