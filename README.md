# Sales BP Analysis Agent Thread Prototype

This is a static interactive prototype for a Codex-style BA analysis experience.

## Run

```powershell
node server.js
```

Then visit `http://127.0.0.1:5173/`.

If port `5173` is already occupied by another local app, use:

```powershell
$env:PORT='5174'
node server.js
```

Then visit `http://127.0.0.1:5174/`.

## Experience Model

- Left side: `Analysis Threads`, similar to conversation history.
- Center: one primary conversation stream. Agent messages and process outputs appear in the thread.
- Right side: `Context Drawer`, opened only when BA needs SQL, metric definitions, field mapping, report preview, or Playbook update context.

## Artifact Types

- `BusinessBrief`
- `AnalysisPlan`
- `DataReadiness`
- `EvidencePack`
- `ReportDraft`
- `PlaybookUpdate`

## Skill-Enriched Agent Layer

The Agent now includes a `Skill Orchestration` Artifact populated from local skills under `C:\Users\wangj\.codex\skills`.

Included skills:

- `exploratory-data-analysis`
- `data-cleaning`
- `data-analysis`
- `sql-query-generation`
- `analytics-reporting`
- `data-visualization`
- `report-generation`
- `crm-data-enrichment`
- `lead-scoring`
- `customer-feedback-analysis`
- `knowledge-graph-creation`

Each skill exposes its role, input, output, stage, and local `SKILL.md` source path in the Context Drawer.

Each Artifact has a status: `draft`, `needs_review`, `approved`, `rejected`, or `superseded`.

## Verified

- `node --check app.js` passed.
- `node --check server.js` passed.
- Browser loaded with no console errors.
- SQL context drawer opens from Evidence Pack.
- Editing an Analysis Plan marks Evidence Pack as needing recalculation.
- Report preview opens in the drawer and supports HTML export.
- New business question creates a new Analysis Thread and starts with clarification, not direct reporting.
- Skill Registry drawer opens and shows local skill sources, including `lead-scoring` and `knowledge-graph-creation`.
- Desktop `1440x900` and mobile `390x844` have no horizontal overflow.
