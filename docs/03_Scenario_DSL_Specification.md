# XG Scenario DSL Specification

> 复杂场景 DSL
> 扩展名：`.xgs.yaml`
> DSL Version：1.1

## 1. 适用范围

```text
Transaction
Concurrency
Multi-session
Backup / Restore
Cluster / HA
Configuration
Administration
Node Restart
Import / Export
复杂跨资源场景
```

## 2. 基本结构

```yaml
dsl_version: "1.1"
metadata_version: "1.1"

id: TX.ISOLATION.RC.0001
title: Read Committed visibility

module: transaction
feature: isolation
subfeature: read_committed
level: P0

requirements: {}
resources: {}
sessions: {}
steps: []
cleanup: []
```

## 3. Session

```yaml
sessions:
  s1: {}
  s2: {}
```

SQL：

```yaml
- sql:
    session: s1
    statement: BEGIN
```

## 4. Query

```yaml
- query:
    session: s2
    statement: |
      SELECT value FROM t1 WHERE id=1
    expect:
      order: exact
      rows:
        - [10]
```

`order`：

```text
exact
rowsort
valuesort
```

## 5. Expected Error

```yaml
- sql:
    session: s1
    statement: |
      INSERT INTO t1 VALUES(1)
    expect_error:
      error_code: XG-10001
      message_regex: duplicate.*
```

## 6. Transaction Step

除了直接 SQL，也可：

```yaml
- transaction:
    session: s1
    action: begin
```

支持：

```text
begin
commit
rollback
savepoint
rollback_to
```

由 Adapter 转换。

## 7. Parallel

```yaml
- parallel:
    branches:

      - name: tx1
        steps:
          - sql:
              session: s1
              statement: |
                UPDATE t1 SET value=1 WHERE id=1

      - name: tx2
        steps:
          - sql:
              session: s2
              statement: |
                UPDATE t1 SET value=2 WHERE id=1
```

默认所有 Branch 成功完成后继续；任一分支失败触发协同取消，其余分支有界退出，再执行 Case Cleanup。禁止永久等 Barrier。

## 8. Barrier

```yaml
- parallel:
    branches:

      - name: tx1
        steps:
          - barrier:
              name: before_update
              parties: 2
          - sql:
              session: s1
              statement: UPDATE t1 SET value=1 WHERE id=1

      - name: tx2
        steps:
          - barrier:
              name: before_update
              parties: 2
          - sql:
              session: s2
              statement: UPDATE t1 SET value=2 WHERE id=1
```

## 9. Signal

```yaml
- signal:
    name: lock_acquired
```

```yaml
- wait_signal:
    name: lock_acquired
    timeout: 10s
```

## 10. Wait

```yaml
- wait:
    condition: cluster_healthy
    timeout: 120s
    interval: 2s
```

Condition 由 Adapter 注册：

```text
cluster_healthy
new_primary
replication_synced
session_blocked
node_online
```

禁止任意 Python 表达式。

## 11. Sleep

```yaml
- sleep: 2s
```

但能用 condition wait 时不应使用固定 sleep。

## 12. Node

```yaml
- node:
    action: stop
    target: primary
```

支持：

```text
start
stop
restart
kill
```

破坏性动作必须：

```yaml
destructive: true
```

## 13. Cluster

```yaml
- cluster:
    action: failover
    target: primary
```

## 14. Backup

```yaml
- backup:
    type: full
    destination: "${backup_dir}/case001"
```

## 15. Restore

```yaml
- restore:
    source: "${backup_dir}/case001"
```

Restore 默认应为：

```text
execution_class = exclusive
destructive = true
idempotency = conditional/unsafe
```

## 16. Script

```yaml
- script:
    path: scripts/check_storage.sh
    timeout: 30s
```

只允许仓库白名单脚本，禁止任意 shell 字符串。

## 17. Assert

```yaml
- assert:
    type: cluster_state
    expect:
      healthy: true
      primary_count: 1
```

或：

```yaml
- assert:
    type: catalog
    object: idx_t1_id
    expect:
      exists: true
```

## 18. Cleanup

```yaml
cleanup:
  - sql:
      session: s1
      statement: DROP TABLE t1
```

无论 PASS/FAIL/超时/取消都尝试；失败记 FIXTURE_CLEANUP 并隔离资源，不能忽略后继续复用。

## 19. Idempotency

```yaml
idempotency: safe
```

枚举：

```text
safe
conditional
unsafe
```

## 20. Destructive

```yaml
destructive: true
```

Test Plan 可显式排除。

## 21. Resource Requirement

```yaml
resources:
  sessions: 2
  schemas: 1
```

HA：

```yaml
resources:
  cluster: 1

requirements:
  topology: 3-node
  capabilities:
    - cluster.failover
```

## 22. Timeout

Case：

```yaml
timeout: 10m
```

Step：

```yaml
- wait:
    condition: new_primary
    timeout: 60s
```

有效 Step 截止点=min(Case 剩余预算, Step 预算)。Case 总超时不能被长 Step 覆盖；Cleanup 使用独立 cleanup_timeout。

## 23. Retry

```yaml
retry:
  max_attempts: 2
  on:
    - INFRA_NETWORK
```

破坏性 Case 默认只允许 1 次 Attempt。

## 24. 完整事务示例

```yaml
dsl_version: "1.1"
metadata_version: "1.1"

id: TX.RC.VISIBILITY.0001
title: Read Committed visibility

module: transaction
feature: isolation
subfeature: read_committed
level: P0

execution_class: normal
isolation: case_schema
idempotency: conditional
reset_contract: case_schema_clean
destructive: false
status: draft

resources:
  sessions: 2

sessions:
  s1: {autocommit: true, isolation_level: read_committed}
  s2: {autocommit: true, isolation_level: read_committed}

setup:
  - sql:
      session: s1
      statement: CREATE TABLE t1(id INT PRIMARY KEY, value INT)
  - sql:
      session: s1
      statement: INSERT INTO t1 VALUES(1,10)

steps:
  - sql:
      session: s1
      statement: BEGIN

  - sql:
      session: s1
      statement: |
        UPDATE t1 SET value=100 WHERE id=1

  - query:
      session: s2
      statement: |
        SELECT value FROM t1 WHERE id=1
      expect:
        order: exact
        rows:
          - [10]

  - sql:
      session: s1
      statement: COMMIT

  - query:
      session: s2
      statement: |
        SELECT value FROM t1 WHERE id=1
      expect:
        order: exact
        rows:
          - [100]

cleanup:
  - transaction:
      session: s1
      action: rollback
  - sql:
      session: s1
      statement: DROP TABLE t1
```

## 25. 安全原则

禁止：

```text
任意 Python eval
任意模板代码执行
任意 shell 字符串
隐式读取全部系统环境变量
```

动态能力必须白名单、类型化、可审计。

## 26. 并发、Session 与同步状态

Session 配置至少定义 autocommit、isolation_level、role、schema；未声明时用 Adapter 的已冻结默认配置并写入 Manifest，不依赖连接历史。
同一 Session 不能同时被多个分支执行；Compiler 检查静态冲突，Session Manager 在运行时也串行准入。
parallel 是结构化并发：子分支不得逃逸父 Step；第一个失败发出取消信号，随后等待有界退出并记录所有分支结论，不用“最后完成的分支”覆盖失败。
barrier 的 name 在当前 parallel 作用域有效；parties 为参与分支数，禁止单分支重复抵达凑数。未达齐即超时/取消时解除全部等待并报告失败。
signal 是 Attempt 内具名、粘性的单次事件；先 signal 后 wait_signal 不丢信号，重复 signal 幂等；新 Attempt 不继承信号状态。
wait_signal/condition/barrier 的时间上限都受 Case 剩余预算约束；condition Adapter 需定义参数 Schema、可观测状态和查询权限。
session_blocked 必须指定被观察 Session 和必要的阻塞者/对象过滤，不能只返回环境中“任意一个 Session 阻塞”。

## 27. Step 标识与 Expected Schema

Step 可以在动作同级声明 id；缺省按 AST 位置生成，例如 parallel-1/branch-tx1/sql-2。引用 coverage 或同步诊断的 Step 必须显式 id。
expect.rows 使用 11 的 JSON 兼容类型与 typed object；expect.columns 为列元数据声明列表，expect.comparison 为比较参数。
各列允许 logical_type、db_type、precision、scale、nullable；未声明字段不额外断言，声明即严格验证。列数、值类型默认仍严格。
浮点容差例：comparison.float_tolerance = {"0": {abs_tol: 0.000001, rel_tol: 0.0}}；索引为从 0 开始的列号，仅 exact 支持。
expect_error 中多个字段全部匹配，禁止把基础设施异常当数据库预期错误。未知动作和 condition 在 validate 阶段失败。

## 28. 资源、取消与版本

node/cluster/restore/script 动作有类型化最小资源与权限约束；Compiler 由动作推导最低要求，不允许 Metadata 将其降级为 non-destructive/parallel safe。
脚本白名单来自快照内的 Registry，声明是否 destructive、资源范围、幂等性、timeout 和输出 Schema；不把 path 白名单当作资源隔离本身。
script、Backup/Restore 路径属于已租赁资源，不得越界。target: primary 在动作前解析为明确 node_id 并记录，不能在重试中静默指向另一个节点。
取消优先停止 Step，再 Cleanup/Reset/Probe；无法确认旧进程/SQL 已终止时进入 QUARANTINED，禁止仅释放 Lease。
Setup/Steps 的 Case 总预算与清理独立预算见 11；Failure Type 和 Retry 统一使用 07/06。
1.0 与 1.1 按版本分派；新增严格并发/类型规则通过显式升级验证，不能静默改变历史文件结果。

YAML 解析使用 04 的 YAML 1.2 Core 规则；Session/Step 的字符串参数禁止隐式日期或布尔转换。transaction rollback 的清理语义由 Adapter 规范为“存在事务则回滚”，无事务时成功返回，避免完整示例 COMMIT 后清理误报。

## 29. Cancel / Barrier 极端场景验收（Phase 3）

framework_tests/scenario 构造三个显式同步的分支：A 开启事务并取得锁，B 经 condition 确认正在等待该锁，C 在独立 Barrier 等待中触发超时。B 的数据库阻塞由 condition 观察，不能靠 sleep 假定已经发生。
Barrier 的参与者配置必须在静态上合法，测试通过让另一个参与分支在抵达前受控延迟来触发超时；不能拿缺少合法参与者、理应被 Compiler 拒绝的脚本充当运行时取消测试。
父 parallel 收到第一个失败后传播取消，A 回滚、B 尝试 Driver cancel、所有 Session 执行 Reset/Probe，Case 在业务与清理预算内得到确定的终态；保留各分支错误，最终状态按 07 裁决。
若 B 的 SQL 无法确认停止，预期为资源隔离而非“全部释放成功”；Cleanup 失败将 Attempt 归为 ERROR/FIXTURE_CLEANUP，不能为了有界结束而提前复用污染资源。
另测 signal 先发后等、分支取消时 Barrier 解除、同 Session 并发使用被拒、清理本身超时，以及同一 Attempt 内并发请求不会被框架 Admission 当成两个独立 Case 互锁。
