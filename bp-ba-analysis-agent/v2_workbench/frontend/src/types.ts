export type Stage = "task_creation" | "analysis_design" | "data_insight" | "report_generation";

export type TaskStatus = "draft" | "input_confirmed" | "design_confirmed" | "insight_confirmed" | "report_ready";

export interface ConversationMessage {
  id: string;
  role: "agent" | "ba" | "system";
  content: string;
  stage: Stage;
  created_at: string;
}

export interface Artifact {
  id: string;
  task_id: string;
  type: string;
  title: string;
  summary: string;
  content: string[];
  status: "draft" | "confirmed" | "updated";
  updated_at: string;
}

export interface Hypothesis {
  id: string;
  title: string;
  rationale: string;
  metrics: string[];
  core: boolean;
  evidence_strength: "强" | "中" | "弱" | "待验证";
  missing_data: string[];
  status: "未验证" | "支持" | "部分支持" | "不支持";
}

export interface CEAReport {
  conclusion: string;
  evidence: string;
  action: string;
}

export interface Task {
  task_id: string;
  task_name: string;
  business_question: string;
  analysis_purpose: string;
  time_range: string;
  comparison_period: string;
  data_source: string;
  status: TaskStatus;
  current_page: Stage;
  selected_dimensions: string[];
  recommended_dimensions: string[];
  hypotheses: Hypothesis[];
  report: CEAReport;
  artifacts: Artifact[];
  messages: ConversationMessage[];
  created_at: string;
  updated_at: string;
}

export interface TaskInput {
  task_name: string;
  business_question: string;
  analysis_purpose: string;
  time_range: string;
  comparison_period: string;
  data_source: string;
}

export interface MetricNode {
  id: string;
  label: string;
  value: number;
  change: number;
  contribution: number;
  children: MetricNode[];
}

export interface ContributionRow {
  dimension: string;
  segment: string;
  current: number;
  previous: number;
  change: number;
  contribution: number;
  insight: string;
}

export interface SqlReview {
  title: string;
  sql: string;
  fields: string[];
  business_explanation: string;
}

export interface DataAnalysis {
  north_star_tree: MetricNode;
  contribution_rows: ContributionRow[];
  hypotheses: Hypothesis[];
  sql_reviews: SqlReview[];
  insight_cards: string[];
}

export interface AgentAction {
  type: string;
  title: string;
  detail: string;
}

export interface ChatResponse {
  assistant_message: ConversationMessage;
  actions: AgentAction[];
  task: Task;
  artifacts: Artifact[];
  next_page: Stage | null;
}
