# 业务问题驱动的 Sales BP 分析 Agent 设计

## 目标

这个 Agent 不绑定单一漏斗场景，而是把 Sales BP 的日常分析工作抽象成：

1. 理解业务问题。
2. 识别问题类型。
3. 匹配业务语义层。
4. 动态组合分析方法。
5. 让 BA 确认分析计划。
6. 执行数据分析和洞察生成。
7. 产出可编辑报告。
8. 沉淀为可复用方法和口径。

当前 register-to-order CSV 只是第一个样例数据资产，用于验证字段映射和分析闭环，不是产品边界。

## 前端页面

### 1. 分析工作台

输入任意业务问题，例如：

- 为什么本月订单下降？
- 哪些渠道线索多但订单转化低？
- 新能源车型到店后成交差异在哪里？
- 哪些经销商承接异常？
- 活动投放是否带来了高质量线索？

页面展示：

- 问题输入。
- 分析对象。
- 时间范围。
- 下钻维度。
- 是否使用样例字段清单判断数据可用性。

### 2. 能力目录

展示 Agent 当前能理解和组合的能力：

- 问题类型。
- 分析方法。
- 业务对象。
- 语义指标。
- 语义维度。
- 样例字段。

这个页面的作用是让 BA 知道 Agent 不是固定模板，而是有可维护的能力资产。

### 3. 分析设计确认页

由分析设计 Agent 输出：

- 推荐业务场景。
- 问题类型。
- 分析目的。
- 澄清问题。
- 业务假设。
- 推荐分析方法。
- 语义对象匹配。
- 数据可用性状态。
- 指标树和字段需求。

BA 必须确认后才能进入数据分析。

### 4. 数据洞察确认页

由数据分析与洞察 Agent 输出：

- 数据源计划。
- SQL/取数计划。
- 校验计划。
- 方法执行计划。
- 洞察候选卡片。
- 数据可用性风险。
- 待 BA 确认事项。

BA 必须确认数据口径、过滤条件、样本风险和洞察解释后，才能进入报告生成。

### 5. 报告生成确认页

由报告生成 Agent 输出：

- 结论摘要。
- PPT 故事线。
- Excel tabs。
- BRD/分析说明结构。
- 发布前最终审核项。

BA 确认后，流程状态变为完成，并可沉淀为知识库模板。

## Agent 工作流

```mermaid
flowchart LR
    A["业务问题输入"] --> B["问题类型识别"]
    B --> C["语义层匹配"]
    C --> D["分析方法组合"]
    D --> E["BA 确认分析设计"]
    E --> F["数据分析与校验"]
    F --> G["BA 确认洞察"]
    G --> H["报告生成"]
    H --> I["BA 最终确认"]
    I --> J["沉淀方法和口径"]
```

## Agent 1：分析设计 Agent

### 输入

- business_question
- scenario，可为空，由 Agent 自动识别
- analysis_purpose，可为空
- target_object
- time_range
- dimensions
- available_fields，可为空
- deliverable_type
- audience

### 核心逻辑

1. 用问题类型库识别问题属于哪几类：
   - 指标变化解释。
   - 原因诊断。
   - 转化链路诊断。
   - 分层对比。
   - 质量与效率评估。
   - 资源规划与策略建议。
   - 数据质量与口径校验。

2. 用方法库动态选择分析模块：
   - 趋势分析。
   - 对比分析。
   - 贡献度拆解。
   - 漏斗链路分析。
   - 分群下钻。
   - 影响因素分析。
   - 异常识别。
   - 队列分析。
   - 时效效率分析。
   - 质量分析。
   - 区域地理分析。
   - 排名与对标。
   - 策略与情景测算。

3. 用语义层匹配业务对象：
   - 客户。
   - 线索。
   - 机会。
   - 到店/客流。
   - 试驾。
   - 订单。
   - 经销商。
   - 渠道与活动。

4. 判断数据可用性：
   - available：字段齐全。
   - partially_available：部分字段可用。
   - requires_mapping：尚未提供物理字段，需要 BA 确认映射。
   - requires_ba_confirmation：方法执行前必须确认口径。

### 输出

- question_types
- selected_methods
- semantic_matches
- data_availability
- clarification_questions
- hypotheses
- metric_tree
- field_requirements
- analysis_path

## Agent 2：数据分析与洞察 Agent

### 输入

- BA 已确认的分析设计。
- 语义层映射。
- 数据源计划。
- 指标口径。
- 过滤条件。
- 下钻维度。

### 核心逻辑

1. 生成取数计划。
2. 生成可审计 SQL 草稿。
3. 生成质量校验计划。
4. 按方法库逐个执行分析模块。
5. 形成证据化洞察卡片。

### 输出

- data_access_plan
- sql_plan
- validation_plan
- method_execution_plan
- semantic_data_availability
- insight_cards
- ba_review_items

## Agent 3：报告生成 Agent

### 输入

- BA 已确认的数据分析和洞察。
- 报告类型。
- 目标受众。
- 输出格式偏好。

### 核心逻辑

1. 组织业务叙事。
2. 根据受众调整表达。
3. 将证据、图表、结论和行动建议串成报告。
4. 标注结论强度和数据限制。

### 输出

- executive_summary
- ppt_storyline
- excel_tabs
- brd_sections
- report_structure
- ba_final_review_items

## 当前实现位置

- 数据契约：[models.py](../src/bp_ba_agent/models.py)
- 方法库：[method_library.py](../src/bp_ba_agent/method_library.py)
- 语义层：[semantic_layer.py](../src/bp_ba_agent/semantic_layer.py)
- 三段式工作流：[multi_agent_workflow.py](../src/bp_ba_agent/multi_agent_workflow.py)
- 前端工作台：[workflow_web.py](../src/bp_ba_agent/workflow_web.py)
- 灵活架构测试：[test_flexible_architecture.py](../tests/test_flexible_architecture.py)

## MVP 验收口径

第一版不追求替代所有 BA 工作，而是验证它能否稳定完成：

1. 任意业务问题转结构化分析计划。
2. 自动判断问题类型，而不是固定漏斗模板。
3. 自动组合多个分析方法。
4. 自动识别需要哪些业务对象、指标和字段。
5. 明确告诉 BA 哪些数据可用、哪些需要补充。
6. 每一步都必须经过 BA 确认。
7. 输出可审计、可编辑、可沉淀的分析过程。
