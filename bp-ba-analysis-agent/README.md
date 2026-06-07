# BP BA 分析 Agent POC

这是一个面向 BI 项目 BP BA 的端到端分析工作流 Agent 原型。它把 BP BA 日常工作中的需求澄清、分析框架、指标拆解、数仓/BI 取数计划、数据校验、交付草稿串成统一的 `Analysis Case`。

## 当前能力

- 自动识别 4 类首期场景：媒体投流策略、车型转化、经销商运营、Target steering。
- 自动生成需求澄清问题、分析目的、业务假设和维度建议。
- 生成核心指标树，覆盖线索、客流、订单、转化率、归因和目标达成。
- 生成只读数据源接入计划，默认面向数仓、Tableau/BI 元数据、KM/AMP 知识库。
- 生成可审核 SQL 计划，保留 Human-in-the-loop 审核点。
- 生成数据校验计划和 Excel/PPT/BRD 交付草稿结构。

## 快速运行

```powershell
$env:PYTHONPATH="src"
python -m bp_ba_agent "分析媒体投流转化下降原因" --time-range "2026年4月" --target-object "华东大区" --json
```

或者查看简版输出：

```powershell
$env:PYTHONPATH="src"
python -m bp_ba_agent "Target steering 月度订单目标如何拆解到大区和车型" --scenario target_steering
```

## 运行测试

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests
```

## 基于真实数据做演示

真实数据 zip 会被流式读取，不会解压原始明细到工作区；输出只包含聚合统计和故事线草稿。

快速样本演示：

```powershell
$env:PYTHONPATH="src"
python -m bp_ba_agent.real_data "C:\Users\wangj\Desktop\ZD 工作\ads_rpt_sal_ncs_register_to_order_sales_ssa_t_202605151845.zip" --max-rows 100000 --md-out "outputs\real_data_demo\sample_report.md" --json-out "outputs\real_data_demo\sample_report.json" --html-out "outputs\real_data_demo\sample_dashboard.html"
```

全量演示：

```powershell
.\examples\run_real_data_demo.ps1
```

报告会包含：

- register、leads、oppty、visit、td、order 漏斗阶段记录量。
- 关键转化率：leads/register、oppty/leads、visit/oppty、td/visit、order/leads、order/oppty。
- 渠道、媒体、区域、品牌、车型、经销商状态等 Top 分布。
- 关键字段填充率和敏感字段识别结果。
- Agent 自动生成的 PPT 故事线草稿和隐私说明。
- 一个可直接打开演示的 HTML Dashboard。


## 三 Agent 工作流前端演示

这个 POC 已拆成三个 Agent，并在后端强制要求 BA 每步确认后才能进入下一步：

- 分析思路拆解和设计 Agent：输入业务问题、场景、对象、周期和维度；输出分析目的、澄清问题、业务假设、指标树、字段需求和分析路径。
- 数据分析和洞察 Agent：输入 BA 已确认的分析设计；输出数据源计划、SQL/取数计划、校验计划、初步洞察卡片和待确认事项。
- 报告产出和生成 Agent：输入 BA 已确认的数据洞察；输出结论摘要、PPT 故事线、Excel tabs、BRD 结构和发布前最终审核项。

启动前端页面：

```powershell
.\examples\run_workflow_web_demo.ps1
```

然后打开：

```text
http://127.0.0.1:8083
```

页面流程：填写业务问题 -> 生成第 1 步 -> BA 确认 -> 生成第 2 步 -> BA 确认 -> 生成第 3 步 -> BA 最终确认。

## 生产化接入建议

- `src/bp_ba_agent/models.py` 是稳定数据契约，后续 API、前端、数据库都应围绕 `Analysis Case` 扩展。
- `src/bp_ba_agent/knowledge_base.py` 当前是种子知识，生产环境应迁移到 KM/AMP、指标语义层和 BI metadata。
- `src/bp_ba_agent/connectors.py` 预留了只读连接器协议，后续分别接 Data Center、Tableau API、历史 Excel/案例库。
- `src/bp_ba_agent/agent.py` 是 6 个子能力的编排层，后续可以把每一步替换为 LLM tool call 或工作流节点。
- `src/bp_ba_agent/real_data.py` 是真实 zip 数据演示入口，可替换为生产数仓/BI connector。

## 0 到 1 排期

- [Sales BP 分析 Agent 0 到 1 排期计划](docs/sales_bp_agent_0_to_1_roadmap.md)
- [可导入表格工具的 WBS CSV](docs/sales_bp_agent_0_to_1_wbs.csv)
- [AI coding 加速版 4 周 MVP 中文 WBS](docs/sales_bp_agent_mvp_4_week_wbs_cn.csv)
- [AI coding 加速版 4 周 MVP 一页 Timeline PPT](docs/sales_bp_agent_mvp_4_week_timeline.pptx)

## 首期验收口径

- 至少跑通 3 个真实业务案例：媒体投流、车型转化、Target steering。
- 每个案例都能追溯业务问题、指标口径、数据来源、SQL 计划、校验计划和交付草稿。
- BP BA 审核后确认：需求澄清和分析框架阶段节省 30% 以上时间。
