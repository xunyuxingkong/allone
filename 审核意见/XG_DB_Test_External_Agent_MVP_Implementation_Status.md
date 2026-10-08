# 外部 Agent MVP 实施记录

日期：2026-09-30。承接《XG_DB_Test_AI_Driven_Usable_MVP_Next_Step_Plan.md》，按用户后续意见调整为外部 Codex/Agent 驱动。

## 本轮实现

| 计划能力 | 当前实现 |
| --- | --- |
| 四个 Application Services | Project、Module、Candidate、Acceptance；复用既有 Core |
| Intent/Plan/Action/Job | 三类 Query 意图、固定动作白名单、严格参数、前置条件校验 |
| 外部 AI 决策入口 | 共用控制器的 CLI 与 7 个 stdio MCP 工具；无内置 LLM API Key 依赖 |
| 文件 Job | 原子状态文件、持久化检查点事件、项目/任务锁、revision、请求去重 |
| 中断恢复 | 普通动作恢复重新预检；保留历史、复用证据；晋升恢复委托 Core journal |
| Failure Analyzer | 接收外部 Agent 分类与解释，保存建议，不能改写执行事实 |
| AI Technical Review | 完整上下文与哈希绑定；独立 AI 记录，不能代替人类评审 |
| 晋升后验证 | 晋升后的新回归为前置条件；调用既有 Post/Final 验证 |
| 最小前端 | Job 列表、详情、动作记录、阻塞、分析、候选证据入口 |
| 分层身份 | 新增控制面代码纳入 control_plane；执行 CID 未变化 |

使用说明见 `docs/external-agent-jobs.md`。

## 实际证据及限制

- `query.status` 任务 `db6e12823e694371bf3a5be3f5a67a41` 完成项目、模块、覆盖检查。
- 完整测试任务 `94b3d304119446a3bb5cc3ffe78dd33a` 的真实预检被数据库网络阻塞；已保存失败与外部 Agent 分析。Windows/WSL 到 `192.168.2.236:1907` 都连接超时。该任务没有本轮真实回归 PASS。
- 既有 21 条候选的 Static/Trial/Mutation 复用校验通过；独立 Application Service 冻结候选包返回 package_integrity=PASS、readiness=WAITING_APPROVAL。这是旧证据的当前完整性检查，不是本轮新执行。
- 已阅读 21 条 SQL、Expected 和双跑原始行；完整任务因预检阻塞，尚未通过控制器提交这一批技术评审。没有写入人类评审或签名。
- 活跃 JOIN 覆盖仍为 17/137，候选晋升后预计 137/137；Query 全模块仍为 MODULE_FULL_INCOMPLETE。
- 执行 CID 保持 `f7589aabf3714f1897cf8bd84eb9de7fdc0f19acadf881be4548d2a4ca172680`；Runtime Profile 沿用 v14。没有重做 v15 制品。
- 未将 MCP 写入用户全局配置。项目服务已通过 stdio 协议握手、工具发现和调用；当前聊天尚未重新加载为已连接 MCP 客户端。

## 验证

- 新增控制器测试覆盖：支持/拒绝意图、未知动作与越权参数、动作顺序、revision、幂等、人工门禁、恢复保留历史、部分事件写入、锁、只读 API、失败展示、环境漂移、晋升恢复与后置回归、浮点上下文哈希。
- 合成恢复测试仅在临时目录中模拟批准与执行结果；不能充当真实数据库验收或真实人工批准。
- 前端构建通过；既有大 bundle 提示仍存在，本轮未扩展做无关拆包优化。
- Browser 专用插件不可用，使用随环境提供的 Playwright + Edge 检查列表、详情、动作展开和移动布局；未安装新浏览器。移动导航新增第六项后已调整为六列。
- 最终全量框架测试：260 passed、1 skipped（真实数据库集成项）、1 个现有 TestClient 依赖弃用提示；其中新增 21 项控制器测试。
- 前端 `vue-tsc -b && vite build` 通过；MCP stdio 握手、7 个工具发现及 list 调用通过。桌面 1440×1000、移动 390×844 下完成列表→详情→动作展开，pageerror 为 0；移动六个导航项同排、无横向溢出。

## 剩余步骤

1. 恢复目标数据库连通性，对现有完整任务 resume，再执行 live preflight 与 Query 回归。
2. 由外部 Agent 提交绑定当前上下文的 21 条技术评审；冻结 Job 候选包。
3. 完成真实人类 ReviewEvidence、CoverageReview；重新冻结包和计划，取得真实签名。
4. 执行签名预检、晋升、晋升后真实活跃集回归与 Post 验证；更新与最终源码匹配的发布检查后确认 Formal Final。
5. 用户之前延后的 PR/GitHub CI 保持延后，不虚构完成。

因此本轮完成了可独立实施的控制器、适配入口和页面；完整真实 E2E 与正式人工验收仍未完成。
