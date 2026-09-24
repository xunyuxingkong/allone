# Admission Conflict Rules v0.1

`src/xgtest/core/admission.py` 提供纯函数 `evaluate_admission`，用于本地规划时判断两组 `ResourceRequest` 是否存在访问模式冲突。它不授予执行权。

当前支持同一 `resource_id`、直接父子 `parent_identity`、`shared_read` / `shared_write` / `exclusive` 对称矩阵，以及同一 Attempt 的 `same_owner` 豁免。不同所有者只有 READ/READ 可以共享重叠资源。输出包含冲突资源、模式和原因。

v0.1 不遍历多级祖先，不合并资源别名或跨分支影响边，不计算 `quantity` / capacity，不提供原子预留、持久化 Lease、Fencing、跨进程锁或 Cluster Drain。调用方不得仅凭 `allowed=True` 启动并发任务；正式执行权仍需后续 Resource Admission Engine 在权威状态中原子授予。

边界测试明确记录：祖父资源与孙资源目前不会自动判为重叠，READ/READ 即使 `quantity` 累计超容量也会返回允许。这些结果表示 v0.1 不支持该场景，不能用于生产准入。
