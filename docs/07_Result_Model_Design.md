# XG DB Test Result Model Design

> Result Schema Version：2（架构 v1.1）

## 1. 目标

Result Model 必须支持：

```text
单集群
多集群
Shard
Matrix
Retry
Agent Lost
Flaky
Step 级结果
大量 PASS Case
失败 Artifact
历史趋势
Allure / JUnit
```

---

## 2. 结果层级

```text
Run
 └── CaseExecution
      └── Attempt
           └── StepResult
                └── Artifact
```

---

## 3. Run

字段：

```text
run_id
plan_name
git_commit
catalog_version
manifest_hash
plan_hash
target_snapshot_hash
result_schema_version
started_at
finished_at
status
selected_case_count
environment_count
```

状态：

```text
CREATED
PLANNING
RUNNING
COMPLETED
FAILED
CANCELLED
```

---

## 4. CaseExecution

表示一个 Case 在一个逻辑测试目标上的聚合结果。Shard 和 Matrix 统一唯一键：

```text
run_id + case_id + target_id
```

字段：case_execution_id、case_id、target_id、compiled_hash、semantic_hash、level、final_status、reason_code、attempt_count、duration_total_ms、first_attempt_at、last_attempt_at。
Manifest 中全部预期目标在执行前建立记录；不支持目标也保留 SKIP/UNSUPPORTED，无可用环境保留 INCOMPLETE/NO_ENVIRONMENT。
每个 Attempt 独立记录实际 environment_id；CaseExecution 不用物理环境作聚合身份。

---

## 5. Attempt

字段：

```text
attempt_id
run_id
case_id
case_execution_id
target_id
environment_id
assignment_epoch
fencing_token
agent_id
worker_id
attempt_no
started_at
finished_at
duration_ms
status
failure_type
failure_signature
primary_status
primary_failure_type
cleanup_status
cleanup_failure_type
recovery_evidence_hash
```

状态：

```text
PENDING
ASSIGNED
RUNNING
PASS
FAIL
ERROR
TIMEOUT
LOST
CANCELLED
SKIP
```

---

## 6. Case Final Status

枚举：PASS、FAIL、ERROR、TIMEOUT、SKIP、FLAKY、INFRA_RECOVERED、CANCELLED、INCOMPLETE。

| Attempt 历史 | final_status |
|---|---|
| 一次通过，Cleanup/Reset/Probe 均成功 | PASS |
| 仅基础设施失败或 LOST，恢复后通过 | INFRA_RECOVERED |
| 曾有测试 FAIL/TEST_TIMEOUT 或非基础设施 ERROR，随后通过 | FLAKY |
| 无后续 PASS，最后有效终态为 FAIL/ERROR/TIMEOUT | 同最后终态，保留全部失败历史 |
| 最后 LOST 且没有成功重试 | INCOMPLETE |
| 明确不适用，未执行 | SKIP + reason_code |
| Run 取消造成未完成 | CANCELLED |
| 未分配、无环境、事件缺失导致不能裁决 | INCOMPLETE + reason_code |

Cleanup 失败不得产生 PASS：primary_status 保留主测试结论，Attempt.status=ERROR、failure_type=FIXTURE_CLEANUP，附清理失败详情。
INCOMPLETE 不等于 SKIP。所有 Attempt 终态不可覆盖，CaseExecution 在允许重试窗口关闭后才定稿。

---

## 7. Failure Type

Scheduler、Agent、Result、Retry 和 Failure Signature 使用同一注册表：

```text
TEST_ASSERTION
TEST_EXPECTED_ERROR_MISMATCH
TEST_SQL_EXECUTION
TEST_TIMEOUT
INFRA_NETWORK
INFRA_AGENT_LOST
INFRA_DB_UNAVAILABLE
INFRA_RESOURCE
FIXTURE_SETUP
FIXTURE_CLEANUP
FRAMEWORK_NORMALIZATION
FRAMEWORK_PROTOCOL
FRAMEWORK_ERROR
```

断言不符和非预期 SQL 错误为 FAIL；TEST_TIMEOUT 为 TIMEOUT；基础设施/Fixture/Framework 异常为 ERROR；失联终态 LOST 对应 INFRA_AGENT_LOST。
SKIP/CANCELLED/INCOMPLETE 使用 reason_code（UNSUPPORTED、CONDITION_FALSE、PLAN_CANCELLED、NO_ENVIRONMENT、EVENT_GAP、ATTEMPT_LOST），不伪造 failure_type。
Result 1 的别名只能由显式导入器映射，不能让新模块继续写两套命名。

---

## 8. StepResult

字段：

```text
step_id
step_index
step_type
status
started_at
finished_at
duration_ms
summary
```

例如：

```text
setup-1
sql-2
query-3
cleanup-1
```

Step 状态：

```text
PASS
FAIL
ERROR
TIMEOUT
SKIP
CANCELLED
```

---

## 9. SQL Result Summary

PASS 不保存全部结果行。

建议保存：

```text
row_count
column_count
result_hash
optional sample
```

FAIL 时保存：

```text
expected
actual
diff
```

并设置最大 Artifact 大小。

---

## 10. Artifact

字段：

```text
artifact_id
attempt_id
step_id
type
name
uri
size
sha256
created_at
```

类型：

```text
sql
expected
actual
diff
server_log
execution_plan
stack
pstack
core_info
cluster_state
backup_log
custom
```

---

## 11. Artifact Storage

Result DB 不直接保存大型日志和二进制。

保存：

```text
URI
size
sha256
metadata
```

MVP：

```text
local filesystem
```

后续：

```text
MinIO / S3 compatible
```

---

## 12. PASS 极简

大量 PASS Case 只保存：

```text
identity
status
duration
environment
worker
version
result summary
```

避免每条 PASS 产生大量 JSON/Allure 附件。

---

## 13. FAIL 详细

失败额外保存：

```text
Case Metadata
SQL
Expected
Actual
Error
Step
Environment
DB Version
Session
Node
Execution Plan
Logs
```

---

## 14. Failure Signature

用于候选失败聚类，不能据此证明同一根因：

```text
hash(
  failure_type
  + normalized_error_code
  + normalized_message
  + normalized_stack
  + failing_step_id + semantic_hash
)
```

Signature 必须剔除：

```text
timestamp
session id
random schema
random object name
address
```

---

## 15. ResultEvent

Agent → Controller 使用 Event。

示例：

```json
{
  "schema_version": "2",
  "event_id": "attempt2-epoch1-0001",
  "event_type": "STEP_FINISHED",
  "run_id": "run1",
  "case_id": "QUERY.JOIN.0001",
  "attempt_id": "attempt2",
  "target_id": "xg51-linux-x86",
  "producer_epoch": "epoch1",
  "assignment_epoch": 1,
  "sequence": 1,
  "fencing_token": 17,
  "environment_id": "cluster-a",
  "timestamp": "2026-09-11T13:00:00+08:00",
  "payload": {}
}
```

---

## 16. Event Types

建议：

```text
ATTEMPT_STARTED
STEP_STARTED
STEP_FINISHED
ARTIFACT_CREATED
ATTEMPT_FINISHED
```

禁止为每一行 Result 发送 Event。

---

## 17. Event 幂等

event_id=(attempt_id, producer_epoch, sequence)；生产者先持久化 ID 与 payload，再发送。sequence 为 Attempt 内的总事件顺序，不能按 Step 各自从 1 起算。
Controller 事务内保存原始事件、去重哈希、按序投影与连续 ACK 游标，提交后才 ACK。
同 ID 同 payload 重发为 no-op；同 ID 不同 payload 为 FRAMEWORK_PROTOCOL，保留冲突证据并隔离生产者，不能静默忽略。
乱序事件暂存，缺口请求重放；未收到完整前缀不直接应用后续 ATTEMPT_FINISHED。超出事件恢复期限则 INCOMPLETE/EVENT_GAP。
进程重启先恢复原 WAL；不能证明 sequence 连续时，由 Controller 创建新 Attempt，不能复用旧 ID 从头发事件。

---

## 18. JSONL

MVP：

```text
results/<run_id>/events.jsonl
```

优点：

```text
append-only
易调试
易恢复
易重新导入
```

---

## 19. Result DB

后续推荐 PostgreSQL。

核心表：

```text
runs
case_executions
attempts
step_results
artifacts
failure_signatures
environments
```

---

## 20. Run Summary

至少统计：

```text
selected
executed
passed
failed
error
timeout
skip
flaky
infra_recovered
duration
```

---

## 21. Allure 映射

建议：

```text
module     → epic
feature    → feature
subfeature → story
level      → severity/tag
tags       → labels
```

Artifact 作为 Attachment。

---

## 22. JUnit 映射

每个 CaseExecution：

```text
<testcase>
```

FAIL：

```text
<failure>
```

ERROR / TIMEOUT / INCOMPLETE / FLAKY 聚合结果：

```text
<error>
```

SKIP：

```text
<skipped>
```

---

## 23. Matrix Report

必须保留 Environment 维度：

| Case | 5.0 x86 | 5.1 x86 | 5.1 ARM |
|---|---|---|---|
| JOIN.001 | PASS | PASS | FAIL |
| UNION.002 | PASS | PASS | PASS |

---

## 24. 历史执行时间

从成功且可信的 Attempt 更新：

```text
avg_duration
p50
p95
last_duration
```

用于 Scheduler。

FAIL/TIMEOUT 不直接参与正常耗时统计。

---

## 25. Flaky

同一个 CaseExecution 曾出现测试失败或非基础设施错误，随后 PASS → FLAKY。基础设施分类优先使用第 6 节规则，不把所有 ERROR 一概判为 Flaky。

基础设施失败后 PASS：

```text
INFRA_RECOVERED
```

两者必须区分。

---

## 26. Retention

建议：

```text
Run Summary       长期
Case Result       长期
PASS Step Detail  可裁剪
FAIL Artifact     长期或按版本策略
Server Log        配置化
Core Dump         独立生命周期
```

---

## 27. Security

Result 中禁止出现：

```text
password
token
private key
connection secret
```

Reporter/Adapter 必须支持 redact。

---

## 28. Query API

后续 Result Service 至少支持：

```text
run
case
version
module
feature
status
failure_signature
environment
```

---

## 29. Catalog 关联

Result 必须记录：

```text
case_id
compiled_hash
git_commit
```

确保历史结果可以恢复当时测试资产版本。

---

## 30. 真相源

定义：

```text
Durable Event Log
= 执行历史事实源
Result DB
= 可重建的查询投影 + 已锁定的发布快照

Allure
= 展示层
```

禁止从 Allure 反向推导核心历史数据。

## 31. Attempt 状态迁移与权威

| 当前状态 | 允许后继 | 权威与条件 |
|---|---|---|
| PENDING | ASSIGNED / SKIP / CANCELLED | Controller 完成准入或明确跳过/取消 |
| ASSIGNED | RUNNING / LOST / CANCELLED | Agent 接收有效分配后报告 RUNNING；Controller 负责失联与撤销 |
| RUNNING | PASS / FAIL / ERROR / TIMEOUT / LOST / CANCELLED | Agent 在清理后提交完成；Controller 可终结失联或撤销任务 |
| 任一终态 | 无 | 新执行必须新 attempt_id；禁止终态回退 |

Controller 持久化的原子状态迁移是裁决权威。Agent 报告经过 assignment_epoch/token/序列和合法迁移校验。
PENDING/SKIP 为无业务执行；终态事件必须包含 Cleanup 状态、最后序列与摘要。预执行 Fixture 异常进入 RUNNING 后 ERROR。
LOST 后迟到 PASS/FAIL 仅存 late_event 审计，不能修改原 Attempt、新 Attempt、CaseExecution 定稿或 Baseline。
同一资源上启动新 Attempt 前必须通过 06 的恢复检查；终态裁决不等于旧执行已停止。

## 32. Run 终结与发布锁定

CREATED → PLANNING → RUNNING → COMPLETED；规划/框架无法继续则 FAILED，用户取消为 CANCELLED。终态无自动回退。
COMPLETED 只表示执行收敛，不代表产品或 Quality Gate 通过。Run 独立保存 gate_status。
定稿前处理全部 Manifest 预期记录、重试决策和事件缺口；每条记录都须有终态或明确 INCOMPLETE 原因。
Baseline 只能锁定已收敛且满足发布选择规则的快照，保存结果投影哈希和 ACK 水位；迟到事件存审计区，不重写快照。修订须新 Run/快照并显式关联。

## 33. WAL、背压和报告映射

Agent WAL 先落盘再确认本地事件，Controller durable ACK 后才压缩。配置高水位/硬上限与保留空间；高水位暂停新 Case，硬上限停止可停止执行并保留恢复记录。
Controller 重启从持久化投影及事件游标恢复；重复/乱序重放必须得出相同结果。
JUnit 中 PASS/INFRA_RECOVERED 为通过（后者附属性），FAIL 为 failure，ERROR/TIMEOUT/INCOMPLETE/FLAKY 为 error；SKIP 为 skipped，CANCELLED 为 skipped 且 Run 非成功。
CI 最终以 Quality Gate/Run 状态决定退出码，不能只看 JUnit 的 skipped 数量。Allure/JUnit 不成为新的结果事实源。

## 34. JSONL MVP 的持久化等价实现

单机由 Local Run Manager 承担上述 Controller 裁决职责。JSONL 为单写者顺序日志，每条提交记录含事件及接收序号；写完并 fsync 才确认接收。
去重索引、投影和 ACK 水位是可重建派生物；进程重启先重放已完整提交日志，再对外接受请求。尾部不完整记录不视为已提交，按恢复策略隔离或截断未提交尾部。
若采用数据库，事件/去重键/投影/ACK 游标在单个事务提交；若采用 JSONL，不跨多个独立文件假装原子事务。相同事件序列必须生成相同聚合哈希。
Baseline 锁定保存单独不可变快照及对应日志水位/hash；本地 JSONL 也遵守迟到审计、不回写终态规则。
