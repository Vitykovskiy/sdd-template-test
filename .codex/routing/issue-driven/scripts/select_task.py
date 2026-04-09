#!/usr/bin/env python3
"""Select exactly one executable task from the repository GitHub Project.

Exit codes:
- 0: task selected
- 2: no valid ready task exists
- 3: configuration blocker
- 4: GitHub CLI call failed
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROLE_LABELS = {
    "role:business-analyst",
    "role:system-analyst",
    "role:architect",
    "role:frontend-developer",
    "role:backend-developer",
    "role:devops",
}

PRIORITY_LABELS = {
    "priority:critical",
    "priority:high",
    "priority:medium",
    "priority:low",
}

PRIORITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}

MANDATORY_SECTIONS = (
    "Id",
    "Role",
    "Title",
    "Purpose",
    "Artifacts",
    "Priority",
)

PROJECT_URL_RE = re.compile(
    r"^https://github\.com/(?:(?:orgs|users)/)?(?P<owner>[^/]+)/projects/(?P<number>\d+)(?:/.*)?$"
)


@dataclass
class TaskValidationResult:
    """Validation outcome for a GitHub Project item treated as a task.

    `is_valid` tells the caller whether the item satisfies all workflow rules.
    `task` contains the normalized summary used for sorting and reporting.
    `violations` lists every rule that failed so the caller can report a full
    diagnostic instead of stopping at the first error.
    """
    is_valid: bool
    task: dict[str, Any]
    violations: list[str]


def make_result(status: str, **extra: Any) -> dict[str, Any]:
    """Build the JSON envelope used by every exit path in this script.

    The result payload always contains a top-level status field plus any
    additional structured metadata needed by the caller. Keeping this in a
    helper makes the emitted schema consistent across success and failure
    paths.
    """
    result = {"status": status}
    result.update(extra)
    return result


def print_json(payload: dict[str, Any]) -> None:
    """Serialize a JSON response to stdout using a stable human-readable form.

    Indentation and UTF-8 preservation are intentional because the script is
    typically consumed by automation and by humans inspecting the output in
    a terminal.
    """
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def run_gh_json(args: list[str], cwd: Path) -> dict[str, Any]:
    """Execute `gh` and decode its JSON output.

    The helper isolates CLI invocation, stderr/stdout error propagation, and
    JSON decoding into one place so the rest of the script can work with a
    typed dictionary. Any non-zero CLI exit or invalid JSON is converted into
    a runtime error for the caller to classify.
    """
    completed = subprocess.run(
        ["gh", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "gh command failed")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"failed to decode GitHub CLI JSON output: {exc}") from exc


def parse_project_url(project_url: str) -> tuple[str, int]:
    """Parse a GitHub Project URL into owner and project number.

    Only the supported project URL pattern is accepted. The function trims
    surrounding whitespace, validates the shape against the compiled regular
    expression, and returns the owner plus numeric project identifier.
    """
    match = PROJECT_URL_RE.match(project_url.strip())
    if not match:
        raise ValueError(f"unsupported GitHub Project URL format: {project_url}")
    return match.group("owner"), int(match.group("number"))


def extract_sections(body: str) -> dict[str, str]:
    """Extract top-level Markdown sections from an issue body.

    The parser looks only for `##` headings because the workflow contract uses
    those headings to encode task metadata. Each section body is trimmed so the
    downstream validation functions can compare values directly.
    """
    sections: dict[str, str] = {}
    matches = list(re.finditer(r"^## (?P<name>[^\r\n]+)\r?\n", body, flags=re.MULTILINE))
    for index, match in enumerate(matches):
        name = match.group("name").strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sections[name] = body[start:end].strip()
    return sections


def extract_code_value(section_value: str) -> str:
    """Extract the first inline code value from a section.

    Workflow templates store canonical values in backticks. If no inline code
    segment is present, the function falls back to the stripped raw section
    content so the caller still gets a usable string.
    """
    match = re.search(r"`([^`]+)`", section_value)
    if match:
        return match.group(1).strip()
    return section_value.strip()


def summarize_task(item: dict[str, Any], sections: dict[str, str] | None = None) -> dict[str, Any]:
    """Normalize a project item into the shape used for validation reporting.

    The summary keeps only the fields that matter for selection and diagnostics:
    identifiers, repository, title, encoded task id, extracted role, priority,
    and the project workflow status. This prevents the rest of the code from
    depending on raw GitHub payload structure.
    """
    content = item["content"]
    role = None
    priority = None
    task_id = None
    if sections:
        role = extract_code_value(sections.get("Role", ""))
        priority = extract_code_value(sections.get("Priority", ""))
        task_id = extract_code_value(sections.get("Id", ""))

    return {
        "project_item_id": item.get("id"),
        "issue_number": content.get("number"),
        "repository": content.get("repository"),
        "url": content.get("url"),
        "title": content.get("title"),
        "task_id": task_id,
        "role": role,
        "workflow_status": item.get("status"),
        "project_status": item.get("status"),
        "priority_label": priority,
    }


def validate_task(item: dict[str, Any]) -> TaskValidationResult:
    """Validate a project item against the task workflow contract.

    The validator checks:
    - the item is a GitHub Issue;
    - it has exactly one role and priority label;
    - the issue body contains all mandatory sections except workflow status;
    - the body values match the corresponding labels;
    - the project status is present and usable for workflow selection.

    All violations are collected so callers can report full diagnostics.
    """
    violations: list[str] = []
    content = item.get("content") or {}
    labels = set(item.get("labels") or [])

    if content.get("type") != "Issue":
        violations.append("content type is not Issue")

    role_labels = sorted(labels & ROLE_LABELS)
    priority_labels = sorted(labels & PRIORITY_LABELS)

    if len(role_labels) != 1:
        violations.append("task must have exactly one role label")
    if len(priority_labels) != 1:
        violations.append("task must have exactly one priority label")

    body = content.get("body") or ""
    sections = extract_sections(body)
    missing_sections = [section for section in MANDATORY_SECTIONS if section not in sections]
    if missing_sections:
        violations.append(f"task body is missing mandatory sections: {', '.join(missing_sections)}")

    role_value = extract_code_value(sections.get("Role", ""))
    priority_value = extract_code_value(sections.get("Priority", ""))
    task_id = extract_code_value(sections.get("Id", ""))

    if not task_id:
        violations.append("task body must contain non-empty task id")

    if len(role_labels) == 1 and role_value != role_labels[0].split(":", 1)[1]:
        violations.append("task body role does not match role label")
    if len(priority_labels) == 1 and priority_value != priority_labels[0].split(":", 1)[1]:
        violations.append("task body priority does not match priority label")
    project_status = item.get("status") or None
    workflow_status = project_status
    if not workflow_status:
        violations.append("task does not expose a workflow status")

    task = summarize_task(item, sections)
    return TaskValidationResult(is_valid=not violations, task=task, violations=violations)


def select_task(valid_ready_tasks: list[dict[str, Any]]) -> dict[str, Any]:
    """Select the single highest-priority task from a validated ready set.

    Ordering is deterministic:
    - lower priority rank wins;
    - within the same priority tier, the lexicographically smallest task id
      wins.

    The extra nested sort helper makes the priority rule explicit and keeps the
    tie-breaker stable.
    """
    def sort_key(task: dict[str, Any]) -> tuple[int, str]:
        """Return the ordering key for one validated task.

        The tuple is ordered so that priority rank is the primary sort key and
        task id becomes the secondary key for deterministic tie-breaking.
        """
        priority_rank = PRIORITY_ORDER[task["priority_label"]]
        return priority_rank, task["task_id"]

    ordered = sorted(valid_ready_tasks, key=sort_key)
    best_priority_rank = PRIORITY_ORDER[ordered[0]["priority_label"]]
    highest_priority = [task for task in ordered if PRIORITY_ORDER[task["priority_label"]] == best_priority_rank]
    return sorted(highest_priority, key=lambda task: task["task_id"])[0]


def load_state(state_path: Path) -> dict[str, Any]:
    """Load and decode the repository state file.

    The file must exist and contain valid JSON. The script relies on this state
    to find the configured GitHub Project and to produce reproducible task
    selection behavior.
    """
    if not state_path.is_file():
        raise FileNotFoundError(f"state file not found: {state_path}")
    with state_path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for task selection.

    Only the state file path is configurable here. The selector always derives
    repository context from the local checkout and project data from the state
    file.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state-file",
        default=".codex/state.json",
        help="Path to .codex/state.json relative to the repository root.",
    )
    return parser.parse_args()


def main() -> int:
    """Select exactly one executable task from the GitHub Project.

    The workflow is:
    1. Locate the repository root that contains `.codex/state.json`.
    2. Load the configured project URL from state.
    3. Fetch all project items from GitHub.
    4. Validate each item against the task contract.
    5. Select the single highest-priority ready task and emit JSON.

    Return codes distinguish between success, no valid task, configuration
    blockers, and GitHub CLI failures.
    """
    args = parse_args()
    repo_root = Path(__file__).resolve().parent
    while repo_root != repo_root.parent:
        if (repo_root / ".codex" / "state.json").is_file():
            break
        repo_root = repo_root.parent
    else:
        print_json(make_result("configuration_blocker", reason="repository root with .codex/state.json was not found"))
        return 3
    state_path = (repo_root / args.state_file).resolve()

    try:
        state = load_state(state_path)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print_json(make_result("configuration_blocker", reason=str(exc)))
        return 3

    project = state.get("project") or {}
    project_url = project.get("gh_project_url")
    if not project_url:
        print_json(
            make_result(
                "configuration_blocker",
                reason="project.gh_project_url is not set in .codex/state.json",
            )
        )
        return 3

    try:
        owner, project_number = parse_project_url(project_url)
    except ValueError as exc:
        print_json(make_result("configuration_blocker", reason=str(exc)))
        return 3

    try:
        items_payload = run_gh_json(
            ["project", "item-list", str(project_number), "--owner", owner, "--format", "json", "-L", "1000"],
            cwd=repo_root,
        )
    except RuntimeError as exc:
        print_json(
            make_result(
                "github_cli_error",
                reason=str(exc),
                project_url=project_url,
            )
        )
        return 4

    items = items_payload.get("items") or []
    invalid_tasks: list[dict[str, Any]] = []
    valid_ready_tasks: list[dict[str, Any]] = []

    for item in items:
        validation = validate_task(item)
        if not validation.is_valid:
            invalid_tasks.append(
                {
                    **validation.task,
                    "violations": validation.violations,
                }
            )
            continue

        if validation.task["workflow_status"] == "ready":
            valid_ready_tasks.append(validation.task)

    if not valid_ready_tasks:
        print_json(
            make_result(
                "no_ready_task",
                reason="no valid task with workflow status ready exists in the GitHub Project",
                project_url=project_url,
                invalid_tasks=invalid_tasks,
            )
        )
        return 2

    selected = select_task(valid_ready_tasks)
    print_json(
        make_result(
            "selected",
            project_url=project_url,
            selected_task=selected,
            invalid_tasks=invalid_tasks,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
