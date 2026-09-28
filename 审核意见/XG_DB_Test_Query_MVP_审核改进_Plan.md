# XG DB Test Query MVP 审核问题、优化方案与前端实现方案

> 审核基线：`main@927d883c669735c4192183d98d51b18782eb72be`  
> 最新提交：`feat: implement single machine query MVP`  
> 目标：在当前单机 Query MVP 基础上，收口剩余质量问题，并增加轻量可视化前端，同时保持与 XG DB Test 总体架构一致。

---

# 1. 总体审核结论

当前 Query MVP 已经形成完整的纵向链路：

```text
Query Case
  ↓
Strict Loader
  ↓
Typed QueryCaseInput
  ↓
Single Target QueryRunner
  ↓
XuguSession
  ↓
Driver Type Mapping
  ↓
XGC1 Canonical
  ↓
Comparator
  ↓
QueryRunReport
  ↓
JSON Result
```

已落地的关键能力包括：

- Query 专用 Contract；
- Typed Expected；
- Query Loader；
- 单 Target 顺序 Runner；
- Xugu Adapter；
- Driver Type Mapping；
- `mapping_fidelity / canonical_encoding / support_status`；
- XGC1 Canonical；
- `exact / rowsort / sha256 / expected_error`；
- Query Result Schema；
- Query CLI；
- 约 30 条只读 Query Case；
- Contract Descriptor；
- Candidate Descriptor stale check；
- Runtime Profile；
- 仓库记录的 113 个 Framework Tests 通过。

当前代码已经不是 Demo，可视为“可用的单机 Query MVP”。整体实现质量约 **8.7～9.0 / 10**。

---

# 2. 已完成且建议保持的设计

## 2.1 Contract Descriptor

当前 Contract Identity 已覆盖：

```text
src/xgtest/core/
src/xgtest/query/
src/xgtest/runtime/profile.py
src/xgtest/runtime/comparator.py
src/xgtest/adapter/xugu.py
registry/
schemas/
framework_tests/contract/
```

这样 Comparator、Profile、Adapter、Query Core 行为发生变化时，`contract_set_id` 会变化。该方案正确。

## 2.2 Candidate stale check

当前已有：

```python
test_committed_candidate_matches_current_contract()
```

可以保证：

```text
Contract 改动
→ candidate JSON 未更新
→ 测试失败
```

这一项已经收口。

## 2.3 Driver 类型证据模型

当前已把原来容易混淆的单一兼容状态拆成：

```text
mapping_fidelity:
  EXACT / LOSSY / AMBIGUOUS / UNKNOWN

canonical_encoding:
  VERIFIED / FAILED / UNKNOWN

support_status:
  SUPPORTED / UNSUPPORTED
```

这是正确方向，应继续沿用。

## 2.4 Query 专用 Contract

当前已有：

```text
QueryStep
QueryCaseInput
QueryStepReport
QueryCaseReport
QueryTargetReport
QueryRunReport
```

Query MVP 已明确只接受：

```text
kind = query
```

不再把 Setup / Statement / Cleanup 混入 Query 主链路，职责清晰。

## 2.5 Loader / Runner 解耦

当前：

```text
YAML
→ Loader
→ QueryCaseInput
→ Runner
```

Runner 不直接消费原始 YAML dict，这一点应保持。

---

# 3. 当前问题总表

| 优先级 | 问题 | 影响 | 优化方向 |
|---|---|---|---|
| P0 | Query timeout 只有 Metadata，没有真实执行控制 | SQL/Driver 卡死可能无限挂住 | 实现真实 timeout + Connection Dispose |
| P0 | 缺少真实 Xugu Query MVP 固定验收制品 | 单测可信，但真实 DB 闭环证据不足 | 全量执行只读 Query Case 并保存 Acceptance Artifact |
| P1 | Result 缺少 Git / Source 追溯字段 | 历史结果无法还原当时 SQL | 增加 git_commit/source_file/case_source_hash |
| P1 | Runtime Profile 仍可选 | 正式 Regression 可能依赖静态 whitelist | 增加 diagnostic / regression 双模式 |
| P1 | 缺少 Run History Index | 前端历史查询困难 | 增加 Result History + Reader |
| P1 | `run_step()` 类型标注与实际返回不一致 | 可维护性与静态检查下降 | 修正返回类型 |
| P1 | 局部仍使用 FailureType 字符串 | 容易枚举漂移 | 全程使用 FailureType enum |
| P1 | 最新 MVP 提交过大 | Review/回滚/定位不方便 | 后续恢复小步提交 |
| P1 | 尚无正式 Web API | UI 直接读文件会耦合 | 增加 FastAPI Read-only API |
| P2 | CLI 使用门槛高 | 不利于团队推广 | 增加 Read-only Dashboard |
| P2 | Allure/JUnit 尚未正式接入 Query MVP | CI/报告生态不足 | MVP 后增加 Reporter |
| P2 | rowsort 大结果仍受内存限制 | 超大集合无法比较 | 后续 External Sort |
| P2 | host_hash 使用普通 SHA256 | 小枚举空间可能被猜测 | 后续改 HMAC/匿名 Target ID |

---

# 4. P0-01：实现真实 Query Timeout

## 4.1 问题

Case 中虽然存在：

```yaml
timeout: 30s
```

但当前 QueryRunner 并没有真正根据该字段终止阻塞 SQL。

可能出现：

```text
SQL 卡住
网络异常
Driver 阻塞
锁等待
数据库内部 Bug
→ Runner 长时间无法退出
```

对未来 Web UI 尤其危险。

## 4.2 目标行为

```text
Step 开始
  ↓
超过 timeout
  ↓
TIMEOUT
  ↓
尝试 cancel
  ↓
cancel 不可靠则废弃 Connection
  ↓
后续 Case 新建 Connection
```

超时后的 Session 禁止重新进入连接池或被后续 Case 复用。

## 4.3 推荐实现

新增：

```text
src/xgtest/query/timeout.py
```

定义：

```python
class QueryTimeoutError(TimeoutError):
    pass
```

长期可靠方案建议采用 **独立 Worker Process**：

```text
Parent Process
    ↓
Worker Process
    ↓
xgcondb.execute/query
```

超时时：

```text
Parent
→ terminate Worker
→ Connection 随进程一起废弃
```

原因是 Python Thread 无法可靠杀死正在阻塞的原生 Driver 调用。

如果短期使用 `signal.alarm`，只能视为 Linux 主线程上的临时方案。

## 4.4 Result 模型

建议增加独立：

```text
TIMEOUT
```

不要把 Timeout 全部折叠成 ERROR。

## 4.5 验收

新增测试：

```text
快速 SQL 不超时
慢 SQL 正确 TIMEOUT
超时后 Connection 不复用
后续 Case 可继续执行
Timeout Result 正确写入
```

---

# 5. P0-02：真实 Xugu Query MVP 验收

## 5.1 当前不足

仓库记录：

```text
113 framework tests passed
```

主要证明：

```text
Model
Loader
Comparator
Mock Runner
Schema
Contract
```

已经较可信。

但仍应补：

```text
真实 Xugu
+
当前全部 Query Case
+
固定验收证据
```

## 5.2 当前优势

Query Case 已基本改成只读 SQL，因此数据库即使当前处于只读状态，也可以跑 Query MVP。

## 5.3 建议验收制品

```text
artifacts/acceptance/query-mvp/
├── acceptance.json
├── runtime-profile.json
├── environment.json
└── framework-tests.txt
```

`acceptance.json` 建议：

```json
{
  "git_commit": "...",
  "contract_set_id": "...",
  "runtime_profile_id": "...",
  "database_version": "...",
  "driver_version": "...",
  "case_count": 30,
  "pass": 30,
  "fail": 0,
  "error": 0,
  "timeout": 0,
  "started_at": "...",
  "finished_at": "..."
}
```

## 5.4 MVP Gate

正式打版本前要求：

```text
Query Validate PASS
Framework Tests PASS
Registry Validate PASS
Schema Verify PASS
Contract Verify PASS
Runtime Profile Validate PASS
Real Xugu Query Run PASS
```

---

# 6. P1-01：增强 Result 可追溯性

## 6.1 当前问题

Result 已有：

```text
run_id
contract_set_id
runtime_profile_id
case_id
status
duration
types
row_count
result_sha256
error
```

但缺少：

```text
git_commit
source_file
case_source_hash
```

如果同一个 Case ID 后续修改 SQL，历史 Result 将无法准确对应当时执行内容。

## 6.2 建议字段

`QueryRunReport`：

```python
git_commit: str | None
```

`QueryCaseReport`：

```python
source_file: str | None
case_source_hash: str
```

## 6.3 Hash

建议：

```text
SHA256(normalized UTF8/LF source bytes)
```

这样 Windows / Linux 一致。

## 6.4 最终效果

```text
历史 Result
→ git_commit
→ source_file
→ source_hash
→ 精确恢复当时测试资产
```

这是未来 Baseline、Delta、Web UI 和缺陷复盘的重要基础。

---

# 7. P1-02：Runtime Profile 双模式

## Diagnostic Mode

```text
runtime_profile optional
```

适用于：

```text
开发
Driver 探测
临时验证
```

## Regression Mode

```text
runtime_profile required
```

必须验证：

```text
Database/Target
Driver Version
Runtime Profile ID
Contract Set ID
Type Support
```

建议 CLI：

```bash
xgtest query run --mode diagnostic
```

正式回归：

```bash
xgtest query run \
  --mode regression \
  --runtime-profile ...
```

正式场景建议默认 `regression`。

---

# 8. P1-03：增加 Result History

## 8.1 当前问题

只有单次 JSON 输出时，前端难以实现历史 Run 与趋势。

## 8.2 推荐目录

```text
artifacts/runs/
├── index.json
├── 20260924_001.json
├── 20260924_002.json
└── 20260925_001.json
```

## 8.3 Index

```json
[
  {
    "run_id": "...",
    "started_at": "...",
    "status": "PASS",
    "case_count": 30,
    "pass": 30,
    "fail": 0,
    "error": 0,
    "timeout": 0,
    "duration_ms": 1280
  }
]
```

## 8.4 Reader

新增：

```text
src/xgtest/query/history.py
```

接口：

```python
list_runs()
get_run(run_id)
get_case(run_id, case_id)
```

前端/API 通过 Reader 查询，不直接操作文件系统。

---

# 9. P1-04：代码细节修复

## 9.1 run_step 返回类型

当前若实际返回：

```python
(QueryStepReport, failure_type)
```

则类型应明确为：

```python
tuple[QueryStepReport, FailureType | None]
```

## 9.2 FailureType 强类型

尽量避免：

```python
failure_type = "ASSERTION_FAILED"
```

改成：

```python
FailureType.ASSERTION_FAILED
```

## 9.3 控制 Runner 职责

不要继续把以下逻辑全部塞进 `runner.py`：

```text
timeout
history
API
report rendering
```

推荐：

```text
query/
├── loader.py
├── runner.py
├── timeout.py
├── history.py
├── result.py
└── service.py
```

---

# 10. P1-05：Git 提交粒度

本次 MVP 大提交同时包含：

```text
Contract
Driver Mapping
Model
Loader
Runner
Result
CLI
Case
Docs
Schema
Tests
```

后续建议恢复：

```text
一个问题
+
一个实现目标
+
一组测试
+
一个 commit
```

例如：

```text
fix: add isolated query timeout handling
feat: persist query run history
feat: add read only result API
feat: add query dashboard
```

---

# 11. P2：大结果比较优化

当前：

```text
MAX_MATERIALIZED_QUERY_ROWS = 10_000
```

对 MVP 是合理的。

未来如果需要 rowsort 处理大结果，可增加：

```text
Query Stream
  ↓
Canonical Row Frame
  ↓
Chunk Sort
  ↓
Temp Files
  ↓
Merge Sort
  ↓
Compare
```

即 External Sort。

当前不作为 MVP 阻塞项。

---

# 12. 原总架构中的 Web UI / Dashboard

可视化并不是后来新增的方向。

原总架构已经明确设计：

```text
Web UI
Dashboard
Allure
```

总体原则是：

```text
Web UI 不成为核心逻辑层
```

UI 只调用 Core API：

```text
Feature
Coverage
Case Catalog
Selector
Test Plan
Run
Result
Baseline
Environment
```

禁止：

```text
UI 自己实现 Selector
UI 自己实现 Scheduler
UI 自己判断测试 PASS/FAIL
UI 自己重新计算 Coverage
```

原完整架构 Phase 6 也明确包含：

```text
Result DB
Baseline / Delta
Failure Signature
Flaky
Coverage History
Quality Gate
API
Dashboard
Allure
```

核心规则：

```text
展示层不重新计算核心语义
```

---

# 13. 为什么现在适合开始做前端

以前不建议早做 Web UI，是因为：

```text
Result Model 不稳定
Runner 不稳定
Contract 不稳定
```

现在已经具备：

```text
QueryRunReport
QueryCaseReport
QueryStepReport
Runtime Profile
Contract Set ID
Typed Status
```

所以当前很适合增加：

```text
Read-only Query MVP Dashboard
```

但不适合直接做成完整 TCMS 或复杂测试管理平台。

---

# 14. 前端 MVP 范围

第一版只做：

```text
Dashboard
Run History
Run Detail
Case Result
Case Detail
Runtime / Contract
Type Support
```

暂不做：

```text
用户体系
复杂 RBAC
Case 在线编辑
Test Plan 编辑
拖拽工作流
Agent 控制
Scheduler
多集群控制
Coverage 编辑
Baseline 审批
完整 TCMS
```

---

# 15. 前端技术架构

```text
                       Browser
                          │
                          ▼
                    Vue Frontend
                          │
                          ▼
                     FastAPI API
                          │
       ┌──────────────────┼──────────────────┐
       ▼                  ▼                  ▼
 Query History        Query Cases        Runtime Info
       │                  │                  │
       └──────────────────┴──────────────────┘
                          │
                     XG Test Core
                          │
                ┌─────────┴─────────┐
                ▼                   ▼
            QueryRunner         Result Reader
                │
                ▼
               Xugu
```

关键原则：

```text
FastAPI 只是包装现有 Core
```

不能再写一套：

```text
cursor.execute
compare
status 判定
```

---

# 16. 推荐技术栈

## Backend

```text
FastAPI
Pydantic
Uvicorn
```

优点：

- 当前 Python Core 可直接复用；
- Pydantic Model 可直接作为 API Response；
- 自动生成 OpenAPI；
- 后续 TypeScript 类型生成方便。

## Frontend

```text
Vue 3
TypeScript
Vite
Element Plus
ECharts
Pinia
Vue Router
```

该项目未来主要是：

```text
表格
筛选
状态
Dashboard
日志
Coverage
历史趋势
```

Vue 很适合这种测试管理/后台平台形态。

---

# 17. Web Backend 目录

```text
src/xgtest/web/
├── __init__.py
├── app.py
├── api/
│   ├── health.py
│   ├── runs.py
│   ├── cases.py
│   └── runtime.py
├── service/
│   ├── run_service.py
│   ├── case_service.py
│   └── runtime_service.py
└── schemas/
```

`service` 只能调用：

```text
query/history.py
query/loader.py
query/runner.py
runtime/profile.py
core/contract_set.py
```

---

# 18. API 设计

## Health

```http
GET /api/health
```

## Run List

```http
GET /api/runs
```

支持：

```text
status
date
limit
offset
```

## Run Detail

```http
GET /api/runs/{run_id}
```

## Run Cases

```http
GET /api/runs/{run_id}/cases
```

支持：

```text
status
feature
case_id
failure_type
```

## Case Detail

```http
GET /api/runs/{run_id}/cases/{case_id}
```

## Runtime Profile

```http
GET /api/runtime/profile
```

## Contract

```http
GET /api/runtime/contract
```

## Type Support

```http
GET /api/runtime/types
```

---

# 19. Dashboard 首页

展示：

```text
Latest Run
Database Alias
Runtime Profile ID
Contract Set ID

Total
PASS
FAIL
ERROR
TIMEOUT

Pass Rate
Duration
Start Time
```

建议组件：

```text
Status Cards
Status Distribution
Failure Summary
Slowest Cases
Recent Runs
```

---

# 20. Run History 页面

字段：

| 字段 |
|---|
| Run ID |
| Time |
| Database |
| Git Commit |
| Total |
| Pass |
| Fail |
| Error |
| Timeout |
| Duration |

支持：

```text
分页
时间筛选
状态筛选
```

---

# 21. Run Detail / Case Result

列表建议：

| Case ID | Feature | Status | Duration | Failure Type |
|---|---|---|---:|---|
| QUERY.BASIC_01 | basic | PASS | 7 ms | - |
| QUERY.JOIN_01 | join | PASS | 14 ms | - |
| QUERY.STRING_04 | string | FAIL | 10 ms | ASSERTION_FAILED |

支持：

```text
Case 搜索
Feature 筛选
Status 筛选
Failure Type 筛选
耗时排序
```

---

# 22. Case Detail

展示：

```text
Case ID
Title
Feature
Tags

Git Commit
Source File
Source Hash

SQL

Comparison Mode
Expected

Columns
Driver Types
Logical Types
Row Count
Result SHA256

Status
Failure Type
Duration

Error Type
Error Code
SQLSTATE
Error Message
```

因此前面提出的：

```text
git_commit
source_file
case_source_hash
```

是前端前非常值得补的字段。

---

# 23. Runtime / Contract 页面

展示：

```text
Database Product
Database Version
Driver Name
Driver Version
Python Version
OS / Arch

Runtime Profile ID
Contract Set ID
Evidence Hash
```

类型矩阵：

| Driver Type | Logical Type | Fidelity | Canonical | Support |
|---|---|---|---|---|
| INTEGER | int | EXACT | VERIFIED | SUPPORTED |
| VARCHAR | string | EXACT | VERIFIED | SUPPORTED |
| NUMERIC | decimal | LOSSY | FAILED | UNSUPPORTED |
| TIMESTAMP | timestamp | AMBIGUOUS | FAILED | UNSUPPORTED |
| BINARY | bytes/string | LOSSY | VERIFIED | UNSUPPORTED |

---

# 24. 第一版前端必须只读

当前第一阶段建议只做：

```text
Read-only Dashboard
```

暂时不要开放：

```text
Run
Stop
Cancel
Rerun
```

原因是：

```text
真实 timeout
cancel proof
connection dispose
```

尚未完全收口。

---

# 25. 第二阶段增加在线执行

完成 Timeout 后再增加：

```http
POST /api/runs
```

请求示例：

```json
{
  "filter": {
    "feature": ["query"]
  }
}
```

API 不同步等待测试全部结束。

建议：

```text
POST /api/runs
  ↓
Create Run
  ↓
Background Worker
  ↓
QueryRunner
  ↓
Result
```

立即返回：

```text
202 Accepted
```

前端再轮询：

```http
GET /api/runs/{run_id}
```

---

# 26. UI 与 Core 的永久边界

必须长期保持：

```text
Core = Truth
API  = Query/Projection Boundary
UI   = Display
```

例如：

错误：

```text
前端根据 HTTP Code 判断 PASS/FAIL
```

正确：

```text
Core Result.status
→ API
→ UI 展示
```

错误：

```text
前端重新计算 Coverage
```

正确：

```text
Coverage Engine
→ API
→ UI 展示
```

Baseline / Delta / Quality Gate 同理。

---

# 27. 前端目录建议

```text
webui/
├── src/
│   ├── api/
│   │   ├── runs.ts
│   │   ├── cases.ts
│   │   └── runtime.ts
│   ├── views/
│   │   ├── Dashboard.vue
│   │   ├── RunList.vue
│   │   ├── RunDetail.vue
│   │   ├── CaseDetail.vue
│   │   └── Runtime.vue
│   ├── components/
│   │   ├── StatusTag.vue
│   │   ├── StatCard.vue
│   │   ├── CaseTable.vue
│   │   ├── TypeSupportTable.vue
│   │   └── SqlViewer.vue
│   ├── stores/
│   ├── router/
│   └── main.ts
├── package.json
└── vite.config.ts
```

路由：

```text
/
→ Dashboard

/runs
→ Run History

/runs/:runId
→ Run Detail

/runs/:runId/cases/:caseId
→ Case Detail

/runtime
→ Runtime / Contract
```

---

# 28. 安全要求

Result/API/UI 禁止出现：

```text
password
token
private key
connection secret
```

默认展示：

```text
database_alias
host_hash
```

而不是数据库明文密码等敏感信息。

第一版 Web 服务建议只监听：

```text
localhost / 内网
```

公网或跨团队开放后再建设：

```text
认证
RBAC
TLS
审计日志
CORS
```

---

# 29. UI MVP DoD

## Backend

- [x] FastAPI 可启动；
- [x] `/api/health`；
- [x] `/api/runs`；
- [x] `/api/runs/{run_id}`；
- [x] `/api/runs/{run_id}/cases`；
- [x] `/api/runs/{run_id}/cases/{case_id}`；
- [x] `/api/runtime/profile`；
- [x] `/api/runtime/contract`；
- [x] `/api/runtime/types`；
- [x] API 无 Secret。

## Frontend

- [x] Dashboard；
- [x] Run History；
- [x] Run Detail；
- [x] Case Detail；
- [x] Runtime / Type Support；
- [x] Status 筛选；
- [x] Feature 筛选；
- [x] Failure Type 筛选；
- [x] 错误详情；
- [x] 响应式布局。

---

# 30. Query MVP 正式 DoD

## Core

- [x] Contract Descriptor；
- [x] Candidate stale check；
- [x] Runtime Profile；
- [x] Driver Type Support；
- [x] Query Contract；
- [x] Loader；
- [x] Runner；
- [ ] 真正 Timeout；
- [x] Exact；
- [x] RowSort；
- [x] SHA256；
- [x] Expected Error；
- [x] Result Schema；
- [ ] Run History；
- [ ] Git/Source Provenance。

## Validation

- [x] Framework Tests 仓库记录通过；
- [ ] Real Xugu Query Case 固定验收制品；
- [x] Registry / Schema 基础校验；
- [x] Contract Verify 基础机制；
- [x] Runtime Profile 基础机制。

## UI

- [x] Read-only API；
- [x] Dashboard；
- [x] Run History；
- [x] Case Detail；
- [x] Runtime / Type Support。

---

# 31. 推荐后续 Commit 顺序

建议严格按以下顺序推进：

```text
1. fix: implement isolated query timeout handling

2. test: record real Xugu query MVP acceptance evidence

3. feat: add git and source provenance to query reports

4. feat: persist query run history index

5. refactor: tighten query runner typing and failure enums

6. feat: add read only query result API

7. feat: add query MVP dashboard

8. feat: expose runtime profile and type support views

9. feat: add async web run control after timeout proof

10. chore: tag v0.1.0-query-mvp
```

---

# 32. 实施阶段建议

## Stage A：收口 Query MVP

```text
Timeout
→ Real Xugu Acceptance
→ Provenance
→ History
```

完成后，Core 基本可以认为是：

```text
v0.1 Core Ready
```

## Stage B：只读前端

```text
FastAPI
→ Result API
→ Runtime API
→ Vue Dashboard
→ Case Detail
```

## Stage C：在线执行

前提：

```text
Timeout / Cancel / Connection Dispose 已验证
```

然后：

```text
POST Run
→ Background Worker
→ Run Status
→ UI Refresh
```

## Stage D：回到完整主线

继续原架构：

```text
XGT Parser
→ Metadata Resolver
→ Compiler
→ Catalog2
→ Selector
→ TestPlan
```

再之后：

```text
Agent
Scheduler
Multi Cluster
Lease/Fencing
Result DB
Baseline/Delta
Quality Gate
```

---

# 33. 最终建议

当前项目已经从：

```text
设计型框架
```

进入：

```text
真正能运行的 Query MVP
```

接下来最值得投入的不是继续扩大 Core 功能范围，而是完成：

```text
正确退出
+
真实验收
+
结果可追溯
+
历史可查询
+
结果可展示
```

即：

```text
Timeout
+ Real Acceptance
+ Provenance
+ History
+ Read-only Dashboard
```

完成这五项后，项目会从：

```text
“有 CLI 的 Query 测试程序”
```

升级为：

```text
“具备实际团队使用体验的数据库 Query 测试工具”
```

同时保持原总架构原则：

```text
Core 是事实源
API 是查询边界
UI 是展示层
```

这也是当前阶段最稳妥、投入产出比最高的演进路线。
