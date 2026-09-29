# JOIN v2 候选人工评审包

状态：**待人工评审**。此表为评审入口，不构成评审结论。全部 21 条候选已通过静态校验和指定 Runtime Profile 下的真实 Xugu 双跑；原始 Trial Artifact 保存在本地 `artifacts/trial-runs/`，完整 SHA-256 见 [trial-run-index.json](trial-run-index.json)。

Codex 的[独立技术评审](../../审核意见/XG_DB_Test_JOIN_v2_AI_Technical_Review.md)发现 5 条 `less_equal` 候选缺少等值边界验证，建议先修复再晋级；本表保留原始候选清单供复核。

- Model / Template 版本：2 / 2；[维度语义定义](../../docs/Query_Generation_JOIN_Model_v2.md)。
- Contract Set：`ff9fad1b73c500e67e782c180ef5190102605a48bb1e29cdd7e6df953040b596`。
- Runtime Profile：`474c848b8b28264c73838e337dcad3a056ad8df295504e976dc4ccc7fd237bac`。
- 当前 Active pairwise 覆盖 17/137；以下候选全部晋级后预计为 137/137，详见 [coverage-summary.json](coverage-summary.json)。

| 候选 | JOIN | 谓词 | 类型 | 输出 NULL 侧 | 交互 | Expected 行数 | Artifact SHA 前缀 |
|---|---|---|---|---|---|---:|---|
| [QUERY.JOIN.1587A38D](../../candidates/archive/query/join-v2/QUERY.JOIN.1587A38D.yaml) | right | less_equal | varchar | left | none | 1 | `9c719e690270` |
| [QUERY.JOIN.4C8C237C](../../candidates/archive/query/join-v2/QUERY.JOIN.4C8C237C.yaml) | left | less_equal | date | right | where | 1 | `0be177c16983` |
| [QUERY.JOIN.6D14282A](../../candidates/archive/query/join-v2/QUERY.JOIN.6D14282A.yaml) | left | equality | date | none | group_by | 1 | `498a2c5edff0` |
| [QUERY.JOIN.6DDD8395](../../candidates/archive/query/join-v2/QUERY.JOIN.6DDD8395.yaml) | cross | none | int | none | none | 1 | `e3c8964b8843` |
| [QUERY.JOIN.73205D44](../../candidates/archive/query/join-v2/QUERY.JOIN.73205D44.yaml) | full | less_equal | int | left | group_by | 2 | `90463ad77dc3` |
| [QUERY.JOIN.7483C7E8](../../candidates/archive/query/join-v2/QUERY.JOIN.7483C7E8.yaml) | full | equality | date | both | group_by | 2 | `0235187c2137` |
| [QUERY.JOIN.844DC9C3](../../candidates/archive/query/join-v2/QUERY.JOIN.844DC9C3.yaml) | full | equality | date | right | subquery | 2 | `2193a5622fbe` |
| [QUERY.JOIN.90375A83](../../candidates/archive/query/join-v2/QUERY.JOIN.90375A83.yaml) | right | equality | date | none | group_by | 1 | `3c9282707b9a` |
| [QUERY.JOIN.92E8C7B5](../../candidates/archive/query/join-v2/QUERY.JOIN.92E8C7B5.yaml) | full | inequality | varchar | right | group_by | 2 | `829f4c836000` |
| [QUERY.JOIN.95FF02CF](../../candidates/archive/query/join-v2/QUERY.JOIN.95FF02CF.yaml) | full | equality | date | none | group_by | 1 | `23420f5458a4` |
| [QUERY.JOIN.98AAF359](../../candidates/archive/query/join-v2/QUERY.JOIN.98AAF359.yaml) | inner | inequality | varchar | none | group_by | 1 | `645afa00fedf` |
| [QUERY.JOIN.9C7749FA](../../candidates/archive/query/join-v2/QUERY.JOIN.9C7749FA.yaml) | inner | less_equal | date | none | where | 1 | `f796658a05b2` |
| [QUERY.JOIN.9D3FFA5C](../../candidates/archive/query/join-v2/QUERY.JOIN.9D3FFA5C.yaml) | cross | none | varchar | none | where | 1 | `406d31285b9b` |
| [QUERY.JOIN.A8062588](../../candidates/archive/query/join-v2/QUERY.JOIN.A8062588.yaml) | left | inequality | varchar | none | subquery | 1 | `ab94f1bd4f56` |
| [QUERY.JOIN.ACD09E7C](../../candidates/archive/query/join-v2/QUERY.JOIN.ACD09E7C.yaml) | full | equality | varchar | both | where | 2 | `beaa197be78d` |
| [QUERY.JOIN.B5FB1A92](../../candidates/archive/query/join-v2/QUERY.JOIN.B5FB1A92.yaml) | cross | none | date | none | group_by | 1 | `11f7242e46b5` |
| [QUERY.JOIN.D231B777](../../candidates/archive/query/join-v2/QUERY.JOIN.D231B777.yaml) | full | inequality | date | both | none | 2 | `676fdc2a84a9` |
| [QUERY.JOIN.EC3FEEF0](../../candidates/archive/query/join-v2/QUERY.JOIN.EC3FEEF0.yaml) | inner | equality | date | none | subquery | 1 | `f8a3fb3f7f43` |
| [QUERY.JOIN.ED774CF9](../../candidates/archive/query/join-v2/QUERY.JOIN.ED774CF9.yaml) | full | less_equal | int | both | subquery | 2 | `f9b8e75c210f` |
| [QUERY.JOIN.F1D5075C](../../candidates/archive/query/join-v2/QUERY.JOIN.F1D5075C.yaml) | right | equality | date | left | subquery | 1 | `5a7d7992662d` |
| [QUERY.JOIN.F6A1656D](../../candidates/archive/query/join-v2/QUERY.JOIN.F6A1656D.yaml) | right | inequality | int | left | where | 1 | `1fd6d95f28f3` |

## 人工评审要点

1. 逐条核对维度组合、SQL、Expected 和 CoverageClaim 是否一致，特别检查 `null_side` 表示输出中的 NULL 扩展侧。
2. 检查 `where`、`group_by`、`subquery` 是否真正影响查询结果或执行路径，并核对 Xugu 双跑证据。
3. 将代码评审引用和覆盖评审引用分别交给 `xgtest candidate review` 的 `--reference`、`--coverage-reference`；评审人身份填写到 `--reviewer`。不得以本评审包代替人工结论。
4. 评审通过后再执行 Promotion Preflight、晋级、全量回归和最终 Active Coverage 快照。
