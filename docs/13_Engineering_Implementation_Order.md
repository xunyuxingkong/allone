# XG DB Test 工程实施顺序与阶段验收

> 日期：2026-09-12 · 依据：v1.1 架构及工程化补充
>
> 本文将设计转为按依赖排序的实施工作包。当前运行框架尚未实现；以下步骤、目录、命令和验收均为计划，不代表已经完成。本文不新增架构范围，也不替代各专项契约。

## 1. 使用方式与总体顺序

先落实三个前置工作包：契约代码、虚谷能力验证、首批验收资产。用一条真实 JOIN 用例验证完整执行链，再扩展四类样板，之后按既定 Phase 2–6 推进。

```text
Phase 0：基线 / 工程骨架 / 最小契约 / 标准向量
  ├── 虚谷环境与 Driver 探测
  └── 首批 SQL、Oracle、Cleanup 与覆盖声明设计
       ↓
Phase 1：单集群 SQL MVP
  Parser → Compiler/Catalog → Selector → Manifest/Bundle
  → 本地 Admission/Runner + Xugu Adapter + Validator/Result
  → 首条 JOIN 闭环 → 四类样板 → 最小 Coverage / Verify / 性能验收
       ↓
Phase 2：Coverage 扩展与 Generator
       ↓
Phase 3：Scenario / Transaction / Concurrency
       ↓
Phase 4：Agent / Multi-cluster / Lease / Recovery
       ↓
Phase 5：Backup / Restore / Cluster / HA / 系统特性
       ↓
Phase 6：Result DB / Baseline / Delta / Quality Gate / Dashboard
```

这是默认交付顺序，不要求每个模块都串行开发。共享接口冻结后可独立推进消费方；但真实环境验证、资源恢复和阶段验收不得用 Mock 结果替代。
Normalizer/Validator 和 Result 的基础接口必须在 Runner 集成前准备好；业务结果随 Step 验证，随后 Cleanup/Reset/Probe，再裁决最终结果。

## 2. 前置条件清单

### 2.1 必须落实的信息

| 编号 | 前置条件 | 具体内容 / 交付物 | 最晚落实时间 | 当前状态 |
|---|---|---|---|---|
| PRE-01 | 设计基线 | 确认总架构、02–12 专项与本实施顺序采用同一版本，记录 Git commit | 共享接口开始实现前 | 文档已存在；待冻结工程起点 |
| PRE-02 | 开发与运行环境 | Python 版本、目标 OS/Arch、依赖安装方式、锁定依赖；Python 3.11+ 需与 Driver 支持范围核对 | 工程骨架阶段 | 待确认 |
| PRE-03 | 虚谷精确版本 | 产品版本/build、兼容模式、部署拓扑、字符集、时区及关键配置 | Adapter 实测前 | 尚未提供实测信息 |
| PRE-04 | Python Driver | 名称/版本、安装来源、Python/OS 支持、连接参数和已知限制 | Adapter 实测前 | 待确认与验证 |
| PRE-05 | 独立测试环境 | 地址/端口、可达性、可分配 Database/Schema、连接数上限、恢复方式 | 真实 SQL 执行前 | 待提供与验证 |
| PRE-06 | 测试账号与权限 | 创建/删除测试对象、事务与状态查询权限；取消他人 Session 如需管理权限须单独声明 | 相应探测前 | 待核对 |
| PRE-07 | 凭据配置 | 本地秘密配置或 Secret Provider 引用；Git/Bundle/Result 不保存明文秘密 | 第一次连接前 | 待配置 |
| PRE-08 | SQL/Oracle 依据 | 小数据集、人工推导或规范依据、错误码来源、审查责任人 | 样板进入 active 前 | 待建立 |
| PRE-09 | 集成验证入口 | 可访问测试环境的执行位置、日志/Artifact 存储、失败清理责任 | 真实集成验收前 | 待建立 |

上表“待确认”不阻止文档、模型、Parser、Catalog 等离线工作，但阻止对应真实环境能力的验收。不能把尚未探测的 Driver 能力写成 supported。

### 2.2 工程技术选择的冻结原则

- 沿用 Python 核心、严格 Pydantic Core Model、Registry、派生 JSON Schema、SQLite Catalog、JSONL/本地 Artifact 的设计。
- CLI、YAML 1.2 解码实现、依赖管理及开发测试工具在工程骨架阶段各选一套并锁定，不能让模块分别引入重复技术栈。
- YAML 解析需支持既定 Core Schema 与重复键拒绝；Pydantic 不能替代解码器检查。
- HTTP/JSON 到 Phase 4 再建设；gRPC、对象存储、复杂 UI 等按后续需求和阶段实施，不作为首条 SQL 跑通的安装依赖。

### 2.3 证据与状态管理

每个工作包记录负责人、前置步骤、状态、代码 commit、测试/探测证据和未解决限制；状态使用 NOT_STARTED / IN_PROGRESS / BLOCKED / ACCEPTED。
只有验收证据完整时标记 ACCEPTED。BLOCKED 要指明缺环境、权限、规则决策还是实现缺陷，并列出仍可继续的独立工作。
依赖目录是实施目标，不提前创建一批无实现的空文件来表示完成。

## 3. Phase 0：工程骨架与最小契约

### 3.1 实现步骤

| 步骤 | 依赖 | 实施内容 | 交付与验收 |
|---|---|---|---|
| P0-01 冻结工作基线 | PRE-01 | 确认 SQL MVP 范围、未支持能力和专项文档权威边界；记录当前设计 commit | 每个关键问题能定位到规范；不同时实现矛盾版本 |
| P0-02 建立工程骨架 | P0-01、PRE-02 | 包结构、pyproject、依赖锁定、CLI 入口、开发测试入口、基础 CI | 干净环境可安装；导入和帮助命令可用；测试与数据库资产发现根分离 |
| P0-03 最小 Registry | P0-02 | 四类样板 Feature、Capability、Level、状态命名空间、失败类型、隔离范围与资源模式 | 枚举唯一且可生成；未知 key 拒绝；事务隔离与框架隔离不混用 |
| P0-04 统一模型 | P0-03 | Raw/Effective Metadata、SQL Step、TestCase、Target、Manifest、Attempt、ResultEvent、Coverage Claim/Review | 类型/必填/默认值固定；无未知字段和隐式类型漂移 |
| P0-05 Schema 与语义校验 | P0-04 | 从 Core Model 导出 Schema；实现最小跨字段、继承、引用和状态校验 | 重复键在解码阶段拒绝；模型导出可复现；Schema 与业务约束边界清楚 |
| P0-06 标准向量 | P0-04/05 | Canonical、XGMJ1、状态、Metadata/Claim 的有效与无效输入；规则与向量共同校准 | 固定输入、精确输出/字节/Hash/错误原因，期望值经独立审定 |
| P0-07 发布最小契约集合 | P0-03–06 | 固定 contract_set_id、版本、源与生成产物指纹，供实现模块引用 | Parser/Compiler/Runner 不自行复制数据模型或枚举 |

P0-04 与 P0-06 可以共同迭代，不能把“标准向量必须先于所有代码完整存在”作为死循环前置条件。
Phase 0 冻结的是 SQL MVP 必需合同。Scenario 完整 Step 集、分布式协议和系统动作合约在相应阶段扩充，并在消费方开发前冻结。

### 3.2 首批标准向量

| 领域 | 至少覆盖 |
|---|---|
| Metadata / Schema | 缺必填、重复键、未知枚举、继承冲突、非法版本、unsafe 自动重试 |
| Canonical | NULL 与字符串、空串、尾空格、重复行、Decimal 精度、有限浮点/特殊值、时间/二进制 |
| Manifest | 键排序、集合排序、Step 顺序保留、URI 与内容 Hash 区分、XGMJ1 最小标准向量 |
| Result | 合法/非法迁移、重复事件、迟到事件不回退终态、Cleanup 失败覆盖最终状态但保留 primary_status |
| Coverage | 无 Claim、错误断言引用、重复点、失效 Review、只改 Claim 导致 review_input_hash 变化 |
| Admission | 同资源访问冲突、不同资源可并行、容量不足、部分申请失败不授予执行权 |

向量放入 framework_tests/contract/，不会进入数据库 Case Catalog。尚未实现的比较模式和动作应被明确拒绝，其拒绝测试不代表该模式已经实现。

### 3.3 G0：进入主体实现的条件

工程可安装；最小模型/Registry/Schema 和标准向量能够执行验证；关键身份、状态、编码与默认值不再由消费方临时决定。未决环境信息仍可保留，但必须单独跟踪。

## 4. 前置工作包 A：虚谷环境、Driver 与能力探测

本工作包可与 Phase 0 离线契约工作并行推进，探测结果反向校准 Adapter 能力声明。

| 步骤 | 依赖 | 实施内容 | 证据与通过标准 |
|---|---|---|---|
| A-01 环境建档 | PRE-03–07 | 冻结 DB/Driver/OS/build/模式与资源配额；验证连接和权限 | 可复现的环境描述与脱敏连接结果，秘密仅保留引用 |
| A-02 类型读取 | A-01 | 建小表并读 NULL、整数、Decimal、float、字符串、时间、binary | 原始 Driver 类型、列元数据、值和精度；无静默字符串化或截断 |
| A-03 事务行为 | A-01 | BEGIN/COMMIT/ROLLBACK、autocommit、DDL 回滚行为；用独立连接观察提交可见性 | 各动作实际语义清楚；不把 PostgreSQL/MySQL 行为假定为虚谷行为 |
| A-04 错误归类 | A-01 | 非法 SQL、约束冲突、权限问题、连接断开 | 可稳定提取的错误码/SQLSTATE；数据库错误与网络错误分开 |
| A-05 取消行为 | A-03/04 | 长查询、锁等待、超时/取消；观察服务端执行是否真正结束 | 同时记录客户端与服务端状态；“cancel 返回成功”不等于已停止 |
| A-06 复位与恢复 | A-02–05 | 会话参数、事务、角色、Schema、临时对象、游标/预编译句柄和锁 | Probe 证明清洁，或连接销毁/资源隔离；无法确认时禁止复用 |
| A-07 最小 Adapter | A-02–06、P0-07 | 将已验证行为封装为连接、执行、流式读取、事务、错误、取消、reset/probe 接口 | 同一接口有真实集成证据，能力边界与运行限制可查询 |

探测使用独立测试资源，仅在已约定的范围内创建/删除对象。需要远程系统配置或项目范围外参数调整时，先明确请求，不能隐式修改服务器系统。

### 4.1 能力表必须记录的字段

每项包含 capability、DB/Driver/OS 版本、探测脚本与参数、原始脱敏结果、判定、限制、证据引用。探测判定可用 VERIFIED / UNSUPPORTED / UNKNOWN / FAILED，属于探测记录，不混入 Case Final Status。
缺权限或无法观察不能自动判 UNSUPPORTED，也不能当 VERIFIED；应记 UNKNOWN 并说明缺少的条件。
能力探测先确定通用 SQL/会话基础；完整事务隔离现象在 Phase 3 验证，节点和备份能力在 Phase 5 验证。

### 4.2 无环境时的处理

可完成模型、Schema、Parser、Catalog、Manifest、纯 Canonical/状态测试与 Fake Adapter 接口测试。A-02–07、真实 JOIN 闭环及 G1 仍不能验收。
不以 Fake Adapter 或另一种数据库执行成功来替代虚谷兼容性结论。

## 5. 前置工作包 B：首批用例、Oracle 与隔离要求

### 5.1 样板分两批冻结

首先冻结约 20 条手写种子用例，用于发现接口和环境问题；首条闭环稳定后扩展到总架构要求的每类 10–50 条，即四类合计 40–200 条。种子批不是最终 MVP 数量验收。

| 功能 | 种子数量 | 初始范围 | 必须特别确认的语义 |
|---|---:|---|---|
| JOIN | 6 | INNER/LEFT、未匹配、NULL、重复匹配、多列条件 | 重复行次数、NULL 扩展、稳定排序 |
| UNION | 4 | UNION 去重、UNION ALL、NULL、外层排序 | 结果类型、去重规则、排序归属 |
| DDL TABLE | 5 | 建表、改表、约束、删除、预期错误 | DDL 提交/回滚行为、对象元数据和错误码 |
| STRING FUNCTION | 5 | 拼接、截取/长度、空串、NULL、中文边界 | 函数名称/参数、字符与字节长度、模式差异 |

每个种子 Case 只承载明确的测试目的；发现多种独立语义混在一起时拆分并调整数量，不为凑数生成重复 Case。

### 5.2 每条样板的交付清单

- 稳定 Case ID、功能归属、Level、标题和测试目的。
- 小型、可人工核对的初始数据；Setup、SQL、Expected/Expected Error。
- Oracle 依据：规范、人工推导或已审查参考，记录来源和证据。
- execution_class、isolation、资源、timeout、idempotency、reset_contract、Cleanup 与 Probe。
- Test Model/版本、Coverage Claim、assertion_refs、覆盖审查输入。
- 成功、失败和中断后的预期资源状态；不得只写正常路径 DROP TABLE。

初始用例为 draft/review。语法、可信 Oracle、Trial Run、可重复执行和 Review/覆盖证据满足条件后才 active；不能仅将实测输出保存为 Expected 就自动认定正确。
未获得可信错误码或函数语义的样板保留待确认状态，不靠宽泛正则或任意容差强行通过。

### 5.3 样板验收方法

逐条独立运行，再重复运行并改变用例顺序；验证不同 Worker/Schema 下结果一致。注入上一条 Case 的异常，检查下一条 Case 不受污染。
人为修改 Expected 应稳定 FAIL；资源清理失败应 ERROR/FIXTURE_CLEANUP 并隔离；重复行和类型差异不能被 Normalizer 吞掉。
所有声明覆盖点由实际断言支撑，Review 与当前 semantic_hash/review_input_hash 匹配。

## 6. Phase 1：单集群 SQL MVP 的实现顺序

### 6.1 模块工作包

| 步骤 | 前置依赖 | 实施内容 | 交付与验收 |
|---|---|---|---|
| P1-01 解码与 XGT Parser | G0 | Metadata Header、显式块边界、JSON Expected、稳定 Step ID、SourceSpan | 正反例通过；未知/未支持指令静态拒绝；不连接数据库 |
| P1-02 Metadata Resolver / Compiler | P1-01 | Suite 继承、Registry 校验、统一 Case、资源下限、Claim 静态校验、依赖与语义指纹 | 确定性编译；非法引用/矛盾元数据拒绝 |
| P1-03 Catalog 2 | P1-02 | 建表、事务提交、索引、删除/改 ID、依赖失效、全量/增量编译 | 相同快照得到相同有效集合；编译失败不提交半新半旧索引 |
| P1-04 Selector / Plan / Target | P1-03 | Feature/Level/Issue/Status 等选择，解析 Plan，冻结本地逻辑目标和完整预期执行集合 | 不支持/缺环境保留原因；过滤不隐式缩小分母 |
| P1-05 Manifest / Bundle | P1-04 | 打包所选 Case/依赖，XGMJ1、内容校验、版本引用、拒绝源漂移 | 执行输入可恢复；实际执行不重新读取工作区最新内容 |
| P1-06 Canonical / Validator | G0、A-02/04 的真实校准 | Exact、RowSort、Expected Error，类型映射、重复行、受限资源比较 | 标准向量及 Driver 值通过；未知类型与资源超限明确失败 |
| P1-07 本地 Result Core | G0 | CaseExecution/Attempt/Step、状态裁决、JSONL 单写持久化、失败 Artifact | 先持久化后确认；重放可恢复；Cleanup 失败保留 primary_status |
| P1-08 本地 Admission / Fixture / Worker | G0、A-06/07 | 资源作用域、Fixture 生命周期、Connection/Schema 准入和复位；先一个 Worker | 未确认清洁不可复用；同一物理资源无冲突授予 |
| P1-09 Runner 集成与首条 JOIN | P1-05–08、A-07、B 的首条样板 | 串联执行、比较、清理、资源释放与结果保存，接入最小 CLI | 完成第 6.2 节的真实闭环验收 |
| P1-10 样板扩展与 Worker Pool | P1-09 | 加入四类种子、再扩展每类 10–50 条；启用多 Worker、Fixture/Schema 复用 | 独立/重复/变序/并行运行一致，污染恢复可验证 |
| P1-11 最小 Coverage / Review | P1-02/07、B、P1-10 | all-values/mandatory-combination、Claim 审查、五阶段 Snapshot | 点去重；UNMAPPED/UNREVIEWED/UNSUPPORTED 单列；分母一致 |
| P1-12 Catalog Verify / Report / CI | P1-03–11 | 对绑定快照只读 Verify、摘要与 JUnit、自动集成检查 | 损坏/漂移/证据不足可区分；报告不覆盖核心结果语义 |
| P1-13 性能和失败恢复验收 | P1-10–12 | Catalog/Compiler/Runner/Canonical/Event 基准与异常注入 | 正确性、隔离、持久化开启时测试；记录目标与实测差距 |

P1-06、P1-07 可在 Parser/Catalog 开发期间独立推进；表格先后表示依赖约束，不要求等 P1-05 完成才开始 Validator。
P1-02 的哈希输入严格遵循 11 的规则：compiled_hash 包含有效 Metadata、依赖指纹和编译器版本，排除编译时间与绝对工作区路径；semantic_hash 使用其独立规定的语义字段。哈希不包含自身，审查输入也不包含自身审查证据；准备好有效审查证据后再冻结 active 发布快照。
CLAIM 静态校验从 Compiler 开始；P1-11 实现覆盖统计，不能把未审 active Claim 暂时放行作为过渡。

### 6.2 首条真实 JOIN 闭环

选用两张小表，包含匹配行、未匹配行和可手工确认的结果。首条作为 draft 试跑，使用显式诊断选择；正式 Release 仍只选择 active。

```text
读取 .xgt 与 Suite
→ validate / compile / index
→ 选择 Case，冻结 target 与 Manifest/Bundle
→ 创建 CaseExecution 和 Attempt
→ 资源准入、Prepare、Setup
→ 执行 JOIN，Canonical/Validator 核对 Expected
→ Cleanup、Reset、Probe
→ 裁决 Attempt / CaseExecution，释放可恢复资源
→ 保存事件、摘要、失败 Artifact 和最小覆盖结果
```

至少验收四种结果：正常通过；故意错 Expected 而失败；Setup/业务阶段中断仍进行清理；清理无法恢复时隔离资源。
另外修改索引后的源文件，执行必须拒绝漂移或继续使用原 Bundle；不能静默跑修改后的 SQL。
通过这一检查点后才扩大样板和并行度。它不是 G1，仍需覆盖、Verify 和性能等后续工作。

### 6.3 G1：单集群 SQL MVP 验收

- 四类样板各 10–50 条，具有可信 Oracle、生命周期和有效覆盖审查。
- 精确选例、不可变执行输入、实际虚谷 Adapter、类型比较和失败诊断形成完整链路。
- 连续、变序和多 Worker 运行均可复现；失败/超时/取消后能证明恢复或正确隔离。
- Catalog 全量/增量等价、Verify 有效、最小覆盖 Snapshot 与结果聚合正确。
- JSONL 重启恢复、重复/迟到事件不错误修改终态，INFRA_RECOVERED 有独立统计。
- 按 11 的测量口径提供性能与限制报告；未达约定阈值的项目作为明确缺口处理，不省略测试。

此阶段不要求远程 Agent、全局 Lease 续租、备份恢复、完整发布质量引擎或 Web UI 已实现。

## 7. Phase 2：Coverage 与 Generator

前置：G1。复用已有 Claim、模型版本、Oracle、Review 和本地 Runner，不重新建立一套用例格式。

| 顺序 | 实施内容 | 交付与验收 |
|---|---|---|
| P2-01 | 扩展 Model/Constraint 校验及有效覆盖点集合 | 不可满足模型、不可达值和非法组合明确报告 |
| P2-02 | Pairwise、Boundary、Negative、Interaction 等覆盖策略按需逐项实现 | 每种策略有合法空间、去重规则和标准向量；不能把 Case 数量当覆盖率 |
| P2-03 | 确定性 Template Generator 与 seed/版本/输入指纹 | 相同输入生成相同候选资产；Expected 来源明确 |
| P2-04 | 候选去重、静态验证、Trial Run、Review/active 流程 | 重复签名只提示审查，不能误删不同目的 Case |
| P2-05 | Coverage Gap → Candidate → Active → Snapshot 反馈 | 补例后对应合法覆盖点增加，模型/Claim 变化可追踪 |

G2：至少选一个 Feature 用真实缺口跑通确定性生成和审查闭环；不要求所有 Domain 同时具备生成器。
Hash/ValueSort 等扩展比较模式若某策略确实依赖，先补齐对应规范与向量再接入；不得静默从未支持模式降级。

## 8. Phase 3：Scenario、事务与并发

前置：G1，以及计划纳入的 Phase 2 交付。若事务测试有更高优先级，可在 G1 后单独推进本阶段，但必须显式调整交付计划；事务执行不应依赖 Generator 才能工作。

| 顺序 | 实施内容 | 交付与验收 |
|---|---|---|
| P3-01 | Scenario Schema/Parser、稳定 Step 树及静态资源检查 | 未知动作/错误引用/同 Session 并用等问题提前拒绝 |
| P3-02 | Session Manager、事务操作和会话能力实测 | 显式 autocommit/隔离设置，独立 Session 的状态不串扰 |
| P3-03 | 结构化 parallel、barrier、signal/wait_signal、condition | 明确作用域、粘性信号、等待预算和取消传播 |
| P3-04 | 事务可见性、阻塞、死锁等 Validator 与样板 | 用条件观察证明实际同步状态，不靠固定 sleep |
| P3-05 | 分支失败、Barrier 超时、取消阻塞 SQL、清理超时 | 有界结束；无法确认停止时隔离，不能提前释放复用 |

G3：正常并发与异常退出都能得到确定结果，保留所有分支证据；资源恢复和覆盖断言引用与统一 Case/Result 模型一致。

## 9. Phase 4：多集群调度、Agent 与恢复

前置：G1/G3 的本地执行与资源恢复能力稳定；至少准备两个可区分且可核验的逻辑/物理环境，具备故障注入和恢复权限。

| 顺序 | 实施内容 | 交付与验收 |
|---|---|---|
| P4-01 | target/Environment Registry、配置快照与能力匹配 | target_id 与 environment_id 分开；不同版本/架构不能错误混入同 target |
| P4-02 | Controller 状态持久化、共享 Admission、原子授予和 Lease/Fencing | 多 Run 冲突、容量、租约 epoch/token、事务恢复验证通过 |
| P4-03 | Agent 注册/心跳、协议版本、Bundle 接收、分配 ACK 与 reconcile | 分配持久化后确认，重复请求不重复执行，旧 epoch 不复活 |
| P4-04 | Shard、Matrix、Weighted LPT、Local Planner/Worker Pool 接入 | 下发 Shard 级任务；本地执行无需每条 SQL 远程 RPC |
| P4-05 | Agent WAL、durable ACK、重放、高水位和硬上限背压 | Controller 暂不可用时仅在有效租约与空间内继续 |
| P4-06 | Agent Lost、重试迁移、停止证明、QUARANTINED Recovery | 新 Attempt 只迁移到同 target 等价环境；enable 不绕过恢复 |
| P4-07 | 网络分区、ACK 丢失、进程重启、租约过期与旧 Agent 返回 | 无冲突双持有者；状态重放一致；迟到 PASS 不回退 LOST |

不得在 P4-02 的准入和所有权协议缺失时，先让多个 Agent 不受控地同时执行同一环境上的任务。P4-05 未通过前也不得宣称具备可靠远程执行。
G4：Shard/Matrix 正常与故障迁移均可审计；同 target 的 A LOST → B PASS 保持一个 CaseExecution、两个 Attempt；停止或恢复未证实时不重新授权。

## 10. Phase 5：系统特性、备份恢复与 HA

前置：G4。准备可恢复的专用环境、节点/备份资源范围、管理权限、备份空间和恢复方案。每类破坏性动作单独验证影响范围。

| 顺序 | 实施内容 | 交付与验收 |
|---|---|---|
| P5-01 | Admin/System/Backup/Cluster Adapter 的能力与权限模型 | 动作推导最低 destructive/isolation/resource 要求，Metadata 不可降级 |
| P5-02 | Node 启停、配置、脚本与受控路径动作 | 目标节点解析留证；越出授权范围拒绝；旧执行停止可确认 |
| P5-03 | Backup 与 Restore，含数据/对象/一致性验证 | 不仅判断命令返回成功，还验证恢复后的数据库状态 |
| P5-04 | Failover、Rejoin、Replication、Consistency 场景 | 由条件和状态断言证明故障转移结果，不只观察进程存活 |
| P5-05 | 部分备份/恢复失败、节点不可达、Cleanup 失败与取消 | 环境隔离、证据保存和受控恢复有效，不盲目自动重放 |

G5：每个宣布支持的系统动作都有真实成功/失败恢复证据；无法支持 fencing 的路径必须通过停止 + Reset/Probe 证明。
尚无完整恢复证明的动作保留未支持状态，不能作为正式 Release 可用能力注册。

## 11. Phase 6：发布质量、持久结果与展示

前置：至少 G1 的可信结果与快照；完整平台发布验收还需覆盖计划所用的 G2–G5 能力。JSONL 历史证据从 Phase 1 已保存，本阶段不追补不存在的历史数据。

| 顺序 | 实施内容 | 交付与验收 |
|---|---|---|
| P6-01 | Result DB 投影与查询、Artifact 索引/保留；按需要接入对象存储 | 原始事件事实源和内容引用可验证，投影可重建 |
| P6-02 | Baseline 选择/锁定与 target 映射 | 显式基线优先；目标匹配歧义报错；迟到事件不重写快照 |
| P6-03 | 资产/语义/环境/模型/结果的正交 Delta | 选例变化不冒充新增用例；不可比样本不冒充产品回归 |
| P6-04 | Failure Signature 聚类、Flaky 与 Coverage 历史分析 | 签名只表示相似候选；不同模型分母不能直接比较提升 |
| P6-05 | 绝对/差异 Quality Gate、INFRA_RECOVERED 独立门禁与 CI 退出码 | 固定分母；缺测、N/A、不确定状态不能默认放行 |
| P6-06 | 报告/API/Dashboard、Allure 集成完善 | 展示复用 Core API，不另算 Selector、Coverage 或质量结论 |
| P6-07 | Change Impact 的受控扩展 | 建立代码到 Feature 的证据映射后再实现推荐选例；推荐不自动替代发布必需范围 |

G6：完整发布范围可输出可信 Baseline/Delta、覆盖变化和门禁；例“100 个 P0 中 20 unsupported、80 PASS”应报告 80% 执行/通过率并阻断严格 P0 门禁。
Dashboard、Change Impact 以及额外存储后端可在 P6-05 核心发布闭环之后分别交付，不应阻塞已有 CLI/CI 发布质量判断。
Controller HA、K8s 动态扩容和 AI 生成仍是后续范围，本文不将其列为完成当前架构的必需条件。

## 12. 可独立推进的工作与阻塞处理

| 条件 | 可继续的工作 | 不得提前验收的内容 |
|---|---|---|
| 没有虚谷环境 | Registry/Model/Schema、Parser/Compiler、Catalog/Manifest、纯函数向量 | 真实 Adapter、取消/Reset、JOIN 闭环与 G1 |
| 无取消/状态查询权限 | 类型和普通事务探测、离线模块 | 停止证明与连接安全复用 |
| Oracle 未确认 | 用例结构、初始化数据、待审 Claim、其他已确认用例 | 对应用例 active 与正式覆盖贡献 |
| Schema/状态规则冲突 | 记录问题、补反例、推进不依赖该规则的工作 | 消费方各自选择解释并发布 |
| 只有一个环境 | 单集群与本地恢复 | 多环境迁移、Matrix 和分布式隔离结论 |
| 系统恢复方式未验证 | SQL/Scenario、只读状态探测 | 相应破坏性动作和 G5 能力声明 |

各工作包在统一模型和标准向量冻结后可独立实现；涉及同一状态库/Schema 的变更需约定版本与集成顺序。独立推进不意味着允许接口自由漂移。

## 13. 第一轮实际开工任务

建议按以下顺序建立可追踪任务，不先铺开全部平台模块：

1. 确认 PRE-01–09，建立环境/Driver 信息表和缺口清单。
2. 完成 P0-02 工程骨架与最小 CI，固定安装/测试方式。
3. 实现 P0-03–07 的最小 Registry、模型、Schema 与标准向量。
4. 在独立环境执行 A-01–06，记录能力证据并封装 A-07。
5. 冻结 B 的约 20 条种子；选定第一条可信 JOIN Case。
6. 按 P1-01–08 实现首条闭环必需模块，接入真实 Adapter。
7. 完成 P1-09 四种结果与源漂移检查，再进行规模/并行扩展。
8. 完成 P1-10–13 并评审 G1，之后进入默认 Phase 2–6 路线。

每次任务交付包含：实现范围、相关规范、关键选择、验证命令/环境、证据位置、限制和下一步依赖。没有实测证据的能力必须明确留在未验收状态。
不预先承诺固定周数：在 Driver 探测和首条 JOIN 闭环完成后，结合实际复杂度、环境可用性与投入人数估算剩余阶段，并以工作包/验收为进度依据。

## 14. 规范索引

| 实施内容 | 对应设计 |
|---|---|
| 架构边界、阶段范围 | [总架构](XG_DB_Test_Architecture_Design_v1.md) |
| XGT / Scenario | [02](02_XGT_DSL_Specification.md)、[03](03_Scenario_DSL_Specification.md) |
| 模型与索引 | [04 Metadata](04_Metadata_Schema.md)、[05 Catalog](05_Case_Catalog_Design.md) |
| 调度、恢复、结果 | [06 Scheduler](06_Distributed_Scheduler_Design.md)、[07 Result](07_Result_Model_Design.md) |
| 覆盖与资产审查 | [08 Coverage](08_Test_Model_and_Coverage_Design.md)、[09 Lifecycle](09_Case_Lifecycle_and_Generation_Design.md) |
| 发布质量 | [10 Baseline/Delta](10_Release_Baseline_and_Delta_Design.md) |
| 快照、比较、隔离、基准 | [11 执行一致性](11_Execution_Consistency_and_Validation_Contract.md) |
| 单一契约源、生成链、Golden Vector | [12 机器契约与工程验收](12_Machine_Contracts_and_Engineering_Validation.md) |

本文件只定义实施依赖和交付检查点。若实施中发现专项契约需调整，应先更新对应权威规范及相关向量，再改变实现；不能只修改本顺序表掩盖语义变化。
