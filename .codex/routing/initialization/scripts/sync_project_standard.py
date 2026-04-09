#!/usr/bin/env python3
"""Ensure repository labels and GitHub Project status field follow the template standard."""

from __future__ import annotations

import argparse
import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

from lib.common import (
    CommandError,
    get_repo_from_origin,
    get_project_status_field,
    gh_label_list,
    load_label_specs,
    load_project_status_specs,
    load_state,
    print_json,
    repo_root_from_script,
    run_command,
    update_project_status_field,
)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the standard synchronization step.

    The command currently accepts only the path to the project standard file.
    The standard file defines the label set and GitHub Project status options
    that the repository must conform to.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--standard-file", default=".codex/routing/initialization/standards/gh-project-standard.md")
    return parser.parse_args()


def main() -> int:
    """Synchronize repository labels and the GitHub Project status field.

    The function performs two consistency checks and repairs:
    - repository labels are created or updated to match the standard file;
    - the GitHub Project status field is reconciled with the standard options;
    - issue bodies are not used as a status source.

    The behavior is strictly operational: the function mutates the project
    state but does not alter the workflow semantics or return-code contract.
    """
    args = parse_args()
    repo_root = repo_root_from_script(__file__)
    repo_ref = get_repo_from_origin(repo_root)
    if repo_ref is None:
        print_json({"status": "error", "reason": "GitHub origin remote is not configured"})
        return 2

    standard_path = (repo_root / args.standard_file).resolve()
    label_specs = load_label_specs(standard_path)
    status_specs = load_project_status_specs(standard_path)
    required_labels = [spec.name for spec in label_specs]

    state = load_state(repo_root)
    project = state.get("project") or {}
    project_id = project.get("gh_project_id")
    project_url = project.get("gh_project_url")
    if not project_id or not project_url:
        print_json({"status": "error", "reason": "GitHub Project is not configured in .codex/state.json"})
        return 2

    try:
        existing_labels = {
            label["name"]: {
                "color": (label.get("color") or "").lower(),
                "description": label.get("description") or "",
            }
            for label in gh_label_list(repo_root, repo_ref.full_name)
        }
        created_labels: list[str] = []
        updated_labels: list[str] = []
        for spec in label_specs:
            if spec.name not in existing_labels:
                run_command(
                    [
                        "gh",
                        "label",
                        "create",
                        spec.name,
                        "-R",
                        repo_ref.full_name,
                        "--color",
                        spec.color,
                        "--description",
                        spec.description,
                    ],
                    repo_root,
                )
                created_labels.append(spec.name)
                continue

            existing = existing_labels[spec.name]
            if existing["color"] != spec.color or existing["description"] != spec.description:
                run_command(
                    [
                        "gh",
                        "label",
                        "edit",
                        spec.name,
                        "-R",
                        repo_ref.full_name,
                        "--color",
                        spec.color,
                        "--description",
                        spec.description,
                    ],
                    repo_root,
                )
                updated_labels.append(spec.name)

        status_field = get_project_status_field(repo_root, project_id)
        if status_field is None:
            raise CommandError("GitHub Project Status field was not found")

        updated_status_field = update_project_status_field(repo_root, status_field["id"], status_specs)
        status_option_names = [option["name"] for option in updated_status_field.get("options") or []]
    except CommandError as exc:
        print_json({"status": "error", "reason": str(exc)})
        return 3

    print_json(
        {
            "status": "synced",
            "repository_full_name": repo_ref.full_name,
            "created_labels": created_labels,
            "updated_labels": updated_labels,
            "required_label_count": len(required_labels),
            "project_url": project_url,
            "project_status_field": updated_status_field.get("name"),
            "project_status_option_names": status_option_names,
            "synced_project_items": [],
            "skipped_project_items": [],
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
