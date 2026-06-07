# Sales BP Analysis Agent

This folder contains a first working design package for a flexible automotive Sales BP analysis agent.

## Deliverables

- `docs/agent-design.md`: product and agent architecture design.
- `config/semantic-layer.json`: draft business semantic layer based on the provided CSV schema.
- `config/analysis-playbooks.json`: reusable business question types, analysis methods, KPI definitions, approval gates, and skill routing.
- `docs/skill-routing.md`: recommended mapping between agent roles and installed Codex skills.
- `prototype/index.html`: static frontend prototype for the analysis workbench.
- `prototype/styles.css`: frontend styling.
- `prototype/app.js`: frontend interaction logic and sample workflow state.
- `prototype/data/analysis-case.json`: real aggregated case generated from the provided CSV.
- `scripts/analyze_sales_csv.py`: repeatable script for regenerating the real case data.

## How To View

Open `prototype/index.html` in a browser. The prototype does not require a dev server.

For the real CSV case data to load through `fetch`, run a local static server from `prototype/` and open the localhost URL. The current preview uses:

`http://127.0.0.1:5508/index.html`

## Design Principle

The agent is not a single scenario tool. It is designed as a business-question-driven analysis system:

`Business Question -> Question Classification -> Skill Routing -> Analysis Plan -> Data Capability Match -> BA Confirmation -> Analysis Execution -> Insight Review -> Report Output`

BA confirmation is required at every major step.

## Skill Routing

The agent is the orchestrator. Installed Codex skills are reusable capability modules selected by question type, analysis method, approval gate, and output format.

Core skill groups now referenced by the playbook:

- Analysis strategy: `deep-research`, `context-retrieval`, `fact-checking`
- Data analysis: `data-cleaning`, `data-analysis`, `exploratory-data-analysis`, `sql-query-generation`, `data-visualization`
- Business insight: `analytics-reporting`, `churn-analysis`, `competitive-battlecard-creation`, `financial-modeling`
- Delivery: `report-generation`, `presentation-creation`, `proposal-generation`, `proofreading`
