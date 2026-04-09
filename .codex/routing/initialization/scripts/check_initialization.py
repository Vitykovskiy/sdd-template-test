#!/usr/bin/env python3
"""Audit repository initialization state without making changes."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

from lib.common import (
    CommandError,
    extract_code_value,
    extract_markdown_sections,
    get_origin_remote_url,
    get_repo_from_origin,
    get_project_status_field,
    get_default_branch_name,
    gh_issue_list,
    gh_label_list,
    gh_branch_protection_view,
    gh_branch_view,
    gh_project_field_list,
    gh_project_view,
    gh_repo_view,
    load_initiating_task_template,
    load_label_specs,
    load_project_status_specs,
    main_branch_protection_is_configured,
    load_state,
    list_project_items,
    parse_project_url,
    print_json,
    repo_root_from_script,
)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the initialization audit script.

    The script accepts only the state file path because all other inputs are
    derived from the repository location and the standard initialization
    artifacts that live under the routing template.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", default=".codex/state.json")
    return parser.parse_args()


def git_initialized(repo_root: Path) -> bool:
    """Return whether ``repo_root`` is inside a Git working tree.

    The check is intentionally shallow: it delegates to
    ``git rev-parse --is-inside-work-tree`` and treats any non-zero exit code
    or non-``true`` output as a negative result. This avoids mutating the
    repository while still giving a reliable initialization gate.
    """
    completed = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def gh_auth_ok(repo_root: Path) -> tuple[bool, str | None]:
    """Check whether the GitHub CLI is authenticated for this repository.

    The function returns a tuple of ``(is_authenticated, diagnostic_message)``.
    The message is populated from ``stderr`` first and falls back to ``stdout``
    because ``gh auth status`` may emit useful authentication details on either
    stream depending on the failure mode.
    """
    completed = subprocess.run(
        ["gh", "auth", "status"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    stderr = completed.stderr.strip() or completed.stdout.strip()
    return completed.returncode == 0, stderr or None


def main() -> int:
    """Inspect the repository initialization state and emit a JSON report.

    The function aggregates Git, GitHub CLI, repository, project, label, and
    initiating-task checks into a single machine-readable report. It does not
    change repository state; instead it records missing prerequisites as
    required actions and returns ``2`` when remediation is needed.
    """
    args = parse_args()
    repo_root = repo_root_from_script(__file__)
    standard_path = repo_root / ".codex/routing/initialization/standards/gh-project-standard.md"
    template_path = repo_root / ".codex/routing/initialization/templates/initiating-task.md"
    label_specs = load_label_specs(standard_path)
    status_specs = load_project_status_specs(standard_path)
    template_text = load_initiating_task_template(template_path)
    template_sections = extract_markdown_sections(template_text)
    initiating_task_title = extract_code_value(template_sections.get("Title", ""))
    mandatory_sections = ("Id", "Role", "Title", "Purpose", "Artifacts", "Priority")
    missing_template_sections = [section for section in mandatory_sections if section not in template_sections]

    report: dict[str, object] = {
        "status": "ok",
        "checks": {},
        "required_actions": [],
    }
    checks = report["checks"]
    required_actions: list[str] = report["required_actions"]  # type: ignore[assignment]

    git_ok = git_initialized(repo_root)
    checks["git_initialized"] = git_ok
    if not git_ok:
        report["status"] = "action_required"
        required_actions.append("create_or_initialize_git_repository")

    auth_ok, auth_message = gh_auth_ok(repo_root)
    checks["github_auth_ok"] = auth_ok
    if auth_message:
        checks["github_auth_message"] = auth_message
    if not auth_ok:
        report["status"] = "action_required"
        required_actions.append("authenticate_github_cli")

    remote_url = get_origin_remote_url(repo_root)
    checks["origin_remote_present"] = bool(remote_url)
    checks["origin_remote_url"] = remote_url

    repo_ref = get_repo_from_origin(repo_root)
    checks["origin_is_github_remote"] = repo_ref is not None
    if not remote_url:
        report["status"] = "action_required"
        required_actions.append("create_github_repository")
    elif repo_ref is None:
        report["status"] = "action_required"
        required_actions.append("replace_non_github_origin_remote")

    repo_exists = False
    repo_full_name = None
    if repo_ref and auth_ok:
        repo_full_name = repo_ref.full_name
        checks["repository_full_name"] = repo_full_name
        try:
            gh_repo_view(repo_root, repo_full_name)
            repo_exists = True
        except CommandError as exc:
            checks["repository_lookup_error"] = str(exc)
        checks["github_repository_exists"] = repo_exists
        if not repo_exists:
            report["status"] = "action_required"
            required_actions.append("create_github_repository")
    else:
        checks["github_repository_exists"] = False

    state_loaded = True
    try:
        state = load_state(repo_root, args.state_file)
    except (FileNotFoundError, ValueError, OSError) as exc:
        state_loaded = False
        state = {}
        checks["state_load_error"] = str(exc)
        report["status"] = "action_required"
        required_actions.append("repair_state_file")

    checks["state_file_loaded"] = state_loaded

    project_url = ((state.get("project") or {}).get("gh_project_url")) if state_loaded else None
    project_ref = None
    project_exists = False
    project_lookup = None
    if project_url:
        checks["project_link_recorded_in_state"] = True
        checks["project_url"] = project_url
        try:
            project_ref = parse_project_url(project_url)
            project_lookup = gh_project_view(repo_root, project_ref.owner, project_ref.number) if auth_ok else None
            project_exists = project_lookup is not None
        except (ValueError, CommandError) as exc:
            checks["project_lookup_error"] = str(exc)
    else:
        checks["project_link_recorded_in_state"] = False

    checks["github_project_exists"] = project_exists
    if not project_exists:
        report["status"] = "action_required"
        required_actions.append("create_or_link_github_project")
    else:
        project_id = ((state.get("project") or {}).get("gh_project_id")) if state_loaded else None
        checks["project_id_recorded_in_state"] = bool(project_id)
        if project_ref:
            try:
                project_fields = gh_project_field_list(repo_root, project_ref.owner, project_ref.number)
                checks["project_field_names"] = [field.get("name") for field in project_fields]
            except CommandError as exc:
                checks["project_field_lookup_error"] = str(exc)

        if project_id:
            try:
                status_field = get_project_status_field(repo_root, project_id)
                expected_status_names = [spec.name for spec in status_specs]
                actual_status_names = [option.get("name") for option in (status_field or {}).get("options") or []]
                checks["project_status_field_exists"] = status_field is not None
                checks["project_status_option_names"] = actual_status_names
                checks["project_standard_status_field_ok"] = actual_status_names == expected_status_names
                if not checks["project_standard_status_field_ok"]:
                    report["status"] = "action_required"
                    required_actions.append("sync_project_standard")
            except CommandError as exc:
                checks["project_status_field_lookup_error"] = str(exc)
                checks["project_standard_status_field_ok"] = False
                report["status"] = "action_required"
                required_actions.append("sync_project_standard")

            try:
                misaligned_items: list[dict[str, object]] = []
                for item in list_project_items(repo_root, project_id):
                    content = item.get("content") or {}
                    if content.get("__typename") != "Issue":
                        continue

                    project_status = ((item.get("fieldValueByName") or {}).get("name")) or ""
                    reason = None
                    if not project_status:
                        reason = "project Status field is empty"
                    elif initiating_task_title and content.get("title") == initiating_task_title and project_status != "ready":
                        reason = "initiating task project Status must be ready"

                    if reason:
                        misaligned_items.append(
                            {
                                "issue_number": content.get("number"),
                                "repository": ((content.get("repository") or {}).get("nameWithOwner")),
                                "project_status": project_status or None,
                                "reason": reason,
                            }
                        )

                checks["misaligned_project_items"] = misaligned_items
                checks["project_item_status_alignment_ok"] = not misaligned_items
                if misaligned_items:
                    report["status"] = "action_required"
                    required_actions.append("sync_project_standard")
            except CommandError as exc:
                checks["project_item_alignment_lookup_error"] = str(exc)
                checks["project_item_status_alignment_ok"] = False
                report["status"] = "action_required"
                required_actions.append("sync_project_standard")
        else:
            checks["project_status_field_exists"] = False
            checks["project_standard_status_field_ok"] = False
            checks["project_item_status_alignment_ok"] = False
            report["status"] = "action_required"
            required_actions.append("sync_project_standard")

    labels_required = [spec.name for spec in label_specs]
    checks["required_label_count"] = len(label_specs)
    missing_labels: list[str] = []
    noncompliant_labels: list[dict[str, object]] = []
    if repo_exists:
        try:
            existing_labels = {
                item["name"]: {
                    "color": (item.get("color") or "").lower(),
                    "description": item.get("description") or "",
                }
                for item in gh_label_list(repo_root, repo_full_name)
            }
            missing_labels = sorted(label for label in labels_required if label not in existing_labels)
            for spec in label_specs:
                if spec.name not in existing_labels:
                    continue
                existing = existing_labels[spec.name]
                if existing["color"] != spec.color or existing["description"] != spec.description:
                    noncompliant_labels.append(
                        {
                            "name": spec.name,
                            "expected": {
                                "color": spec.color,
                                "description": spec.description,
                            },
                            "actual": existing,
                        }
                    )
            checks["missing_labels"] = missing_labels
            checks["noncompliant_labels"] = noncompliant_labels
            checks["project_standard_labels_ok"] = not missing_labels and not noncompliant_labels
            if missing_labels or noncompliant_labels:
                report["status"] = "action_required"
                required_actions.append("sync_project_standard")
        except CommandError as exc:
            checks["label_lookup_error"] = str(exc)
            checks["project_standard_labels_ok"] = False
            report["status"] = "action_required"
            required_actions.append("sync_project_standard")
    else:
        checks["project_standard_labels_ok"] = False
        checks["missing_labels"] = labels_required
        checks["noncompliant_labels"] = []
        report["status"] = "action_required"
        required_actions.append("sync_project_standard")

    checks["initiating_task_template_missing_sections"] = missing_template_sections
    checks["initiating_task_template_valid"] = bool(initiating_task_title) and not missing_template_sections

    if repo_exists:
        search = f'in:title "{initiating_task_title}"' if initiating_task_title else ""
        try:
            issues = gh_issue_list(repo_root, repo_full_name, search) if search else []
            checks["initiating_task_present"] = any(issue["title"] == initiating_task_title for issue in issues)
        except CommandError as exc:
            checks["initiating_task_lookup_error"] = str(exc)
            checks["initiating_task_present"] = False
        if not checks["initiating_task_present"] or not checks["initiating_task_template_valid"]:
            report["status"] = "action_required"
            required_actions.append("create_initiating_task")
    else:
        checks["initiating_task_present"] = False
        report["status"] = "action_required"
        required_actions.append("create_initiating_task")

    if checks.get("initiating_task_present"):
        checks["initialization_mode_can_advance"] = True
    else:
        checks["initialization_mode_can_advance"] = False

    checks["initiating_task_template_available"] = bool(template_text.strip())

    branch_protection_gate_ready = bool(repo_exists and project_exists and checks.get("initiating_task_present"))
    checks["default_branch_protection_gate_ready"] = branch_protection_gate_ready
    checks["default_branch_exists"] = False
    checks["default_branch_protection_present"] = False
    checks["default_branch_protection_ok"] = False
    checks["default_branch_protection_status"] = "deferred_until_repo_project_and_initiating_task_ready"
    if branch_protection_gate_ready:
        try:
            default_branch_name = get_default_branch_name(repo_root, repo_full_name)
            checks["default_branch_name"] = default_branch_name
            default_branch = gh_branch_view(repo_root, repo_full_name, default_branch_name)
            checks["default_branch_exists"] = default_branch is not None
            if default_branch is None:
                checks["default_branch_protection_status"] = "awaiting_default_branch_push"
            else:
                protection = gh_branch_protection_view(repo_root, repo_full_name, default_branch_name)
                checks["default_branch_protection_present"] = protection is not None
                checks["default_branch_protection_ok"] = main_branch_protection_is_configured(protection)
                if checks["default_branch_protection_ok"]:
                    checks["default_branch_protection_status"] = "ok"
                else:
                    checks["default_branch_protection_status"] = "action_required"
                    report["status"] = "action_required"
                    required_actions.append("protect_main_branch")
        except CommandError as exc:
            checks["default_branch_protection_lookup_error"] = str(exc)
            checks["default_branch_protection_status"] = "lookup_error"
            report["status"] = "action_required"
            required_actions.append("protect_main_branch")

    action_order = [
        "repair_state_file",
        "authenticate_github_cli",
        "create_or_initialize_git_repository",
        "create_github_repository",
        "replace_non_github_origin_remote",
        "create_or_link_github_project",
        "sync_project_standard",
        "create_initiating_task",
        "protect_main_branch",
    ]
    unique_actions = set(required_actions)
    report["required_actions"] = [action for action in action_order if action in unique_actions]
    print_json(report)
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    sys.exit(main())
