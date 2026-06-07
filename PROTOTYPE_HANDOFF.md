# Prototype Handoff

## Design Direction

The prototype is no longer a BI workbench. It is a Codex-style analysis thread for BA users:

- BA asks a business question.
- Agent asks clarification questions.
- Agent generates process Artifacts in the conversation.
- BA reviews, approves, edits, rejects, or requests more analysis.
- Complex evidence opens in a right-side Context Drawer.
- Agent capabilities are represented as a `Skill Orchestration` Artifact sourced from local Codex skills.

## Key Frames

1. `Analysis Threads`
   - Conversation list
   - Thread status
   - Data source and last updated time

2. `Main Thread`
   - User question
   - Agent clarification
   - Structured Artifact cards
   - Composer with data source and CSV entry

3. `Artifact Card`
   - Type, status, version
   - Summary and key bullets
   - Expand / collapse
   - Decision actions

4. `Context Drawer`
   - SQL and human explanation
   - Metric definitions
   - Field mapping / lineage
   - Report preview
   - Playbook update target
   - Skill Registry and individual Skill details

5. `Mobile`
   - Single-column conversation
   - Drawer becomes full-screen overlay

## Interaction Rules

- Agent must generate `BusinessBrief` and `AnalysisPlan` before data analysis.
- Evidence conclusions must bind metric, contribution, SQL / logic, data limitation, and confidence.
- Data gaps must render as `Data Gap Card`, not as unsupported conclusions.
- BA edits create a human-edit record and can mark downstream Artifacts as stale.
- Agent should explicitly show which local skill is used for each major Artifact and why.
