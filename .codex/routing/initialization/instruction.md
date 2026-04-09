# Initialization

## Purpose

Initialize the repository and the linked GitHub Project for the template workflow.

Use `standards/gh-project-standard.md` as the mandatory standard for this stage.

The canonical workflow status lives only in GitHub Project `Status`.
The canonical statuses are `ready`, `in_progress`, `review`, `in_testing`, and `done`.
Issue body is not a status carrier and must not be treated as one.

## Execution rule

The agent must operate only through this stage folder.

The agent must first run the audit script from the repository root:

```bash
python .codex/routing/initialization/scripts/check_initialization.py
```

## Audit result

The audit script prints a JSON report with:

- `status`
- `checks`
- `required_actions`

Interpretation:

- `status = "ok"` means initialization is already complete
- `status = "action_required"` means mutation scripts are required

The agent must show the audit result to the user before any mutation script is executed.

## Mandatory consent rule

If `required_actions` is not empty, the agent must request the user's confirmation before running any mutation script.

The agent must not:

- create a GitHub repository without user confirmation
- create or attach a GitHub Project without user confirmation
- modify labels or the project `Status` field without user confirmation
- create the initiating task without user confirmation

## Conflict handling

If `create_github_repository.py` or `ensure_github_project.py` returns `status: "name_conflict"`, the agent must stop immediately and ask the user to choose one of two options:

1. create the object with a new name or title
2. attach the existing GitHub repository or GitHub Project

If multiple existing objects are returned, the user must also choose which existing object to attach.

The agent must not continue to later initialization scripts until the conflict is resolved.

After the user chooses, the agent must rerun the same script with the corresponding argument:

- `create_github_repository.py`: rerun with a new `--name`, or rerun with `--attach-existing-url "<repository url>"`
- `ensure_github_project.py`: rerun with a new `--title`, or rerun with `--project-url "<project url>"`

## Completion rule

When all required mutation scripts finish successfully, the agent must:

1. create a git commit from the repository root
2. push the resulting changes to the repository default branch
3. run the branch-protection script for the repository default branch

Initialization is not complete until the commit exists, the changes are pushed to the repository default branch, and branch protection for that default branch is applied.

## Mutation scripts

Run only the scripts required by the audit report.

### 1. Create GitHub repository

Use when `required_actions` contains `create_github_repository`.

```bash
python .codex/routing/initialization/scripts/create_github_repository.py --owner <owner> --name <repo> --visibility <private|public|internal>
```

### 2. Create or attach GitHub Project

Use when `required_actions` contains `create_or_link_github_project`.

Create a new project:

```bash
python .codex/routing/initialization/scripts/ensure_github_project.py --title "<project title>"
```

Attach an existing project:

```bash
python .codex/routing/initialization/scripts/ensure_github_project.py --project-url "<project url>"
```

### 3. Apply template standard

Use when `required_actions` contains `sync_project_standard`.

```bash
python .codex/routing/initialization/scripts/sync_project_standard.py
```

### 4. Create initiating task and advance mode

Use when `required_actions` contains `create_initiating_task`.

```bash
python .codex/routing/initialization/scripts/create_initiating_task.py
```

This script must:

- create or reuse the first BA task from `templates/initiating-task.md`
- add the task to the configured GitHub Project
- set the project item `Status` to `ready`, the workflow value required for the next stage
- change `mode` in `.codex/state.json` to `issue_driven`

The initiating task is created during initialization with `status:ready`, but it is a task for the next stage and must be executed only after the workflow enters `issue_driven`.

### 5. Protect the default branch

Use when all required mutation scripts have completed successfully and the changes have been committed and pushed to the repository default branch.

```bash
python .codex/routing/initialization/scripts/protect_main_branch.py
```

## Required order

If multiple mutation scripts are needed, the agent must run them in this order:

1. `create_github_repository.py`
2. `ensure_github_project.py`
3. `sync_project_standard.py`
4. `create_initiating_task.py`
5. `protect_main_branch.py`

The agent must not reorder these steps.

## Output

After successful initialization:

- the repository exists on GitHub
- `.codex/state.json` contains the linked project URL and ID
- the repository contains the required workflow labels for role and priority
- the linked GitHub Project `Status` field contains the canonical workflow statuses `ready`, `in_progress`, `review`, `in_testing`, and `done`
- the initiating task exists in the linked GitHub Project
- the initiating task project column matches its workflow status
- `.codex/state.json` has `mode = "issue_driven"`
- the initialization changes are captured in a git commit
- the initialization changes are pushed to the repository default branch
- the repository default branch is protected against direct pushes
