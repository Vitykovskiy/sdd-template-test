#!/usr/bin/env python3
"""Create or attach a GitHub Project and link it to the repository."""

from __future__ import annotations

import argparse
import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

from lib.common import (
    CommandError,
    get_repo_from_origin,
    gh_project_view,
    load_state,
    parse_project_url,
    print_json,
    repo_root_from_script,
    run_command,
    run_json_command,
    save_state,
)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for project discovery or creation.

    The script accepts a state file location plus optional project owner,
    project title, and an existing project URL. These values are used later
    to either attach to an already configured project or create a new one
    before linking it to the current repository.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", default=".codex/state.json")
    parser.add_argument("--owner", help="GitHub project owner. Defaults to repository owner.")
    parser.add_argument("--title", help="Project title. Required when a project must be created.")
    parser.add_argument("--project-url", help="Existing GitHub Project URL to attach instead of creating a new one.")
    return parser.parse_args()


def list_owner_projects(repo_root: Path, owner: str) -> list[dict[str, object]]:
    """Return all GitHub Projects visible for the given owner.

    The function shells out to the GitHub CLI and normalizes the payload into
    a list of project dictionaries. If the CLI response shape is unexpected,
    the function returns an empty list instead of raising, because the caller
    treats that case as "no exact title matches found".
    """
    payload = run_json_command(
        ["gh", "project", "list", "--owner", owner, "--closed", "--format", "json", "-L", "1000"],
        repo_root,
    )
    projects = payload.get("projects") if isinstance(payload, dict) else payload
    return projects if isinstance(projects, list) else []


def summarize_project(project: dict[str, object]) -> dict[str, object]:
    """Reduce a project payload to the fields needed for conflict reporting.

    This keeps the response stable and compact by extracting identifiers,
    title, URL, owner login, and closed flag only. The caller uses this data
    when reporting name collisions to the user.
    """
    owner = project.get("owner") if isinstance(project.get("owner"), dict) else {}
    owner_login = owner.get("login") if isinstance(owner, dict) else None
    return {
        "project_id": project.get("id"),
        "project_number": project.get("number"),
        "project_title": project.get("title"),
        "project_url": project.get("url"),
        "owner_login": owner_login,
        "closed": project.get("closed"),
    }


def build_name_conflict_response(
    title: str,
    owner: str,
    projects: list[dict[str, object]],
) -> dict[str, object]:
    """Build a structured response for a project title collision.

    The response contains the conflicting title, the owner scope, a compact
    summary of existing projects, and explicit resolution options. This is
    emitted as JSON so a caller can decide whether to attach to an existing
    project or rerun the command with another title.
    """
    existing_projects = [summarize_project(project) for project in projects]
    resolution_options = [
        {
            "action": "attach_existing_project",
            "project_url": project.get("url"),
            "project_id": project.get("id"),
            "project_number": project.get("number"),
            "project_title": project.get("title"),
        }
        for project in projects
    ]
    resolution_options.append(
        {
            "action": "create_new_project",
            "note": "rerun with a different --title",
        }
    )
    return {
        "status": "name_conflict",
        "conflict_type": "project_title",
        "requested_title": title,
        "owner_login": owner,
        "existing_projects": existing_projects,
        "resolution_options": resolution_options,
    }


def find_exact_title_projects(repo_root: Path, owner: str, title: str) -> list[dict[str, object]]:
    """Find projects whose title matches the requested title exactly.

    This is used as a collision check before creating a new project and again
    after a failed create attempt, so the script can report a deterministic
    "name_conflict" result instead of a generic command failure.
    """
    projects = list_owner_projects(repo_root, owner)
    return [
        project
        for project in projects
        if isinstance(project, dict) and project.get("title") == title
    ]


def main() -> int:
    """Create or attach a GitHub Project and link it to the repository.

    Execution flow:
    1. Resolve the repository from the origin remote.
    2. Load stored state to reuse an already configured project when possible.
    3. Either attach to an existing project URL or create a project by title.
    4. Link the resulting project to the repository.
    5. Persist the project metadata back into the state file and print JSON.

    Return codes are intentionally stable because other routing scripts depend
    on them for orchestration and error handling.
    """
    args = parse_args()
    repo_root = repo_root_from_script(__file__)

    repo_ref = get_repo_from_origin(repo_root)
    if repo_ref is None:
        print_json({"status": "error", "reason": "GitHub origin remote is not configured"})
        return 2

    state = load_state(repo_root, args.state_file)
    project_url = args.project_url or ((state.get("project") or {}).get("gh_project_url"))
    project_payload = None

    try:
        if project_url:
            project_ref = parse_project_url(project_url)
            project_payload = gh_project_view(repo_root, project_ref.owner, project_ref.number)
        else:
            owner = args.owner or repo_ref.owner
            if not args.title:
                print_json(
                    {
                        "status": "error",
                        "reason": "project title is required when no existing project is configured",
                    }
                )
                return 2
            exact_matches = find_exact_title_projects(repo_root, owner, args.title)
            if exact_matches:
                print_json(build_name_conflict_response(args.title, owner, exact_matches))
                return 2
            project_payload = run_json_command(
                ["gh", "project", "create", "--owner", owner, "--title", args.title, "--format", "json"],
                repo_root,
            )

        run_command(
            [
                "gh",
                "project",
                "link",
                str(project_payload["number"]),
                "--owner",
                project_payload["owner"]["login"],
                "--repo",
                repo_ref.full_name,
            ],
            repo_root,
        )
    except (CommandError, ValueError, KeyError) as exc:
        if args.title and not project_url:
            owner = args.owner or repo_ref.owner
            try:
                exact_matches = find_exact_title_projects(repo_root, owner, args.title)
            except CommandError:
                exact_matches = []
            if exact_matches:
                print_json(build_name_conflict_response(args.title, owner, exact_matches))
                return 2
        print_json({"status": "error", "reason": str(exc)})
        return 3

    state.setdefault("project", {})
    state["project"]["gh_project_url"] = project_payload["url"]
    state["project"]["gh_project_id"] = project_payload["id"]
    save_state(repo_root, state, args.state_file)

    print_json(
        {
            "status": "ready",
            "project_url": project_payload["url"],
            "project_id": project_payload["id"],
            "project_number": project_payload["number"],
            "project_title": project_payload["title"],
            "repository_full_name": repo_ref.full_name,
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
