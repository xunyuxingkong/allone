# 执行一致性、隔离与结果比较契约

> Design Version：1.1 · Canonical Version：1 · 状态：待实现规范
>
> 本文约束 Compiler、Planner、Runner、Adapter 和 Validator；不增加原范围之外的功能。

## 1. 不可变执行输入

Git 保存资产，Catalog 保存派生索引；实际执行以规划时冻结的 Run Manifest 和 Compiled Bundle 为准。

```text
干净 Git tree / 显式工作区快照
→ 全依赖解析与验证
→ Catalog snapshot
→ Selector / target expansion
→ immutable Manifest + Bundle
→ Runner / Agent verify
```

Release 默认 require_clean_git=true。开发运行允许 dirty，但必须把实际源文件与依赖内容存入 Bundle，不能只记录 commit。
快照生成期间任一输入变化，规划失败并重新生成；Bundle 发布使用临时文件完成写入、哈希校验后原子切换。
Agent 缺 Bundle、哈希不符、插件版本不兼容时报告框架错误，不能回到工作区读取“最新文件”。

## 2. Manifest 字段

| 字段 | 内容 |
|---|---|
| run_id / manifest_version | 执行身份 / "1" |
| git_commit / dirty / source_snapshot_hash | 资产来源 |
| catalog_snapshot_id / plan_hash | 索引与解析后的完整 Plan |
| case_entries | case_id、level、status、compiled_hash、semantic_hash、coverage refs |
| target_entries | target_id、数据库精确 build、OS/arch/topology/mode、配置及数据集指纹；SQL Target 的 sql_runtime_profile_id |
| expected_executions | case_id × target_id、选择原因、适用性结果、reason_code |
| bundles | 内容 URI、SHA-256、大小、依赖清单；不包含凭据 |
| runtime_versions | Compiler、DSL、Metadata、Canonical、Adapter/Driver/Runner/Protocol 版本，以及 contract_set_id |
| coverage_scope | model_id/version/hash、strategy、要求级别、点集合引用及分母 |
| baseline / quality_gate | 解析后的基线 ID、比较策略、数值阈值 |
| manifest_hash | 第 12 节定义的身份投影与 XGMJ1 规范字节的 SHA-256 |

解析后的 Plan 包括参数值、选择/排除原因和目标快照。秘密值只保留受控引用与版本，不写入 Bundle/日志；秘密变化是否影响可比性由目标配置策略明确。
case_entries 还需关联当前 Catalog 全量 ID/status/semantic_hash 的轻量资产清单，供 Delta 区分未选中、禁用和真正删除。
contract_set_id 固定数据库无关核心契约，core_contract_set_id 仅为实施阶段同义称呼，不重复序列化。每个 SQL Target 的 sql_runtime_profile_id 必须关联同一核心契约，并进入 Manifest 身份投影；不同 Target 可引用不同 Profile。Bundle 依赖固定所需 Profile 内容，执行前核验实际环境和 Driver 匹配；字段、身份编码与发布规则见 [12 §2.1](12_Machine_Contracts_and_Engineering_Validation.md#21-核心契约与运行时-profile-的发布身份)。Profile 漂移属于运行上下文变化，不能静默替换。

## 3. 内容哈希

所有哈希使用 SHA-256；对象键排序、数组按各自语义处理。源文本的换行只在指定输入步骤规范化，不能对序列化后的字符串内容全局替换；原始 source_hash 对原始字节计算。Manifest 使用第 12 节独立的 XGMJ1 编码，不能直接套用数据库结果的 XGC1 行编码。

- dependency_hash：按稳定输入键排序的完整内容哈希清单，含 Suite、默认值、Fixture、脚本、Registry、Model、策略与工具版本。
- compiled_hash：最终 Unified Case 的规范序列化，包含 effective_metadata、dependency_hash 和编译器版本；排除编译时间与绝对工作区路径。
- semantic_hash：执行 Step 树、SQL 原文的换行规范形式、Fixture/脚本内容、Oracle/期望值、比较规则、执行参数默认值、规范化语义版本。不得通过去除 SQL 字符串空白或改写 SQL 猜测等价。
- 标题、Owner、Tag、source_path、生成时间不进 semantic_hash；策略/分类变化仍在 Manifest 中报告。
- Adapter/Driver/DB build 和目标配置在运行上下文单独比较；不能因为 SQL 未变就忽略它们。

Bundle 内相对路径不得越出快照根。DSL 1.0 与 1.1、Canonical 版本不兼容时显式转换或拒绝，不能只替换版本号后继续执行。

## 4. Attempt 执行与隔离

```text
Resource Admission → Prepare → Setup → Steps（含 Normalizer / Validator）
→ Cleanup → Reset → Probe → Result Finalize → Release
```

每个阶段都有记录。Cleanup 在 Setup 部分成功、断言失败、超时和取消后仍必须尝试，按“可能已分配”的资源清单清理。
Fixture 定义 scope、mutability、setup、reset/teardown、probe、timeout 和版本；共享 immutable Fixture 只读，mutable Fixture 不跨并发 Case 共享。
worker/suite scope 的初始化和销毁由引用计数与单个所有者管理；依赖按拓扑初始化、反向清理，初始化失败回滚已创建部分。

Session Reset 至少处理：未提交事务、隔离级别/autocommit、角色/权限上下文、当前 schema/search path、timezone/locale、会话参数、游标/预编译句柄、临时对象和未释放锁。
每个 Adapter 明确能验证的项目；未支持项目不得假定已恢复。无法可靠重置的连接销毁重建；Schema 或数据库污染则隔离对应资源。
DDL/系统动作不能依赖事务 rollback 作为通用清理。case_schema/database/cluster 的强隔离优先于连接和 Schema 复用优化。

## 5. 清理、超时与重试

| 情形 | Attempt 结论与资源行为 |
|---|---|
| Steps 通过，恢复成功 | PASS，资源可复用 |
| Steps 失败，恢复成功 | 保留 FAIL/TIMEOUT/ERROR，资源可复用 |
| Cleanup/Reset/Probe 失败 | ERROR/FIXTURE_CLEANUP，保留 primary_status，资源隔离 |
| 旧 SQL/进程是否停止未知 | TIMEOUT/LOST 等主结论保留，禁止资源再分配 |

Case timeout 从 Prepare 开始覆盖 Setup/业务 Step，不含排队；每个 Step 的有效截止时间为 min(Case 剩余预算, Step 显式预算)，没有 Step 预算则继承 Case 剩余预算。
Cleanup 使用独立 cleanup_timeout，不能被业务超时跳过，也不能无限延长。Run Cancel 停止新分配，取消可取消 SQL/进程后再恢复资源。
重试一定使用新 attempt_id。safe 只表示设计允许重复，不替代停止/复位证明；conditional 额外要求 reset_contract；unsafe/destructive 不自动重放。

## 6. Canonical 类型与默认比较

Canonical 1 采用以下逻辑类型：null、bool、int、decimal、float、string、date、time、timestamp、timestamp_tz、bytes。
Adapter 负责把数据库类型和 Driver 值映射到这些类型，并保留原始列元数据；未知类型为 FRAMEWORK_NORMALIZATION，不自动 str(value)。
Column 数量和行长度必须匹配。默认比较逻辑类型和值；原始数据库类型名、precision/scale/nullability 仅在 expect.columns 显式声明时断言。

| 类型 | canonical-v1-strict 规则 |
|---|---|
| NULL | 独立 null token；与字符串 NULL、""、"<NULL>" 不相等 |
| bool / int | 严格区分；int 为任意精度十进制值，禁止 float 中转 |
| decimal | 用精确系数/指数计算值；默认 1.0 与 1.00 数值相等，scale 用列断言验证；不与 int/float 隐式互转 |
| float | 默认有限值精确比较；+0/-0 值相等；NaN 仅与显式 NaN 相等；Infinity 必须同符号 |
| string | 保留大小写、尾空格和 Unicode 码点；CHAR 也不默认 trim；不默认 Unicode normalization |
| date / time | 固定 ISO 格式、保留有效小数秒精度；不丢失超出 Driver 表示范围的精度 |
| timestamp | 无时区的日期时间元组，禁止猜测本地时区 |
| timestamp_tz | 规范为 UTC 精确时刻；原始 offset 仅在测试显式声明时另行断言，不与无时区 timestamp 比较 |
| bytes / BLOB | 精确字节；DSL 使用 base64；CLOB 按 string 处理或分块同语义校验 |

类型返回是否精确可表示由 Adapter 能力声明决定。无法无损读取的字段不能静默截断后判 PASS。
Float 容差必须按列显式指定 abs_tol/rel_tol，满足 abs(a-b) <= max(abs_tol, rel_tol*max(abs(a),abs(b)))；只用于有限浮点值。
MVP 容差仅支持 exact；rowsort/hash/valuesort 禁止容差，避免非传递近似相等导致排序匹配歧义。容差不得用于 Decimal。

## 7. Expected 编码

XGT 1.1 使用一行一个 JSON Row 数组；字符串、null、bool 为原生 JSON 类型，所有 JSON number 必须以十进制精确解析，整数映射 int，小数映射 decimal。
float、bytes、日期/时间等采用显式 typed object，不使用 YAML 隐式转换：

```json
[1, "hello world", null, {"type":"decimal","value":"1.20"}, {"type":"float","value":"NaN"}, {"type":"bytes","base64":"AAE="}]
```

typed date/time/timestamp/timestamp_tz 使用 {"type":"timestamp","value":"2026-09-11T10:00:00.123456"} 同类格式。
Scenario expect.rows 使用等价 JSON 兼容值；复杂类型仍使用 typed object。重复 JSON/YAML 键、行长度不一致、未知 type 和不合法时间值均编译失败。

## 8. 比较模式与 Hash 编码

- exact：流式逐行比较，顺序必须由用例明确保证；ORDER BY 键不唯一时仍需用例设计稳定次序。
- rowsort：按 Canonical Row 的完整编码字节排序后比较，保留重复行和列位置；不同类型不会混淆。
- valuesort：显式忽略行列归属，仅保留值多重集合和总行列数量，可能漏掉关联错误；仅扩展阶段支持，MVP 编译拒绝。
- expected_error：声明的 error_code/sqlstate/error_class/message_regex 全部满足（AND）；无错误、错误类别不符均 FAIL；网络断连不能匹配成预期 SQL 错误。

Canonical Hash 流为 UTF-8 magic `XGC1` + 长度分帧 header + 逐行分帧 payload。整数长度统一 unsigned 64-bit big-endian。
header 为键排序、无多余空白的 JSON，包含 mode、column_count、logical_types、comparison_profile；Result 行编码为列数及连续 cell frame。
cell frame = 1-byte type tag + 8-byte payload length + payload；类型标签按上述逻辑类型顺序固定为 0..10。Row frame 以 8-byte 行字节长度开头，禁止拼接裸值造成边界歧义。
int 用无前导零十进制；decimal 去无意义尾零、零统一为 0，采用精确科学计数系数/指数；float 用 IEEE-754 binary64 big-endian，NaN 统一 quiet NaN，-0 规范为 +0。
string 为 UTF-8；bytes 为原始字节；日期时间为规范 ISO ASCII，分秒尾零只按值规范，不得减少实际有效精度；null payload 为空、bool 为 0/1 单字节。
hash rowsort 对完整 Row frame 作全局排序再增量 SHA-256，并另外核验 row_count/column_count；不能 XOR 行哈希或把分批排序当全局排序。
任何编码规则变更必须升级 canonical_version，并在 Delta 中视为比较上下文变化。

## 9. 内存、磁盘和失败证据

Exact/Hash Exact 使用 fetchmany，内存与总行数解耦；RowSort 使用受限内存排序块 + 临时文件外部归并。
设置 memory_budget_bytes、temp_disk_budget_bytes、artifact_budget_bytes；超过上限为 INFRA_RESOURCE，不能截断结果后通过。
失败保存总行数、差异总量、截断标记、前 N 个差异和内容哈希；Artifact 截断只影响诊断细节，不改变完整比较结论。
临时文件纳入资源清理；断电/进程退出后的残留通过 Run/Attempt 所有权恢复，禁止跨项目任意清理。

## 10. 分阶段验收

下列是实现验收要求；文档修订本身不代表这些场景已被产品验证。

| 阶段 | 必须验证的反例 | 期望 |
|---|---|---|
| SQL MVP | 索引后改 Case/Suite/Fixture | 拒绝漂移或继续使用原 Bundle |
| SQL MVP | active/disabled、issue 选例与 Catalog rebuild | 集合正确，增量与全量相同 |
| SQL MVP | NULL/"NULL"、空串、尾空格、重复行、Decimal 精度、浮点/时区/二进制 | 无误报、无错误归一化通过 |
| SQL MVP | Case A 未回滚或 Cleanup 失败，随后 Case B | 复位或隔离，B 不受污染 |
| SQL MVP | 反复执行与不同顺序运行样板 | 结果一致、资源数量稳定 |
| SQL MVP | 覆盖重复 Case、缺 Claim、断言未执行 | 点去重、缺口可解释 |
| Scenario | 分支失败、Barrier 超时、同 Session 并用、取消阻塞 SQL | 有界退出，清理完整 |
| 多集群 | Lease 过期但 DB 仍可达、旧 Agent 回归 | 无双持有者，必要时隔离 |
| 多集群 | 重复/乱序事件、ACK 丢失、Controller 重启、WAL 满 | 投影一致、终态不回退、受控背压 |
| Release | P0 100 条中 20 条 unsupported，80 条通过 | 执行率/通过率均 80%，必需门禁失败 |
| Release | 用例、模型、驱动、目标环境变化及迟到事件 | 差异分类明确，Baseline 不被改写 |

## 11. 性能验收口径

固定并记录 CPU、内存、磁盘、OS、Driver/DB build、连接上限和数据集；冷/热缓存分别报告。
Catalog 场景：100000 Case，module/feature/level/tag/issue/status 混合筛选，热查询 p95 目标 <=2s；全量索引及 1% 源变更、Suite/Fixture 扇出重编译单独记录时间与峰值内存。
Runner 场景：分别使用空/快速查询与真实复杂查询，测每 Case 框架开销 p50/p95、吞吐、连接峰值及失败诊断成本。Fast Path 初始目标为框架附加开销 p95 <=5ms/Case，目标是否可达以基准实测决定。
百万行结果：memory_budget_bytes=256MiB，记录 Runner RSS、排序临时磁盘与总耗时；超预算拒绝或显式资源错误，不能无界 fetchall。
性能结果不能只给 Case/秒；必须同时确认比较正确性、隔离和事件持久化开启。吞吐未达目标先定位瓶颈，再调整资源与实现。

## 12. Manifest Canonical Serialization：XGMJ1

Manifest 1 使用 XGMJ1；该标识与 Golden Vector 一起冻结，不能将 Python/Go/Java 默认 JSON 输出直接视为规范编码。

1. 严格解析并校验 Schema/静态语义，重复键在构造对象前拒绝；数字按精确十进制读取，禁止先转 binary64 再序列化。
2. 构造身份投影：仅去掉根 manifest_hash，以及 Schema 明确标记的 ContentRef.uri。ContentRef 必须同时保留 sha256 与 size；没有内容哈希的引用不能仅保留 URI 后当作不可变输入。
3. run_id、target_id、catalog_snapshot_id、Plan 参数、版本、模型、选择原因、Bundle hash 均保留。本哈希标识本次冻结运行输入，包含运行身份，不用于断言不同 Run 的执行语义相等；后者使用 semantic_hash 与目标可比规则。
4. 集合型数组先规范排序：case_entries 按 case_id，target_entries 按 target_id，expected_executions 按 (case_id,target_id)，bundles 按 sha256，依赖清单按 input_kind/input_path；重复标识拒绝。其他集合数组必须在 Schema 标明排序键，未标明的一律保留顺序。
5. Step、SQL 参数、Expected 行和显式排序指令等顺序敏感数组原样保留。不能为“稳定 Hash”全局排序所有数组。
6. 对象键按 Unicode 标量值序列升序排列；UTF-8、无 BOM、无结构空白、文件尾不加 LF。源码格式中的 CRLF/LF 不影响解析后 JSON，但字符串内的 CR/LF 不擅自互换。
7. 字符串仅转义双引号、反斜线和 U+0000..U+001F 控制字符；控制字符统一小写六字符形式 `\u00xx`，不使用 `\n`/`\t` 缩写。其他有效 Unicode 标量直接 UTF-8 编码，不转义斜线、不做 NFC/NFD 归一化；孤立 surrogate 拒绝。
8. number 使用有限精确十进制、无指数、无前导加号、整数部分无多余前导零，小数尾零删除、空小数部分连同小数点删除，-0 归为 0。true/false/null 使用 JSON 小写字面量；NaN/Infinity 禁止作为 Manifest number。
9. Schema 给每个数值字段设范围；XGMJ1 统一限制规范数字 token <=128 个 ASCII 字符，超过则拒绝而非截断。SQL 大整数、Decimal、特殊浮点等测试值位于 Bundle typed value 中，不因 Manifest 数值上限改变测试语义。
10. manifest_hash 为 SHA-256(canonical_bytes) 的小写十六进制。不得移除任意名字包含 uri/path/time 的字段；脚本参数中的路径与业务时间仍可能是执行语义。

最小编码向量（只验证编码器，不是完整 Manifest）：输入 `{"z":1.00,"a":"中","b":-0}` 的期望 UTF-8 文本为 `{"a":"中","b":0,"z":1}`，末尾无换行。
该向量长 23 字节，十六进制为 `7b2261223a22e4b8ad222c2262223a302c227a223a317d`，SHA-256 为 `d7096f9172852751f9434e5208521cfb0d4ccda2ee58c7e1206a0ae5a6a18cef`。
完整 Manifest 向量还必须验证：Bundle ContentRef URI 变化哈希不变；Bundle hash、run_id 或参数变化哈希变化；集合重排不变；Step 顺序变化则变化。向量同时固定精确字节及 SHA-256，按 [12](12_Machine_Contracts_and_Engineering_Validation.md)审定。

## 13. semantic_hash 边界与审查失效

semantic_hash 是执行语义输入指纹，不是 SQL 逻辑等价证明。SQL 原文仅规范换行，不做交换律、常量折叠、去注释或空白重写来合并 Case。
执行参数、timeout/cleanup_timeout、Setup/Step/Cleanup 树、Fixture、Oracle、Expected、comparison_profile 和所用语义版本必须列入规范化输入清单；不通过“重要参数”这种自由判断决定是否入 Hash。
标题、Owner、Tag、Coverage Claim 与审查人/日期不入执行 semantic_hash。Claim/模型/断言映射有独立 review_input_hash（08 §19），变化会使覆盖审查失效，即使 SQL 完全未变。
编译产物保留完整有效 Metadata，因此审查证据变化会影响 compiled_hash。审查输入不能包含其自身 evidence_hash、reviewer 或 reviewed_at，避免循环引用。
验收必须包含 SELECT a+b 与 SELECT b+a 得到不同 semantic_hash；同一 SQL 的 LF/CRLF 得到相同语义指纹；不同 Expected、Timeout 或 Fixture 得到不同指纹。

## 14. Reset / Probe 合约测试

framework_tests/integration/reset_probe 按 Adapter/Driver/DB build 执行并记录以下维度：未提交事务、autocommit、事务隔离、current schema/search_path、timezone/locale、会话参数、role、temporary table、cursor、prepared statement 和锁。
先取得干净基线，再让 Case A 修改受支持维度并在 Setup、执行或清理阶段注入异常，随后 Case B 用独立 Probe 验证状态与数据隔离。根据数据库能力拆成多个合法 SQL 场景，不能假设所有数据库都支持同一段 SET/PREPARE/DDL 或事务性 DDL。
除了异常退出，还验证成功、断言失败、取消、Driver 断连和进程丢失；每项预期为“验证恢复成功”或“隔离/销毁且不复用”，不是一律要求原连接继续可用。
Adapter 不支持的 Probe 显式记录 unsupported，且不得将其当作该资源恢复证明；Session 重建不能代替共享数据库或集群状态恢复。

## 15. Benchmark 记录与阶段预算

benchmarks/ 的五类脚本与阶段安排见 [12](12_Machine_Contracts_and_Engineering_Validation.md)。Phase 1 至少记录 Selector p50/p95、全量/增量编译时间、Runner 开销、Canonical 吞吐/内存、PASS 事件字节数、事件持久化吞吐及背压。
Runner 使用同一 Driver、SQL、数据和连接复用策略做直接执行对照；报告独立样本分布、样本数、预热次数和固定随机种子，不能直接把两个独立 p95 相减当“p95 框架开销”。
PASS 大小分别报告业务摘要、Step Event 和 Artifact 总量，按 Case/Step 数给出总量估算；事件吞吐必须在持久化开启时测量，CPU 时间和 fsync 等待分开记录。
2s 查询/5ms 框架附加开销/256MiB 工作内存是固定测量条件下的初始目标，不是未经测试的承诺；进程基础 RSS 与可控排序工作内存分别统计。未有绝对目标的指标先建立基线，目标或回归阈值写入基准配置再启用门禁。
Hash/大结果扩展模式未实现时不记为性能验收通过；只测试当前阶段真正执行的模式。故障恢复和数据正确性不得因关闭日志、重置或验证来换取达标。
