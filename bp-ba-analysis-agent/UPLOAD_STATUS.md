# Upload Status

Target branch: `codex/bp-ba-analysis-agent`

Target directory: `bp-ba-analysis-agent/`

Uploaded through the GitHub plugin after repository authorization was restored.

## Uploaded directly

- Project README and Python project config
- Core package entrypoints and data contracts
- Read-only connector contracts
- CLI entrypoint
- Demo run scripts
- V2 workbench README and dependency metadata
- BP BA sales analysis Skill definition and agent metadata

## Local files intentionally excluded from direct plugin upload

- `outputs/`
- `node_modules/`
- generated PPT files
- screenshots and rendered artifacts
- original zip/xlsx raw data files
- cache folders and virtual environments

## Note

The GitHub plugin writes files through the repository contents API. It does not provide a native local directory push, so this branch contains the uploaded source subset and project structure. A clean local upload package was also generated at `outputs/github_upload/bp-ba-analysis-agent-upload.zip` in the local workspace for a full git-based push if needed.
