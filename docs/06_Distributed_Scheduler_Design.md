# XG DB Test Distributed Scheduler Design

> Scheduler / Agent Protocol Design Version：1.1

## 1. 目标

分布式调度负责：

```text
一个 Test Run
→ 多数据库环境
→ 多 Agent
→ 每个 Environment 多 Worker
```

并支持：

```text
Shard
Matrix
Capability Match
Environment Weight
Resource Lease
Failure Reschedule
Exclusive Case
Historical-duration Scheduling
```

---

## 2. 两级调度

采用：

```text
Global Planner / Scheduler
+
Local Planner
```

Global 负责：

```text
Case → Environment
```

Local 负责：

```text
Environment 内 Case → Worker
```

Controller 不做 SQL 级远程调度。

---

## 3. 组件

```text
Controller
├── Run Manager
├── Global Planner
├── Global Scheduler
├── Environment Registry
├── Lease Manager
└── Result Aggregator

Agent
├── Registration
├── Heartbeat
├── Local Planner
├── Resource Manager
├── Worker Pools
├── Executor
└── Result Buffer
```

---

## 4. Environment 状态

```text
ONLINE
DEGRADED
OFFLINE
DRAINING
MAINTENANCE
QUARANTINED
```

只有符合策略的 ONLINE/DEGRADED 环境可参与调度。

---

## 5. Agent 注册

Agent 启动后上报：

```text
agent_id
environment_id
agent_version
protocol_version
capabilities
capacity
database_version
topology
labels
```

Controller 校验协议版本后注册。

---

## 6. Heartbeat

建议每：

```text
5s~30s
```

上报：

```text
timestamp
health
running_shards
worker_usage
db_connections
resource_usage
result_buffer_size
```

---

## 7. Offline 判定

示例策略：

```text
3 个 heartbeat 周期缺失 → DEGRADED
6 个周期缺失          → OFFLINE
```

阈值配置化。

---

## 8. Compatibility Resolver

Case Requirements：

```text
topology
os
arch
storage
mode
capabilities
labels
```

Environment 使用相同模型。

Resolver 计算：

```text
Compatible Environment Set
```

不兼容的 Case × target 保留预期执行记录：

```text
final_status = SKIP
reason_code = UNSUPPORTED
```

或在 Plan 校验阶段直接报错，取决于 Test Plan 策略。

---

## 9. Shard Mode

同一 Case 在一个逻辑 target 下只产生一个 CaseExecution；重试产生新 Attempt。
target 必须冻结 database build/version、OS、arch、topology、mode、关键配置与数据集版本；等价物理环境组成 Shard 池。
同版本不同 build 也不能隐式混跑。target 配置来自 Test Plan，environment_id 仅是物理资源位置。
目标是满足优先级与资源约束后缩短 makespan；不以牺牲环境可比性换取吞吐。

---

## 10. Matrix Mode

同一 Case 在多个逻辑 target 下分别执行；CaseExecution 统一唯一键为 run_id + case_id + target_id。
一个 target 内可使用等价环境进行 Shard 分配或重试。物理环境替换不改变逻辑测试目标。
选定 Case × target 的完整预期集合在 Resolver 过滤前写入 Manifest；UNSUPPORTED、无在线环境和取消都不得静默减少此集合。

---

## 11. Weighted LPT

Shard 初始算法建议使用 Weighted LPT：

1. Case 按 `estimated_duration_ms` 降序；
2. 过滤出兼容环境；
3. 计算每个环境当前 `normalized_load`；
4. 把当前最长 Case 放入负载最低的兼容环境。

```text
normalized_load =
assigned_duration / capacity_weight
```

---

## 12. Environment Capacity

示例：

```yaml
capacity:
  fast_workers: 32
  normal_workers: 8
  heavy_workers: 2
  exclusive_workers: 1
  max_connections: 64

weight: 2.0
```

Global Planner 不应超配环境。

---

## 13. Shard 作为调度单位

Controller 下发：

```text
Shard
```

而不是逐 Case RPC。

Shard 字段：

```text
shard_id
run_id
environment_id
case_ids
execution_class
estimated_duration
bundle_uri/hash
manifest_hash
target_id
assignment_epoch
```

一个 Shard 可包含：

```text
100~5000 Cases
```

具体由 Case 重量决定。

---

## 14. Local Planner

Agent 将 Shard 分配到：

```text
Fast Pool
Normal Pool
Heavy Pool
Exclusive Queue
```

并考虑：

```text
fixture locality
worker schema
session requirement
resource lease
historical duration
```

---

## 15. Fixture Affinity

共享 immutable Fixture 的 Case 尽量：

```text
同 Environment
同 Worker
```

减少重复 Setup。

---

## 16. Resource Lease

资源包括 environment、cluster、database、schema、node、backup_dir；必须有层级归属与读写/独占冲突表。

```text
lease_id / resource_type / resource_id
owner_run / owner_attempt
fencing_token / issued_at / expires_at
state: ACTIVE | EXPIRED | REVOKED | RELEASED
```

Lease Manager 在一个事务中验证环境状态、资源冲突、容量并授予递增 fencing_token。普通任务和独占任务都走相同准入路径。
cluster 独占与其下所有资源使用冲突；不同 Run 也受约束。Local Planner 不能绕过全局排空或只靠独立 Exclusive Queue 实现互斥。
多资源按稳定资源 ID 顺序申请或原子批量申请；部分失败必须回滚预留，避免死锁和容量泄漏。

---

## 17. Lease Renew

Controller 使用自己的时钟决定租约有效期；Agent 依据往返时延与安全裕量换算保守的本地单调时钟截止点，不直接比较两台机器墙钟。
只有匹配 lease_id、owner_attempt、fencing_token 的当前持有者可续租；过期后不能复活旧 token。
续租失败停止启动新 Step/Case。到本地截止点必须停止受保护操作；无法确认停止则上报并隔离资源。

租约过期只撤销所有权，不证明数据库 SQL、Restore 或远程进程终止。资源重分配必须满足以下之一：

1. 实际操作入口已验证新 token，旧 token 的后续写入被可靠拒绝；还需清理已发生的部分状态。
2. 不支持 fencing 的直连 SQL/系统动作，已确认旧 Session/进程停止并完成 Reset/Probe。

不能满足时进入 QUARANTINED，由恢复流程确认后重新 ONLINE。禁止仅等待 expires_at 就重新分配。

---

## 18. Exclusive Case

1. 原子将 Environment 置 DRAINING，阻止所有 Run/Shard 的新资源准入。
2. 停止 Local Planner 启动已入队普通 Case，等待运行中的 Attempt 退出；排空有截止时间。
3. 确认资源为空后授予 exclusive lease；执行前再次验证 token。
4. 执行、Cleanup、Reset、健康与数据状态 Probe。
5. 持久化成功恢复证明后释放租约并恢复 ONLINE。

排空超时不得强行并发启动独占任务；Cleanup/Reset/Probe 失败进入 QUARANTINED。
恢复证明包含旧 owner、token、session/process 终止状态、reset_contract 版本和 probe 结果。

---

## 19. Failure Classification

```text
TEST_ASSERTION
TEST_EXPECTED_ERROR_MISMATCH
TEST_SQL_EXECUTION
TEST_TIMEOUT

INFRA_NETWORK
INFRA_AGENT_LOST
INFRA_DB_UNAVAILABLE
INFRA_RESOURCE

FRAMEWORK_ERROR
FIXTURE_SETUP
FIXTURE_CLEANUP
FRAMEWORK_NORMALIZATION
FRAMEWORK_PROTOCOL
```

---

## 20. Retry Policy

默认 max_attempts=1。配置重试必须使用 [07](07_Result_Model_Design.md) 的完整 failure_type，不接受 infrastructure_error/timeout 等另一套别名。

| 条件 | 自动重试规则 |
|---|---|
| TEST_ASSERTION / TEST_EXPECTED_ERROR_MISMATCH / TEST_SQL_EXECUTION | 不自动重试 |
| INFRA_NETWORK / INFRA_AGENT_LOST / INFRA_DB_UNAVAILABLE / INFRA_RESOURCE | 仅在 on 白名单、次数未耗尽及恢复证明成立时重试 |
| TEST_TIMEOUT | 默认不重试；诊断 Plan 显式允许且旧 SQL 停止、资源复位后才可重试 |
| FRAMEWORK_* / FIXTURE_* | 默认不重试，先暴露框架或清理缺陷 |
| destructive / unsafe | 禁止自动重放 |
| conditional | 除上述条件外，reset_contract 必须执行成功 |
| safe | 仍须旧执行停止、资源清洁；safe 不是绕过隔离的权限 |

release Plan 不允许重试测试断言失败。人工诊断重跑保留所有 Attempt；曾测试失败后通过为 FLAKY，纯基础设施失败后通过为 INFRA_RECOVERED。

---

## 21. Attempt

每次实际执行都有独立：

```text
attempt_id
```

例：

```text
Attempt 1 → Cluster B → LOST
Attempt 2 → Cluster C → PASS
```

两个 Attempt 都保留。

---

## 22. Agent Lost

Controller 经心跳策略判定离线，将其 RUNNING/ASSIGNED Attempt 终结为 LOST；未开始的 Case 按持久化分配记录撤销旧 assignment_epoch。
旧 Agent 恢复后先 reconcile，不得继续旧队列；旧 epoch/token 不再具有启动权限。
safe/conditional Case 仅在租约与恢复条件满足后产生新 Attempt，并迁移至同 target 的等价环境。无可靠停止证明则隔离，不自动重跑。
旧 Agent 未 ACK 事件仍可重放为审计事实，但不能覆盖 LOST 终态或已存在的新 Attempt 结论。

---

## 23. Local Result Buffer

Agent 本地使用 append-only WAL/Buffer：

```text
Worker
→ Local Event Buffer
→ Controller
→ ACK
→ Compact
```

Controller 暂时不可用时，只允许在有效租约和 WAL 容量范围内继续已有任务；失租按第 17 节停止与隔离。

---

## 24. ResultEvent 幂等

每个 Event：

```text
event_id
```

Controller：

```text
durable deduplicate + ordered projection + terminal-state guard
```

允许 Agent 安全重发。

---

## 25. Cancel

Run Cancel：

```text
Controller
→ Cancel Shard
→ Agent 停止分配新 Case
→ 尽量取消可取消 Step
→ Cleanup
→ Release Lease
```

破坏性 Step 不保证瞬时取消。

---

## 26. Drain Environment

```bash
xgtest env drain cluster-a
```

行为：

```text
DRAINING
不接受新 Shard
等待当前任务完成
```

维护完成后：

```bash
xgtest env enable cluster-a
```

---

## 27. Matrix 示例

```yaml
environment_selector:
  version:
    - "5.0.3"
    - "5.1.0"

  os:
    - linux

distribution:
  mode: matrix
```

---

## 28. 优先级

推荐：

```text
P0 > P1 > P2 > P3
```

并支持优先完成：

```text
Fast P0
```

尽快给发布流程反馈。

---

## 29. 多 Run 公平性

MVP：

```text
FIFO + Run Priority
```

后续再实现：

```text
quota
fair share
team priority
```

---

## 30. Controller 持久化

即使 Controller 第一阶段单实例，也必须持久化：

```text
Run Manifest / Bundle reference
Shard / assignment_epoch
CaseExecution / Attempt
Environment / target snapshot
Lease / fencing_token
Result receipt / contiguous ACK checkpoint
```

这样未来才能支持 Controller HA。

---

## 31. Agent Protocol

长期推荐：

```text
gRPC
```

MVP 使用 HTTP/JSON 也可以。

关键不是协议技术，而是消息模型稳定。

---

## 32. Agent 最小 API

```text
register
heartbeat
assign_shard
cancel_shard
renew_lease
push_result_events
get_status
reconcile_assignment
```

---

## 33. Security

Agent/Controller：

```text
TLS
Token 或 mTLS
```

数据库凭据：

```text
Secret Provider
```

禁止出现在普通 Result Event 和日志中。

---

## 34. Observability

Controller 指标：

```text
queued_cases
running_cases
completed_cases
scheduler_latency
environment_online
lease_count
```

Agent 指标：

```text
worker_busy
connection_count
case_rate
heartbeat_delay
result_buffer_size
```

---

## 35. 第一阶段可简化

多集群 MVP 可以：

```text
静态 Environment
固定 Agent
HTTP/JSON
单 Controller
Weighted LPT
本地/PostgreSQL 状态库
```

但以下模型必须从第一天存在：

```text
Attempt
Lease
Idempotency
ResultEvent
Environment ID
```

## 36. 调度准入与恢复验收

Weighted LPT 只是初始负载启发式；资源准入还要验证连接数、Session 峰值、heavy 配额、互斥层级和 Fixture 访问模式。
历史耗时按 target 配置与 execution_class 统计；无历史时采用可配置保守默认值。
P0 优先后在同级按 LPT 分配；不能让不兼容环境因负载低被选中。
必须覆盖：网络分区但 DB 可达、续租失败、旧队列恢复、Controller 重启、多 Run 抢占同一集群、Cleanup 失败和硬超时 SQL 无法取消。
所有场景验证“不会同时存在两个可写入的资源持有者”，而非仅验证新任务最后 PASS。

## 37. Agent Protocol 1.1 信封

所有请求含 protocol_version、request_id、agent_id、agent_instance_id；分配/取消还含 run_id、shard_id、assignment_epoch、manifest_hash、target_id，资源操作带 lease_id/token。
register/heartbeat 的能力与容量必须和 Registry/target 快照相容；assign_shard 同 request_id 同内容重试返回相同收据，同 ID 不同内容为 FRAMEWORK_PROTOCOL。
Controller 未收到分配 ACK 时先查询/reconcile，不把未知分配直接当未执行。Agent 在持久化分配和 Bundle 验证后 ACK，启动每个 Attempt 前核对当前 assignment_epoch 与租约。
push_result_events 的事件含 producer_epoch、sequence、assignment_epoch 与 token，ACK 返回每个 Attempt 连续持久化 sequence；重放只补缺口，不取得新的执行权。
Agent/Controller 重启恢复各自持久化 epoch/游标；旧实例不能通过重新注册复活失效分配。静态单集群 MVP 由 Local Run Manager 执行相同身份/状态规则，无需远程 API。
