# BA Daily Data Analysis Agent

一个面向 BA 日常分析工作的本地聊天式 Agent 原型。

它实现了：

- 编排状态机：`analysis_design -> data_plan -> insight_review -> report_plan -> final_review`
- 三个子 Agent：分析设计、数据分析和洞察、报告产出
- BA 确认门禁：每个阶段必须确认后才能进入下一阶段
- Master Agent 风格主协调器：管理工作流配置、审批、修订、拒绝、执行历史
- 可插拔 SkillsManager：第一版内置“销售漏斗转化分析”，后续可扩展知识库/SQL 模板/指标库
- 数据源 profile：支持 `xlsx`、`csv`，预留 `database` schema 接入
- 隐私边界：默认只使用字段元数据，不把客户级样本传给外部模型

## Quick Start

推荐直接使用启动脚本，它会绕过 Windows Store 的 `python.exe` alias，改用 Codex bundled Python：

```powershell
cd "C:\Users\wangj\Documents\Agent开发"
.\run_agent.ps1 -Provider disabled
```

启用 OpenAI：

```powershell
cd "C:\Users\wangj\Documents\Agent开发"
.\run_agent.ps1 -Provider openai
```

脚本会隐藏读取 API key，不会把 key 打在命令行里。

启动 Web chat 页面：

```powershell
cd "C:\Users\wangj\Documents\Agent开发"
.\run_agent_web.ps1 -Provider disabled
```

然后打开：

```text
http://127.0.0.1:8765
```

如果要在 Web chat 中启用 OpenAI：

```powershell
.\run_agent_web.ps1 -Provider openai
```

手动启动方式：

```powershell
cd "C:\Users\wangj\Documents\Agent开发"
$env:PYTHONPATH="src"
$env:PYTHONIOENCODING="utf-8"
python -m ba_analysis_agent.cli --source "C:\Users\wangj\Desktop\ZD 工作\数据\ads_rpt_sal_ncs_register_to_order_sales_ssa_t_202605151845\sales 宽表demo.xlsx"
```

看到 `ba-agent>` 后，再输入 agent 内部命令。

常用命令：

```text
new <业务问题>        创建新分析任务
show                 查看当前阶段产出
confirm              确认当前阶段并进入下一阶段
revise <修改意见>    要求当前阶段按意见修订
reject <原因>        拒绝当前阶段
status               查看任务状态
history              查看执行和修订历史
workflow             查看当前工作流配置
llm                  查看当前 LLM provider 和隐私边界
exit                 退出
```

示例：

```text
new 帮我分析 5 月注册到订单转化率下降的原因
show
confirm
show
```

## Design Notes

第一版不会自动执行生产 SQL，只生成取数计划、SQL 草稿和校验计划。联网或外部 LLM 能力应通过 provider 接口接入，并且只能读取字段元数据、业务问题和 BA 已确认的中间产物。

## LLM 配置

默认情况下，如果没有配置 `OPENAI_API_KEY`，Agent 会使用本地规则和 skill 运行，并在输出里标记：

```json
{"llm_enrichment": {"status": "not_used_or_failed"}}
```

每次 `new <业务问题>` 的输出里也会包含：

- `detected_intent`: Agent 识别出的时间范围、漏斗阶段、关注维度、问题类型、指标焦点。
- `llm_enrichment`: LLM 是否 applied；如果失败，会显示 `error`。

启用 OpenAI Responses API：

```powershell
$env:OPENAI_API_KEY="你的 key"
$env:BA_AGENT_LLM_PROVIDER="openai"
$env:BA_AGENT_OPENAI_MODEL="gpt-4.1-mini"
```

隐私边界：

- 发送给 LLM 的只有业务问题、字段名、字段类型、业务域、敏感标记、skill 草稿。
- 不发送 Excel/CSV 原始行、手机号、VIN、客户 ID、订单明细样本。
- LLM 返回失败时自动回退到本地 skill 草稿。

当前实现参考了 Master Agent 设计，但保持为本地轻量原型：

- `MasterAnalyticsAgent` 是主协调器，`BAAnalysisOrchestrator` 保留为兼容别名。
- `workflow.py` 管理 analytics 工作流阶段、顺序、审批要求。
- `SkillsManager` 管理业务 skill、指标树、字段需求、字段到数据源映射和 SQL 模板。
- 每个子 Agent 都暴露统一的 `run(input_data)` 方法，方便后续替换为异步后端服务。

## Playbook Skill

当前本地 skill 试点读取：

```text
C:\Users\wangj\Documents\需求整理\skills\automotive-sales-crm-analysis\references\analysis_playbook.md
```

分析设计阶段会输出：

- `playbook_guidance.enabled`
- `playbook_guidance.matched_topics`
- `playbook_guidance.available_playbook_fields`
- `playbook_guidance.missing_playbook_fields`

如需换成其他 playbook：

```powershell
$env:BA_AGENT_PLAYBOOK_PATH="C:\path\to\analysis_playbook.md"
```
