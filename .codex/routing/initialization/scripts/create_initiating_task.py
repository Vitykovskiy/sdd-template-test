#!/usr/bin/env python3
"""Create the initiating task issue and advance initialization mode."""

from __future__ import annotations

import argparse
import re
import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

from lib.common import (
    add_issue_to_project,
    CommandError,
    extract_code_value,
    extract_markdown_sections,
    get_project_status_field,
    get_repo_from_origin,
    gh_issue_list,
    gh_issue_view,
    gh_project_view,
    list_project_items,
    load_initiating_task_template,
    load_state,
    parse_project_url,
    print_json,
    repo_root_from_script,
    run_command,
    save_state,
    update_project_item_status,
)

MANDATORY_TASK_SECTIONS = (
    "Id",
    "Role",
    "Title",
    "Purpose",
    "Artifacts",
    "Priority",
)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the initiating-task creation workflow.

    The script needs only the state file location and the task template path;
    both defaults are anchored in the routing template so the command can be
    run without additional configuration in the standard initialization flow.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", default=".codex/state.json")
    parser.add_argument("--template-file", default=".codex/routing/initialization/templates/initiating-task.md")
    return parser.parse_args()


def build_issue_labels(sections: dict[str, str]) -> list[str]:
    """Build the GitHub labels required by the initiating task contract.

    Only role and priority remain as labels. Workflow status is tracked in the
    GitHub Project status field, not as a GitHub label or body section.
    """
    return [
        f"role:{extract_code_value(sections['Role'])}",
        f"priority:{extract_code_value(sections['Priority'])}",
    ]


def issue_number_from_url(issue_url: str) -> int:
    """Extract the numeric issue identifier from a GitHub issue URL.

    The function expects the canonical issue URL format ending in
    ``/issues/<number>`` and raises ``ValueError`` when the input does not match
    that contract.
    """
    match = re.search(r"/issues/(?P<number>\d+)$", issue_url.strip())
    if not match:
        raise ValueError(f"failed to extract issue number from URL: {issue_url}")
    return int(match.group("number"))


def validate_initiating_task_template(sections: dict[str, str]) -> None:
    """Ensure that the initiating-task template contains all mandatory sections.

    The template is treated as a governed artifact: missing structural sections
    are rejected immediately so downstream issue creation cannot proceed with an
    incomplete contract.
    """
    missing_sections = [section for section in MANDATORY_TASK_SECTIONS if section not in sections]
    if missing_sections:
        raise ValueError(
            "initiating task template is missing mandatory sections: "
            + ", ".join(missing_sections)
        )


def main() -> int:
    """Create or reconcile the initiating task issue and update initialization state.

    The function either creates a new issue or reattaches an existing one,
    ensures it belongs to the configured GitHub Project, aligns the project
    status field to ``ready``, and then advances the local initialization mode
    to ``issue_driven``. It preserves the existing workflow contract and
    returns ``3`` on validation or GitHub command failures.
    """
    args = parse_args()
    repo_root = repo_root_from_script(__file__)
    repo_ref = get_repo_from_origin(repo_root)
    if repo_ref is None:
        print_json({"status": "error", "reason": "GitHub origin remote is not configured"})
        return 2

    state = load_state(repo_root, args.state_file)
    project_url = (state.get("project") or {}).get("gh_project_url")
    project_id = (state.get("project") or {}).get("gh_project_id")
    if not project_url or not project_id:
        print_json({"status": "error", "reason": "GitHub Project is not configured in state.json"})
        return 2

    template_path = (repo_root / args.template_file).resolve()
    template_text = load_initiating_task_template(template_path)
    sections = extract_markdown_sections(template_text)
    validate_initiating_task_template(sections)
    issue_title = extract_code_value(sections["Title"])
    issue_labels = build_issue_labels(sections)

    project_ref = parse_project_url(project_url)
    try:
        project_payload = gh_project_view(repo_root, project_ref.owner, project_ref.number)
        issues = gh_issue_list(repo_root, repo_ref.full_name, f'in:title "{issue_title}"')
        existing_issue = next((issue for issue in issues if issue["title"] == issue_title), None)

        if existing_issue:
            issue_number = existing_issue["number"]
            run_command(
                [
                    "gh",
                    "issue",
                    "edit",
                    str(issue_number),
                    "-R",
                    repo_ref.full_name,
                    "--add-project",
                    project_payload["title"],
                ]
                + [item for label in issue_labels for item in ("--add-label", label)],
                repo_root,
            )
            issue_url = existing_issue["url"]
            result_status = "already_exists"
        else:
            create_output = run_command(
                [
                    "gh",
                    "issue",
                    "create",
                    "-R",
                    repo_ref.full_name,
                    "--title",
                    issue_title,
                    "--body-file",
                    str(template_path),
                    "--project",
                    project_payload["title"],
                ]
                + [item for label in issue_labels for item in ("--label", label)],
                repo_root,
            )
            issue_url = create_output.strip().splitlines()[-1]
            issue_number = issue_number_from_url(issue_url)
            result_status = "created"

        issue_payload = gh_issue_view(repo_root, repo_ref.full_name, issue_number)
        status_field = get_project_status_field(repo_root, project_id)
        if status_field is None:
            raise CommandError("GitHub Project Status field was not found")

        desired_status = "ready"
        option_id_by_name = {
            option["name"]: option["id"]
            for option in status_field.get("options") or []
            if option.get("name") and option.get("id")
        }
        option_id = option_id_by_name.get(desired_status)
        if option_id is None:
            raise CommandError(f"GitHub Project Status option '{desired_status}' was not found")

        project_item_id = None
        for item in list_project_items(repo_root, project_id):
            content = item.get("content") or {}
            if content.get("__typename") != "Issue":
                continue
            if content.get("number") == issue_number and ((content.get("repository") or {}).get("nameWithOwner")) == repo_ref.full_name:
                project_item_id = item.get("id")
                break

        if not project_item_id:
            issue_node_id = issue_payload.get("id")
            if not issue_node_id:
                raise CommandError("GitHub issue node id is not available")
            project_item_id = add_issue_to_project(repo_root, project_id, issue_node_id)

        update_project_item_status(repo_root, project_id, project_item_id, status_field["id"], option_id)
    except (CommandError, KeyError, ValueError) as exc:
        print_json({"status": "error", "reason": str(exc)})
        return 3

    state["mode"] = "issue_driven"
    save_state(repo_root, state, args.state_file)

    print_json(
        {
            "status": result_status,
            "issue_title": issue_title,
            "issue_url": issue_url,
            "labels": issue_labels,
            "mode": state["mode"],
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
