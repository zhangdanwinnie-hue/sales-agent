const STATUS_LABELS = {
  draft: 'Draft',
  needs_review: 'Needs review',
  approved: 'Approved',
  rejected: 'Rejected',
  superseded: 'Superseded',
};

const CLARIFY_OPTIONS = [
  { question: '北极星指标用什么？', options: ['总客流量', '有效到店', '订单量'] },
  { question: '对比基准是什么？', options: ['上月', '去年同期', '活动前 30 天'] },
  { question: '需要多深的证据链？', options: ['完整证据链', '快速判断', '仅输出数据需求'] },
];

const SKILL_REGISTRY = [
  ['exploratory-data-analysis', 'Exploratory Data Analysis', 'Data Readiness', '检查数据结构、缺失率、重复、异常值和分布。', '数据画像、质量分、异常字段、推荐下一步'],
  ['data-cleaning', 'Data Cleaning', 'Data Readiness', '处理缺失、重复、类型错误、异常值，并生成清洗日志。', '清洗策略、可用代理指标、不可分析字段'],
  ['data-analysis', 'Data Analysis', 'Evidence Pack', '做趋势、贡献度、相关性、假设检验和异常识别。', '指标结果、假设验证、置信度和限制'],
  ['sql-query-generation', 'SQL Query Generation', 'Evidence Pack', '把业务问题和指标口径转成可解释 SQL。', 'SQL、JOIN 路径、聚合逻辑、业务解释'],
  ['analytics-reporting', 'Analytics Reporting', 'Report Draft', '把 KPI、渠道贡献、漏斗和建议组织成业务报告。', '管理层摘要、渠道拆解、So what、行动建议'],
  ['data-visualization', 'Data Visualization', 'Report Draft', '选择趋势图、贡献度条形图、漏斗图或分布图。', '图表类型、图表说明、注释点'],
  ['report-generation', 'Report Generation', 'Report Draft', '生成 HTML 报告并做质量检查。', '可导出报告、图表占位、追溯说明'],
  ['crm-data-enrichment', 'CRM Data Enrichment', 'Playbook Update', '识别 CRM 字段缺口，补全客户/经销商画像。', '补字段建议、置信度、审计记录'],
  ['lead-scoring', 'Lead Scoring', 'Scenario Skill', '用于线索质量与转化效率场景，产出 Hot/Warm/Cold 分层。', '线索得分、分层、跟进动作'],
  ['customer-feedback-analysis', 'Customer Feedback Analysis', 'Scenario Skill', '用于战败原因、客户反馈、NPS/CSAT 主题提取。', '主题、趋势、代表性反馈、建议'],
  ['knowledge-graph-creation', 'Knowledge Graph Creation', 'Ontology', '把业务对象、事件和字段关系抽成三元组。', '业务对象图、关系三元组、可视化关系'],
].map(([id, name, stage, purpose, output]) => ({
  id,
  name,
  stage,
  purpose,
  output,
  input: 'Business context, semantic model, metric definition, and artifact state',
  path: `C:/Users/wangj/.codex/skills/${id}/SKILL.md`,
}));

const sqlText = `SELECT channel_type,
       SUM(CASE WHEN period = 'current' THEN visit_cnt ELSE 0 END) AS current_visit,
       SUM(CASE WHEN period = 'baseline' THEN visit_cnt ELSE 0 END) AS baseline_visit,
       current_visit - baseline_visit AS delta,
       (current_visit - baseline_visit) / SUM(delta) OVER() AS contribution
FROM sales_visit_wide
WHERE visit_date BETWEEN :baseline_start AND :current_end
GROUP BY channel_type
ORDER BY contribution ASC;`;

function artifactsFor(question) {
  return [
    {
      id: 'brief', type: 'BusinessBrief', title: 'Business Brief', status: 'approved', version: 2,
      summary: `诊断“${question}”对应的分析对象、时间范围、基准和业务目标。`,
      bullets: ['分析对象：到店/客流', '时间范围：2026-04-01 至 2026-04-30', '对比基准：2026-03-01 至 2026-03-31'],
      details: [['标准化问题', '诊断客流下降的主要渠道、客户结构和区域贡献，并给出可行动建议。'], ['业务目标', '识别拉动项和拖累项，判断新客获取与老客回店变化。'], ['BA 已确认', '北极星指标=总客流量；基准=上月；证据链=完整。']],
    },
    {
      id: 'plan', type: 'AnalysisPlan', title: 'Analysis Plan', status: 'approved', version: 3,
      summary: '用趋势、渠道贡献度、客户结构和区域承接验证 3 条核心假设。',
      bullets: ['假设 1：线上预约减少是主因', '假设 2：老客回店下滑扩大缺口', '假设 3：华东经销商承接不足'],
      details: [['验证方法', '趋势对比 + 贡献度拆解 + 客户结构拆分 + 区域经销商对标。'], ['所需指标', '客流量、自然到店、邀约到店、线上预约、新客到店、老客回店。'], ['human_edit', 'BA 可修改假设优先级，下游 Evidence Pack 会被标记为需重算。']],
    },
    {
      id: 'skills', type: 'SkillOrchestration', title: 'Skill Orchestration', status: 'needs_review', version: 1,
      summary: 'Agent 从本地 Codex skills 中选择能力，组成从澄清、取数、验证到报告沉淀的执行链。',
      bullets: ['Data Readiness：EDA + Data Cleaning', 'Evidence Pack：Data Analysis + SQL Query Generation', 'Report Draft：Analytics Reporting + Visualization + Report Generation'],
      skillIds: ['exploratory-data-analysis', 'data-cleaning', 'data-analysis', 'sql-query-generation', 'analytics-reporting', 'data-visualization', 'report-generation', 'crm-data-enrichment', 'knowledge-graph-creation'],
    },
    {
      id: 'readiness', type: 'DataReadiness', title: 'Data Readiness', status: 'approved', version: 1,
      summary: '客流、渠道和客户结构可分析；经销商 SLA 只能做代理判断。',
      bullets: ['调用 exploratory-data-analysis 生成数据画像', '调用 data-cleaning 判断缺失/重复/类型问题', '需补充数据：SLA 首跟进时长'],
      gaps: [
        { field: 'first_follow_minutes', impact: '不能严格归因经销商承接效率', workaround: '使用到店到订单转化率做代理判断', owner: '数据平台' },
        { field: 'loss_reason', impact: '不能解释试驾后流失原因', workaround: '仅输出后续数据需求', owner: 'CRM 团队' },
      ],
    },
    {
      id: 'evidence', type: 'EvidencePack', title: 'Evidence Pack', status: 'needs_review', version: 1,
      summary: '总客流下降 13.0%，主要拖累来自线上预约和自然到店。',
      bullets: ['data-analysis：线上预约贡献度 -47%', 'sql-query-generation：生成贡献度 SQL 和人话解释', '老客回店缺口需要补充 SLA 证据'],
      sql: sqlText,
      evidence: [
        ['线上预约减少是客流下降主因', '线上预约', '1560', '2150', '-590', '-47%', '高', '渠道归因使用首触渠道，未拆到活动创意。'],
        ['自然到店下降同步拖累总客流', '自然到店', '2480', '2960', '-480', '-38%', '高', '门店自然到店记录存在少量补录。'],
        ['经销商承接不足只能做代理判断', '到店到订单转化率', '31.8%', '36.9%', '-5.1pp', '-21%', '中', 'SLA 字段覆盖 62%，不能下严格归因结论。'],
      ],
    },
    {
      id: 'report', type: 'ReportDraft', title: 'Report Draft', status: 'draft', version: 1,
      summary: '面向管理层的报告草稿，等待 BA 采纳证据后生成最终 HTML。',
      bullets: ['analytics-reporting：结论、So what、行动建议', 'data-visualization：贡献度图和趋势图规格', 'report-generation：HTML 导出和质量检查'],
      report: {
        summary: '4 月总客流较 3 月下降 13.0%，主要拖累来自线上预约和自然到店。',
        evidence: '线上预约贡献度 -47%，自然到店贡献度 -38%；经销商承接归因因 SLA 覆盖不足只给代理判断。',
        action: '优先恢复线上预约投放，补充 SLA 字段，并对华东/华南重点经销商做承接复盘。',
        appendix: '数据时间：2026-04-01 至 2026-04-30；基准：2026-03-01 至 2026-03-31；口径版本：Metric v2.0。',
      },
    },
    {
      id: 'playbook', type: 'PlaybookUpdate', title: 'Playbook Update', status: 'draft', version: 1,
      summary: '本次可沉淀：客流下降场景中客户结构应默认进入核心验证路径。',
      bullets: ['回写：客流下降分析 Playbook v1.3', 'knowledge-graph-creation：更新业务对象/事件关系', 'crm-data-enrichment：补充经销商承接字段需求'],
    },
  ];
}

const seedQuestion = '近期客流下降明显，想分析是哪些渠道在下降，以及新客获取和老客回店的表现变化。';
const threads = [
  { id: 'traffic-channel', title: '客流下降渠道分析', updatedAt: '今天 14:52', status: 'Evidence review', source: 'Sales 宽表 Demo', question: seedQuestion, clarifyAnswers: ['总客流量', '上月', '完整证据链'], history: [{ actor: 'BA', text: seedQuestion }, { actor: 'AI', text: '我先不直接出报表。先确认北极星指标、对比基准和证据链深度，再生成 Business Brief。' }], artifacts: artifactsFor(seedQuestion) },
  { id: 'order-april', title: '4 月订单下降原因分析', updatedAt: '昨天 18:10', status: 'Plan review', source: '企业语义模型', question: '为什么 4 月订单下降？请判断是渠道结构、区域经销商承接，还是转化效率的问题。', clarifyAnswers: ['订单量', '上月', '完整证据链'], history: [{ actor: 'BA', text: '为什么 4 月订单下降？请判断是渠道结构、区域经销商承接，还是转化效率的问题。' }, { actor: 'AI', text: '我会先生成 Business Brief 和 Analysis Plan，确认后再计算漏斗与贡献度。' }], artifacts: artifactsFor('为什么 4 月订单下降') },
];

let activeThreadId = threads[0].id;
let expandedArtifacts = new Set(['evidence']);
let drawerContext = null;

const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value).replace(/[&<>]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[char]));
const skillById = (id) => SKILL_REGISTRY.find((skill) => skill.id === id);
const activeThread = () => threads.find((thread) => thread.id === activeThreadId);

function init() {
  $('#threadSearch').addEventListener('input', renderThreads);
  $('#newThreadButton').addEventListener('click', () => { $('#composerInput').value = seedQuestion; sendComposer(); });
  $('#sendButton').addEventListener('click', sendComposer);
  $('#composerInput').addEventListener('keydown', (event) => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) sendComposer(); });
  $('#openContextButton').addEventListener('click', () => openDrawer('metric'));
  $('#closeDrawerButton').addEventListener('click', closeDrawer);
  $('#exportReportButton').addEventListener('click', exportReport);
  $('#uploadCsvButton').addEventListener('click', () => addAiMessage('CSV 上传入口已记录；真实版本会触发字段识别和语义映射。'));
  renderAll();
}

function renderAll() {
  renderThreads();
  renderHeader();
  renderStream();
  renderDrawer();
  if (window.lucide) lucide.createIcons();
}

function renderThreads() {
  const query = $('#threadSearch').value.trim().toLowerCase();
  const filtered = threads.filter((thread) => `${thread.title} ${thread.question} ${thread.source}`.toLowerCase().includes(query));
  $('#threadList').innerHTML = filtered.map((thread) => `
    <button class='thread-card ${thread.id === activeThreadId ? 'active' : ''}' data-thread-id='${thread.id}'>
      <div class='thread-meta'><span class='tag ${thread.status.includes('review') ? 'amber' : 'neutral'}'>${thread.status}</span><span class='tag neutral'>${thread.source}</span></div>
      <strong>${esc(thread.title)}</strong><p>${esc(thread.question)}</p><p>${thread.updatedAt}</p>
    </button>`).join('');
  document.querySelectorAll('[data-thread-id]').forEach((button) => button.addEventListener('click', () => { activeThreadId = button.dataset.threadId; expandedArtifacts = new Set(['brief']); closeDrawer(); renderAll(); }));
}

function renderHeader() {
  const thread = activeThread();
  $('#threadTitle').textContent = thread.title;
  $('#dataSourceSelect').value = thread.source;
}

function renderStream() {
  const thread = activeThread();
  $('#threadStream').innerHTML = [...thread.history.map(renderMessage), renderClarification(thread), ...thread.artifacts.map(renderArtifact)].join('');
  bindStreamEvents();
}

function renderMessage(message) {
  const isUser = message.actor === 'BA';
  return `<article class='message ${isUser ? 'user' : ''}'><div class='avatar'>${isUser ? 'BA' : 'AI'}</div><div class='bubble'><p>${esc(message.text)}</p></div></article>`;
}

function renderClarification(thread) {
  return `<article class='message'><div class='avatar'>AI</div><div class='bubble'><p>在进入正式分析前，我需要锁定三个澄清项。回答后我只会先生成 Business Brief，不会直接跳到报表。</p><div class='clarify-grid'>${CLARIFY_OPTIONS.map((item, index) => `<div class='clarify-card'><strong>${item.question}</strong><div class='chip-row'>${item.options.map((option) => `<button class='chip-button ${thread.clarifyAnswers[index] === option ? 'selected' : ''}' data-clarify-index='${index}' data-clarify-value='${option}'>${option}</button>`).join('')}</div></div>`).join('')}</div></div></article>`;
}

function renderArtifact(artifact) {
  const expanded = expandedArtifacts.has(artifact.id);
  return `<article class='message'><div class='avatar'>AI</div><div class='bubble'><section class='artifact-card ${expanded ? 'expanded' : ''}' data-artifact-id='${artifact.id}'>
    <div class='artifact-header'><div class='artifact-title'><div class='artifact-meta'><span class='status-pill ${artifact.status}'>${STATUS_LABELS[artifact.status]}</span><span class='version-pill'>v${artifact.version}</span><span class='tag'>${artifact.type}</span></div><h3>${artifact.title}</h3><p>${esc(artifact.summary)}</p></div><button class='artifact-action' data-toggle-artifact='${artifact.id}'><span data-icon='${expanded ? 'chevron-up' : 'chevron-down'}'></span><span>${expanded ? 'Collapse' : 'Expand'}</span></button></div>
    <ul class='artifact-summary'>${artifact.bullets.map((bullet) => `<li><span data-icon='check'></span>${esc(bullet)}</li>`).join('')}</ul>
    <div class='artifact-details'>${renderArtifactDetails(artifact)}</div><div class='artifact-actions'>${renderActions(artifact)}</div>
  </section></div></article>`;
}

function renderArtifactDetails(artifact) {
  if (artifact.details) return `<div class='detail-grid'>${artifact.details.map(([label, value]) => `<div class='detail-box'><span>${label}</span><strong>${esc(value)}</strong></div>`).join('')}</div>${artifact.type === 'AnalysisPlan' ? skillChips(['data-analysis', 'sql-query-generation', 'knowledge-graph-creation']) : ''}`;
  if (artifact.type === 'SkillOrchestration') return `<div class='skill-grid'>${artifact.skillIds.map((id) => { const skill = skillById(id); return `<div class='skill-card'><span>${skill.stage}</span><strong>${skill.name}</strong><p>${skill.purpose}</p></div>`; }).join('')}</div>`;
  if (artifact.type === 'DataReadiness') return `<div class='detail-grid'>${artifact.gaps.map((gap) => `<div class='gap-card'><span>Data Gap Card</span><strong>${gap.field}</strong><p>影响：${gap.impact}</p><p>替代方案：${gap.workaround}</p><p>Owner：${gap.owner}</p></div>`).join('')}</div>${skillChips(['exploratory-data-analysis', 'data-cleaning'])}`;
  if (artifact.type === 'EvidencePack') return `<div class='evidence-grid'>${artifact.evidence.map((item) => `<div class='evidence-box'><span>Evidence Card</span><strong>${item[0]}</strong><p>${item[1]}: ${item[2]} vs ${item[3]}, 变化 ${item[4]}, 贡献度 ${item[5]}</p><p>置信度：${item[6]}</p><p>限制：${item[7]}</p></div>`).join('')}</div>${skillChips(['data-analysis', 'sql-query-generation'])}`;
  if (artifact.type === 'ReportDraft') return `<div class='report-grid'>${Object.entries(artifact.report).map(([key, value]) => `<div class='report-box'><span>${key}</span><p>${esc(value)}</p></div>`).join('')}</div>${skillChips(['analytics-reporting', 'data-visualization', 'report-generation'])}`;
  return `<div class='detail-box'><span>Playbook Update</span><p>${esc(artifact.summary)}</p></div>${skillChips(['crm-data-enrichment', 'knowledge-graph-creation', 'customer-feedback-analysis'])}`;
}

function skillChips(ids) {
  return `<div class='skill-chip-row'>${ids.map((id) => `<button class='skill-chip' data-open-skill='${id}'><span data-icon='sparkles'></span>${id}</button>`).join('')}</div>`;
}

function renderActions(artifact) {
  const actions = [];
  if (artifact.status !== 'approved') actions.push(`<button class='artifact-action primary' data-approve='${artifact.id}'><span data-icon='check-circle'></span>Approve</button>`);
  actions.push(`<button class='artifact-action' data-regenerate='${artifact.id}'><span data-icon='refresh-cw'></span>Regenerate</button>`);
  actions.push(`<button class='artifact-action danger' data-reject='${artifact.id}'><span data-icon='x-circle'></span>Reject</button>`);
  if (artifact.type === 'AnalysisPlan') actions.push(`<button class='artifact-action' data-edit-plan='${artifact.id}'><span data-icon='pencil'></span>修改假设</button>`);
  if (artifact.type === 'SkillOrchestration') actions.push(`<button class='artifact-action' data-open-drawer='skills'><span data-icon='sparkles'></span>Skill Registry</button>`);
  if (artifact.type === 'DataReadiness') actions.push(`<button class='artifact-action' data-open-drawer='lineage'><span data-icon='database'></span>字段映射</button>`);
  if (artifact.type === 'EvidencePack') actions.push(`<button class='artifact-action' data-open-drawer='sql'><span data-icon='file-code-2'></span>SQL</button><button class='artifact-action' data-open-drawer='metric'><span data-icon='book-open'></span>指标口径</button><button class='artifact-action' data-more-analysis='${artifact.id}'><span data-icon='list-plus'></span>要求补充分析</button>`);
  if (artifact.type === 'ReportDraft') actions.push(`<button class='artifact-action' data-open-drawer='report'><span data-icon='file-text'></span>Preview</button><button class='artifact-action primary' data-export-report><span data-icon='download'></span>Export HTML</button>`);
  if (artifact.type === 'PlaybookUpdate') actions.push(`<button class='artifact-action' data-open-drawer='playbook'><span data-icon='blocks'></span>回写位置</button>`);
  return actions.join('');
}

function bindStreamEvents() {
  document.querySelectorAll('[data-clarify-index]').forEach((button) => button.addEventListener('click', () => { activeThread().clarifyAnswers[Number(button.dataset.clarifyIndex)] = button.dataset.clarifyValue; addAiMessage(`已记录澄清项：${button.dataset.clarifyValue}`); }));
  document.querySelectorAll('[data-toggle-artifact]').forEach((button) => button.addEventListener('click', () => { const id = button.dataset.toggleArtifact; expandedArtifacts.has(id) ? expandedArtifacts.delete(id) : expandedArtifacts.add(id); renderAll(); }));
  document.querySelectorAll('[data-approve]').forEach((button) => button.addEventListener('click', () => { setStatus(button.dataset.approve, 'approved'); addAiMessage('BA 已确认该 Artifact。Agent 可以继续推进下一步。'); }));
  document.querySelectorAll('[data-reject]').forEach((button) => button.addEventListener('click', () => { setStatus(button.dataset.reject, 'rejected'); addAiMessage('BA 驳回了该 Artifact，Agent 需要重新生成。'); }));
  document.querySelectorAll('[data-regenerate]').forEach((button) => button.addEventListener('click', () => regenerate(button.dataset.regenerate)));
  document.querySelectorAll('[data-edit-plan]').forEach((button) => button.addEventListener('click', editPlan));
  document.querySelectorAll('[data-more-analysis]').forEach((button) => button.addEventListener('click', () => { const artifact = findArtifact(button.dataset.moreAnalysis); artifact.status = 'needs_review'; artifact.bullets.push('新增补充分析请求：下钻华东/华南重点经销商。'); addAiMessage('已追加补充分析请求，并保留当前 Evidence Pack。'); }));
  document.querySelectorAll('[data-open-drawer]').forEach((button) => button.addEventListener('click', () => openDrawer(button.dataset.openDrawer)));
  document.querySelectorAll('[data-open-skill]').forEach((button) => button.addEventListener('click', () => openDrawer('skill', button.dataset.openSkill)));
  document.querySelectorAll('[data-export-report]').forEach((button) => button.addEventListener('click', exportReport));
}

function findArtifact(id) { return activeThread().artifacts.find((artifact) => artifact.id === id); }
function setStatus(id, status) { findArtifact(id).status = status; renderAll(); }
function regenerate(id) { const artifact = findArtifact(id); artifact.version += 1; artifact.status = 'needs_review'; artifact.summary += '（已按 BA 反馈重新生成）'; expandedArtifacts.add(id); addAiMessage(`${artifact.title} 已生成 v${artifact.version}，旧版本保留在版本记录中。`); }
function editPlan() { const plan = findArtifact('plan'); const evidence = findArtifact('evidence'); plan.version += 1; plan.status = 'needs_review'; plan.bullets[1] = '假设 2：客户结构变化应作为核心验证路径'; plan.details.push(['human_edit', 'BA 修改假设优先级，客户结构从次要变为核心。']); evidence.status = 'draft'; addAiMessage('BA 修改了 Analysis Plan。Evidence Pack 已标记为需重算，避免旧结论继续被采纳。'); }
function addAiMessage(text) { activeThread().history.push({ actor: 'AI', text }); renderAll(); $('#threadStream').scrollTop = $('#threadStream').scrollHeight; }

function sendComposer() {
  const input = $('#composerInput');
  const text = input.value.trim();
  if (!text) return;
  const isNewQuestion = /为什么|下降|分析|评估|诊断|渠道|订单|客流|线索/.test(text);
  if (isNewQuestion) {
    const id = `thread-${Date.now()}`;
    threads.unshift({ id, title: text.slice(0, 18), updatedAt: '刚刚', status: 'Clarifying', source: $('#dataSourceSelect').value, question: text, clarifyAnswers: ['总客流量', '上月', '完整证据链'], history: [{ actor: 'BA', text }, { actor: 'AI', text: '我先追问关键澄清项，并只生成 Business Brief；不会直接跳到数据分析或报表。' }], artifacts: artifactsFor(text) });
    activeThreadId = id;
    expandedArtifacts = new Set(['brief']);
  } else {
    activeThread().history.push({ actor: 'BA', text });
    activeThread().history.push({ actor: 'AI', text: '已记录追加要求。我会将其作为当前 Artifact 的 human_edit，并在下次生成时保留版本记录。' });
  }
  input.value = '';
  renderAll();
  $('#threadStream').scrollTop = $('#threadStream').scrollHeight;
}

function openDrawer(type, skillId) { drawerContext = { type, skillId }; renderDrawer(); }
function closeDrawer() { drawerContext = null; renderDrawer(); }
function titleFor(type) { return { sql: 'SQL / Calculation Logic', metric: 'Metric Definitions', lineage: 'Field Mapping / Data Lineage', report: 'Report Preview', playbook: 'Playbook Update Target', skills: 'Skill Registry', skill: 'Skill Detail' }[type] || 'Context'; }

function renderDrawer() {
  $('.thread-app').classList.toggle('drawer-open', !!drawerContext);
  if (!drawerContext) return;
  $('#drawerEyebrow').textContent = 'Context Drawer';
  $('#drawerTitle').textContent = titleFor(drawerContext.type);
  $('#drawerBody').innerHTML = drawerBody(drawerContext.type);
  if (window.lucide) lucide.createIcons();
}

function drawerBody(type) {
  const evidence = findArtifact('evidence');
  const report = findArtifact('report');
  if (type === 'skills') return `<section class='drawer-section'><h4>Agent Skill Registry</h4><p>这些能力来自 C:/Users/wangj/.codex/skills。Agent 会按 Artifact 阶段选择并记录调用理由。</p><table class='data-table'><thead><tr><th>Skill</th><th>Stage</th><th>Output</th></tr></thead><tbody>${SKILL_REGISTRY.map((skill) => `<tr><td>${skill.id}</td><td>${skill.stage}</td><td>${skill.output}</td></tr>`).join('')}</tbody></table></section>`;
  if (type === 'skill') { const skill = skillById(drawerContext.skillId); return `<section class='drawer-section'><h4>${skill.name}</h4><p>${skill.purpose}</p></section><section class='drawer-section'><h4>输入 / 输出</h4><p><strong>Input:</strong> ${skill.input}</p><p><strong>Output:</strong> ${skill.output}</p><p><strong>Source:</strong> ${skill.path}</p></section>`; }
  if (type === 'sql') return `<section class='drawer-section'><h4>SQL</h4><pre class='code-block'>${esc(evidence.sql)}</pre></section><section class='drawer-section'><h4>人话解释</h4><p>按渠道聚合本期与基期客流，计算差值，并用单渠道差值除以总差值形成贡献度。负贡献代表拖累总客流，正贡献代表抵消下降。</p></section>`;
  if (type === 'metric') return `<section class='drawer-section'><h4>指标口径</h4><table class='data-table'><thead><tr><th>指标</th><th>定义</th><th>版本</th></tr></thead><tbody><tr><td>总客流量</td><td>有效到店人次，按 visit_date 统计。</td><td>v2.0</td></tr><tr><td>线上预约</td><td>预约渠道产生且确认到店的 visit。</td><td>v1.4</td></tr><tr><td>到店到订单转化率</td><td>有效订单数 / 到店客户数。</td><td>v1.4</td></tr></tbody></table></section>`;
  if (type === 'lineage') return `<section class='drawer-section'><h4>字段映射</h4><table class='data-table'><thead><tr><th>业务对象</th><th>字段</th><th>覆盖</th><th>说明</th></tr></thead><tbody><tr><td>visit</td><td>visit_id, visit_date, visit_type</td><td>94%</td><td>可直接分析</td></tr><tr><td>leads</td><td>lead_id, channel, campaign</td><td>96%</td><td>可直接分析</td></tr><tr><td>SLA</td><td>first_follow_minutes</td><td>62%</td><td>需补充数据</td></tr></tbody></table></section>`;
  if (type === 'report') return `<section class='drawer-section'><h4>HTML 报告预览</h4><p><strong>摘要：</strong>${report.report.summary}</p><p><strong>证据：</strong>${report.report.evidence}</p><p><strong>行动：</strong>${report.report.action}</p><p><strong>Appendix：</strong>${report.report.appendix}</p><button class='primary-button' onclick='exportReport()'><span data-icon='download'></span>Export HTML</button></section>`;
  if (type === 'playbook') return `<section class='drawer-section'><h4>回写位置</h4><p>目标资产：客流下降分析 Playbook v1.3</p><p>回写内容：客户结构默认进入核心验证路径；SLA 覆盖不足时生成 Data Gap Card。</p><p>来源：BA human_edit + Evidence Pack 审核反馈。</p></section>`;
  return `<section class='drawer-section'><h4>Context</h4><p>选择 Artifact 中的 SQL、指标口径、字段映射或报告预览查看详情。</p></section>`;
}

function exportReport() {
  const thread = activeThread();
  const report = findArtifact('report').report;
  const html = `<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>${thread.title}</title><body style='font-family:Arial,Microsoft YaHei,sans-serif;line-height:1.6;padding:32px;color:#18212f'><h1>${thread.title}</h1><p><strong>摘要：</strong>${report.summary}</p><p><strong>证据：</strong>${report.evidence}</p><p><strong>行动：</strong>${report.action}</p><p><strong>Appendix：</strong>${report.appendix}</p></body></html>`;
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${thread.id}-report.html`;
  link.click();
  URL.revokeObjectURL(url);
}

window.exportReport = exportReport;
document.addEventListener('DOMContentLoaded', init);
