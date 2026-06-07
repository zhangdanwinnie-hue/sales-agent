# Skill Routing

This agent should treat installed Codex skills as reusable capability modules, not as separate decision makers.

## Agent Roles

| Agent role | Responsibility | Recommended skills |
|---|---|---|
| Analysis Strategy Agent | Classify the business question, retrieve context, propose hypothesis tree, choose playbook | `deep-research`, `context-retrieval`, `fact-checking` |
| Data Analysis Agent | Clean data, map fields, generate SQL, run EDA, calculate metrics | `data-cleaning`, `data-analysis`, `exploratory-data-analysis`, `sql-query-generation`, `data-visualization` |
| Business Insight Agent | Translate facts into BP/BA language, separate fact from inference, propose actions | `analytics-reporting`, `churn-analysis`, `competitive-battlecard-creation`, `financial-modeling`, `fact-checking` |
| Report Generation Agent | Build executive memo, dashboard narrative, PPT/report/proposal outputs | `report-generation`, `presentation-creation`, `proposal-generation`, `proofreading` |

## Routing Rules

1. Route first by `question_type` in `config/analysis-playbooks.json`.
2. Add method-level skills from selected `analysis_methods`.
3. Add gate-level skills when BA confirmation is required.
4. Add output-format skills for dashboard, markdown report, PPT, or proposal.
5. Always include `fact-checking` before insight or report confirmation.

## Priority For Sales BP MVP

| Business scenario | Primary skills |
|---|---|
| Performance decline diagnosis | `data-analysis`, `exploratory-data-analysis`, `sql-query-generation`, `analytics-reporting` |
| Funnel conversion diagnosis | `exploratory-data-analysis`, `sql-query-generation`, `churn-analysis`, `data-visualization` |
| Channel and campaign evaluation | `analytics-reporting`, `competitive-battlecard-creation`, `data-analysis`, `data-visualization` |
| Opportunity identification | `data-analysis`, `financial-modeling`, `analytics-reporting`, `proposal-generation` |
| Forecast and warning | `financial-modeling`, `data-analysis`, `analytics-reporting`, `fact-checking` |
| Operations monitoring | `data-cleaning`, `exploratory-data-analysis`, `data-analysis`, `analytics-reporting` |
