# XG DB Test Case Catalog Design

> Catalog Version：2（架构 v1.1）

## 1. 目标

Case Catalog 解决：

```text
10万~50万 Case 下快速选择
避免每次全量扫描文件
增量编译
测试资产版本追踪
历史耗时关联
```

Catalog 不是测试资产事实源，事实源仍是 Git 中的：

```text
.xgt
.xgs.yaml
_suite.yaml
fixtures
```

Catalog 必须可随时重建。

---

## 2. MVP 实现

推荐：

```text
SQLite
```

路径：

```text
.xgtest/catalog.sqlite
```

原因：

- 无额外服务；
- 单文件；
- SQL 查询能力足够；
- 支持事务和索引；
- 十万到百万级元数据足够。

---

## 3. cases 表

```sql
CREATE TABLE cases (
    case_id               TEXT PRIMARY KEY,
    source_path           TEXT NOT NULL,
    source_type           TEXT NOT NULL,

    module                TEXT NOT NULL,
    feature               TEXT NOT NULL,
    subfeature            TEXT,
    scenario              TEXT,

    level                 TEXT NOT NULL,
    complexity            TEXT,

    status                TEXT NOT NULL CHECK(status IN ('generated','draft','review','active','deprecated','disabled')),
    title                 TEXT NOT NULL,
    issue                 TEXT,
    owner                 TEXT,
    disable_reason        TEXT,
    replaced_by_json      TEXT NOT NULL DEFAULT '[]',
    generated_by_json     TEXT,
    oracle_provenance_json TEXT,
    parallel              TEXT NOT NULL CHECK(parallel IN ('safe','restricted','exclusive')),
    retry_json            TEXT NOT NULL,
    reset_contract        TEXT,
    comparison_profile    TEXT NOT NULL,
    effective_metadata_json TEXT NOT NULL,
    source                TEXT NOT NULL,
    oracle                TEXT,

    since_version         TEXT,
    until_version         TEXT,

    execution_class       TEXT NOT NULL,
    isolation             TEXT NOT NULL,

    destructive           INTEGER NOT NULL DEFAULT 0,
    idempotency           TEXT NOT NULL,

    timeout_ms            INTEGER,
    estimated_duration_ms INTEGER,

    source_hash           TEXT NOT NULL,
    compiled_hash         TEXT NOT NULL,
    semantic_hash         TEXT NOT NULL,
    dependency_hash       TEXT NOT NULL,
    dirty                 INTEGER NOT NULL DEFAULT 0,
    canonical_version     TEXT NOT NULL,

    dsl_version           TEXT,
    metadata_version      TEXT,
    compiler_version      TEXT NOT NULL,
    git_commit            TEXT,

    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL
);
```

---

## 4. tags 表

```sql
CREATE TABLE case_tags (
    case_id TEXT NOT NULL,
    tag     TEXT NOT NULL,
    PRIMARY KEY(case_id, tag)
);
```

```sql
CREATE INDEX idx_case_tags_tag
ON case_tags(tag);
```

---

## 5. requirements 表

```sql
CREATE TABLE case_requirements (
    case_id     TEXT NOT NULL,
    req_type    TEXT NOT NULL,
    req_key     TEXT NOT NULL,
    req_value   TEXT NOT NULL DEFAULT '',
    PRIMARY KEY(case_id, req_type, req_key, req_value)
);
```

例如：

```text
capability / cluster.failover
os         / linux
arch       / x86_64
topology   / 3-node
```

---

## 6. resources 表

```sql
CREATE TABLE case_resources (
    case_id       TEXT PRIMARY KEY,
    sessions      INTEGER DEFAULT 0,
    schemas       INTEGER DEFAULT 0,
    databases     INTEGER DEFAULT 0,
    nodes         INTEGER DEFAULT 0,
    cluster_count INTEGER DEFAULT 0
);
```

---

## 7. fixtures 表

```sql
CREATE TABLE case_fixtures (
    case_id     TEXT NOT NULL,
    fixture_id  TEXT NOT NULL,
    PRIMARY KEY(case_id, fixture_id)
);
```

---

## 8. dependencies 表

未来可预留：

```sql
CREATE TABLE case_dependencies (
    case_id          TEXT NOT NULL,
    depends_on       TEXT NOT NULL,
    dependency_type  TEXT NOT NULL,
    PRIMARY KEY(case_id, depends_on)
);
```

MVP 不建议引入复杂 Case 间依赖。

---

## 9. file_state

用于增量编译：

```sql
CREATE TABLE file_state (
    path             TEXT PRIMARY KEY,
    size             INTEGER,
    mtime_ns         INTEGER,
    source_hash      TEXT,
    compiler_version TEXT,
    last_indexed_at  TEXT
);
```

流程：

```text
mtime/size 未变
→ 仅开发增量扫描可快速跳过；Release 仍核对内容哈希

发生变化
→ 计算 source_hash

hash 未变
→ reuse

hash 变化
→ recompile
```

---

## 10. suite_state

`_suite.yaml` 会影响整个子树：

```sql
CREATE TABLE suite_state (
    path         TEXT PRIMARY KEY,
    source_hash  TEXT NOT NULL,
    subtree_hash TEXT,
    updated_at   TEXT NOT NULL
);
```

Suite 变化时重新编译受影响子树。

---

## 11. catalog_meta

```sql
CREATE TABLE catalog_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

保存：

```text
catalog_version
compiler_version
repository_commit
generated_at
```

---

## 12. 推荐索引

```sql
CREATE INDEX idx_cases_module
ON cases(module);

CREATE INDEX idx_cases_feature
ON cases(feature);

CREATE INDEX idx_cases_module_feature
ON cases(module, feature);

CREATE INDEX idx_cases_level
ON cases(level);

CREATE INDEX idx_cases_execution_class
ON cases(execution_class);

CREATE INDEX idx_cases_destructive
ON cases(destructive);
```

---

## 13. Selector 查询示例

`--feature join`：

```sql
SELECT case_id, source_path
FROM cases
WHERE feature = 'join' AND status = 'active';
```

JOIN + UNION + P0/P1：

```sql
SELECT case_id, source_path
FROM cases
WHERE feature IN ('join','union')
  AND level IN ('P0','P1') AND status = 'active';
```

---

## 14. Tag 查询

```sql
SELECT c.case_id, c.source_path
FROM cases c
JOIN case_tags t
  ON t.case_id = c.case_id
WHERE t.tag = 'regression' AND c.status = 'active';
```

---

## 15. Catalog Builder

```text
Discover Files
   ↓
Detect Changed Files
   ↓
Resolve Suite Inheritance
   ↓
Parse DSL
   ↓
Validate Metadata
   ↓
Compile Unified Case
   ↓
Write Catalog Transaction
```

先在暂存区编译全部受影响 Case，再在一个短写事务中提交新目录版本、索引与文件状态。整个对外可见的 Index 更新必须事务化。

编译失败时不能留下“半新半旧”的 Catalog。

---

## 16. 删除文件

发现源文件被删除，应同一事务删除：

```text
cases
tags
requirements
resources
fixtures
file_state
case_coverage_claims
case_inputs
case_dependencies
```

必须清理所有引用已删除 Case 的记录；源路径相同但 ID 改变也按旧 ID 删除、新 ID 插入处理。

---

## 17. Case ID 冲突

两个源文件定义同一个 Case ID：

```text
Catalog Build 必须失败
```

禁止 last-write-wins。

---

## 18. Source Traceability

每条 Case 必须保存：

```text
source_path
source_hash
compiled_hash
git_commit
dsl_version
compiler_version
```

Result 记录 `compiled_hash`，保证历史结果可追溯。

---

## 19. Compiled Cache

后续可增加：

```text
.xgtest/cache/<compiled_hash>.msgpack
```

MVP 必须执行由规划快照生成的 Bundle。允许生成 Bundle 时仅 Parse 选中 Case，但必须核对源文件及全部依赖指纹；索引后的工作区变化必须重新规划，不能静默执行新内容。

---

## 20. Catalog Distribution

多 Agent 时推荐长期方案：

```text
Controller
→ 从 Catalog 选择
→ 生成 Compiled Case Bundle
→ Shard 下发 Agent
```

这样 Agent 不依赖共享文件系统。

---

## 21. Secrets

Catalog 禁止保存：

```text
password
token
private key
```

Credential 由独立 Secret Provider 注入。

---

## 22. 性能目标

建议目标：

```text
100,000 cases
按 module/feature/level/tag 筛选
< 1s~数秒级
```

具体以真实 Benchmark 为准。

---

## 23. 全量重建

必须支持：

```bash
xgtest index --rebuild
```

因为 Catalog 永远是派生物。

---

## 24. Catalog Version

当 `catalog_version` 不兼容时：

```text
明确提示 rebuild
```

禁止静默读取不兼容 Schema。

---

## 25. 覆盖、依赖和查询索引

```sql
CREATE TABLE case_coverage_claims (
    case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    claim_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    model_version TEXT NOT NULL,
    model_hash TEXT NOT NULL,
    assignment_json TEXT NOT NULL,
    assertion_refs_json TEXT NOT NULL,
    claim_hash TEXT NOT NULL,
    PRIMARY KEY(case_id, claim_id)
);
CREATE TABLE case_inputs (
    case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    input_path TEXT NOT NULL,
    input_kind TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    PRIMARY KEY(case_id, input_path, input_kind)
);
CREATE INDEX idx_cases_status_level ON cases(status, level);
CREATE INDEX idx_cases_issue ON cases(issue);
CREATE INDEX idx_cases_source ON cases(source);
CREATE INDEX idx_claim_model ON case_coverage_claims(model_id, model_version);
CREATE INDEX idx_inputs_path ON case_inputs(input_path);
```

case_inputs 包含源文件、父级 Suite、Global Defaults、Fixture、脚本、Registry、Model/Constraint 和比较策略。编译器/插件版本使用稳定的虚拟输入键。
模型点集合由模型哈希与策略决定；case_coverage_claims 存声明，Coverage Engine 派生并去重点集合，不把重复 Case 数量当覆盖数。

## 26. 一致性与快照

catalog_meta 保存 catalog_version=2、snapshot_id、dependency_root_hash、repository_commit、dirty、generated_at。
每次连接启用外键；现有 case_tags/requirements/resources/fixtures/dependencies 也必须使用外键或在同一事务显式清理。req_value 使用非空规范字符串，不用 NULL 表示集合成员。
增量构建和全量构建必须生成相同有效 Case 与语义哈希集合。大小/时间戳不能作为 Release 内容身份。
全局注册表、默认值或编译器改变时，从依赖反向索引失效；删除 Fixture 或脚本不得复用旧编译结果。
Catalog 1 不兼容，必须 rebuild 为 2；Result 历史不随 rebuild 改写。完整契约见 [11](11_Execution_Consistency_and_Validation_Contract.md)。

## 27. Catalog Verify（Phase 1）

```bash
xgtest catalog verify
```

该命令只读，使用与 Compiler 相同的 contract_set_id、模型、继承和哈希函数，对 Catalog 所引用的资产快照做一致性验证，不连接被测数据库，也不自动 rebuild 或修复。

| 检查 | 必须发现的问题 |
|---|---|
| identity / references | 重复 Case ID、主键/外键损坏、悬空 Fixture/依赖/断言引用 |
| effective_metadata | 索引列及 tags/resources/requirements 与有效 Metadata 不一致 |
| dependency | case_inputs 内容、dependency_hash、Suite/全局继承结果不一致 |
| compiled / semantic | Bundle 内容与 compiled_hash、重新计算的 semantic_hash 不一致 |
| coverage | 模型版本/hash、约束、assertion_refs 或 coverage_review 不一致 |
| snapshot | Registry/Schema/Compiler 版本、catalog snapshot 与资产来源不一致 |

默认核对 Catalog 绑定的不可变快照；显式 `--workspace` 可额外检查当前工作区漂移，不能用工作区的新文件代替旧输入后宣称旧 Catalog 损坏。
结果为 VALID / CORRUPT / STALE / UNVERIFIABLE，附 Case ID、字段、期望/实际哈希和来源。CORRUPT 是内部矛盾，STALE 是指定工作区已变化，UNVERIFIABLE 是缺旧快照或所需工具版本；不得把无法验证当通过。
存在多类问题时逐项报告，整体以 CORRUPT > UNVERIFIABLE > STALE > VALID 排序；仅 VALID 返回成功。规划针对本次冻结快照验证，无需网络连接或全局服务。

## 28. 增量与重建等价验收

framework_tests/contract 和集成验证构造同一资产快照，分别增量 index 与全量 rebuild，比较按 Case ID 规范化的有效 Metadata、依赖、Coverage Claim/Review 与内容哈希；不比较 SQLite 文件字节、物理行序、created_at 等生成时间。
至少覆盖源文件修改、保持 mtime/size 的内容修改、Suite 扇出、Fixture/模型/Registry 变化、文件删除、改 ID、重复 ID 和索引中途失败。失败不得提交半新半旧索引。
Catalog Verify 与编译共用函数可减少漂移，但不能独立证明该函数正确；必须加入人工审定输入和预期值，不能只让两个相同错误实现相互印证。
