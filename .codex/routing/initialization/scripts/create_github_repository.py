#!/usr/bin/env python3
"""Create a GitHub repository for the current local repository."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

from lib.common import (
    CommandError,
    RepoRef,
    get_current_login,
    get_origin_remote_url,
    get_repo_from_origin,
    gh_repo_view,
    print_json,
    parse_remote_url,
    repo_root_from_script,
    run_command,
)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for GitHub repository creation or attachment.

    The parser supports two execution modes:
    creating a new remote repository for the local project, or attaching an
    existing GitHub repository URL to the local ``origin`` remote.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", help="GitHub owner. Defaults to the authenticated user.")
    parser.add_argument("--name", help="Repository name. Defaults to the local directory name.")
    parser.add_argument(
        "--attach-existing-url",
        help="Existing GitHub repository URL to attach to origin instead of creating a new repository.",
    )
    parser.add_argument(
        "--visibility",
        choices=("private", "public", "internal"),
        default="private",
        help="Visibility for a newly created repository.",
    )
    parser.add_argument("--remote", default="origin", help="Remote name to create.")
    parser.add_argument("--push", action="store_true", help="Push local refs after creating the repository.")
    return parser.parse_args()


def repo_exists(repo_root: Path, repo_ref: RepoRef) -> bool:
    """Return whether the referenced GitHub repository is reachable.

    The helper converts a failed ``gh repo view`` call into ``False`` so the
    caller can distinguish between a name collision / inaccessible target and a
    successful repository lookup without handling the exception at every call
    site.
    """
    try:
        gh_repo_view(repo_root, repo_ref.full_name)
        return True
    except CommandError:
        return False


def ensure_origin_remote(repo_root: Path, repository_url: str) -> None:
    """Set ``origin`` to ``repository_url``, creating the remote if needed.

    The function preserves the existing remote name and only switches between
    ``git remote set-url`` and ``git remote add`` depending on whether ``origin``
    already exists in the local clone.
    """
    current_origin = get_origin_remote_url(repo_root)
    if current_origin:
        run_command(["git", "remote", "set-url", "origin", repository_url], repo_root)
    else:
        run_command(["git", "remote", "add", "origin", repository_url], repo_root)


def git_initialized(repo_root: Path) -> bool:
    """Return whether ``repo_root`` is already a Git repository.

    This is a guardrail for the creation workflow because the script derives
    both the repository name and the local source path from the current working
    tree, so running outside a Git repo is a hard error.
    """
    completed = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def main() -> int:
    """Create, attach, or validate the GitHub repository for the local project.

    The function exits with distinct status codes for missing Git context,
    repository name conflicts, command failures, and successful completion so
    the surrounding initialization workflow can branch deterministically.
    """
    args = parse_args()
    repo_root = repo_root_from_script(__file__)

    if not git_initialized(repo_root):
        print_json({"status": "error", "reason": "current directory is not a git repository"})
        return 2

    existing = get_repo_from_origin(repo_root)
    if existing and repo_exists(repo_root, existing):
        print_json(
            {
                "status": "already_exists",
                "repository_full_name": existing.full_name,
                "repository_url": f"https://github.com/{existing.full_name}",
            }
        )
        return 0

    if args.attach_existing_url:
        try:
            repo_ref = parse_remote_url(args.attach_existing_url)
        except ValueError as exc:
            print_json({"status": "error", "reason": str(exc)})
            return 2

        repository_url = f"https://github.com/{repo_ref.full_name}"
        if not repo_exists(repo_root, repo_ref):
            print_json(
                {
                    "status": "error",
                    "reason": "target repository does not exist or is not accessible",
                    "repository_full_name": repo_ref.full_name,
                    "repository_url": repository_url,
                }
            )
            return 2

        try:
            ensure_origin_remote(repo_root, repository_url)
        except CommandError as exc:
            print_json({"status": "error", "reason": str(exc)})
            return 3

        print_json(
            {
                "status": "attached",
                "repository_full_name": repo_ref.full_name,
                "repository_url": repository_url,
                "remote": "origin",
            }
        )
        return 0

    owner = args.owner or get_current_login(repo_root)
    name = args.name or repo_root.name
    repo_ref = RepoRef(owner=owner, name=name)

    if repo_exists(repo_root, repo_ref):
        print_json(
            {
                "status": "name_conflict",
                "conflict_type": "repository_name",
                "repository_full_name": repo_ref.full_name,
                "repository_url": f"https://github.com/{repo_ref.full_name}",
                "resolution_options": [
                    {
                        "action": "attach_existing_repo",
                        "repository_full_name": repo_ref.full_name,
                        "repository_url": f"https://github.com/{repo_ref.full_name}",
                        "cli": ["--attach-existing-url", f"https://github.com/{repo_ref.full_name}"],
                    },
                    {
                        "action": "create_new_repo",
                        "note": "rerun with a different --name",
                    },
                ],
            }
        )
        return 2

    create_args = [
        "gh",
        "repo",
        "create",
        repo_ref.full_name,
        f"--{args.visibility}",
        "--source",
        ".",
        "--remote",
        args.remote,
    ]
    if args.push:
        create_args.append("--push")

    try:
        run_command(create_args, repo_root)
    except CommandError as exc:
        if repo_exists(repo_root, repo_ref):
            print_json(
                {
                    "status": "name_conflict",
                    "conflict_type": "repository_name",
                    "repository_full_name": repo_ref.full_name,
                    "repository_url": f"https://github.com/{repo_ref.full_name}",
                    "resolution_options": [
                        {
                            "action": "attach_existing_repo",
                            "repository_full_name": repo_ref.full_name,
                            "repository_url": f"https://github.com/{repo_ref.full_name}",
                            "cli": ["--attach-existing-url", f"https://github.com/{repo_ref.full_name}"],
                        },
                        {
                            "action": "create_new_repo",
                            "note": "rerun with a different --name",
                        },
                    ],
                }
            )
            return 2
        print_json({"status": "error", "reason": str(exc)})
        return 3

    print_json(
        {
            "status": "created",
            "repository_full_name": repo_ref.full_name,
            "repository_url": f"https://github.com/{repo_ref.full_name}",
            "remote": args.remote,
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
