# XGT DSL Specification

> SQL 类确定性测试 DSL · 扩展名 .xgt · DSL Version：1.1
>
> 1.1 显式定义块边界和类型化 Expected；不修改 1.0 的既有语义。历史文件须使用独立 1.0 Parser 或经显式转换与 Review 后升级。

## 1. 范围与结构

适用于 Query、DDL、DML、Datatype、Function、Index、Partition、View、Sequence、Privilege SQL、简单 Procedure/Trigger。
多 Session、HA、Backup/Restore 和节点动作使用 Scenario DSL。MVP 一个文件一个 Case。
结构为 Metadata Header、条件指令、Setup/Statement/Query、Cleanup；统一 UTF-8，推荐 LF，兼容 CRLF。

## 2. 完整示例

下面的 Case 假定父级 Suite 已给出 module/feature/level、资源和默认 Metadata；合并后按 04 校验。status=draft 可通过静态校验，但不会进入正式 Release。

```text
# xg:dsl_version 1.1
# xg:metadata_version 1.1
# xg:id QUERY.JOIN.INNER.000001
# xg:title Inner Join 基本等值连接
# xg:module query
# xg:feature join
# xg:subfeature inner_join
# xg:level P0
# xg:status draft
# xg:execution_class fast
# xg:isolation worker_schema
# xg:idempotency conditional
# xg:reset_contract worker_schema_clean
# xg:destructive false

setup id=setup-tables
CREATE TABLE t1(id INT, name VARCHAR(20));
@end-sql

statement ok id=insert-t1
INSERT INTO t1 VALUES(1,'A'),(2,'B'),(3,'C');
@end-sql

statement ok id=create-t2
CREATE TABLE t2(id INT);
@end-sql

statement ok id=insert-t2
INSERT INTO t2 VALUES(1),(2);
@end-sql

query rowsort id=query-rows
SELECT t1.id,t1.name FROM t1 INNER JOIN t2 ON t1.id=t2.id;
@end-sql
----
[1, "A"]
[2, "B"]
@end-expect

cleanup id=drop-t2
DROP TABLE t2;
@end-sql

cleanup id=drop-t1
DROP TABLE t1;
@end-sql
```

该例验证 INNER JOIN 保留匹配行并排除 t1 中未匹配的第 3 行；正式 active 样板还需提交 coverage 声明和 Oracle/Review 证据。

## 3. Header、注释与复杂 Metadata

块外 `# comment` 为普通注释；Header 使用 `# xg:key value`。
标量按 04 的字段类型解析；list/object 使用严格单行 JSON，禁止 eval：

```text
# xg:tags ["join", "regression"]
# xg:retry {"max_attempts":2,"on":["INFRA_NETWORK"]}
```

只允许 Header 声明 Metadata，不能在 SQL/Expected 内注入覆盖。重复键和未知键报错。
Header 与 Suite 的合并规则、status/source/Oracle/coverage 字段均以 04 为准。
SQL 块内除显式终止符外全部是 SQL 原文，不把 #、statement、query 或 cleanup 当 DSL 指令。

## 4. 块语法和边界

```text
statement ok [id=<step_id>]
statement error [id=<step_id>]
query exact|rowsort|valuesort [id=<step_id>]
query hash exact|rowsort [id=<step_id>]
setup [id=<step_id>]
cleanup [id=<step_id>]
```

每个 SQL 块以独占一行、从第 1 列开始的 `@end-sql` 结束。一个块包含一条 Driver 可执行语句，允许 Procedure/Trigger 内部分号；不按分号切 SQL。
SQL 中需要字面终止符行时，在该行前加反斜线转义；以反斜线开头的原始行也加一层反斜线。解析器只移除这一个转义前缀，不做 SQL 字符串转义。
需要 Expected 的块在 @end-sql 后必须跟独占行 `----`，直到独占行 `@end-expect`。缺失终止符在静态校验时失败。
未知块外内容、Case SQL 块零条或多条 Driver 语句均拒绝；多语句识别由方言词法校验负责，不能用全局 split(';')。
显式 id 在 Case 内唯一；省略时 Compiler 按稳定 AST 位置生成 sql-1/query-2 等 ID。coverage 引用的断言必须使用显式 id，避免增删步骤导致引用错位。

## 5. Statement 和 Expected Error

statement ok 要求 SQL 成功。statement error 期望内容是一个 JSON 对象，至少声明一个字段，多个字段为 AND：

```text
statement error id=duplicate-key
INSERT INTO t1 VALUES(1);
@end-sql
----
{"error_code":"XG-1001","message_regex":"duplicate.*"}
@end-expect
```

支持 error_code、sqlstate、error_class、message_regex；正则在静态阶段编译并限制长度。网络错误不能当作预期 SQL 错误通过。
错误码示例为占位，真实样板须使用 Adapter 验证过的数据库错误码。

## 6. Query 和类型化 Expected

exact 严格比较行序、列数、类型与值；rowsort 按 Canonical Row 全局排序并保留重复次数。
Expected 一行一个 JSON Row，零行结果为空 Expected 区域；没有 Expected 区域不等于零行结果。

```text
query exact id=ordered-rows
SELECT id FROM t1 ORDER BY id;
@end-sql
----
[1]
[2]
@end-expect
```

NULL 使用 JSON null；真实字符串用 "NULL"，空字符串用 ""，字面 "<NULL>" 也是字符串。字符串使用 JSON quoting，支持空白、tab、换行和 Unicode。
小数精确解析为 decimal；float/日期/时间/二进制使用 11 的 typed object。禁止通过列数猜测空格分隔的期望值。
需要列元数据断言或按列容差时，可在 Row 之前声明唯一的 `@columns <JSON array>` 和 `@compare <JSON object>`；其 Schema 与 Scenario expect.columns/comparison 相同：

```text
@columns [{"logical_type":"float"}]
@compare {"float_tolerance":{"0":{"abs_tol":0.000001,"rel_tol":0.0}}}
```

只允许 exact 的浮点列容差，且 comparison_profile 必须支持；默认 strict 不隐式放宽。

## 7. Hash 和大结果

```text
query hash rowsort id=large-result
SELECT id,name FROM big_table;
@end-sql
----
{"rows":100000,"columns":2,"canonical_version":"1","sha256":"<64 hex chars>"}
@end-expect
```

Hash 必须使用 11 的类型编码、分帧及全局排序；不能逐批排序后直接 hash。
MVP 支持 exact/rowsort/statement error；hash 和 valuesort 未实现时在 validate/index 明确拒绝，不能降级比较。

## 8. Setup 与 Cleanup

Setup 归类为 FIXTURE_SETUP；部分 Setup 失败仍尝试 Cleanup。
Cleanup 必须尝试且有独立预算；失败保留 primary_status，Attempt=ERROR/FIXTURE_CLEANUP，资源隔离。
不能把“best-effort”解释为清理失败后继续共享连接。恢复规则统一见 11。

## 9. 条件执行

只允许在第一个执行块前出现：

```text
onlyif capability=sql.window
skipif mode=oracle_compatible
```

支持 =、!= 和 capability=；字段必须在 Registry 内。作用域是整个 Case，不是下一条 SQL。
onlyif 不满足为 SKIP/UNSUPPORTED，skipif 满足为 SKIP/CONDITION_FALSE；都保留 Manifest 记录和门禁分母。

## 10. 受控变量

允许 ${schema}、${worker_id}、${run_id}、${case_id}；Scenario 还允许已登记的 ${backup_dir}。
变量带类型和来源：schema 为已分配标识符，路径为资源内路径，值由 Adapter 绑定/引用；禁止把原始字符串直接拼进任意 SQL 字符串或 shell。
值参数优先 Driver bind，标识符由 Adapter quote；文件路径必须位于被授予的资源根内。未知变量、变量类型不匹配、系统环境变量自动注入均拒绝。

## 11. Parser / validate

Parser 不连接数据库，输出统一的 Setup/Step/Cleanup 树与 SourceSpan。
validate/index 必须检查版本、Case/Step ID、Metadata、Registry、块边界、Expected 类型/行长度、错误断言、变量、资源需求、覆盖声明、未支持模式和重复键。
Oracle 正确性由 Review/证据保证，Parser 通过不等于 Oracle 可信。

## 12. Case ID 与兼容性

推荐 <MODULE>.<FEATURE>.<SUBFEATURE>.<NUMBER>，如 QUERY.JOIN.LEFT.000001；稳定且全仓库唯一，不因文件移动改变。
1.0 的空格分隔结果和隐式块边界不能混入 1.1。转换器需生成语义差异清单、重新试跑和 Review；历史结果保持原 DSL/Canonical 版本。
