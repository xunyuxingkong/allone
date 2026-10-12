# XG DB Test 最新提交现状审核

## 1. 当前远端基线

- 仓库：`xunyuxingkong/allone`
- 分支：`codex/join-model-v2`
- 当前 HEAD：`8f9a6bbcaa7b7fce3dd8cdfd5fce86c2bf15702e`
- 最新提交：`chore: update review documents and add Xugu console tools`
- 提交时间：2026-10-12
- 相对上次审核基线 `564b82d`：**ahead 20 commits**
- 分支保护：OFF
- GitHub Commit Status：无
- GitHub Workflow Runs：无
- Commit：unsigned

## 2. 总体现状

这一轮已经把之前规划的 Test Product Layer 大量落地。新增/完善了：

```text
Job Abandon
Test Mission
Mission 创建 / 列表 / 详情
Mission Dashboard
Scope Matrix
Case Semantic Path / Origin
Tested / Untested Scope
AI Test Summary
Filter Plugin
Aggregate Plugin
Subquery Plugin
Sort / Limit Plugin
AI Exploratory Briefing
```

Query 已从单 JOIN 扩展为五个建模 Feature：

```text
JOIN
Filter / WHERE
Aggregate / GROUP BY
Subquery
Sort / Limit
```

方向上已经明显更接近真正的 AI 数据库测试产品。

## 3. 已解决：Job Abandon

现在 JobController 已有可审计 abandon：记录 operator、reason、时间和 prior state，转为 FAILED，追加 `JOB_ABANDONED_BY_OPERATOR` 和 `ABANDONED` event，同时保留历史 Job/Event/Evidence/Identity。CLI 和 MCP 都有入口。上一轮“旧 BLOCKED Job 永久占唯一 Mutable Slot”的问题已经解决。

## 4. 产品入口已明显改善

前端 `/tests/new` 已支持：

```text
测试目的
测试范围
Smoke / Standard / Full / AI Exploratory
风险重点
数据规模
预计 Case / SQL 数量
明确不测范围
启动 AI 测试
```

Dashboard 也已经从 Run/Job-first 改为 Mission/Coverage/Result-first。Scope Matrix 能区分 Requirement、Case、SQL Execution；Case 页能解释“这条用例测什么、为什么生成、来自哪里”。

## 5. 五个 Feature 的插件化扩展是成功的

Filter、Aggregate、Subquery、Sort/Limit 都复用了既有 Model → Template → FeaturePlugin → Coverage → Candidate → Mutation → Static Validation 链，没有为每个 Feature 重写 Core。这证明 FeaturePlugin 抽象基本成立。

## 6. AI Exploratory 目前只是 Briefing v1

当前 AI Exploratory 可以读取 Coverage Gap、按风险分类、读取 Regression Failure、输出风险区域和建议，但明确是 read-only / advisory-only，不会自动生成新 Case、不会循环执行、不会根据失败继续扩展测试空间。因此它目前更准确地叫 `AI Exploratory Briefing v1`。

## 7. 当前最重要的新 P0：多 Feature Mission 与真实执行不一致

前端允许同时勾选：

```text
JOIN
Filter
Aggregate
Subquery
Sort / Limit
```

`TestMission.features` 也是 list。

但 `ServiceContext._resolve_scope()` 实际只使用：

```python
self.features[0]
```

也就是说用户选 5 个 Feature，Mission 页面会显示 5 个范围，但真实 Job 只会按第一个 Feature 的 Scope 执行。

这是严重的 **Product Truth** 问题。

建议正式方案：

```text
Mission
├─ FeatureJob(join)
├─ FeatureJob(filter)
├─ FeatureJob(aggregate)
├─ FeatureJob(subquery)
└─ FeatureJob(sort_limit)
```

Mission 聚合多个 Feature Job 的 Coverage / Execution / Failure / Completion。短期若不做编排，前端必须先改成单选，不能继续多选。

## 8. 第二个 P0：Smoke / Standard / Full 目前没有真正控制执行

Mission 支持四个 strategy，前端还展示不同预计 Case 数，但 Job 创建时实际传入的核心参数只有：

```text
intent
features
```

`TestIntent` 没有 `strategy / data_scale / risk_focus`，CandidateService 仍使用 Scope 自己固定的 `coverage_strategy`。

所以现在用户选择 Smoke 或 Full，真实生成/执行逻辑可能完全一样。SMALL/MEDIUM/LARGE 和 risk_focus 也主要是产品元数据。

必须打通：

```text
Mission.strategy
→ TestIntent / ExecutionPolicy
→ GenerationPolicy
→ Case Budget / Coverage Strategy
```

建议语义：

```text
SMOKE       = 核心值 + 最小 Pairwise + 小 Case Budget
STANDARD    = Pairwise 全要求
FULL        = all_values / higher-order interactions
AI_EXPLORATORY = Standard baseline + AI gap expansion rounds
```

## 9. 首页 “Query Coverage” 目前也容易误导

Dashboard 直接调用默认 `getCoverage(pairwise)`，而 `QueryReadService.from_environment()` 仍由默认 Scope 决定 Coverage。现在已经有 5 个 Feature，但首页标题是 `Query 覆盖`，实际很可能只展示默认 Feature（通常 JOIN）的 Coverage。

应改成真正的 Feature Dashboard：

| Feature | Requirements | Covered | Missing | Cases | 状态 |
|---|---:|---:|---:|---:|---|
| JOIN | ... | ... | ... | ... | ... |
| Filter | ... | ... | ... | ... | ... |
| Aggregate | ... | ... | ... | ... | ... |
| Subquery | ... | ... | ... | ... | ... |
| Sort / Limit | ... | ... | ... | ... | ... |

## 10. Mission tested_scope 语义现在过早

当前 Mission View 直接：

```text
tested_scope = mission.features
untested_scope = mission.excluded_scope
```

但“用户选择了 Feature”不等于“Feature 已经被测试”。应该拆成：

```text
requested_scope
executed_scope
covered_scope
excluded_scope
unmodelled_scope
```

## 11. “测试用例太少”只解决了一半

本轮真正扩大的主要是 Test Space Model、Generator Template 和 FeaturePlugin。对比中没有看到成规模新增正式 Active Case Pack。

因此当前应该区分：

```text
Test Space 已扩展
Executable Active Case Library 仍需扩展
```

建议 Product MVP 的 Standard 真实规模：

```text
JOIN            40~60 Cases
Filter          40~70 Cases
Aggregate       30~60 Cases
Subquery        30~60 Cases
Sort / Limit    20~40 Cases
总计            180~300 Cases
SQL Executions  500~1000
```

不能只把 Requirement Count 做大。

## 12. Execution Contract 已变化

当前 descriptor 的 `contract_set_id` 已更新为：

```text
663374ea6b647f4f7f27a706bc8d1a3e2c6a0c725052e8cb3c7bb10ca6f7dba6
```

旧版本是 `f7589aab...`。如果仍沿用旧 v14 Runtime Profile，那么下一次真实运行应预期 `RUNTIME_PROFILE_STALE`。真实 Xugu E2E 前必须重新 Probe、生成 Runtime Profile、确认 DB Build 和 Contract ID。

## 13. mission_logic 已定义但尚未强制

`contract_set.py` 已新增 `mission_logic` 层，它比 broad control_plane 更适合作为 Durable Job identity，但当前 `job_source_identity()` 仍冻结 `control_plane_layer_id`。文档也明确说明 mission_logic 只是定义/测试，尚未启用。这个问题可以放到真实 E2E 后收敛。

## 14. 文档已经出现漂移

`docs/external-agent-jobs.md` 部分文字仍写“当前 feature 为 join / Filter 不在本轮范围”，但代码已经支持 5 个 Feature。MVP Freeze 前需要做一次 Docs Truth Review。

## 15. 最新提交加入 Xugu Console ZIP 的建议

HEAD 新增：

```text
tools/xgconsole_linux_aarch64_2.2.1.zip
tools/xgconsole_windows_amd64_2.2.1.zip
```

长期更建议用 GitHub Release 或 Git LFS，并提供 SHA256、来源和许可证/分发说明，避免普通 Git 仓库持续膨胀并改善供应链审计。

## 16. GitHub 工程 Gate 仍未建立

当前：

```text
Branch Protection: OFF
Commit Status: none
Workflow Runs: none
Commit unsigned
```

因此当前代码质量仍主要依赖本地测试和人工审核。用户此前延后 CI，所以暂不作为 Product MVP blocker，但进入 24h Autonomous Testing / Auto Repair PR 前必须补上。

## 17. 当前综合状态

| 维度 | 当前状态 |
|---|---|
| Deterministic Core | 9/10 |
| Evidence / Acceptance | 9/10 |
| AI Control Plane | 8.5/10 |
| Test Product Layer | 7.5/10 |
| 前端测试认知体验 | 7/10 |
| Feature 模型丰富度 | 8/10 |
| Active Case 内容规模 | 5/10 |
| AI Exploratory | 5.5/10 |
| 真实 Xugu E2E | 未完成 |
| Product MVP 完成度 | 约 82~86% |

与上次相比，产品层已经有明显跃迁，但现在最大的短板变成：

```text
产品参数是否真的控制执行
+
多个 Feature 是否真的一起测试
+
有没有足够真实 Test Cases
```

## 18. 下一步优先级

### P0-1 Multi-feature Mission 真执行
不要继续存在“选五个，实际只跑第一个”。

### P0-2 Strategy 真执行
让 Smoke / Standard / Full / AI Exploratory 真正改变 Generation / Coverage / Case Budget。

### P0-3 重建 Runtime Profile
基于新 Contract `663374ea...` 重建真实数据库 Runtime Profile。

### P1-1 五 Feature Coverage Dashboard
首页真正展示五个 Feature 的 Coverage。

### P1-2 扩充 Active Case Pack
形成 180~300 个 Standard 可执行正式 Case，而不是只扩 Model。

### P1-3 AI Exploratory 从 Briefing 进化成受控 Loop

```text
Observe Coverage
→ AI Select Risk
→ Generate Limited Candidates
→ Core Execute
→ Observe
→ Next Round
```

Core 继续决定真相，AI 只决定下一探索动作。

## 19. 现在不建议继续加第六个 Feature

五个 Feature 已经足够做 Query MVP。当前继续加 Window / CTE / Set Operation 的收益小于把 Multi-feature Mission、Strategy、Case Scale、Runtime Profile、真实 E2E 做实。

## 20. Product MVP 真正完成标准

```text
1. 用户创建一个 Query Standard Mission
2. 选择 JOIN + Filter + Aggregate + Subquery + Sort/Limit
3. 系统真的编排执行五个 Feature
4. Dashboard 展示五个 Feature Coverage
5. Standard 实际运行 180~300 Case
6. AI 对 Gap / Failure 做分析
7. AI Exploratory 至少完成一轮受控补测
8. PASS/FAIL 仍由 Core 决定
9. Human Gate 仍控制 Promotion
10. 真实 Xugu 完整 E2E 跑通
```

做到这里才能正式定义：

```text
XG DB Test AI-Driven Product MVP v1 = DONE
```
