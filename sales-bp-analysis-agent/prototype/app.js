const gates = [
  { id: "problem", name: "问题确认", done: false },
  { id: "plan", name: "方案确认", done: false },
  { id: "data", name: "数据确认", done: false },
  { id: "metrics", name: "口径确认", done: false },
  { id: "insights", name: "洞察确认", done: false },
  { id: "report", name: "报告确认", done: false }
];

const templates = [
  {
    id: "performance",
    name: "业绩表现诊断",
    desc: "定位订单、交车或销量缺口，拆解到区域、经销商、车系和渠道。",
    tags: ["趋势", "贡献度", "结构", "目标差距"]
  },
  {
    id: "conversion",
    name: "转化效率诊断",
    desc: "分析 register、lead、oppty、visit、TD、order 的阶段转化和耗时。",
    tags: ["漏斗", "时效", "Cohort", "战败"]
  },
  {
    id: "campaign",
    name: "渠道活动评估",
    desc: "比较不同渠道、媒体、活动的线索质量和后链路转化表现。",
    tags: ["渠道", "活动", "质量", "ROI"]
  },
  {
    id: "opportunity",
    name: "增长机会识别",
    desc: "识别高潜区域、经销商、车系，形成资源配置建议。",
    tags: ["潜力", "对标", "排名", "策略"]
  },
  {
    id: "forecast",
    name: "预测预警",
    desc: "评估目标达成风险，定位未来可能掉队的对象。",
    tags: ["目标", "Run Rate", "风险", "预警"]
  },
  {
    id: "operation",
    name: "运营监控",
    desc: "跟踪 SLA、异常战败、异常取消和门店处理质量。",
    tags: ["异常", "SLA", "明细", "负责人"]
  }
];

const branches = [
  {
    title: "订单缺口由谁贡献",
    items: ["按区域、小区、城市、经销商拆解", "按车系、车型、能源类型拆解", "输出下滑贡献排名"]
  },
  {
    title: "前链路流量是否变化",
    items: ["线索量、机会量趋势", "渠道和活动结构变化", "线索星级和预计购买时间"]
  },
  {
    title: "中链路承接是否变差",
    items: ["首次跟进时效", "到店率、试驾率", "跟进次数和机会阶段"]
  },
  {
    title: "订单端是否有阻塞",
    items: ["订单取消率", "交车耗时", "取消原因和战败原因"]
  }
];

const methods = [
  ["trend", "趋势分析", "按日、周、月观察订单、线索、到店和试驾变化。"],
  ["contribution", "贡献度分析", "定位缺口主要由哪些区域、经销商、车系或渠道贡献。"],
  ["funnel", "漏斗分析", "检查 register 到 order 的阶段转化和掉点。"],
  ["latency", "时效分析", "评估首次跟进、到店、试驾、订单的处理耗时。"],
  ["reason", "原因枚举分析", "分析战败、拒绝、订单取消原因。"],
  ["potential", "潜力评分", "识别值得优先干预的经销商和车系。"]
];

const skillCatalog = {
  "data-analysis": ["Data analysis", "Run metric comparisons, segmentation, and diagnostic cuts."],
  "exploratory-data-analysis": ["Exploratory analysis", "Find distributions, anomalies, and candidate drivers."],
  "sql-query-generation": ["SQL generation", "Draft metric queries, joins, validation checks, and drilldowns."],
  "analytics-reporting": ["Analytics reporting", "Turn findings into KPI narrative and management-ready messages."],
  "data-cleaning": ["Data cleaning", "Check missing values, invalid codes, duplicates, and field consistency."],
  "data-visualization": ["Data visualization", "Select chart types and prepare chart-ready structures."],
  "churn-analysis": ["Drop-off analysis", "Diagnose funnel loss, cancellation, refusal, and retention-like behavior."],
  "competitive-battlecard-creation": ["Battlecard creation", "Structure battle-fail and competitive insights for sales action."],
  "financial-modeling": ["Financial modeling", "Model target gaps, ROI, scenarios, and sensitivity when inputs exist."],
  "report-generation": ["Report generation", "Create structured reports with evidence, limitations, and actions."],
  "presentation-creation": ["Presentation creation", "Build executive storyline and deck-ready page flow."],
  "proposal-generation": ["Proposal generation", "Package recommended initiatives, scope, impact, and plan."],
  "deep-research": ["Deep research", "Gather external market, competitor, policy, and context evidence."],
  "context-retrieval": ["Context retrieval", "Retrieve business rules, historical cases, and reusable playbooks."],
  "fact-checking": ["Fact checking", "Check that claims are supported by facts and assumptions are explicit."],
  "proofreading": ["Proofreading", "Polish wording, consistency, and executive readability."]
};

const skillRecommendations = [
  ["performance", ["data-analysis", "exploratory-data-analysis", "sql-query-generation", "analytics-reporting"]],
  ["conversion", ["exploratory-data-analysis", "sql-query-generation", "churn-analysis", "data-visualization"]],
  ["campaign", ["analytics-reporting", "competitive-battlecard-creation", "data-analysis", "data-visualization"]],
  ["opportunity", ["data-analysis", "financial-modeling", "analytics-reporting", "proposal-generation"]],
  ["forecast", ["financial-modeling", "data-analysis", "analytics-reporting", "fact-checking"]],
  ["operation", ["data-cleaning", "exploratory-data-analysis", "data-analysis", "analytics-reporting"]]
];

const dataCapabilities = [
  ["订单缺口由谁贡献", "good", "可直接分析", "order、dealer_region、brand、series", "目标数据缺失，无法直接判断目标缺口"],
  ["前链路流量是否变化", "good", "可直接分析", "register、lead、opportunity、channel、campaign", "投放成本缺失，不能计算 CPL"],
  ["中链路承接是否变差", "good", "可直接分析", "lead、opportunity、visit、test_drive", "排班和人员产能缺失"],
  ["订单端是否有阻塞", "proxy", "可用代理指标", "order、opportunity reason fields", "库存、价格、优惠政策缺失"],
  ["市场和竞品影响", "gap", "需补充数据", "当前 CSV 不包含", "需要市场大盘、竞品销量和价格数据"]
];

const objects = [
  ["register", 117],
  ["lead", 144],
  ["opportunity", 172],
  ["visit", 169],
  ["test_drive", 36],
  ["order", 84],
  ["customer", 30],
  ["dealer_region", 21]
];

const metrics = [
  ["订单量", "选定周期内去重订单数", "count_distinct(order_id)", "待 BA 确认是否排除取消订单"],
  ["交车量", "有交车时间或交车入库标记的订单数", "count_distinct(order_id where handover)", "待确认交车口径"],
  ["有效到店量", "有效 visit 事件去重数", "count_distinct(visit_id)", "待确认 visit_valid_flag 取值"],
  ["试驾量", "试驾事件去重数", "count_distinct(td_id)", "待确认删除和取消试驾过滤"],
  ["首次跟进时效", "线索或机会创建到首次跟进的分钟数", "avg(first_follow_mindiff)", "待确认使用 lead 或 oppty 口径"],
  ["订单取消率", "取消订单数 / 总订单数", "cancel_order_count / order_count", "待确认取消标记"]
];

const runSteps = [
  ["趋势模块", "订单、线索、到店和试驾的周期变化"],
  ["贡献度模块", "区域、经销商、车系、渠道的缺口贡献"],
  ["漏斗模块", "各阶段转化率和主要掉点"],
  ["时效模块", "首次跟进和关键阶段耗时"],
  ["原因模块", "战败、拒绝、取消原因排序"],
  ["洞察合成", "生成事实、推断、建议和数据限制"]
];

const insights = [
  {
    title: "订单缺口优先由经销商承接差异解释",
    body: "缺口集中在少数经销商，且这些经销商的首次跟进时效和到店转化均低于区域均值。",
    meta: ["事实", "置信度中高", "需排除库存影响"]
  },
  {
    title: "渠道结构变化可能拉低后链路质量",
    body: "社交媒体和批量导入线索占比上升，但机会到到店转化弱于自然进店和垂直网站。",
    meta: ["推断", "置信度中", "缺少投放成本"]
  },
  {
    title: "订单端取消和战败原因需要单独复核",
    body: "部分车系的取消和战败原因集中在购买计划变化、其他品牌购买和到店未试驾。",
    meta: ["事实", "置信度中", "需业务复核枚举"]
  }
];

const storyline = [
  "4 月订单低于预期，需要先把缺口拆到区域、小区、经销商和车系。",
  "前链路线索量不是唯一解释，渠道结构和机会质量变化需要同步查看。",
  "中链路承接指标显示部分经销商存在跟进慢、到店弱、试驾弱的问题。",
  "订单端存在取消和战败集中项，但库存、价格、竞品因素需要补充数据验证。",
  "建议优先干预高贡献缺口经销商，并用渠道质量和承接 SLA 做周度跟踪。"
];

const actions = [
  ["经销商承接复盘", "锁定贡献缺口 Top 经销商，复核首次跟进、邀约、到店和试驾动作。"],
  ["渠道质量校准", "对低转化渠道按活动和媒体平台拆解，调整后续资源分配。"],
  ["补充外部因素", "接入库存、价格、目标和竞品大盘数据，验证订单端原因。"]
];

let realCase = null;

const pageTitles = {
  problem: "问题工作台",
  canvas: "分析方案画布",
  data: "数据能力匹配",
  metrics: "指标与口径确认",
  run: "分析执行",
  insights: "洞察审核",
  report: "报告与行动"
};

function el(selector) {
  return document.querySelector(selector);
}

function fmt(value, suffix = "") {
  if (value === null || value === undefined) return "NA";
  if (typeof value === "number") return `${value.toLocaleString("zh-CN")}${suffix}`;
  return `${value}${suffix}`;
}

function safeRate(value) {
  return value === null || value === undefined ? "NA" : `${value}%`;
}

function renderGates(activeId = "problem") {
  el("#gateList").innerHTML = gates.map((gate) => {
    const cls = gate.done ? "done" : gate.id === activeId ? "active" : "";
    const label = gate.done ? "已确认" : gate.id === activeId ? "当前" : "等待";
    return `<div class="gate-item ${cls}"><span class="gate-dot"></span><span>${gate.name}</span><small>${label}</small></div>`;
  }).join("");
}

function setGateDone(id) {
  const gate = gates.find((item) => item.id === id);
  if (gate) gate.done = true;
  renderGates(id);
}

function showPage(id) {
  document.querySelectorAll(".page").forEach((page) => page.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
  el(`#${id}`).classList.add("active");
  document.querySelector(`[data-page="${id}"]`).classList.add("active");
  el("#pageTitle").textContent = pageTitles[id];
  const gateMap = { problem: "problem", canvas: "plan", data: "data", metrics: "metrics", run: "metrics", insights: "insights", report: "report" };
  renderGates(gateMap[id]);
}

function renderTemplates() {
  el("#templateGrid").innerHTML = templates.map((template) => `
    <article class="template-card">
      <h4>${template.name}</h4>
      <p>${template.desc}</p>
      <div class="tag-row">${template.tags.map((tag) => `<span class="tag">${tag}</span>`).join("")}</div>
    </article>
  `).join("");
}

function renderClassification() {
  el("#classificationStatus").textContent = "已生成";
  el("#classificationStatus").classList.add("done");
  el("#classificationBox").innerHTML = `
    <div class="result-line"><span>问题类型</span><strong>业绩表现诊断 + 归因解释</strong></div>
    <div class="result-line"><span>推荐 Playbook</span><strong>业绩表现诊断</strong></div>
    <div class="result-line"><span>目标指标</span><strong>${el("#metricInput").value}</strong></div>
    <div class="result-line"><span>分析范围</span><strong>${el("#scopeInput").value}</strong></div>
    <div class="result-line"><span>对比基准</span><strong>${el("#periodInput").value} | ${el("#baselineInput").value}</strong></div>
  `;
}

function renderBranches() {
  el("#hypothesisBranches").innerHTML = branches.map((branch) => `
    <article class="branch">
      <h4>${branch.title}</h4>
      <ul>${branch.items.map((item) => `<li>${item}</li>`).join("")}</ul>
    </article>
  `).join("");
}

function renderMethods() {
  el("#methodList").innerHTML = methods.map((method, idx) => `
    <article class="method-item">
      <div>
        <h4>${method[1]}</h4>
        <p>${method[2]}</p>
      </div>
      <button class="method-toggle ${idx < 5 ? "on" : ""}" aria-label="${method[1]}"></button>
    </article>
  `).join("");
  document.querySelectorAll(".method-toggle").forEach((button) => {
    button.addEventListener("click", () => button.classList.toggle("on"));
  });
}

function renderSkillRouting() {
  el("#skillRoutingList").innerHTML = skillRecommendations.map(([scenario, skillIds]) => `
    <article class="skill-route-card">
      <div class="skill-route-head">
        <strong>${scenario}</strong>
        <span>${skillIds.length} skills</span>
      </div>
      <div class="skill-chip-row">
        ${skillIds.map((id) => {
          const [label, desc] = skillCatalog[id] || [id, ""];
          return `<span class="skill-chip" title="${desc}">${id}<small>${label}</small></span>`;
        }).join("")}
      </div>
    </article>
  `).join("");
}

function renderData() {
  el("#dataCapabilityRows").innerHTML = dataCapabilities.map(([branch, type, label, source, gap]) => `
    <tr>
      <td>${branch}</td>
      <td><span class="capability ${type}">${label}</span></td>
      <td>${source}</td>
      <td>${gap}</td>
    </tr>
  `).join("");

  el("#objectInventory").innerHTML = objects.map(([name, count]) => `
    <div class="object-item"><strong>${name}</strong><span>${count} fields</span></div>
  `).join("");
}

function renderMetrics() {
  el("#metricRows").innerHTML = metrics.map(([name, definition, formula, status]) => `
    <tr>
      <td><strong>${name}</strong></td>
      <td>${definition}</td>
      <td><code>${formula}</code></td>
      <td><span class="capability proxy">${status}</span></td>
    </tr>
  `).join("");
}

function renderRunSteps(done = false) {
  el("#runModules").innerHTML = runSteps.map((step, idx) => `
    <div class="run-step ${done ? "done" : ""}">
      <div class="step-index">${idx + 1}</div>
      <div>
        <h4>${step[0]}</h4>
        <p>${step[1]}</p>
      </div>
      <span class="status-pill ${done ? "done" : ""}">${done ? "完成" : "等待"}</span>
    </div>
  `).join("");
}

function renderFunnel(metrics) {
  const max = Math.max(metrics.leads || 0, metrics.opportunities || 0, metrics.visits || 0, metrics.testDrives || 0, metrics.orders || 0);
  const stages = [
    ["Leads", metrics.leads],
    ["Oppty", metrics.opportunities],
    ["Visit", metrics.visits],
    ["TD", metrics.testDrives],
    ["Order", metrics.orders]
  ];
  el("#realFunnelChart").innerHTML = stages.map(([name, value]) => {
    const width = max ? Math.max(5, Math.round(value / max * 100)) : 0;
    return `<div style="--v: ${width}%"><span>${name}</span><strong>${fmt(value)}</strong></div>`;
  }).join("");
}

function renderKpis(metrics) {
  const cards = [
    ["线索量", metrics.leads, "去重 leads_id"],
    ["订单量", metrics.orders, `线索到订单 ${safeRate(metrics.leadToOrderRate)}`],
    ["取消率", safeRate(metrics.cancelRate), `${fmt(metrics.cancelOrders)} 个取消订单`],
    ["平均首次跟进", metrics.avgLeadFirstFollowMin, "分钟"]
  ];
  el("#realKpis").innerHTML = cards.map(([label, value, note]) => `
    <article class="kpi-card">
      <span>${label}</span>
      <strong>${fmt(value)}</strong>
      <small>${note}</small>
    </article>
  `).join("");
}

function renderMonthlyTrend(rows) {
  const recentRows = rows.slice(-8).reverse();
  el("#monthlyTrendRows").innerHTML = recentRows.map((row) => `
    <tr>
      <td>${row.month}</td>
      <td>${fmt(row.leads)}</td>
      <td>${fmt(row.orders)}</td>
      <td>${safeRate(row.leadToOrderRate)}</td>
    </tr>
  `).join("");
}

function renderBarList(items, valueField = "value", limit = 6) {
  const data = items.slice(0, limit);
  const max = Math.max(...data.map((item) => item[valueField] || 0), 1);
  return `<div class="bar-list">${data.map((item) => {
    const value = item[valueField] || 0;
    const width = Math.max(4, Math.round(value / max * 100));
    return `
      <div class="bar-row">
        <span class="bar-label" title="${item.name}">${item.name}</span>
        <span class="bar-track"><span class="bar-fill" style="--w: ${width}%"></span></span>
        <span class="bar-value">${fmt(value)}</span>
      </div>
    `;
  }).join("")}</div>`;
}

function renderDimensionCards(breakdown) {
  const cards = [
    ["订单区域 Top", renderBarList(breakdown.regionsByOrders || [])],
    ["订单经销商 Top", renderBarList(breakdown.dealersByOrders || [])],
    ["订单车系 Top", renderBarList(breakdown.seriesByOrders || [])],
    ["渠道后链路", renderBarList((breakdown.channels || []).map((item) => ({ name: item.name, value: item.orders })))],
    ["战败/拒绝原因", renderBarList(breakdown.battleFailReasons || [])],
    ["订单取消原因", renderBarList(breakdown.cancelReasons || [])]
  ];
  el("#dimensionCards").innerHTML = cards.map(([title, body]) => `
    <article class="dimension-card">
      <h4>${title}</h4>
      ${body}
    </article>
  `).join("");
}

function renderRealCase() {
  if (!realCase) return;
  const metrics = realCase.overall;
  el("#realCaseBanner").innerHTML = `
    <strong>${realCase.case.title}</strong>
    <span>${realCase.case.scope} | ${fmt(realCase.source.rows)} 行 | 使用 ${fmt(realCase.source.columnsUsed)} 个关键字段 | ETL ${realCase.source.etlBatchTime || "NA"}</span>
  `;
  el("#summarySourceStatus").textContent = "真实 CSV";
  el("#summarySourceStatus").classList.add("done");
  renderKpis(metrics);
  renderFunnel(metrics);
  renderMonthlyTrend(realCase.monthlyTrend || []);
  renderDimensionCards(realCase.dimensionBreakdown || {});
  el("#realLimitations").textContent = (realCase.limitations || []).join(" ");
  renderInsights();
  renderReport();
}

async function loadRealCase() {
  try {
    const response = await fetch("data/analysis-case.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    realCase = await response.json();
    renderRealCase();
  } catch (error) {
    el("#realCaseBanner").innerHTML = `
      <strong>真实案例数据未加载</strong>
      <span>${error.message}。请确认本地服务从 prototype 目录启动。</span>
    `;
    renderFunnel({ leads: 100, opportunities: 74, visits: 43, testDrives: 28, orders: 18 });
  }
}

function renderInsights() {
  const sourceInsights = realCase ? realCase.insights.map((item) => ({
    title: item.title,
    body: `${item.evidence} ${item.recommendation}`,
    meta: [item.type, `置信度${item.confidence}`, "真实 CSV"]
  })) : insights;

  el("#insightList").innerHTML = sourceInsights.map((item, idx) => `
    <article class="insight-card">
      <div>
        <h4>${item.title}</h4>
        <p>${item.body}</p>
        <div class="insight-meta">${item.meta.map((tag) => `<span class="tag">${tag}</span>`).join("")}</div>
      </div>
      <div class="insight-actions">
        <button class="small-button selected" data-insight="${idx}">采纳</button>
        <button class="small-button">修改</button>
        <button class="small-button">驳回</button>
      </div>
    </article>
  `).join("");
}

function renderReport() {
  const realStoryline = realCase ? [
    `本案例已读取真实 CSV：${fmt(realCase.source.rows)} 行，覆盖 register、lead、opportunity、visit、test drive、order 等链路对象。`,
    `全量漏斗为：线索 ${fmt(realCase.overall.leads)}、机会 ${fmt(realCase.overall.opportunities)}、到店 ${fmt(realCase.overall.visits)}、试驾 ${fmt(realCase.overall.testDrives)}、订单 ${fmt(realCase.overall.orders)}。`,
    `线索到订单转化率为 ${safeRate(realCase.overall.leadToOrderRate)}，订单取消率为 ${safeRate(realCase.overall.cancelRate)}，交车率为 ${safeRate(realCase.overall.handoverRate)}。`,
    `订单 Top 区域为 ${(realCase.dimensionBreakdown.regionsByOrders[0] || {}).name || "NA"}，Top 渠道为 ${(realCase.dimensionBreakdown.channels[0] || {}).name || "NA"}。`,
    "当前数据可支持链路诊断、区域/经销商/渠道/车系拆解；目标、成本、库存、价格和竞品因素需要补充数据验证。"
  ] : storyline;

  const realActions = realCase ? [
    ["优先复盘 Top 区域和经销商", "从真实订单贡献最高的区域、城市、经销商开始下钻，确认是否存在承接能力或结构性问题。"],
    ["把渠道分析升级为质量分析", "当前已能看渠道订单和转化，补充投放成本后可扩展为 CPL/CPA/ROI。"],
    ["沉淀为 Agent 标准案例", "把本次真实 CSV 的字段映射、指标口径和限制说明保存为通用 Playbook。"]
  ] : actions;

  el("#storyline").innerHTML = realStoryline.map((item) => `<li>${item}</li>`).join("");
  el("#actionList").innerHTML = realActions.map((item) => `
    <article class="action-card">
      <h4>${item[0]}</h4>
      <p>${item[1]}</p>
    </article>
  `).join("");
}

function init() {
  renderGates();
  renderTemplates();
  renderBranches();
  renderMethods();
  renderSkillRouting();
  renderData();
  renderMetrics();
  renderRunSteps();
  renderInsights();
  renderReport();
  loadRealCase();

  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => showPage(button.dataset.page));
  });

  el("#classifyBtn").addEventListener("click", renderClassification);
  el("#confirmProblemBtn").addEventListener("click", () => {
    renderClassification();
    setGateDone("problem");
    showPage("canvas");
  });
  el("#confirmPlanBtn").addEventListener("click", () => {
    setGateDone("plan");
    showPage("data");
  });
  el("#confirmDataBtn").addEventListener("click", () => {
    setGateDone("data");
    showPage("metrics");
  });
  el("#confirmMetricsBtn").addEventListener("click", () => {
    setGateDone("metrics");
    showPage("run");
  });
  el("#runAnalysisBtn").addEventListener("click", () => {
    renderRunSteps(true);
    el("#runStatus").textContent = "已完成";
    el("#runStatus").classList.add("done");
    setTimeout(() => showPage("insights"), 400);
  });
  el("#confirmInsightsBtn").addEventListener("click", () => {
    setGateDone("insights");
    showPage("report");
  });
  el("#confirmReportBtn").addEventListener("click", () => setGateDone("report"));
  el("#addBranchBtn").addEventListener("click", () => {
    branches.push({
      title: "补充外部因素验证",
      items: ["接入目标、库存、价格、竞品大盘", "将当前推断升级为验证结论", "标记报告中的数据限制"]
    });
    renderBranches();
  });
  el("#savePlaybookBtn").addEventListener("click", () => {
    el("#savePlaybookBtn").textContent = "已保存";
    setTimeout(() => {
      el("#savePlaybookBtn").textContent = "保存 Playbook";
    }, 1300);
  });
}

init();
