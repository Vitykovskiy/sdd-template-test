#!/usr/bin/env python3
"""Finish issue-driven local work by committing, pushing, and opening a PR."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.common import (
    CommandError,
    add_issue_to_project,
    get_default_branch_name,
    get_project_status_field,
    get_repo_from_origin,
    gh_issue_view,
    gh_pr_list,
    list_project_items,
    load_state,
    print_json,
    repo_root_from_script,
    run_command,
    run_json_command,
    update_project_item_status,
)


class ValidationError(Exception):
    """Raised when repository or issue state violates the workflow contract."""


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the completion workflow."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue-number", type=int, required=True)
    parser.add_argument("--commit-message", required=True)
    parser.add_argument("--branch")
    parser.add_argument("--base-branch")
    parser.add_argument("--pr-title")
    parser.add_argument("--pr-body")
    parser.add_argument("--pr-body-file")
    parser.add_argument("--stage-all", action="store_true")
    parser.add_argument("--state-file", default=".codex/state.json")
    return parser.parse_args()


def normalize_branch_slug(text: str) -> str:
    """Normalize free-form text into a Git branch slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "issue"


def auto_branch_name(issue_number: int, title: str) -> str:
    """Build the default feature branch name from issue metadata."""
    slug = normalize_branch_slug(title)[:48].strip("-")
    if slug:
        return f"issue-{issue_number}-{slug}"
    return f"issue-{issue_number}"


def current_branch(repo_root: Path) -> str:
    """Return the currently checked-out branch name."""
    branch = run_command(["git", "branch", "--show-current"], repo_root).strip()
    if not branch:
        raise CommandError("repository is in detached HEAD state")
    return branch


def git_status_porcelain(repo_root: Path) -> list[str]:
    """Return the porcelain status lines for the working tree."""
    output = run_command(["git", "status", "--porcelain=v1"], repo_root)
    return [line for line in output.splitlines() if line.strip()]


def git_head_sha(repo_root: Path) -> str:
    """Return the current HEAD commit SHA."""
    return run_command(["git", "rev-parse", "HEAD"], repo_root).strip()


def checkout_branch(repo_root: Path, branch: str, base_branch: str) -> None:
    """Switch to ``branch``, creating it from ``base_branch`` when needed."""
    local_ref = f"refs/heads/{branch}"
    if _git_ref_exists(repo_root, local_ref):
        run_command(["git", "checkout", branch], repo_root)
        return
    run_command(["git", "checkout", "-b", branch, base_branch], repo_root)


def _git_ref_exists(repo_root: Path, ref: str) -> bool:
    """Return whether ``ref`` exists in the local Git repository."""
    try:
        run_command(["git", "show-ref", "--verify", "--quiet", ref], repo_root)
        return True
    except CommandError:
        return False


def has_staged_changes(repo_root: Path) -> bool:
    """Return whether the index contains staged changes."""
    return bool(run_command(["git", "diff", "--cached", "--name-only"], repo_root).strip())


def has_unstaged_or_untracked_changes(repo_root: Path) -> bool:
    """Return whether the working tree has unstaged or untracked changes."""
    status_lines = git_status_porcelain(repo_root)
    return any(line.startswith("??") or len(line) > 1 and line[1] != " " for line in status_lines)


def git_commit(repo_root: Path, message: str) -> str:
    """Create a commit from the staged index and return its SHA."""
    run_command(["git", "commit", "-m", message], repo_root)
    return git_head_sha(repo_root)


def git_push(repo_root: Path, branch: str) -> None:
    """Push ``branch`` to ``origin`` and set the upstream tracking branch."""
    run_command(["git", "push", "-u", "origin", branch], repo_root)


def read_pr_body(repo_root: Path, args: argparse.Namespace, issue_number: int) -> str:
    """Resolve the PR body from CLI arguments or fall back to a compact default."""
    if args.pr_body_file:
        body_path = Path(args.pr_body_file)
        if not body_path.is_absolute():
            body_path = (repo_root / body_path).resolve()
        return body_path.read_text(encoding="utf-8").strip() + "\n"
    if args.pr_body is not None:
        return args.pr_body.strip() + "\n"
    return f"Related issue: #{issue_number}\n"


def find_open_pr_by_issue(repo_root: Path, repo_full_name: str, issue_number: int) -> dict[str, Any] | None:
    """Try to reuse an open PR that explicitly references the issue number."""
    payload = run_json_command(
        [
            "gh",
            "pr",
            "list",
            "-R",
            repo_full_name,
        "--state",
        "open",
        "--search",
        f"#{issue_number}",
        "--json",
        "number,title,url,state,headRefName,baseRefName",
    ],
        repo_root,
    )
    prs = payload if isinstance(payload, list) else []
    if not prs:
        return None
    if len(prs) > 1:
        raise ValidationError(f"multiple open pull requests reference issue #{issue_number}")
    return prs[0]


def detect_or_create_branch(
    repo_root: Path,
    repo_full_name: str,
    issue_number: int,
    issue_title: str,
    base_branch: str,
    explicit_branch: str | None,
) -> str:
    """Select the working branch for the completion workflow."""
    if explicit_branch:
        checkout_branch(repo_root, explicit_branch, base_branch)
        return explicit_branch

    branch = current_branch(repo_root)
    if branch != base_branch:
        return branch

    existing_pr = find_open_pr_by_issue(repo_root, repo_full_name, issue_number)
    if existing_pr:
        pr_branch = existing_pr.get("headRefName") or ""
        if pr_branch:
            checkout_branch(repo_root, pr_branch, base_branch)
            return pr_branch

    generated = auto_branch_name(issue_number, issue_title)
    checkout_branch(repo_root, generated, base_branch)
    return generated


def open_or_reuse_pr(
    repo_root: Path,
    repo_full_name: str,
    branch: str,
    base_branch: str,
    pr_title: str,
    pr_body: str,
) -> tuple[dict[str, Any], bool]:
    """Return the open PR for ``branch`` or create one when necessary."""
    existing_prs = gh_pr_list(repo_root, repo_full_name, branch, base_branch, state="open")
    if existing_prs:
        return existing_prs[0], False

    create_args = [
        "gh",
        "pr",
        "create",
        "-R",
        repo_full_name,
        "--head",
        branch,
        "--base",
        base_branch,
        "--title",
        pr_title,
        "--body",
        pr_body,
    ]
    run_command(create_args, repo_root)

    created_prs = gh_pr_list(repo_root, repo_full_name, branch, base_branch, state="open")
    if not created_prs:
        raise CommandError("pull request was created but could not be resolved")
    return created_prs[0], True


def ensure_issue_project_link(
    repo_root: Path,
    repo_full_name: str,
    project_id: str | None,
    issue: dict[str, Any],
) -> dict[str, Any]:
    """Ensure the issue has a GitHub Project item without touching the issue body."""
    if not project_id:
        return {
            "status": "skipped",
            "reason": "GitHub Project is not configured in .codex/state.json",
        }

    status_field = get_project_status_field(repo_root, project_id)
    if status_field is None:
        raise CommandError("GitHub Project Status field was not found")

    option_id_by_name = {
        option["name"]: option["id"]
        for option in status_field.get("options") or []
        if option.get("name") and option.get("id")
    }
    option_id = option_id_by_name.get("review")
    if option_id is None:
        raise CommandError("GitHub Project Status option 'review' was not found")

    project_item_id = None
    current_status = None
    for item in list_project_items(repo_root, project_id):
        content = item.get("content") or {}
        if content.get("__typename") != "Issue":
            continue
        repository_name = ((content.get("repository") or {}).get("nameWithOwner")) or ""
        if content.get("number") == issue.get("number") and repository_name == repo_full_name:
            project_item_id = item.get("id")
            current_status = ((item.get("fieldValueByName") or {}).get("name")) or None
            break

    created = False
    if not project_item_id:
        issue_node_id = issue.get("id")
        if not issue_node_id:
            raise CommandError("GitHub issue node id is not available")
        project_item_id = add_issue_to_project(repo_root, project_id, issue_node_id)
        created = True

    if current_status != "review":
        update_project_item_status(repo_root, project_id, project_item_id, status_field["id"], option_id)

    return {
        "status": "synced",
        "project_item_id": project_item_id,
        "created": created,
        "from": current_status,
        "to": "review",
    }


def main() -> int:
    """Run the commit, push, PR, and issue-review completion workflow."""
    args = parse_args()
    repo_root = repo_root_from_script(__file__)

    try:
        state = load_state(repo_root, args.state_file)
        repo_ref = get_repo_from_origin(repo_root)
        if repo_ref is None:
            print_json({"status": "error", "reason": "GitHub origin remote is not configured"})
            return 1
        repo_full_name = repo_ref.full_name
        base_branch = args.base_branch or get_default_branch_name(repo_root, repo_full_name)
        project_id = ((state.get("project") or {}).get("gh_project_id"))

        issue = gh_issue_view(repo_root, repo_full_name, args.issue_number)
        branch = detect_or_create_branch(
            repo_root,
            repo_full_name,
            args.issue_number,
            issue.get("title") or f"Issue {args.issue_number}",
            base_branch,
            args.branch,
        )
        open_pr = gh_pr_list(repo_root, repo_full_name, branch, base_branch, state="open")
        existing_pr = open_pr[0] if open_pr else None

        staged_changes_present = has_staged_changes(repo_root)
        if args.stage_all:
            run_command(["git", "add", "-A"], repo_root)
            staged_changes_present = has_staged_changes(repo_root)
        else:
            if has_unstaged_or_untracked_changes(repo_root):
                print_json(
                    {
                        "status": "validation_error",
                        "reason": "unstaged or untracked changes are present; rerun with --stage-all",
                        "branch": branch,
                        "issue_number": args.issue_number,
                        "changed": False,
                    }
                )
                return 2

        if not staged_changes_present and existing_pr is None:
            print_json(
                {
                    "status": "validation_error",
                    "reason": "no staged changes are available to commit",
                    "branch": branch,
                    "issue_number": args.issue_number,
                    "changed": False,
                }
            )
            return 2

        commit_sha: str | None = None
        if staged_changes_present:
            commit_sha = git_commit(repo_root, args.commit_message)
            git_push(repo_root, branch)

        pr_title = args.pr_title or (issue.get("title") or f"Issue {args.issue_number}")
        pr_body = read_pr_body(repo_root, args, args.issue_number)
        pr, created_pr = open_or_reuse_pr(
            repo_root,
            repo_full_name,
            branch,
            base_branch,
            pr_title,
            pr_body,
        )

        project_sync = ensure_issue_project_link(repo_root, repo_full_name, project_id, issue)
        project_changed = project_sync.get("status") == "synced" and (
            project_sync.get("created") or project_sync.get("from") != project_sync.get("to")
        )

        if commit_sha is None:
            commit_sha = git_head_sha(repo_root)

        changed = bool(staged_changes_present or created_pr or project_changed)
        output_status = "created" if created_pr else "updated_existing_pr"
        print_json(
            {
                "status": output_status,
                "repository": repo_full_name,
                "issue_number": args.issue_number,
                "branch": branch,
                "base_branch": base_branch,
                "commit_sha": commit_sha,
                "pr_number": pr.get("number"),
                "pr_url": pr.get("url"),
                "from_status": project_sync.get("from"),
                "to_status": "review",
                "changed": changed,
                "project_sync": project_sync,
                "workflow_mode": state.get("mode"),
            }
        )
        return 0
    except ValidationError as exc:
        print_json(
            {
                "status": "validation_error",
                "reason": str(exc),
                "issue_number": getattr(args, "issue_number", None),
                "changed": False,
            }
        )
        return 2
    except CommandError as exc:
        print_json(
            {
                "status": "error",
                "reason": str(exc),
                "issue_number": getattr(args, "issue_number", None),
                "changed": False,
            }
        )
        return 1
    except Exception as exc:
        print_json(
            {
                "status": "error",
                "reason": str(exc),
                "issue_number": getattr(args, "issue_number", None),
                "changed": False,
            }
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
