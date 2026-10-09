# 6311887 审核修复实施记录

日期：2026-10-08。依据 `XG_DB_Test_Latest_Code_Review_6311887.md`，本轮优先完成第 16 节要求的四项修复。

## 修复结果

| 审核问题 | 实施结果 | 核验 |
| --- | --- | --- |
| P0 技术评审 FAIL/CONCERNS 被当作完成 | 分开记录 valid 与 accepted；只有 PASS + READY_FOR_HUMAN_REVIEW 可进入验收。其他结论保存评审记录、Job BLOCKED，并返回明确原因 | FAIL、CONCERNS、PASS 但建议人工核查、重评通过、上下文过期测试 |
| P1 Job 缺少控制面身份 | 创建时冻结 control_plane_layer_id/git_commit；Action/Resume 前核对，执行期间再检查。源码变化时 BLOCKED，已有结果保持真实；旧任务缺少身份时拒绝自动继承新版本 | 控制面变化而 Execution CID 不变、旧任务缺少身份、Action/Resume 拒绝测试 |
| P1 多 Job 交替修改全局候选 | 创建、执行、恢复均在项目锁下检查单个可修改工作流；PLANNED/RUNNING/WAITING_APPROVAL/BLOCKED 占用位置，query.status 可并存 | 各状态拒绝第二个任务、FAILED 旧任务恢复竞争、并发创建测试 |
| P1 凭据/异常泄露 | WSL 使用子进程 WSLENV 环境继承，密码不进入 argv；Worker 只返回安全错误码与通用提示。回归失败只保留摘要和原始制品引用 | 启动命令无密码、真实 WSL 环境继承、Driver 自定义异常不进入结果文件/Event/Final Report、回归摘要不复制行数据测试 |

没有更改执行 Core、SQL 模板或 v14 候选数据。身份文件只更新控制面和测试层内容，Execution CID 仍为：

`f7589aabf3714f1897cf8bd84eb9de7fdc0f19acadf881be4548d2a4ca172680`

使用说明已更新到 `docs/external-agent-jobs.md`。

## 验证

- 四项修复相关控制器与服务测试：39 项，包括原有 21 项及新增 18 项。
- 最终全量框架：278 passed、1 skipped、1 个 TestClient 依赖弃用提示。真实数据库集成项仍因环境配置跳过。
- 真实 WSL 子进程检查：变量成功继承、启动命令不含测试凭据、退出码 0。没有修改父进程或系统 WSLENV。
- 真实 MCP 调用：任务 `d373254aa0b84b73bd49ae594c51ed74` 完成创建 query.status → 项目检查 → 模块检查 → 覆盖检查 → COMPLETED；同时验证第二个可修改任务被拒绝。活跃 JOIN 覆盖 17/137，候选晋升预计 137/137。现场信息保存在忽略目录 `artifacts/review-6311887-mcp-verification.json`。
- MCP 实际调用中发现 Git 元数据查询会继承协议标准输入并挂住捕获管道，已改为 DEVNULL 输入、临时输出文件和有限超时；新增真实 stdio 子进程创建/检查回归测试，避免只验证工具发现而遗漏执行路径。
- 本轮没有前端源码变更，因此没有重复前端构建或扩展页面。
- 以上均为本地验证，未把它们描述为 GitHub 独立 CI；用户此前延后的 PR/CI 仍为延后。

## 真实 E2E 的当前阻塞

目标 `192.168.2.236:1907` 当前仍连接超时，已保存本轮网络检查结果。无法执行新的真实 Query 回归、候选流程及 Post 验证，不能宣布真实完整 E2E 通过。

新版 WSL Worker 的独立只读 preflight 也返回 BLOCKED / DATABASE_NETWORK_UNREACHABLE，结果保存在 `artifacts/review-6311887-worker-preflight.json`。这验证了新凭据通道能启动实际 Worker 并安全记录连接阻塞，不代表完整工作流通过。

原完整任务 `94b3d304119446a3bb5cc3ffe78dd33a` 来自身份字段引入之前，仍保留历史记录和证据，读取会提示 `JOB_CONTROL_PLANE_IDENTITY_MISSING`。它处于 BLOCKED，按单工作流规则仍占用可修改任务位置。没有自动改写旧任务身份、删除历史、或将其标成完成来腾出位置。

数据库恢复后，操作者还需明确确认旧任务的跨版本处理。当前没有自动迁移入口；后续处理应保留旧检查点和旧/新身份记录，并重新预检。真实人工 ReviewEvidence、CoverageReview 与签名批准仍是晋升前置条件。

## 本轮未扩展的建议

- Event Delta/周期 Snapshot：审核认为 JOIN MVP 可暂用当前完整检查点，保留后续优化。
- ActionResult 通用大小限制：已先收窄回归失败投影；其他类型的统一大小策略待后续专项处理。
- query.join.verify 产品命名/默认权限，以及 UI 独立展示 Workflow 与 Formal Acceptance：当前行为沿用已公开说明，本轮先按第 16 节完成四项修复。
- ActiveManifest、远程 ArtifactStore、Filter、Repair、多 Agent 和常驻调度未进入本轮范围。
