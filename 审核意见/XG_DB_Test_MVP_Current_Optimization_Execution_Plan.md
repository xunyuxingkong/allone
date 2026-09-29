# XG DB Test MVP 当前优化与执行计划

评估日期：2026-09-29。依据当前工作区代码、`acceptance/query-generation-mvp/`、`docs/G0A_ACCEPTANCE.md` 与 JOIN v2 AI 技术评审。工作区位于 `codex/join-model-v2`，存在大量未提交改动；本文件按工作区现状判断，不把旧计划的未勾选项直接当作仍未实现。

## 1. 当前基线

| 范围 | 当前状态 | 证据与边界 |
|---|---|---|
| Query Runner | 已有单用例子进程隔离、独立连接和超时控制 | 当前不复用 Session；`reset()` 明确为未实现，`cancel()` 未证明服务端停止。 |
| JOIN 生成 | Model v2、Template v2、`all_values` / `pairwise`、确定性生成、静态校验、双跑、Review/Promote 门禁已落地 | 只覆盖 JOIN 模型定义的组合，不代表数据库内核代码分支全覆盖。 |
| 真实证据 | 21 条候选静态校验、真实 Xugu 双跑通过；现有查询回归 30/30 PASS | 21 条仍为 `review`；本地 Trial Artifact 需要可核验的持久副本。 |
| 覆盖 | Active 17/137；21 条全部按当前 Claim 晋级的理论值 137/137 | 5 条 `less_equal` 候选缺少等值边界，不能把理论值写成验收结果。 |
| 评审 | AI 技术评审 16 条通过、5 条暂缓；真实人工评审尚未记录 | `review_evidence` 与 `coverage_review` 尚不能由 AI 报告代替。 |
| Web | Coverage、Candidate、Runtime 等只读页面和 API 已有；前端构建已纳入 CI | 候选页现核对双跑投影结果哈希；覆盖与候选详情已防止旧请求覆盖新数据。 |
| G0A | 候选 Contract/Profile 与能力探针已有记录 | `docs/G0A_ACCEPTANCE.md` 仍为 HOLD，尚无正式 Freeze Git 提交。 |

## 2. 优化优先级

| 优先级 | 优化点 | 当前问题 | 交付标准 |
|---|---|---|---|
| P0 | `less_equal` 边界与覆盖口径 | 5 条候选无法区分 `<` 和 `<=`；`int`、`null_side`、Active LEFT Claim、DB build 口径仍需确认 | 语义定义、SQL/Expected 与试运行证据一致；暂缓项有明确评审结论。按用户当前要求先跳过修改。 |
| P0 | 候选到 Active 的真实门禁 | 真实人工评审、晋级后回归和最终 Active 快照未完成 | 每条晋级候选具备 Review、Coverage Review、当前 Contract/Profile 证据；全量回归通过并生成最终快照。 |
| P1 | Trial Artifact 可移交 | 完整哈希已绑定，但原始制品仅在本机 | 存入受控、不可随意覆盖的位置；评审包包含相对路径、SHA-256、Contract/Profile 和取回方式；抽样取回可核验。 |
| P1 | Run History 并发写入 | `record()` 原子替换单个文件，但索引仍是无锁读改写 | 两个并发 Run 均出现在索引；重复 Run ID 行为确定；异常中断后可恢复。 |
| P1 | CI 与验收门禁 | 前端构建和常规 Python 测试已在 CI；真实 Xugu 测试需目标环境，分支保护属于仓库设置 | 合约检查、前端构建和候选静态门禁均有明确作业；真实验收在受控环境执行并保存证据；Required Checks 配置与结果一致。 |
| P1 | Host Identity | 裸 SHA-256 的内网地址可被字典反推 | 制定不泄露主机名、且跨运行稳定的目标标识；若改变 Profile/Contract，按版本迁移并重建证据。 |
| P2 | 晋级前批量预检与原子性 | 逐条晋级可能产生部分 Active 状态 | 先对全部目标做无写入预检；批量提交失败时不留下半批 Active，也不丢失候选。 |
| P2 | Cancel 服务端停止证明 | 进程超时不等于数据库端 SQL 已停止 | 真实长查询取消后，以服务端会话/语句状态确认停止，并记录清理结果。 |
| P2 | 完整 Session Reset | 当前 `reset()` 明确未实现 | 仅在引入连接或 Worker 复用前实施；事务、角色、Schema、参数、临时对象、锁和游标均有真实验证。 |
| 后续阶段 | Web Review/Promote、Catalog2、Selector、TestPlan、Result DB、Baseline/Delta | 超出当前只读 Web 与 JOIN 生成闭环 | 分别立项，先确认身份认证、审计和持久存储边界。 |

## 3. 完整实施顺序

### 阶段 A：固定可复核的工作基线

1. 清点当前未提交改动，按 Model/Template、候选与证据、Web、CI/文档拆分审查；记录每组文件和对应验证结果。不要用旧文档中的完成标记覆盖实际代码状态。
2. 固定当前 Contract Set、Runtime Profile、21 条候选和 21 份 Trial Artifact 的对应关系。更改 `models/`、`generators/`、相关 Schema 或生命周期代码前，先判断是否会改变 Contract Set 并使既有双跑证据过期。
3. 验证 Registry/Schema、非 Xugu 框架检查、前端构建、现有 Active 回归；将命令、版本、输出和失败项记录在同一验收记录中。

完成标准：任何人都能从提交、候选清单和证据索引定位当前基线；没有把本地 21/21 Trial 当作人工评审通过。

### 阶段 B：完成不依赖候选语义决策的可靠性优化

1. 将 Trial Artifact 及其索引存放到受控持久位置；复制后重新计算 SHA-256，验证与候选 `validation_evidence` 一致，并在评审包中注明读取权限和保存期限。
2. 为 Run History 的索引读改写增加同目录互斥或等价的单写者机制；保留当前原子替换，明确重复 Run ID、写入失败和损坏索引的处理。只改 History 相关代码。
3. 补齐 CI 中候选/覆盖的离线静态检查，区分无需数据库的 PR 检查与需要真实 Xugu 的验收作业；核查 GitHub Required Checks 配置。前端构建作业已存在，无需重复添加。
4. 复核 Web 只读状态与晋级门禁的一致性，包括失效 Artifact、Contract/Profile 漂移、旧请求结果和空候选集；不在页面开放 Review/Promote 写操作。

完成标准：证据可取回、并发写入不丢 Run、CI 分层清楚、Web 不把缺失或失效证据显示成已核验。

### 阶段 C：恢复暂缓的 JOIN 语义工作

此阶段按用户当前要求暂缓。恢复时先明确 `datatype=int` 的逻辑类型口径、`null_side=none` 是否需独立证明外连接、LEFT Active Claim 的 NULL 证明方式，以及是否要求精确 DB build。

1. 仅修复 `less_equal` 所需的测试数据与 Expected，使等值匹配在输出中可观察；补上针对 `<` 与 `<=` 的反例。若口径确认需要修改其他语义，再单独处理对应维度。
2. 版本化受影响的 Model/Template，重新计算 Contract Set；保留旧候选和 Trial Artifact 作为历史，不覆盖它们。
3. 按当前 Coverage Gap 重新生成必要候选，对相关候选静态校验；如 Contract/Profile 变化，重建 Profile 并对全部待晋级候选在真实 Xugu 上重新双跑。
4. 重新计算 Active 与 provisional 覆盖，检查每个 Claim 的 SQL、Expected、断言引用和维度值一致；更新 AI 技术评审与评审包。

完成标准：5 条暂缓候选有能检出边界错误的断言，所有拟晋级候选的静态与真实双跑证据绑定同一当前 Contract/Profile。

### 阶段 D：真实评审、晋级与最终验收

1. 评审人逐条核对 SQL、Expected、维度 Claim 和真实 Trial Artifact；对无法确认的类型或 NULL 口径单独记录待决项，不写入通过结论。
2. 将真实代码评审和覆盖评审引用写入各候选的 Review Evidence；在晋级前统一预检当前静态证据、语义哈希、Artifact SHA、Contract Set、Runtime Profile 和 Review Input Hash。
3. 只晋级全部门禁通过的候选；记录晋级清单。运行现有 Active 全量回归，重建正式覆盖快照，核对缺口数与晋级清单。
4. 更新 `final-acceptance.json`、G0A 验收文档和正式 Freeze 信息；未满足的条件保持 HOLD，不把理论 137/137 写成实际 Active 137/137。

完成标准：真实评审可追溯；晋级后回归 PASS；最终覆盖从 Active 文件重新计算；正式 Contract/Profile/Freeze 信息一致。

### 阶段 E：按使用需求处理后续能力

1. 如果需要一次晋级多条候选，先做只读批量预检，再设计文件写入、快照更新与失败回滚的原子边界。
2. 如果长查询导致服务端资源残留，做 Cancel 的服务端停止探针，并把结果并入 Runtime Profile 能力证据。
3. 如果准备复用连接或 Worker，先实现并证明完整 Session Reset；在证明之前继续使用现有单用例进程与连接隔离。
4. Web 写操作只有在身份认证、审计、Artifact Store 和稳定 Core API 明确后再实施。Catalog2、Selector、TestPlan 等作为下一阶段项目，不作为本次 JOIN MVP 的验收前置条件。

## 4. 本轮已实施的局部优化

- Coverage API 把缺口维度取值转换为对象，并给出覆盖该缺口的待评审候选；候选详情展示相对 Active 新增的 Pairwise 要求。
- Web Trial Evidence 除文件 SHA、语义和 Contract/Profile 外，重新计算两次运行的结果哈希；当前 21 条本地候选仍全部显示 `verified`。
- Coverage 策略切换和候选详情路由切换使用请求序号，旧响应不能覆盖新页面数据；前端 `npm run build` 通过。

这些只读优化不改变生成用例、Coverage Claim、Contract Set 或候选生命周期状态。
