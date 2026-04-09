#!/usr/bin/env python3
"""Protect the repository default branch from direct pushes."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

from lib.common import (
    CommandError,
    get_default_branch_name,
    get_repo_from_origin,
    gh_branch_protection_update,
    gh_branch_protection_view,
    gh_branch_view,
    main_branch_protection_payload,
    main_branch_protection_is_configured,
    print_json,
    repo_root_from_script,
)


def main() -> int:
    """Apply the canonical protection policy to the repository default branch or report preconditions.

    The script is intentionally idempotent. When the remote branch does not
    exist yet, the function returns a machine-readable waiting status instead of
    failing. When the branch already matches the canonical policy, the function
    returns ``already_protected`` without making a remote mutation. Any other
    GitHub or authentication failure is reported as ``error``.
    """
    repo_root = repo_root_from_script(__file__)
    repo_ref = get_repo_from_origin(repo_root)
    if repo_ref is None:
        print_json(
            {
                "status": "error",
                "reason": "GitHub origin remote is not configured",
                "default_branch_name": None,
            }
        )
        return 2

    repository_full_name = repo_ref.full_name
    branch_name = get_default_branch_name(repo_root, repository_full_name)
    default_branch_exists = False
    protection_present = False

    try:
        branch_payload = gh_branch_view(repo_root, repository_full_name, branch_name)
        if branch_payload is None:
            print_json(
                {
                    "status": "awaiting_default_branch_push",
                    "reason": f"remote default branch {branch_name!r} does not exist yet",
                    "changed": False,
                    "repository_full_name": repository_full_name,
                    "default_branch_name": branch_name,
                    "default_branch_exists": False,
                    "default_branch_protection_present": False,
                    "default_branch_protection_ok": False,
                    "policy": "require_pull_request_before_merging; block_force_pushes; enforce_admins",
                }
            )
            return 0
        default_branch_exists = True

        protection_payload = gh_branch_protection_view(repo_root, repository_full_name, branch_name)
        protection_present = protection_payload is not None
        if main_branch_protection_is_configured(protection_payload):
            print_json(
                {
                    "status": "already_protected",
                    "changed": False,
                    "repository_full_name": repository_full_name,
                    "default_branch_name": branch_name,
                    "default_branch_exists": default_branch_exists,
                    "default_branch_protection_present": protection_present,
                    "default_branch_protection_ok": True,
                    "policy": "require_pull_request_before_merging; block_force_pushes; enforce_admins",
                }
            )
            return 0

        updated_payload = gh_branch_protection_update(
            repo_root,
            repository_full_name,
            branch_name,
            main_branch_protection_payload(),
        )
        protection_ok = main_branch_protection_is_configured(updated_payload)
        if not protection_ok:
            refreshed = gh_branch_protection_view(repo_root, repository_full_name, branch_name)
            protection_ok = main_branch_protection_is_configured(refreshed)
            updated_payload = refreshed or updated_payload
        if not protection_ok:
            raise CommandError("branch protection update did not converge to the canonical default-branch policy")

    except CommandError as exc:
        print_json(
            {
                "status": "error",
                "reason": str(exc),
                "changed": False,
                "repository_full_name": repository_full_name,
                "default_branch_name": branch_name,
                "default_branch_exists": default_branch_exists,
                "default_branch_protection_present": protection_present,
                "default_branch_protection_ok": False,
                "policy": "require_pull_request_before_merging; block_force_pushes; enforce_admins",
            }
        )
        return 3

    print_json(
        {
            "status": "applied",
            "changed": True,
            "repository_full_name": repository_full_name,
            "default_branch_name": branch_name,
            "default_branch_exists": default_branch_exists,
            "default_branch_protection_present": True,
            "default_branch_protection_ok": True,
            "policy": "require_pull_request_before_merging; block_force_pushes; enforce_admins",
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
