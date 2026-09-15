# 机器契约与工程验收设计

> 设计基线：v1.1 工程化补充 · 日期：2026-09-11 · 状态：待实现
>
> 本文承接优化清单中可采纳的建议，规定契约源、生成链、测试资产和阶段验收。目录、命令和测试均为实现要求，不表示本次已经建设运行框架。

## 1. 范围与依赖顺序

五平面不变。共享契约是各模块使用的库与构建产物，不新增每条 SQL 都访问的远程服务。

```text
Registry 枚举 / 统一 Core Model / 语义规则
→ 导出 JSON Schema / 生成枚举与参考表
→ 静态契约检查 + 人工审定 Golden Vector
→ Parser / Compiler / Catalog / Runner / Result 共同消费
```

Phase 0 冻结 SQL MVP 所需模型、序列化和关键反例；标准向量与 Core Model 可以共同迭代。不能要求所有分布式混沌测试和全部功能代码在“编码前”已经完成。
阶段使用的规范必须先冻结，再并行实现消费方；后期契约在对应阶段开始前补齐，禁止为了预留范围实现未使用的服务。

## 2. 单一权威源与生成方向

| 对象 | 唯一可编辑源 | 派生物与约束 |
|---|---|---|
| 枚举、功能和能力 key | registry/*.yaml | 生成 Python Enum、Schema enum、参考表；禁止手写第二套字符串 |
| 字段、类型、必填和默认值 | xgtest/core/model/ 中统一的严格 Pydantic Model | 导出 JSON Schema；业务模块复用模型，不各自声明 DTO |
| 跨字段、引用与状态规则 | 对应领域的纯函数校验器 + 02–11 权威规范 | Contract Test；不声称 JSON Schema 可表达全部业务语义 |
| Canonical/Manifest 编码 | 11 的带版本编码规则 | 人工审定输入/字节/Hash 向量，不以某实现当前输出自动定答案 |
| API/传输映射 | 上述模型的明确映射 | 多集群 MVP HTTP/JSON；Protobuf/gRPC 后置，需独立兼容审核 |

顺序为 Registry → 生成 Python Enum → Core Model → 导出 JSON Schema。JSON Schema 与 Pydantic 不同时手工维护；约束不能导出时必须列入 semantic-validator 清单。
每次导出附 contract_set_id、模型/Registry 版本、源内容哈希、生成器版本和各产物哈希。CI 重新生成到临时输出并对比，漂移则失败；生成时间不参与内容身份。
Manifest.runtime_versions 冻结 contract_set_id；Agent 必须能加载同一已发布契约集合，不能凭“字段看起来差不多”接受新版本。
版本 1.1 的工程化补充尚无运行数据需要迁移；一旦模型/向量用于正式执行，修改字段解释、枚举含义或编码规则必须发布新契约版本，不回写历史快照。

### 2.1 核心契约与运行时 Profile 的发布身份

G0A 冻结数据库无关的核心规则；G0B 冻结具体 Driver/数据库组合的实测映射。实施文档中的 core_contract_set_id 是 contract_set_id 的同义称呼，协议与模型只保留 contract_set_id 一个核心身份字段。

| 发布对象 | 内容与身份 |
|---|---|
| Core Contract Descriptor | descriptor_version、契约语义版本、Registry/Core Model/语义校验器/Golden Vector 的源内容清单与哈希、生成器版本、Schema/枚举等派生产物清单与哈希；contract_set_id 为该身份投影经 XGMJ1 编码后的 SHA-256 |
| SQL Runtime Profile | profile_schema_version、Profile 语义版本、contract_set_id、适用 DB build/Driver/OS/arch/兼容模式及影响行为的配置、Type/Error Mapping、cancel/stop/reset/probe 策略、能力判定/限制，以及探测脚本/输入/脱敏证据的内容哈希；sql_runtime_profile_id 为该身份投影经 XGMJ1 编码后的 SHA-256 |

身份投影排除自身 ID、导出时间、机器绝对路径和下载 URI；产物/证据以内容哈希固定。清单以稳定相对键排序，能力按 capability key 排序，映射规则等有语义的顺序保持不变。Core 生成产物不嵌入自身 contract_set_id，发布描述符在生成完成后计算；Profile 的证据不引用其最终 Profile ID，避免自引用。具体身份投影和正反 Golden Vector 必须在各自冻结 Gate 验收。

两类描述符作为按内容寻址的不可变发布产物，与所引用证据一起提供可校验引用；Bundle 的依赖清单必须包含执行所需描述符和映射内容。证据可用受控 Artifact 引用，不能只留下可变的本机路径。不得保存凭据明文。

Manifest.runtime_versions.contract_set_id 固定核心集合；每个 SQL target_entry 的 sql_runtime_profile_id 固定其运行时 Profile。一个 Run 可含不同 SQL Profile，但这些 Profile 必须引用该 Run 的同一核心集合。Runner/Agent 在执行前校验内容哈希、核心关联、Profile Schema、运行器支持范围以及实际 DB/Driver/模式是否匹配；缺失、不匹配或无法校验时拒绝执行并报告明确原因，不自动切换到最新 Profile。

未探测能力记录 UNKNOWN，不因 Profile 已发布就认定 supported；执行仍按所需能力判定适用性，缺口保留在原目标分母中。核心规则或 Profile 行为调整均发布新语义版本及新身份，证据/内容变化也产生新身份。允许发布新版核心契约并重新验证 Profile，禁止原地改写旧版本或历史 Manifest。Profile 变化作为运行上下文差异交由 Baseline/Delta 判定可比性，不冒充 Case 语义变化。

## 3. Registry 命名与治理

```text
registry/
├── failure_types.yaml
├── statuses.yaml
├── capabilities.yaml
├── features.yaml
├── reason_codes.yaml
├── resource_types.yaml
├── resource_access_modes.yaml
├── execution_classes.yaml
├── isolation_scopes.yaml
└── transaction_isolation_levels.yaml
```

statuses 按 run/attempt/step/case_execution/environment/gate 命名空间分开；禁止将相同文本的不同状态机合并成无约束大枚举。
isolation_scopes 指 worker_schema/case_schema/database/cluster 等框架隔离；transaction_isolation_levels 指 read_committed 等数据库事务隔离，两者不能混用。
每项记录稳定 key、语义、适用阶段、引入/废弃版本及允许消费方。failure_types 还声明类别和默认重试资格，最终重试仍需资源恢复与 Plan 校验。
Registry 中保留废弃 key，不复用历史语义。Protobuf 若启用，应单独分配稳定数值编号和字段 tag，删除后 reserved；不能按 YAML 行号自动重编号，也不能假设一键生成传输协议即可安全兼容。
`registry/features.yaml` 与 `registry/capabilities.yaml` 取代旧设计路径 configs/features.yaml、configs/capabilities.yaml；当前尚未实现，不保留第二份可编辑副本。configs/ 只存运行配置。

## 4. Schema 范围与分层校验

生成的 schemas/ 至少包含 metadata、unified_case、test_model、coverage_claim、scenario、test_plan、environment、resource_request、manifest、result_event、result_snapshot。
每个 Schema 有稳定 $id 和版本。封闭对象拒绝未知字段；标签、参数等开放 map 也必须限定键和值类型，不能成为任意扩展协议的入口。

| 层次 | 责任 | 例子 |
|---|---|---|
| 解码 | 重复键、非法编码、输入大小/深度和 YAML 1.2 规则 | JSON/YAML 转成字典前拒绝重复字段 |
| 结构 | 类型、枚举、必填、边界、版本 | sessions 为非负整数，不接受字符串隐式转整数 |
| 静态语义 | 继承、资源下限、模型约束、断言引用、审查哈希 | active Claim 的审查绑定不符则拒绝发布 |
| 运行时 | 环境匹配、资源准入、token、事件序列与合法状态迁移 | 单条事件 Schema 通过，不等于可修改终态 |

默认值只在规范指定阶段注入；原始 Metadata 与 effective Metadata 使用明确的不同输入模型，避免索引时再注入另一套默认值。
结构/静态语义错误在 validate/index/plan 阶段报告稳定 error_code、字段路径与 SourceSpan。Compiler 不连接数据库；运行时检查由相应 Registry/Admission/Adapter 承担。
Schema 校验器无法找回被普通解析器覆盖掉的重复键，也无法单独证明 Oracle、Coverage Claim 或 Reset 正确，不能省略其他三层。

## 5. 工程目录与数据库用例目录分离

```text
allone/
├── schemas/                     # 从 Core Model 生成
├── registry/                    # 枚举与能力等唯一源
├── tests/                       # 数据库测试资产，继续由 Catalog 发现
│   ├── query/
│   ├── transaction/
│   └── ...
├── framework_tests/             # 不进入数据库 Case Catalog
│   ├── contract/
│   │   ├── schema/
│   │   ├── canonical/
│   │   ├── manifest/
│   │   ├── event/
│   │   ├── coverage/
│   │   └── admission/
│   ├── integration/
│   │   └── reset_probe/
│   ├── scenario/
│   └── chaos/
├── benchmarks/
│   ├── catalog_benchmark.py
│   ├── compiler_benchmark.py
│   ├── runner_overhead.py
│   ├── canonical_benchmark.py
│   └── result_event_benchmark.py
└── xgtest/
    └── core/
        ├── model/
        ├── registry/
        ├── contracts/
        └── resource_admission/
```

Framework Tests 验证平台本身，tests/ 中的 .xgt/.xgs.yaml 验证被测数据库。发现根路径必须显式配置，不能递归仓库把标准向量误索引成数据库 Case。
以上为未来实施布局；本次只更新设计，未创建空目录或虚构已可调用的框架命令。

## 6. Contract Test 与 Golden Vector

每个向量记录 vector_id、contract_version、前置条件、输入、预期输出/拒绝原因、审定依据和稳定内容哈希。

| 领域 | 标准向量 | 验证内容 |
|---|---|---|
| Schema | 重复键、未知键、类型错误、版本、继承冲突 | 解码与各层校验边界 |
| Canonical | NULL/字符串、Decimal、NaN/Infinity、时区、bytes、重复行、rowsort、hash | 完整编码字节及 SHA-256；仅已有模式参与阶段门禁 |
| Manifest | 键序、集合数组顺序、语义数组顺序、URI 变化、数字与 Unicode、越界值 | 身份投影、精确 UTF-8 字节、Hash 和拒绝行为 |
| Event | 重复、冲突重复、乱序、缺口、ACK 丢失、LOST 后迟到 PASS | 输入事件轨迹和预期状态/ACK/审计轨迹 |
| Coverage | 重复点、UNMAPPED、UNSUPPORTED、断言失效、仅 Claim 改动 | 五阶段点集合、Review 失效与分母 |
| Admission | 同/异资源、祖先独占、跨库 Session、部分预留失败、过期 token | 是否准入、冲突原因、完整状态前后差异 |

不同语言对纯数据转换向量必须得到相同字节/哈希/状态；并发测试使用可控时钟和确定性消息轨迹验证不变量，不要求真实进程日志时间戳完全相同。
Golden 输出由规则推导并人工审定，或由独立实现交叉核对。禁止测试运行时自动重录期望值，让同一个错误编码器同时生成输入答案和验证答案。
纯函数向量不能替代数据库 Reset 或失租后停止进程的集成验证；真实 Driver/DB build 下的证据必须另留。

## 7. 阶段门禁

| 阶段 | 必需交付 |
|---|---|
| Phase 0 | 最小 Registry、Core Model/Schema 生成方案、Manifest/Canonical 基础向量、资源冲突规则与 SQL MVP 反例 |
| Phase 1 | SQL 所需 Schema/Registry 落地、Catalog Verify、Claim Review、Reset/Probe 集成验证、基础事件重放与性能基线 |
| Phase 2 | 组合生成、扩展覆盖策略及其模型/Claim 向量 |
| Phase 3 | 结构化并发取消、Barrier 极端场景、事务隔离 Adapter 验证 |
| Phase 4 | 全局 Admission/Lease/Fencing、恢复流程、WAL 故障注入、Matrix 重试身份 |
| Phase 5 | 系统动作的真实破坏范围、无法 fencing 的恢复证明 |
| Phase 6 | 基线可比性、绝对与差异门禁、INFRA_RECOVERED 独立健康门禁 |

基础设施恢复计数从 Phase 1 的 Result 保存；完整发布门禁引擎仍在 Phase 6，不因新增一项指标把整个发布系统提前。
CI 按当前阶段选择 required contract 集，不用“尚未支持模式被拒绝”的测试代替未来模式成功实现的验收，也不宣称待开发目录已经通过测试。

各阶段的前置环境、具体工作包、首条真实 JOIN 闭环及交付顺序见 [13 工程实施顺序与阶段验收](13_Engineering_Implementation_Order_Revised.md)。本文定义共用契约与工程验收规则，13 负责安排其实现依赖。
