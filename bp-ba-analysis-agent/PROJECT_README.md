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
