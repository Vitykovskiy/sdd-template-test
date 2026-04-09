# Issue-Driven Mode

## Purpose

Work through tasks defined in the repository GitHub Project.

The canonical workflow status lives only in GitHub Project `Status`.
The canonical statuses are `ready`, `in_progress`, `review`, `in_testing`, and `done`.
Issue body is not a status carrier.

## Task selection

The agent must not select a task manually from this instruction.

The agent must run the selector script from the repository root:

```bash
python .codex/routing/issue-driven/scripts/select_task.py
```

The script prints a JSON object to stdout.

Successful selection is indicated by:

- `status = "selected"`
- `selected_task` object is present

The `selected_task` object is the source of truth for:

- `task_id`
- `title`
- `role`
- `priority_label`
- `status` from GitHub Project `Status`
- `url`

If the script exits with a non-zero code, the agent must stop and report the blocker.

## Required actions

After the script returns `status = "selected"`, the agent must:

1. Read the selected GitHub Project task by `selected_task.url`.
2. Determine the assigned role from `selected_task.role`.
3. Open `.codex/roles/<role>/instruction.md`.
4. Execute the task according to the role instruction.

## Post-execution delivery

After role-specific execution is complete, the agent must check whether the repository contains changes that should be published.

If there are changes, the agent must publish them through the shared script `.codex/routing/_shared/scripts/commit_push_pr.py`.

This script is the standard `branch -> commit -> push -> PR` path for `issue-driven`. The PR is created immediately as ready for review; draft mode is not used.

The delivery target must be the repository default branch via PR. Direct push to the default branch is forbidden after initialization because it is protected.

The agent must not replace this step with an ad hoc sequence of `git` or `gh` commands.
