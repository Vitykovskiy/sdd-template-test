# AGENTS.md

## Routing

Project state is stored in `.codex/state.json`.

When the user explicitly asks the agent to start work on the project, the agent must:

1. Read `.codex/state.json`
2. Determine the current `mode`
3. Open the corresponding instruction:
   - `initialization` -> `.codex/routing/initialization/instruction.md`
   - `issue_driven` -> `.codex/routing/issue-driven/instruction.md`

The agent must not take a task unless the user explicitly asked to start work.

## Task Selection

In `issue_driven` mode the agent must not choose a task directly from this file.

GitHub Project parameters are stored in `.codex/state.json`:

- `project.gh_project_url` - canonical GitHub Project URL
- `project.gh_project_id` - GitHub Project identifier

The agent must open:

- `.codex/routing/issue-driven/instruction.md`

This stage instruction must route the agent to exactly one task in the repository GitHub Project.

## Role Routing

After the task is selected, the agent must:

1. Read the selected GitHub Project task
2. Determine the assigned role
3. Open the role instruction from `.codex/roles/<role>/instruction.md`
4. Execute the task according to the role instruction

## BA Boundary

If the assigned role is `business-analyst`, the agent may change only the canonical business artifact families under `docs/business/`: `vision`, `glossary`, `business-rules`, `scenarios`.
It must follow the BA role instruction order and stop on blocker instead of inventing facts or expanding scope.
