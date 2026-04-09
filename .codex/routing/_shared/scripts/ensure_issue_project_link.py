#!/usr/bin/env python3
"""Ensure a GitHub issue is linked to the repository GitHub Project."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.common import (
    CommandError,
    add_issue_to_project,
    get_repo_from_origin,
    gh_issue_view,
    list_project_items,
    load_state,
    print_json,
    repo_root_from_script,
)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for issue-to-project synchronization.

    The caller must specify the issue number. Repository and state-file
    overrides are optional because the script can infer the repository from the
    current origin remote and uses the shared state file by default.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue-number", type=int, required=True)
    parser.add_argument("--repository", help="Repository in owner/name format. Defaults to current origin.")
    parser.add_argument("--state-file", default=".codex/state.json")
    return parser.parse_args()


def main() -> int:
    """Ensure one issue has a corresponding GitHub Project item.

    The script no longer reads workflow status from the issue body. It only
    makes sure the issue is attached to the configured GitHub Project so that
    other automation can manage project status directly.
    """
    args = parse_args()
    repo_root = repo_root_from_script(__file__)
    state = load_state(repo_root, args.state_file)
    project = state.get("project") or {}
    project_id = project.get("gh_project_id")
    if not project_id:
        print_json({"status": "skipped", "reason": "GitHub Project is not configured in .codex/state.json"})
        return 0

    repo_full_name = args.repository
    if not repo_full_name:
        repo_ref = get_repo_from_origin(repo_root)
        if repo_ref is None:
            print_json({"status": "error", "reason": "GitHub origin remote is not configured"})
            return 2
        repo_full_name = repo_ref.full_name

    try:
        issue = gh_issue_view(repo_root, repo_full_name, args.issue_number)
        project_item_id = None
        created = False
        for item in list_project_items(repo_root, project_id):
            content = item.get("content") or {}
            if content.get("__typename") != "Issue":
                continue
            repository_name = ((content.get("repository") or {}).get("nameWithOwner")) or ""
            if content.get("number") == args.issue_number and repository_name == repo_full_name:
                project_item_id = item.get("id")
                break

        if not project_item_id:
            issue_node_id = issue.get("id")
            if not issue_node_id:
                print_json({"status": "error", "reason": "GitHub issue node id is not available"})
                return 6
            project_item_id = add_issue_to_project(repo_root, project_id, issue_node_id)
            created = True

        print_json(
            {
                "status": "synced",
                "repository": repo_full_name,
                "issue_number": args.issue_number,
                "project_item_id": project_item_id,
                "created": created,
            }
        )
        return 0
    except CommandError as exc:
        print_json({"status": "error", "reason": str(exc)})
        return 7


if __name__ == "__main__":
    sys.exit(main())
