"""Generate the documentation architecture SVG; no project/runtime behavior is changed.

Run from the repository root: python docs/render_architecture.py
PNG is exported from this SVG by a browser at its intrinsic dimensions.
"""
from pathlib import Path
from html import escape

ROOT = Path(__file__).resolve().parent.parent
W, H = 2140, 1760
FONT = 'Microsoft YaHei, PingFang SC, Arial, sans-serif'
LANES = [
    ('design', '01', '测试设计平面', 'Test Design', '#2466ad', '#f0f6fc',
     '定义能力、合法组合与覆盖要求', [
        ('feature', 'Feature / Capability Registry', '功能与能力注册表', ['Domain / Feature / Level', '统一分类、版本与环境能力', '拒绝自由命名和未知值']),
        ('model', 'Test Model / Constraint', '测试模型与合法空间', ['model_id + version + hash', '维度、合法值、组合约束', '无效或不可满足模型直接拒绝']),
        ('coverage', 'Coverage Model / Points', '覆盖点与显式声明', ['Claim → assertion_refs', '五阶段、点去重、固定分母', 'UNMAPPED / UNSUPPORTED 单列']),
        ('author', 'Case Design / Generator', '用例设计与审查', ['候选 → Trial Run → Review', 'Oracle 来源与语义哈希绑定', '只有有效 active 进入发布'])]),
    ('asset', '02', '测试资产平面', 'Test Asset', '#75519b', '#f6f2fa',
     '固定来源、编译内容与依赖', [
        ('git', 'Git / Asset Snapshot', '测试资产事实源', ['Case / Fixture / Model / Plan', 'Release 固定干净 Git tree', '开发 dirty 必须保存实际内容']),
        ('dsl', 'XGT / Scenario 1.1', '类型化双 DSL', ['SQL 显式边界 / JSON Expected', '并发 Step 树 / 稳定 Step ID', '版本分派，不静默改变旧语义']),
        ('catalog', 'Compiler / Catalog 2', '统一模型与查询索引', ['有效 Metadata / status / issue', '覆盖声明、全依赖失效', '增量与全量结果必须一致']),
        ('bundle', 'Immutable Bundle', '不可变编译内容', ['compiled_hash / semantic_hash', 'Case、Fixture、脚本、依赖', '执行前校验，拒绝工作区漂移'])]),
    ('control', '03', '控制平面', 'Control', '#187f87', '#eef8f8',
     '规划逻辑目标并控制资源准入', [
        ('selector', 'Selector / Test Plan', '精确选例与发布范围', ['Feature / Level / Issue / Status', '先冻结范围，再做能力过滤', '排除和不支持都有原因记录']),
        ('manifest', 'Run Manifest 1', '不可变运行清单', ['Case × target / Bundle hash', '配置、工具、模型与基线快照', '锁定预期执行集合和分母']),
        ('scheduler', 'Global Planner / Scheduler', '目标调度与故障恢复', ['Shard：同 target 等价环境', 'Matrix：多个逻辑 target', '新 Attempt，不改变逻辑身份']),
        ('lease', 'Registry / Resource Lease', '资源所有权与排空', ['层级冲突 / 跨 Run 原子准入', 'Lease + fencing_token', '旧执行停止证明后才能回收'])]),
    ('execution', '04', '执行与环境平面', 'Execution & Environment', '#ad641c', '#fff7ed',
     'Agent 本地执行，隔离失败资源', [
        ('worker', 'Local Planner / Worker Pools', '两级并行与资源复用', ['Fast / Normal / Heavy / Exclusive', 'Session / Fixture / Schema', '普通任务也遵守 Lease 准入']),
        ('executor', 'Executors / Adapters', 'SQL、事务与系统动作', ['Xugu / Admin / Cluster / Backup', 'Canonical 1 / 类型与值断言', '同步、取消与有界超时']),
        ('reset', 'Cleanup / Reset / Probe', '恢复证明与污染隔离', ['保留 primary_status / 清理状态', '恢复失败 → QUARANTINED', '禁止未经确认的重试与复用']),
        ('wal', 'Agent Result WAL', '本地持久化与有界离线', ['event_id / sequence / token', '有效租约 + WAL 空间才继续', '高水位暂停，ACK 后压缩'])]),
    ('quality', '05', '结果与质量平面', 'Result & Quality', '#267649', '#f0f8f2',
     '可信聚合、可比差异与发布判定', [
        ('events', 'Durable Event Log', '执行历史事实源', ['落盘、去重、有序接收', '持久化 ACK / 缺口重放', '旧终态事件只作迟到审计']),
        ('result', 'Result Projection / Artifacts', '可重建结果与失败证据', ['CaseExecution → Attempt → Step', '终态不回退 / Flaky 不隐藏', 'JSONL → Result DB / JUnit']),
        ('delta', 'Baseline / Delta', '锁定基线与可比集合', ['显式基线优先 / 目标映射', '用例、环境、模型变化分列', '失败签名只用于候选聚类']),
        ('gate', 'Quality Gate / Coverage', '门禁与缺口反馈', ['固定分母 / 缺测不可隐藏', 'PASS / FAIL / 不确定 / 不适用', '必需门禁全部 PASS 才放行'])]),
]

svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">',
       '<title id="title">XG DB Test 总体架构 v1.1</title>',
       '<desc id="desc">五平面从测试设计、Git 资产与不可变 Bundle，经 Manifest 和资源准入到 Agent 执行，再经可靠事件和可比差异形成发布门禁。失租或恢复失败隔离资源，覆盖缺口反馈测试设计。全部为设计契约，非已实现声明。</desc>',
       '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="context-stroke"/></marker></defs>',
       '<rect width="100%" height="100%" fill="#fff"/>']

def text(x, y, value, size=19, fill='#213448', weight=400, anchor='start', extra=''):
    svg.append(f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" {extra}>{escape(value)}</text>')

def rect(x,y,w,h,fill,stroke='none',radius=12):
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')

def edge(points, color='#6a7c8d', dashed=False):
    svg.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2" marker-end="url(#arrow)"'+(' stroke-dasharray="7 5"' if dashed else '')+'/>')

text(70,65,'XG DB Test',40,weight=800)
text(340,65,'总体架构 v1.1',35,weight=700)
text(70,105,'显式覆盖声明 → 不可变执行输入 → 受控资源执行 → 可信结果与发布门禁',24,fill='#496077')
text(2060,60,'设计基线 · 2026-09-11',20,anchor='end',fill='#496077')
text(2060,99,'五平面结构 / 非部署数量图',18,anchor='end',fill='#496077')

node_ids=[]
transitions=[]
for i,(lane_id,num,title,en,color,bg,note,nodes) in enumerate(LANES):
    y=145+i*282
    svg.append(f'<g id="plane-{lane_id}">')
    rect(60,y,2020,238,bg,color,16)
    rect(60,y,8,238,color,color,3)
    text(90,y+44,num,26,color,800)
    text(90,y+85,title,27,weight=700)
    text(90,y+118,en,19,fill=color,weight=600)
    # Split the compact lane explanation into two readable lines.
    split=11 if len(note)>16 else len(note)
    text(90,y+158,note[:split],18,fill='#496077')
    if split<len(note): text(90,y+184,note[split:],18,fill='#496077')
    for j,(nid,heading,subtitle,lines) in enumerate(nodes):
        node_ids.append(nid)
        x=400+j*410
        svg.append(f'<g id="node-{nid}">')
        rect(x,y+30,355,182,'#fff',color,10)
        text(x+18,y+63,heading,20,weight=700)
        text(x+18,y+93,subtitle,22,fill=color,weight=700)
        svg.append(f'<line x1="{x+18}" y1="{y+107}" x2="{x+337}" y2="{y+107}" stroke="{color}" opacity="0.25"/>')
        for k,line in enumerate(lines): text(x+18,y+133+k*26,line,18)
        svg.append('</g>')
        if j<3: edge(f'{x+355},{y+121} {x+401},{y+121}',color)
    svg.append('</g>')
    if i<4:
        # Inter-plane flow occupies only the horizontal gutter.
        next_y=y+282
        captions=['审查后沉淀为版本化资产','从同一资产快照规划执行','下发 Shard / Bundle / 有效资源授权','ResultEvent 上送 / 反向持久化 ACK']
        transitions.append((f'1985,{y+212} 2025,{y+212} 2025,{y+259} 577,{y+259} 577,{next_y+26}',color,y,captions[i]))

for points,color,y,caption in transitions:
    edge(points,color)
    rect(900,y+245,570,27,'#fff',radius=3)
    text(1185,y+265,caption,18,fill=color,anchor='middle',weight=600)

# Feedback uses a dedicated outside gutter, never running under a node.
edge('1985,1458 2110,1458 2110,130 1397,130 1397,171','#267649',True)
text(2125,940,'Coverage Gap → 补充模型 / 用例',18,fill='#267649',anchor='middle',extra='transform="rotate(-90 2125 940)"')

rect(60,1582,2020,112,'#f4f6f8','#cbd5df',12)
text(90,1619,'三条不可绕过的契约',23,weight=700)
text(430,1619,'内容不漂移：Manifest + Bundle',21,weight=600)
text(960,1619,'资源不双占：Fencing + 恢复证明',21,weight=600)
text(1530,1619,'结果不虚高：固定分母 + 终态裁决',21,weight=600)
text(90,1659,'实线：主处理路径    虚线：覆盖反馈    ·    详细状态 / Schema / 反例验收见 docs/01–11',19,fill='#496077')
text(70,1730,'图源：docs/render_architecture.py  ·  依据：总架构 v1.1、Metadata 1.1、Catalog/Result 2、执行一致性契约',18,fill='#496077')
text(2060,1730,'SVG 可搜索、可缩放；PNG 同源导出',18,fill='#496077',anchor='end')
svg.append('</svg>')
assert len(node_ids)==len(set(node_ids))==20
path=ROOT/'架构图_v1.svg'
path.write_text('\n'.join(svg)+'\n',encoding='utf-8')
print(path)
