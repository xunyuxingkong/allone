# G0A 验收候选快照

状态：**HOLD，尚未 Freeze**（2026-09-24）。`freeze_git_commit`、正式 `contract_set_id` 发布和进入 XGT Parser 主线，均等待以下真实 Driver 验收完成。当前候选描述符见 [contract-descriptor-candidate.json](g0a/contract-descriptor-candidate.json)。候选 `contract_set_id` 为 `a0f9d22048aaa864e742f8f8f6c101cd8b5ac26d67e8771ae95cb82b1cdd63ad`，由描述符身份投影经 XGMJ1/SHA-256 得到；它不是已发布的 Freeze ID。源码哈希统一使用 LF 换行，确保 Windows 与 Linux 重算一致。

| 检查 | 结果 | 证据或限制 |
|---|---|---|
| Runtime Profile Identity v0.2 | PASS | 语义变更与运行期噪声向量通过；基准 Profile ID 为 `3a4fcf68668615743c5d4303c814ff79277dc82bec8096ac41117f35e3644cea`。 |
| Typed Expected v1 | PASS | 空/混合/负数/空字符串拒绝；`rows: []` 表示 0 行，`rows: [[]]` 表示 1 行 0 列；Bootstrap 解码在执行前拒绝混合结构。 |
| Admission Conflict Rules v0.1 | PASS（限定范围） | 同资源、直接父子和访问模式矩阵通过；完整准入不在 v0.1 范围，见 [14_Admission_Conflict_Rules_v0.1.md](14_Admission_Conflict_Rules_v0.1.md)。 |
| Registry / Schema | PASS | 237 项目 Python 环境执行 `registry validate`，Schema 重新导出与仓库文件逐项比较无差异。 |
| Framework Tests | PASS | 237 隔离 Python 3.14：113 tests passed（含 Query MVP）。 |
| Runtime Profile Build | PASS | 旧有脱敏证据构建出的 v0.2 Profile ID 为 `84d78277f2e244aba87b2249911d17652919606127ebdf17df2501dfd7bc888c`。 |
| 真实 Xugu Driver 元数据 | PARTIAL | xgcondb 2.3.9 在只读表达式探测中取得 21/22 组元数据；`VARBINARY(8)` 为语法错误。详细样本见 [xugu_driver_type_mapping_v1.json](../framework_tests/fixtures/xugu_driver_type_mapping_v1.json)，SHA-256 `2d525d7d85b529c940940c7b86a981cfa5b64afca462d0d096637d03fc350e07`。 |
| 真实 Xugu 四类 MVP | 历史 PASS，当前 BLOCKED | 2026-09-16 曾完成 JOIN、UNION、DDL TABLE、STRING FUNCTION 四用例 PASS；本轮数据库返回 `E22007`（集群降级只读），22/22 建表样本无法执行，不能复验 DDL/写入/清理完整链。失败记录见 [xugu_driver_type_mapping_write_attempt_v1.json](../framework_tests/fixtures/xugu_driver_type_mapping_write_attempt_v1.json)，SHA-256 `f59263185f061a9bfa780d4d9cd0430215b35cfbb9533ccb9ae68403b220e8af`。 |

Driver 样本表明，当前 `NUMERIC/DECIMAL/NUMBER` 元数据统一为 `NUMERIC`，但值为 `float`，不满足 Decimal 精确 Canonical；`DATETIME/TIMESTAMP/TIMESTAMP WITH TIME ZONE` 统一报告 `DATETIME`，返回字符串尚未满足 timestamp Canonical，带时区语义无法仅靠元数据区分；`BINARY/RAW` 被报告为 `VARCHAR` 并返回字符串。它们不能标记为已支持的精确映射。`INT/INTEGER/BIGINT/SMALLINT/FLOAT/DOUBLE/CHAR/VARCHAR/TEXT/DATE/TIME/BLOB/BOOLEAN` 在只读表达式样本中得到唯一 Logical Type 与可编码值；仍需可写环境的表往返验证才能完成 G0A 所需的真实行为证据。

候选快照记录：Registry 文件哈希、全部 Schema 哈希、Core Model 和语义校验器文件哈希均写入描述符。XGMJ1/XGC1 Golden Vector 文件为 `framework_tests/contract/test_canonical.py`，SHA-256 `d75b20cd02a217f99f6148a1acb93e3e2ca45a361197280eda750ada9228bf59`；Runtime Profile Vector 文件 SHA-256 为 `f86b827df82b2fff354224b5425811e7c0e18c25ae083bb6a227523ca8815f1a`。YAML Vector 当前由 `framework_tests/contract/test_registry.py` 承载，版本标记为候选 v1；Logical Type Mapping v1、Typed Expected v1 和 Admission Rules v0.1 由源码常量与描述符哈希约束。

解除 HOLD 的条件：数据库恢复可写后，重新执行表往返 Driver Metadata Probe，确认清理成功；明确最终支持/不支持类型集合；重新运行真实四类 MVP、框架测试、Registry 和 Schema 检查，再生成新候选描述符并记录实际 Freeze Git 提交。不要将本文件中的候选 ID 用作正式 Manifest `contract_set_id`。
