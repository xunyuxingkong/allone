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
| target_entries | target_id、数据库精确 build、OS/arch/topology/mode、配置及数据集指纹 |
| expected_executions | case_id × target_id、选择原因、适用性结果、reason_code |
| bundles | 内容 URI、SHA-256、大小、依赖清单；不包含凭据 |
| runtime_versions | Compiler、DSL、Metadata、Canonical、Adapter/Driver/Runner/Protocol 版本 |
| coverage_scope | model_id/version/hash、strategy、要求级别、点集合引用及分母 |
| baseline / quality_gate | 解析后的基线 ID、比较策略、数值阈值 |
| manifest_hash | 除自身与存储位置外的规范化 Manifest 内容哈希 |

解析后的 Plan 包括参数值、选择/排除原因和目标快照。秘密值只保留受控引用与版本，不写入 Bundle/日志；秘密变化是否影响可比性由目标配置策略明确。
case_entries 还需关联当前 Catalog 全量 ID/status/semantic_hash 的轻量资产清单，供 Delta 区分未选中、禁用和真正删除。

## 3. 内容哈希

所有哈希使用 SHA-256；对象键排序、数组顺序按语义保留，文本使用 UTF-8/LF。原始 source_hash 仍对原始字节计算。

- dependency_hash：按稳定输入键排序的完整内容哈希清单，含 Suite、默认值、Fixture、脚本、Registry、Model、策略与工具版本。
- compiled_hash：最终 Unified Case 的规范序列化，包含 effective_metadata、dependency_hash 和编译器版本；排除编译时间与绝对工作区路径。
- semantic_hash：执行 Step 树、SQL 原文的换行规范形式、Fixture/脚本内容、Oracle/期望值、比较规则、执行参数默认值、规范化语义版本。不得通过去除 SQL 字符串空白或改写 SQL 猜测等价。
- 标题、Owner、Tag、source_path、生成时间不进 semantic_hash；策略/分类变化仍在 Manifest 中报告。
- Adapter/Driver/DB build 和目标配置在运行上下文单独比较；不能因为 SQL 未变就忽略它们。

Bundle 内相对路径不得越出快照根。DSL 1.0 与 1.1、Canonical 版本不兼容时显式转换或拒绝，不能只替换版本号后继续执行。

## 4. Attempt 执行与隔离

```text
Resource Admission → Prepare → Setup → Steps
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
