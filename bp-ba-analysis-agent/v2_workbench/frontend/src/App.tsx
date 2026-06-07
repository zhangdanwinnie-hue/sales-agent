import {
  CheckCircle2,
  Database,
  Download,
  FileText,
  LayoutDashboard,
  MessageSquare,
  Network,
  Plus,
  Save,
  Sparkles,
  Star,
  Table2,
  Trash2
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api } from "./api";
import type {
  Artifact,
  AgentAction,
  CEAReport,
  ChatResponse,
  ConversationMessage,
  ContributionRow,
  DataAnalysis,
  Hypothesis,
  MetricNode,
  SqlReview,
  Stage,
  Task,
  TaskInput
} from "./types";

type Page = "task_center" | "analysis_workbench" | "data_insight" | "report_output" | "capability_assets";
type AgentTab = "chat" | "artifacts" | "context";

const pageMap: Record<Stage, Page> = {
  task_creation: "task_center",
  analysis_design: "analysis_workbench",
  data_insight: "data_insight",
  report_generation: "report_output"
};

const defaultInput: TaskInput = {
  task_name: "客流下降原因分析",
  business_question: "近期客流下降明显，想分析是哪些渠道在下降，以及新客获取和老客回店的表现变化。",
  analysis_purpose: "定位客流下降的核心原因，并给出可执行改善动作。",
  time_range: "2026/01/01 - 2026/03/31",
  comparison_period: "2025/10/01 - 2025/12/31",
  data_source: "sales_demo"
};

const defaultReport: CEAReport = {
  conclusion: "客流下降主要由高意向线索减少和到店转化下降共同驱动。",
  evidence: "渠道贡献度显示自然流量和区域活动线索的负贡献最高，visit/oppty 转化率同步下降。",
  action: "优先修复高意向线索供给，针对下降区域补充邀约动作，并建立周度漏斗监控。"
};

function App() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [currentTask, setCurrentTask] = useState<Task | null>(null);
  const [page, setPage] = useState<Page>("task_center");
  const [agentTab, setAgentTab] = useState<AgentTab>("chat");
  const [form, setForm] = useState<TaskInput>(defaultInput);
  const [dataAnalysis, setDataAnalysis] = useState<DataAnalysis | null>(null);
  const [report, setReport] = useState<CEAReport>(defaultReport);
  const [catalog, setCatalog] = useState<Record<string, string[]> | null>(null);
  const [semantic, setSemantic] = useState<Record<string, unknown> | null>(null);
  const [assets, setAssets] = useState<Record<string, unknown> | null>(null);
  const [exportMessage, setExportMessage] = useState("");
  const [chatActions, setChatActions] = useState<AgentAction[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    void loadInitial();
  }, []);

  useEffect(() => {
    if (!currentTask) return;
    setForm(taskToInput(currentTask));
    setReport(currentTask.report ?? defaultReport);
    setPage(pageMap[currentTask.current_page] ?? "task_center");
  }, [currentTask?.task_id]);

  useEffect(() => {
    if (page === "data_insight" && currentTask) {
      void loadDataAnalysis(currentTask.task_id);
    }
  }, [page, currentTask?.task_id]);

  const followups = useMemo(() => localFollowups(form), [form]);
  const statusText = currentTask ? statusLabel(currentTask.status) : "未选择任务";

  async function loadInitial() {
    try {
      const [taskData, catalogData, semanticData, assetData] = await Promise.all([
        api<{ tasks: Task[]; stats: Record<string, number> }>("/api/tasks"),
        api<Record<string, string[]>>("/api/catalog"),
        api<Record<string, unknown>>("/api/semantic-state"),
        api<Record<string, unknown>>("/api/data-assets")
      ]);
      setTasks(taskData.tasks);
      setCurrentTask(taskData.tasks[0] ?? null);
      setCatalog(catalogData);
      setSemantic(semanticData);
      setAssets(assetData);
    } catch (err) {
      setError(errorText(err));
    }
  }

  async function reloadTasks(preferredId?: string) {
    const data = await api<{ tasks: Task[]; stats: Record<string, number> }>("/api/tasks");
    setTasks(data.tasks);
    const id = preferredId ?? currentTask?.task_id;
    setCurrentTask(data.tasks.find((task) => task.task_id === id) ?? data.tasks[0] ?? null);
  }

  function patchCurrent(patch: Partial<Task>) {
    if (!currentTask) return;
    const next = { ...currentTask, ...patch };
    setCurrentTask(next);
    setTasks((items) => items.map((item) => (item.task_id === next.task_id ? next : item)));
  }

  async function createTask() {
    try {
      const data = await api<{ task: Task }>("/api/tasks", { method: "POST", body: JSON.stringify(form) });
      setCurrentTask(data.task);
      await reloadTasks(data.task.task_id);
      setAgentTab("artifacts");
      setPage("task_center");
    } catch (err) {
      setError(errorText(err));
    }
  }

  async function openTask(taskId: string) {
    try {
      const data = await api<{ task: Task }>(`/api/tasks/${taskId}`);
      setCurrentTask(data.task);
      setDataAnalysis(null);
    } catch (err) {
      setError(errorText(err));
    }
  }

  async function saveInput(confirm = false) {
    try {
      let task = currentTask;
      if (!task) {
        const created = await api<{ task: Task }>("/api/tasks", { method: "POST", body: JSON.stringify(form) });
        task = created.task;
      }
      const path = confirm ? "input/confirm" : "input/update";
      const data = await api<{ task: Task }>(`/api/tasks/${task.task_id}/${path}`, {
        method: "POST",
        body: JSON.stringify(form)
      });
      setCurrentTask(data.task);
      await reloadTasks(data.task.task_id);
      if (confirm) {
        setPage("analysis_workbench");
        setAgentTab("artifacts");
      }
    } catch (err) {
      setError(errorText(err));
    }
  }

  async function saveDesign(confirm = false) {
    if (!currentTask) return;
    try {
      const payload = {
        selected_dimensions: currentTask.selected_dimensions,
        hypotheses: currentTask.hypotheses
      };
      const data = await api<{ task: Task }>(`/api/tasks/${currentTask.task_id}/analysis-design/update`, {
        method: "POST",
        body: JSON.stringify(payload)
      });
      setCurrentTask(data.task);
      if (confirm) {
        const confirmed = await api<{ task: Task; analysis: DataAnalysis }>(
          `/api/tasks/${data.task.task_id}/analysis-design/confirm`,
          {
            method: "POST",
            body: JSON.stringify({ confirmed_by: "BA User", feedback: "确认分析思路配置。" })
          }
        );
        setCurrentTask(confirmed.task);
        setDataAnalysis(confirmed.analysis);
        setPage("data_insight");
        setAgentTab("artifacts");
      }
      await reloadTasks(data.task.task_id);
    } catch (err) {
      setError(errorText(err));
    }
  }

  async function loadDataAnalysis(taskId: string) {
    try {
      setDataAnalysis(await api<DataAnalysis>(`/api/tasks/${taskId}/data-analysis`));
    } catch (err) {
      setError(errorText(err));
    }
  }

  async function confirmInsight() {
    if (!currentTask) return;
    try {
      const data = await api<{ task: Task }>(`/api/tasks/${currentTask.task_id}/data-insight/confirm`, {
        method: "POST",
        body: JSON.stringify({ confirmed_by: "BA User", feedback: "确认数据洞察。" })
      });
      setCurrentTask(data.task);
      await reloadTasks(data.task.task_id);
      setPage("report_output");
      setAgentTab("artifacts");
    } catch (err) {
      setError(errorText(err));
    }
  }

  async function saveReport() {
    if (!currentTask) return;
    try {
      const data = await api<{ task: Task }>(`/api/tasks/${currentTask.task_id}/report/update`, {
        method: "POST",
        body: JSON.stringify({ report })
      });
      setCurrentTask(data.task);
      await reloadTasks(data.task.task_id);
      setAgentTab("artifacts");
    } catch (err) {
      setError(errorText(err));
    }
  }

  async function exportReport(format: "html" | "markdown" | "json") {
    if (!currentTask) return;
    try {
      await saveReport();
      const data = await api<{ file_name: string; download_url: string; format: string }>(
        `/api/tasks/${currentTask.task_id}/report/export`,
        { method: "POST", body: JSON.stringify({ format, report }) }
      );
      setExportMessage(`已导出 ${data.file_name}`);
    } catch (err) {
      setError(errorText(err));
    }
  }

  async function sendChat(messageText: string, onDelta: (chunk: string) => void) {
    const payload = {
      message: messageText,
      active_page: currentTask?.current_page ?? "task_creation",
      allow_task_update: true,
      client_context: { page, form, report }
    };
    if (!currentTask) {
      const data = await api<ChatResponse>("/api/chat/start", { method: "POST", body: JSON.stringify(payload) });
      onDelta(data.assistant_message.content);
      applyChatResponse(data);
      return;
    }

    const response = await fetch(`/api/tasks/${currentTask.task_id}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok || !response.body) {
      throw new Error(await response.text());
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalResponse: ChatResponse | null = null;
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";
      for (const event of events) {
        const line = event
          .split("\n")
          .find((item) => item.startsWith("data: "));
        if (!line) continue;
        const payload = JSON.parse(line.slice(6));
        if (payload.type === "delta") {
          onDelta(payload.content);
        }
        if (payload.type === "final") {
          finalResponse = payload.response as ChatResponse;
        }
      }
    }
    if (finalResponse) {
      applyChatResponse(finalResponse);
    }
  }

  function applyChatResponse(data: ChatResponse) {
    setCurrentTask(data.task);
    setReport(data.task.report ?? defaultReport);
    setDataAnalysis(null);
    setChatActions(data.actions);
    setAgentTab("chat");
    setTasks((items) => {
      const exists = items.some((item) => item.task_id === data.task.task_id);
      return exists ? items.map((item) => (item.task_id === data.task.task_id ? data.task : item)) : [data.task, ...items];
    });
    if (data.next_page) {
      setPage(pageMap[data.next_page]);
    }
  }

  const isBAWorkspace = page === "analysis_workbench" || page === "data_insight" || page === "report_output";

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <LayoutDashboard size={18} />
          <span>BP BA Agent V2</span>
        </div>
        <div className="task-context">
          <span>{currentTask?.task_name ?? "新任务"}</span>
          <strong>{statusText}</strong>
          <span>{currentTask?.business_question ?? form.business_question}</span>
        </div>
      </header>

      <div className="workspace">
        <aside className="side-menu" aria-label="主导航">
          <NavButton active={page === "task_center"} icon={<Sparkles size={16} />} label="任务中心" onClick={() => setPage("task_center")} />
          <NavButton active={page === "analysis_workbench"} icon={<Network size={16} />} label="BA 分析" onClick={() => setPage("analysis_workbench")} />
          <NavButton active={page === "data_insight"} icon={<Table2 size={16} />} label="数据洞察" onClick={() => setPage("data_insight")} />
          <NavButton active={page === "report_output"} icon={<FileText size={16} />} label="报告产出" onClick={() => setPage("report_output")} />
          <NavButton active={page === "capability_assets"} icon={<Database size={16} />} label="能力资产" onClick={() => setPage("capability_assets")} />
        </aside>

        <main className="main-workbench">
          {error && (
            <div className="alert">
              <span>{error}</span>
              <button onClick={() => setError("")}>关闭</button>
            </div>
          )}

          {page === "task_center" && (
            <TaskCenter
              tasks={tasks}
              currentTask={currentTask}
              form={form}
              followups={followups}
              setForm={setForm}
              createTask={createTask}
              openTask={openTask}
              saveDraft={() => saveInput(false)}
              confirmInput={() => saveInput(true)}
            />
          )}
          {isBAWorkspace && (
            <BAAnalysisModule
              page={page}
              currentTask={currentTask}
              form={form}
              actions={chatActions}
              sendChat={sendChat}
              dataAnalysis={dataAnalysis}
              loadDataAnalysis={loadDataAnalysis}
              patchCurrent={patchCurrent}
              saveDesign={() => saveDesign(false)}
              confirmDesign={() => saveDesign(true)}
              confirmInsight={confirmInsight}
              report={report}
              setReport={setReport}
              saveReport={saveReport}
              exportReport={exportReport}
              exportMessage={exportMessage}
            />
          )}
          {page === "capability_assets" && <CapabilityAssets catalog={catalog} semantic={semantic} assets={assets} />}
        </main>
      </div>
    </div>
  );
}

function NavButton({ active, icon, label, onClick }: { active: boolean; icon: ReactNode; label: string; onClick: () => void }) {
  return (
    <button className={active ? "nav-button active" : "nav-button"} onClick={onClick}>
      {icon}
      <span>{label}</span>
    </button>
  );
}

function BAAnalysisModule({
  page,
  currentTask,
  form,
  actions,
  sendChat,
  dataAnalysis,
  loadDataAnalysis,
  patchCurrent,
  saveDesign,
  confirmDesign,
  confirmInsight,
  report,
  setReport,
  saveReport,
  exportReport,
  exportMessage
}: {
  page: Page;
  currentTask: Task | null;
  form: TaskInput;
  actions: AgentAction[];
  sendChat: (messageText: string, onDelta: (chunk: string) => void) => Promise<void>;
  dataAnalysis: DataAnalysis | null;
  loadDataAnalysis: (taskId: string) => Promise<void>;
  patchCurrent: (patch: Partial<Task>) => void;
  saveDesign: () => void;
  confirmDesign: () => void;
  confirmInsight: () => void;
  report: CEAReport;
  setReport: (report: CEAReport) => void;
  saveReport: () => void;
  exportReport: (format: "html" | "markdown" | "json") => void;
  exportMessage: string;
}) {
  return (
    <section className="ba-analysis-module">
      <div className="ba-module-header">
        <div>
          <h1>BA Copilot 分析工作台</h1>
          <p>通过对话澄清需求、确认分析思路、生成洞察和报告；三个 Agent 的输入输出会同步沉淀为模块化产物。</p>
        </div>
        <div className="stage-pills">
          <span className={page === "analysis_workbench" ? "stage-pill active" : "stage-pill"}>1 分析设计 Agent</span>
          <span className={page === "data_insight" ? "stage-pill active" : "stage-pill"}>2 数据洞察 Agent</span>
          <span className={page === "report_output" ? "stage-pill active" : "stage-pill"}>3 报告生成 Agent</span>
        </div>
      </div>

      <div className="ba-copilot-layout">
        <BACopilotGuide currentTask={currentTask} form={form} actions={actions} sendChat={sendChat} />
        <div className="ba-output-workbench">
          <AgentModuleBoard task={currentTask} artifacts={currentTask?.artifacts ?? []} dataAnalysis={dataAnalysis} report={report} />
          {page === "analysis_workbench" && currentTask && (
            <AnalysisWorkbench currentTask={currentTask} patchCurrent={patchCurrent} saveDesign={saveDesign} confirmDesign={confirmDesign} />
          )}
          {page === "analysis_workbench" && !currentTask && <EmptyState text="可以先在左侧 Copilot 输入一句业务问题，我会自动创建任务并生成分析设计。" />}
          {page === "data_insight" && currentTask && (
            <DataInsightWorkbench analysis={dataAnalysis} refresh={() => loadDataAnalysis(currentTask.task_id)} confirmInsight={confirmInsight} />
          )}
          {page === "data_insight" && !currentTask && <EmptyState text="可以先通过 Copilot 创建任务，再进入数据洞察。" />}
          {page === "report_output" && currentTask && (
            <ReportWorkbench report={report} setReport={setReport} saveReport={saveReport} exportReport={exportReport} exportMessage={exportMessage} />
          )}
          {page === "report_output" && !currentTask && <EmptyState text="可以先通过 Copilot 生成分析任务和洞察，再产出报告。" />}
        </div>
      </div>
    </section>
  );
}

function BACopilotGuide({
  currentTask,
  form,
  actions,
  sendChat
}: {
  currentTask: Task | null;
  form: TaskInput;
  actions: AgentAction[];
  sendChat: (messageText: string, onDelta: (chunk: string) => void) => Promise<void>;
}) {
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [pendingUser, setPendingUser] = useState<ConversationMessage | null>(null);
  const [localError, setLocalError] = useState("");
  const messages = currentTask?.messages ?? [
    {
      id: "draft",
      role: "agent" as const,
      content: "像 Codex Plan 模式一样，先告诉我你要分析的业务问题。我会追问口径、生成分析计划，并把中间产物同步到右侧工作台。",
      stage: "task_creation" as const,
      created_at: ""
    }
  ];
  const visibleMessages = [
    ...messages,
    ...(pendingUser ? [pendingUser] : []),
    ...(streamText
      ? [
          {
            id: "streaming",
            role: "agent" as const,
            content: streamText,
            stage: currentTask?.current_page ?? "task_creation",
            created_at: ""
          }
        ]
      : [])
  ];

  async function submitChat() {
    const text = draft.trim();
    if (!text || sending) return;
    setDraft("");
    setSending(true);
    setStreamText("");
    setLocalError("");
    setPendingUser({
      id: `pending_${Date.now()}`,
      role: "ba",
      content: text,
      stage: currentTask?.current_page ?? "task_creation",
      created_at: ""
    });
    try {
      await sendChat(text, (chunk) => setStreamText((value) => value + chunk));
      setPendingUser(null);
      setStreamText("");
    } catch (err) {
      setLocalError(errorText(err));
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="ba-copilot-panel">
      <div className="copilot-title">
        <div>
          <h2>Copilot 对话引导</h2>
          <p>自然语言驱动任务、维度、假设、洞察和报告。</p>
        </div>
        <MessageSquare size={18} />
      </div>
      <ConversationThread
        messages={visibleMessages}
        actions={actions}
        draft={draft}
        setDraft={setDraft}
        sending={sending}
        error={localError}
        submitChat={submitChat}
      />
      <div className="copilot-context">
        <InfoRow label="当前业务问题" value={currentTask?.business_question ?? form.business_question} />
        <InfoRow label="当前阶段" value={currentTask ? stageLabel(currentTask.current_page) : "等待创建任务"} />
      </div>
    </div>
  );
}

function AgentModuleBoard({
  task,
  artifacts,
  dataAnalysis,
  report
}: {
  task: Task | null;
  artifacts: Artifact[];
  dataAnalysis: DataAnalysis | null;
  report: CEAReport;
}) {
  const designArtifacts = artifacts.filter((artifact) => ["clarification", "analysis_plan", "dimension_recommendation", "hypothesis_pool"].includes(artifact.type));
  const insightArtifacts = artifacts.filter((artifact) => ["data_insight", "sql_review"].includes(artifact.type));
  const reportArtifacts = artifacts.filter((artifact) => artifact.type === "cea_report");
  return (
    <div className="agent-module-board">
      <AgentStageModule
        title="分析设计 Agent"
        status={task ? statusLabel(task.status) : "待创建"}
        input={task?.business_question ?? "等待 BA 输入业务问题"}
        output={designArtifacts.map((artifact) => artifact.title).join("、") || "等待生成需求澄清、分析计划、维度推荐和假设池"}
      />
      <AgentStageModule
        title="数据洞察 Agent"
        status={dataAnalysis || insightArtifacts.length ? "已产出" : "待生成"}
        input={task?.selected_dimensions.length ? task.selected_dimensions.join("、") : "等待确认维度和假设"}
        output={insightArtifacts.map((artifact) => artifact.title).join("、") || "等待生成北极星归因树、贡献度和假设验证"}
      />
      <AgentStageModule
        title="报告生成 Agent"
        status={reportArtifacts.length || task?.status === "report_ready" ? "报告就绪" : "待生成"}
        input={dataAnalysis ? "已接收数据洞察和 SQL 业务解释" : "等待数据洞察确认"}
        output={report.conclusion || "等待生成结论-证据-行动报告"}
      />
    </div>
  );
}

function AgentStageModule({ title, status, input, output }: { title: string; status: string; input: string; output: string }) {
  return (
    <article className="agent-stage-module">
      <div>
        <strong>{title}</strong>
        <span>{status}</span>
      </div>
      <p>
        <b>输入</b>
        {input}
      </p>
      <p>
        <b>输出</b>
        {output}
      </p>
    </article>
  );
}

function TaskCenter({
  tasks,
  currentTask,
  form,
  followups,
  setForm,
  createTask,
  openTask,
  saveDraft,
  confirmInput
}: {
  tasks: Task[];
  currentTask: Task | null;
  form: TaskInput;
  followups: string[];
  setForm: (value: TaskInput) => void;
  createTask: () => void;
  openTask: (id: string) => void;
  saveDraft: () => void;
  confirmInput: () => void;
}) {
  const update = (key: keyof TaskInput, value: string) => setForm({ ...form, [key]: value });
  return (
    <section className="page-grid two-cols">
      <div className="surface">
        <div className="section-title">
          <h1>创建任务</h1>
          <button className="icon-button primary" onClick={createTask} title="新建任务">
            <Plus size={16} />
          </button>
        </div>
        <div className="form-grid">
          <label>
            <span>任务名称</span>
            <input value={form.task_name} onChange={(event) => update("task_name", event.target.value)} />
          </label>
          <label>
            <span>业务问题</span>
            <textarea value={form.business_question} onChange={(event) => update("business_question", event.target.value)} rows={4} />
          </label>
          <label>
            <span>分析目的</span>
            <textarea value={form.analysis_purpose} onChange={(event) => update("analysis_purpose", event.target.value)} rows={3} />
          </label>
          <div className="inline-fields">
            <label>
              <span>分析周期</span>
              <input value={form.time_range} onChange={(event) => update("time_range", event.target.value)} />
            </label>
            <label>
              <span>对比周期</span>
              <input value={form.comparison_period} onChange={(event) => update("comparison_period", event.target.value)} />
            </label>
          </div>
          <label>
            <span>数据源</span>
            <select value={form.data_source} onChange={(event) => update("data_source", event.target.value)}>
              <option value="sales_demo">Sales Demo 漏斗样例</option>
              <option value="real_sample">真实结构样例</option>
              <option value="semantic_model">语义模型样例</option>
            </select>
          </label>
        </div>
        <div className="action-row">
          <button className="secondary" onClick={saveDraft}>
            <Save size={16} /> 保存草稿
          </button>
          <button className="primary" onClick={confirmInput}>
            <CheckCircle2 size={16} /> 确认输入
          </button>
        </div>
      </div>

      <div className="stack">
        <div className="surface">
          <div className="section-title">
            <h2>AI 追问区</h2>
            <Sparkles size={18} />
          </div>
          <div className="question-list">
            {followups.map((item) => (
              <div className="question-item" key={item}>
                {item}
              </div>
            ))}
          </div>
        </div>
        <div className="surface">
          <div className="section-title">
            <h2>任务列表</h2>
            <span className="count-pill">{tasks.length}</span>
          </div>
          <div className="task-list">
            {tasks.map((task) => (
              <button key={task.task_id} className={currentTask?.task_id === task.task_id ? "task-row selected" : "task-row"} onClick={() => openTask(task.task_id)}>
                <strong>{task.task_name}</strong>
                <span>{statusLabel(task.status)}</span>
                <small>{task.business_question}</small>
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function AnalysisWorkbench({
  currentTask,
  patchCurrent,
  saveDesign,
  confirmDesign
}: {
  currentTask: Task;
  patchCurrent: (patch: Partial<Task>) => void;
  saveDesign: () => void;
  confirmDesign: () => void;
}) {
  const [customDimension, setCustomDimension] = useState("");
  const selected = currentTask.selected_dimensions;
  const dimensions = Array.from(new Set([...currentTask.recommended_dimensions, "客户维度", "经销商维度", "活动维度", ...selected]));

  function toggleDimension(dimension: string) {
    patchCurrent({
      selected_dimensions: selected.includes(dimension) ? selected.filter((item) => item !== dimension) : [...selected, dimension]
    });
  }

  function addDimension() {
    const value = customDimension.trim();
    if (!value) return;
    patchCurrent({ selected_dimensions: Array.from(new Set([...selected, value])) });
    setCustomDimension("");
  }

  function updateHypothesis(id: string, patch: Partial<Hypothesis>) {
    patchCurrent({ hypotheses: currentTask.hypotheses.map((item) => (item.id === id ? { ...item, ...patch } : item)) });
  }

  function addHypothesis() {
    patchCurrent({
      hypotheses: [
        ...currentTask.hypotheses,
        {
          id: `hyp_${crypto.randomUUID().slice(0, 8)}`,
          title: "新增业务假设",
          rationale: "补充该假设的业务依据。",
          metrics: ["待补指标"],
          core: false,
          evidence_strength: "待验证",
          missing_data: ["待补数据"],
          status: "未验证"
        }
      ]
    });
  }

  function deleteHypothesis(id: string) {
    patchCurrent({ hypotheses: currentTask.hypotheses.filter((item) => item.id !== id) });
  }

  return (
    <section className="page-grid">
      <div className="surface">
        <div className="section-title">
          <h1>分析工作台</h1>
          <div className="action-row compact">
            <button className="secondary" onClick={saveDesign}>
              <Save size={16} /> 保存
            </button>
            <button className="primary" onClick={confirmDesign}>
              <CheckCircle2 size={16} /> 确认思路
            </button>
          </div>
        </div>
        <div className="dimension-zone">
          <h2>维度选择</h2>
          <div className="chip-row">
            {dimensions.map((dimension) => (
              <button key={dimension} className={selected.includes(dimension) ? "chip selected" : "chip"} onClick={() => toggleDimension(dimension)}>
                {dimension}
              </button>
            ))}
          </div>
          <div className="inline-add">
            <input value={customDimension} onChange={(event) => setCustomDimension(event.target.value)} placeholder="补充维度" />
            <button className="secondary" onClick={addDimension}>
              <Plus size={16} /> 补充
            </button>
          </div>
        </div>
      </div>

      <div className="surface">
        <div className="section-title">
          <h2>假设卡片</h2>
          <button className="secondary" onClick={addHypothesis}>
            <Plus size={16} /> 新增假设
          </button>
        </div>
        <div className="hypothesis-grid">
          {currentTask.hypotheses.map((hypothesis) => (
            <article className={hypothesis.core ? "hypothesis-card core" : "hypothesis-card"} key={hypothesis.id}>
              <div className="hypothesis-actions">
                <button className={hypothesis.core ? "icon-button active-star" : "icon-button"} onClick={() => updateHypothesis(hypothesis.id, { core: !hypothesis.core })} title="核心标记">
                  <Star size={16} />
                </button>
                <button className="icon-button danger" onClick={() => deleteHypothesis(hypothesis.id)} title="删除">
                  <Trash2 size={16} />
                </button>
              </div>
              <label>
                <span>假设</span>
                <input value={hypothesis.title} onChange={(event) => updateHypothesis(hypothesis.id, { title: event.target.value })} />
              </label>
              <label>
                <span>业务依据</span>
                <textarea value={hypothesis.rationale} onChange={(event) => updateHypothesis(hypothesis.id, { rationale: event.target.value })} rows={3} />
              </label>
              <label>
                <span>关联指标</span>
                <input value={hypothesis.metrics.join(", ")} onChange={(event) => updateHypothesis(hypothesis.id, { metrics: splitList(event.target.value) })} />
              </label>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function DataInsightWorkbench({ analysis, refresh, confirmInsight }: { analysis: DataAnalysis | null; refresh: () => void; confirmInsight: () => void }) {
  if (!analysis) {
    return (
      <div className="surface">
        <div className="section-title">
          <h1>数据洞察</h1>
          <button className="primary" onClick={refresh}>
            <Sparkles size={16} /> 生成洞察
          </button>
        </div>
        <EmptyState text="等待生成数据洞察。" />
      </div>
    );
  }
  return (
    <section className="page-grid">
      <div className="surface">
        <div className="section-title">
          <h1>数据洞察</h1>
          <div className="action-row compact">
            <button className="secondary" onClick={refresh}>
              <Sparkles size={16} /> 刷新
            </button>
            <button className="primary" onClick={confirmInsight}>
              <CheckCircle2 size={16} /> 确认洞察
            </button>
          </div>
        </div>
        <div className="insight-cards">
          {analysis.insight_cards.map((card) => (
            <div className="insight-card" key={card}>
              {card}
            </div>
          ))}
        </div>
      </div>

      <div className="page-grid two-cols">
        <div className="surface">
          <h2>北极星指标归因树</h2>
          <MetricTree node={analysis.north_star_tree} />
        </div>
        <div className="surface">
          <h2>贡献度表格</h2>
          <ContributionTable rows={analysis.contribution_rows} />
        </div>
      </div>

      <div className="surface">
        <h2>假设验证</h2>
        <div className="validation-grid">
          {analysis.hypotheses.map((hypothesis) => (
            <article className="validation-card" key={hypothesis.id}>
              <div>
                <strong>{hypothesis.title}</strong>
                <span className={strengthClass(hypothesis.evidence_strength)}>{hypothesis.evidence_strength}</span>
              </div>
              <p>{hypothesis.rationale}</p>
              <small>验证状态：{hypothesis.status}</small>
              <small>待补数据：{hypothesis.missing_data.length ? hypothesis.missing_data.join("、") : "无"}</small>
            </article>
          ))}
        </div>
      </div>

      <div className="surface">
        <h2>SQL 业务解释</h2>
        <div className="sql-grid">
          {analysis.sql_reviews.map((review) => (
            <SqlCard review={review} key={review.title} />
          ))}
        </div>
      </div>
    </section>
  );
}

function MetricTree({ node }: { node: MetricNode }) {
  return (
    <div className="metric-node">
      <div className="metric-box">
        <strong>{node.label}</strong>
        <span>{formatValue(node.value)}</span>
        <small>
          环比 {node.change}% · 贡献 {node.contribution}%
        </small>
      </div>
      {node.children.length > 0 && (
        <div className="metric-children">
          {node.children.map((child) => (
            <MetricTree node={child} key={child.id} />
          ))}
        </div>
      )}
    </div>
  );
}

function ContributionTable({ rows }: { rows: ContributionRow[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>维度</th>
            <th>切片</th>
            <th>本期</th>
            <th>对比</th>
            <th>变化</th>
            <th>贡献</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.dimension}-${row.segment}`}>
              <td>{row.dimension}</td>
              <td>{row.segment}</td>
              <td>{row.current}</td>
              <td>{row.previous}</td>
              <td>{row.change}%</td>
              <td>{row.contribution}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SqlCard({ review }: { review: SqlReview }) {
  return (
    <article className="sql-card">
      <strong>{review.title}</strong>
      <pre>{review.sql}</pre>
      <p>{review.business_explanation}</p>
      <div className="chip-row">
        {review.fields.map((field) => (
          <span className="chip static" key={field}>
            {field}
          </span>
        ))}
      </div>
    </article>
  );
}

function ReportWorkbench({
  report,
  setReport,
  saveReport,
  exportReport,
  exportMessage
}: {
  report: CEAReport;
  setReport: (report: CEAReport) => void;
  saveReport: () => void;
  exportReport: (format: "html" | "markdown" | "json") => void;
  exportMessage: string;
}) {
  const update = (key: keyof CEAReport, value: string) => setReport({ ...report, [key]: value });
  return (
    <section className="page-grid">
      <div className="surface">
        <div className="section-title">
          <h1>报告产出</h1>
          <div className="action-row compact">
            <button className="secondary" onClick={saveReport}>
              <Save size={16} /> 保存
            </button>
            <button className="primary" onClick={() => exportReport("html")}>
              <Download size={16} /> HTML
            </button>
            <button className="secondary" onClick={() => exportReport("markdown")}>
              <Download size={16} /> MD
            </button>
            <button className="secondary" onClick={() => exportReport("json")}>
              <Download size={16} /> JSON
            </button>
          </div>
        </div>
        {exportMessage && <div className="export-message">{exportMessage}</div>}
      </div>

      <div className="report-grid">
        <label className="report-block">
          <span>结论</span>
          <textarea value={report.conclusion} onChange={(event) => update("conclusion", event.target.value)} rows={6} />
        </label>
        <label className="report-block">
          <span>证据</span>
          <textarea value={report.evidence} onChange={(event) => update("evidence", event.target.value)} rows={6} />
        </label>
        <label className="report-block">
          <span>行动</span>
          <textarea value={report.action} onChange={(event) => update("action", event.target.value)} rows={6} />
        </label>
      </div>
    </section>
  );
}

function CapabilityAssets({ catalog, semantic, assets }: { catalog: Record<string, string[]> | null; semantic: Record<string, unknown> | null; assets: Record<string, unknown> | null }) {
  return (
    <section className="page-grid two-cols">
      <AssetList title="问题类型库" items={catalog?.question_types ?? []} />
      <AssetList title="分析方法库" items={catalog?.methods ?? []} />
      <AssetList title="指标口径" items={catalog?.metrics ?? []} />
      <AssetList title="语义对象" items={Array.isArray(semantic?.entities) ? (semantic.entities as string[]) : []} />
      <div className="surface wide">
        <h2>数据资产样例</h2>
        <pre className="json-preview">{JSON.stringify(assets, null, 2)}</pre>
      </div>
    </section>
  );
}

function AssetList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="surface">
      <h2>{title}</h2>
      <div className="asset-list">
        {items.map((item) => (
          <span key={item}>{item}</span>
        ))}
      </div>
    </div>
  );
}

function AgentPanel({
  currentTask,
  activeTab,
  setActiveTab,
  form,
  actions,
  sendChat
}: {
  currentTask: Task | null;
  activeTab: AgentTab;
  setActiveTab: (tab: AgentTab) => void;
  form: TaskInput;
  actions: AgentAction[];
  sendChat: (messageText: string, onDelta: (chunk: string) => void) => Promise<void>;
}) {
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [pendingUser, setPendingUser] = useState<ConversationMessage | null>(null);
  const [localError, setLocalError] = useState("");
  const messages = currentTask?.messages ?? [
    {
      id: "draft",
      role: "agent" as const,
      content: "填写业务问题后，我会生成追问、分析思路和过程文档。",
      stage: "task_creation" as const,
      created_at: ""
    }
  ];
  const visibleMessages = [
    ...messages,
    ...(pendingUser ? [pendingUser] : []),
    ...(streamText
      ? [
          {
            id: "streaming",
            role: "agent" as const,
            content: streamText,
            stage: currentTask?.current_page ?? "task_creation",
            created_at: ""
          }
        ]
      : [])
  ];
  const artifacts = currentTask?.artifacts ?? [];

  async function submitChat() {
    const text = draft.trim();
    if (!text || sending) return;
    setDraft("");
    setSending(true);
    setStreamText("");
    setLocalError("");
    setActiveTab("chat");
    setPendingUser({
      id: `pending_${Date.now()}`,
      role: "ba",
      content: text,
      stage: currentTask?.current_page ?? "task_creation",
      created_at: ""
    });
    try {
      await sendChat(text, (chunk) => setStreamText((value) => value + chunk));
      setPendingUser(null);
      setStreamText("");
    } catch (err) {
      setLocalError(errorText(err));
    } finally {
      setSending(false);
    }
  }

  return (
    <aside className="agent-panel">
      <div className="agent-tabs">
        <button className={activeTab === "chat" ? "active" : ""} onClick={() => setActiveTab("chat")}>
          <MessageSquare size={16} /> 对话
        </button>
        <button className={activeTab === "artifacts" ? "active" : ""} onClick={() => setActiveTab("artifacts")}>
          <FileText size={16} /> 过程文档
        </button>
        <button className={activeTab === "context" ? "active" : ""} onClick={() => setActiveTab("context")}>
          <Database size={16} /> 上下文
        </button>
      </div>
      <div className="agent-body">
        {activeTab === "chat" && (
          <ConversationThread
            messages={visibleMessages}
            actions={actions}
            draft={draft}
            setDraft={setDraft}
            sending={sending}
            error={localError}
            submitChat={submitChat}
          />
        )}
        {activeTab === "artifacts" && <ArtifactPanel artifacts={artifacts} />}
        {activeTab === "context" && <ContextPanel task={currentTask} form={form} />}
      </div>
    </aside>
  );
}

function ConversationThread({
  messages,
  actions,
  draft,
  setDraft,
  sending,
  error,
  submitChat
}: {
  messages: { id: string; role: string; content: string; stage: string; created_at: string }[];
  actions: AgentAction[];
  draft: string;
  setDraft: (value: string) => void;
  sending: boolean;
  error: string;
  submitChat: () => void;
}) {
  return (
    <div className="conversation-shell">
      <div className="conversation">
        {messages.map((message) => (
          <article className={`message ${message.role}`} key={message.id}>
            <span>{message.role === "agent" ? "Agent" : "BA"}</span>
            <p>{message.content}</p>
            <small>{stageLabel(message.stage)}</small>
          </article>
        ))}
      </div>
      {actions.length > 0 && (
        <div className="action-log">
          <strong>已执行动作</strong>
          {actions.map((action, index) => (
            <div className="action-item" key={`${action.type}-${index}`}>
              <span>{action.title}</span>
              <p>{action.detail}</p>
            </div>
          ))}
        </div>
      )}
      {error && <div className="chat-error">{error}</div>}
      <div className="chat-composer">
        <textarea
          value={draft}
          rows={4}
          placeholder="直接输入：把维度加上经销商 / 新增一个假设：渠道投放质量下降 / 基于洞察生成报告"
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submitChat();
            }
          }}
        />
        <button className="primary" onClick={submitChat} disabled={sending || !draft.trim()}>
          <MessageSquare size={16} /> {sending ? "发送中" : "发送"}
        </button>
      </div>
    </div>
  );
}

function ArtifactPanel({ artifacts }: { artifacts: Artifact[] }) {
  if (!artifacts.length) return <EmptyState text="暂无过程文档。" />;
  return (
    <div className="artifact-list">
      {artifacts.map((artifact) => (
        <ModuleArtifactCard artifact={artifact} key={artifact.id} />
      ))}
    </div>
  );
}

function ModuleArtifactCard({ artifact }: { artifact: Artifact }) {
  return (
    <article className="artifact-card">
      <div>
        <strong>{artifact.title}</strong>
        <span className={`artifact-status ${artifact.status}`}>{artifact.status}</span>
      </div>
      <p>{artifact.summary}</p>
      <ul>
        {artifact.content.slice(0, 4).map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </article>
  );
}

function ContextPanel({ task, form }: { task: Task | null; form: TaskInput }) {
  const context = task ?? form;
  return (
    <div className="context-list">
      <InfoRow label="业务问题" value={context.business_question} />
      <InfoRow label="分析目的" value={context.analysis_purpose} />
      <InfoRow label="周期" value={context.time_range} />
      <InfoRow label="对比" value={context.comparison_period} />
      <InfoRow label="数据源" value={context.data_source} />
      {task && <InfoRow label="维度" value={(task.selected_dimensions.length ? task.selected_dimensions : task.recommended_dimensions).join("、")} />}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="info-row">
      <span>{label}</span>
      <p>{value}</p>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="empty-state">{text}</div>;
}

function taskToInput(task: Task): TaskInput {
  return {
    task_name: task.task_name,
    business_question: task.business_question,
    analysis_purpose: task.analysis_purpose,
    time_range: task.time_range,
    comparison_period: task.comparison_period,
    data_source: task.data_source
  };
}

function localFollowups(input: TaskInput) {
  const items = [
    "本次下降判断使用哪个北极星指标：线索量、到店量、订单量，还是整体转化率？",
    "对比周期是否需要排除节假日、活动日或门店休假等异常日期？",
    "是否需要按区域、渠道、车型和新老客户拆分贡献度？"
  ];
  const text = `${input.business_question} ${input.analysis_purpose}`;
  if (text.includes("渠道")) items.push("渠道口径是否区分自然流量、付费媒体、区域活动和经销商自建线索？");
  if (text.includes("客流") || text.includes("到店")) items.push("客流口径是 register、leads、visit 还是线下进店客流？");
  return items;
}

function splitList(value: string) {
  return value
    .split(/[,，、]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    draft: "输入草稿",
    input_confirmed: "输入已确认",
    design_confirmed: "思路已确认",
    insight_confirmed: "洞察已确认",
    report_ready: "报告就绪"
  };
  return labels[status] ?? status;
}

function stageLabel(stage: string) {
  const labels: Record<string, string> = {
    task_creation: "任务创建",
    analysis_design: "分析思路",
    data_insight: "数据洞察",
    report_generation: "报告产出"
  };
  return labels[stage] ?? stage;
}

function strengthClass(strength: string) {
  return strength === "强" ? "strength strong" : strength === "中" ? "strength medium" : "strength weak";
}

function formatValue(value: number) {
  if (value < 1) return `${(value * 100).toFixed(1)}%`;
  return value.toLocaleString("zh-CN");
}

function errorText(err: unknown) {
  return err instanceof Error ? err.message : "操作失败";
}

export default App;
