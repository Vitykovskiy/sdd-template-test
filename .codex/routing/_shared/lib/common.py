from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_URL_RE = re.compile(
    r"^https://github\.com/(?:(?:orgs|users)/)?(?P<owner>[^/]+)/projects/(?P<number>\d+)(?:/.*)?$"
)
REMOTE_URL_RE = re.compile(
    r"^(?:https://github\.com/|git@github\.com:)(?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$"
)


class CommandError(RuntimeError):
    pass


@dataclass
class ProjectRef:
    owner: str
    number: int
    url: str


@dataclass
class RepoRef:
    owner: str
    name: str

    @property
    def full_name(self) -> str:
        """Return the canonical ``owner/name`` repository identifier."""
        return f"{self.owner}/{self.name}"


@dataclass
class LabelSpec:
    name: str
    color: str
    description: str


@dataclass
class ProjectStatusOptionSpec:
    name: str
    color: str
    description: str


def repo_root_from_script(script_file: str) -> Path:
    """Return the repository root for a script located anywhere inside it.

    The search starts from the directory that contains ``script_file`` and
    walks upward until a directory containing ``.codex/state.json`` is found.
    This makes the helper resilient to scripts being moved deeper into the
    template tree while preserving a single source of truth for repository
    discovery.
    """
    current = Path(script_file).resolve().parent
    while current != current.parent:
        if (current / ".codex" / "state.json").is_file():
            return current
        current = current.parent
    raise FileNotFoundError("repository root with .codex/state.json was not found")


def load_json_file(path: Path) -> dict[str, Any]:
    """Load and decode a JSON document from ``path``.

    The file is read using ``utf-8-sig`` so the helper tolerates BOM-prefixed
    files, which is important for repository state files that may be edited by
    different tools.
    """
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    """Serialize ``payload`` as normalized JSON at ``path``.

    The output is written with UTF-8 encoding, two-space indentation, and a
    trailing newline to keep generated state files stable and diff-friendly.
    """
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def print_json(payload: dict[str, Any]) -> None:
    """Print ``payload`` to standard output as formatted JSON."""
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def get_github_token(repo_root: Path | None = None) -> str:
    """Return a GitHub API token from the environment or ``gh auth token``.

    The lookup order is ``GH_TOKEN``, then ``GITHUB_TOKEN``, and finally the
    GitHub CLI token associated with ``repo_root`` or the current working
    directory. This keeps REST and GraphQL helpers aligned on a single
    authentication strategy.
    """
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    cwd = repo_root or Path.cwd()
    token = run_command(["gh", "auth", "token"], cwd).strip()
    if not token:
        raise CommandError("GitHub token is not available")
    return token


def run_command(args: list[str], cwd: Path) -> str:
    """Run ``args`` in ``cwd`` and return the captured standard output.

    The command is executed without ``check=True`` so the function can raise a
    unified :class:`CommandError` that includes the most useful failure text
    from stderr or stdout.
    """
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        raise CommandError(stderr or stdout or f"command failed: {' '.join(args)}")
    return completed.stdout


def run_json_command(args: list[str], cwd: Path) -> dict[str, Any]:
    """Run a command and parse its standard output as JSON.

    This is the canonical adapter for ``gh --json`` style commands used by the
    routing helpers. Non-JSON output is normalized into :class:`CommandError`
    so callers do not need to handle parsing concerns individually.
    """
    output = run_command(args, cwd)
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise CommandError(f"failed to decode JSON output: {exc}") from exc


def graphql_request(query: str, variables: dict[str, Any] | None = None, repo_root: Path | None = None) -> dict[str, Any]:
    """Execute a GitHub GraphQL request and return the ``data`` payload.

    Authentication is resolved in the following order: ``GH_TOKEN``,
    ``GITHUB_TOKEN``, and finally ``gh auth token`` executed in ``repo_root``
    or the current working directory. GraphQL and transport errors are wrapped
    in :class:`CommandError` to keep failure handling consistent for callers.
    """
    token = get_github_token(repo_root)

    payload = json.dumps(
        {
            "query": query,
            "variables": variables or {},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace").strip()
        raise CommandError(details or str(exc)) from exc
    except urllib.error.URLError as exc:
        raise CommandError(str(exc)) from exc

    if response_payload.get("errors"):
        raise CommandError(json.dumps(response_payload["errors"], ensure_ascii=False))
    return response_payload.get("data") or {}


def github_rest_request(
    method: str,
    path: str,
    repo_root: Path | None = None,
    payload: dict[str, Any] | None = None,
    allow_404: bool = False,
) -> dict[str, Any] | None:
    """Execute a GitHub REST request and return the decoded JSON payload.

    The helper uses the same token resolution strategy as
    :func:`graphql_request`. Non-404 HTTP failures raise :class:`CommandError`
    with the response body when available so callers receive a useful
    diagnostic. When ``allow_404`` is true, missing resources are normalized to
    ``None`` instead of raising.
    """
    token = get_github_token(repo_root)
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace").strip()
        if allow_404 and exc.code == 404:
            return None
        raise CommandError(details or str(exc)) from exc
    except urllib.error.URLError as exc:
        raise CommandError(str(exc)) from exc


def load_state(repo_root: Path, state_file: str = ".codex/state.json") -> dict[str, Any]:
    """Load the persisted routing state from ``state_file`` under ``repo_root``."""
    return load_json_file((repo_root / state_file).resolve())


def save_state(repo_root: Path, state: dict[str, Any], state_file: str = ".codex/state.json") -> None:
    """Persist routing ``state`` to ``state_file`` under ``repo_root``."""
    write_json_file((repo_root / state_file).resolve(), state)


def parse_project_url(project_url: str) -> ProjectRef:
    """Parse a GitHub Projects URL into a normalized :class:`ProjectRef`."""
    match = PROJECT_URL_RE.match(project_url.strip())
    if not match:
        raise ValueError(f"unsupported GitHub Project URL format: {project_url}")
    return ProjectRef(
        owner=match.group("owner"),
        number=int(match.group("number")),
        url=project_url.strip(),
    )


def parse_remote_url(remote_url: str) -> RepoRef:
    """Parse a GitHub remote URL into a normalized :class:`RepoRef`."""
    match = REMOTE_URL_RE.match(remote_url.strip())
    if not match:
        raise ValueError(f"unsupported GitHub remote URL format: {remote_url}")
    return RepoRef(owner=match.group("owner"), name=match.group("repo"))


def get_origin_remote_url(repo_root: Path) -> str | None:
    """Return the configured ``origin`` remote URL, or ``None`` if unavailable."""
    try:
        return run_command(["git", "remote", "get-url", "origin"], repo_root).strip()
    except CommandError:
        return None


def get_repo_from_origin(repo_root: Path) -> RepoRef | None:
    """Return the repository reference derived from the ``origin`` remote."""
    remote_url = get_origin_remote_url(repo_root)
    if not remote_url:
        return None
    try:
        return parse_remote_url(remote_url)
    except ValueError:
        return None


def get_current_login(repo_root: Path) -> str:
    """Return the authenticated GitHub login name for the current environment."""
    payload = run_json_command(["gh", "api", "user"], repo_root)
    login = payload.get("login")
    if not login:
        raise CommandError("failed to determine authenticated GitHub login")
    return login


def gh_repo_view(repo_root: Path, repo_full_name: str) -> dict[str, Any]:
    """Fetch basic metadata for ``repo_full_name`` via ``gh repo view``."""
    return run_json_command(["gh", "repo", "view", repo_full_name, "--json", "name,owner,url"], repo_root)


def get_default_branch_name(repo_root: Path, repo_full_name: str) -> str:
    """Return the repository default branch name from GitHub metadata."""
    payload = github_rest_request("GET", f"/repos/{repo_full_name}", repo_root)
    default_branch = (payload or {}).get("default_branch")
    if not default_branch:
        raise CommandError(f"failed to determine default branch for {repo_full_name}")
    return str(default_branch)


def gh_project_view(repo_root: Path, owner: str, project_number: int) -> dict[str, Any]:
    """Fetch metadata for a GitHub Project owned by ``owner``."""
    return run_json_command(
        ["gh", "project", "view", str(project_number), "--owner", owner, "--format", "json"],
        repo_root,
    )


def gh_project_list(repo_root: Path, owner: str) -> dict[str, Any]:
    """List GitHub Projects visible to ``owner``."""
    return run_json_command(["gh", "project", "list", "--owner", owner, "--format", "json"], repo_root)


def gh_project_field_list(repo_root: Path, owner: str, project_number: int) -> list[dict[str, Any]]:
    """Return the field definitions for a GitHub Project."""
    payload = run_json_command(
        ["gh", "project", "field-list", str(project_number), "--owner", owner, "--format", "json", "-L", "100"],
        repo_root,
    )
    return payload.get("fields") or []


def gh_label_list(repo_root: Path, repo_full_name: str) -> list[dict[str, Any]]:
    """Return up to 1000 labels defined in ``repo_full_name``."""
    payload = run_json_command(
        ["gh", "label", "list", "-R", repo_full_name, "--limit", "1000", "--json", "name,color,description"],
        repo_root,
    )
    return payload if isinstance(payload, list) else []


def gh_issue_list(repo_root: Path, repo_full_name: str, search: str) -> list[dict[str, Any]]:
    """Return issues matching ``search`` in ``repo_full_name``."""
    payload = run_json_command(
        [
            "gh",
            "issue",
            "list",
            "-R",
            repo_full_name,
            "--limit",
            "100",
            "--search",
            search,
            "--json",
            "number,title,url,labels,state",
        ],
        repo_root,
    )
    return payload if isinstance(payload, list) else []


def gh_issue_view(repo_root: Path, repo_full_name: str, issue_number: int) -> dict[str, Any]:
    """Return detailed metadata for a single issue."""
    return run_json_command(
        [
            "gh",
            "issue",
            "view",
            str(issue_number),
            "-R",
            repo_full_name,
            "--json",
            "id,number,title,url,body,labels",
        ],
        repo_root,
    )


def gh_issue_update(
    repo_root: Path,
    repo_full_name: str,
    issue_number: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Update a GitHub issue with the provided REST payload."""
    response = github_rest_request(
        "PATCH",
        f"/repos/{repo_full_name}/issues/{issue_number}",
        repo_root,
        payload=payload,
    )
    return response or {}


def gh_pr_list(
    repo_root: Path,
    repo_full_name: str,
    head: str,
    base: str | None = None,
    state: str = "open",
) -> list[dict[str, Any]]:
    """Return pull requests filtered by ``head`` and optional ``base``."""
    args = [
        "gh",
        "pr",
        "list",
        "-R",
        repo_full_name,
        "--head",
        head,
        "--state",
        state,
        "--json",
        "number,title,url,state,headRefName,baseRefName",
    ]
    if base:
        args.extend(["--base", base])
    payload = run_json_command(args, repo_root)
    return payload if isinstance(payload, list) else []


def extract_backtick_values(markdown_text: str) -> list[str]:
    """Return every substring enclosed in backticks in ``markdown_text``."""
    return re.findall(r"`([^`]+)`", markdown_text)


def load_label_specs(standard_path: Path) -> list[LabelSpec]:
    """Parse label specifications from the repository standard document.

    Each matching Markdown bullet is converted into a :class:`LabelSpec` with
    normalized lowercase color codes so downstream comparisons are stable.
    """
    content = standard_path.read_text(encoding="utf-8-sig")
    specs: list[LabelSpec] = []
    pattern = re.compile(
        r"^- `(?P<name>[^`]+)` \| color: `(?P<color>[0-9A-Fa-f]{6})` \| description: `(?P<description>[^`]+)`$",
        flags=re.MULTILINE,
    )
    for match in pattern.finditer(content):
        specs.append(
            LabelSpec(
                name=match.group("name"),
                color=match.group("color").lower(),
                description=match.group("description"),
            )
        )
    return specs


PROJECT_STATUS_COLOR_MAP = {
    "c5def5": "GRAY",
    "0e8a16": "GREEN",
    "fbca04": "YELLOW",
    "f9d0c4": "ORANGE",
    "5319e7": "PURPLE",
    "0052cc": "BLUE",
    "1d76db": "BLUE",
    "d93f0b": "RED",
    "6a737d": "GRAY",
}


def load_project_status_specs(standard_path: Path) -> list[ProjectStatusOptionSpec]:
    """Parse canonical GitHub Project status options from the standard document.

    Workflow status is governed only by the GitHub Project ``Status`` field, so
    the standard declares the allowed options explicitly inside the project
    status section instead of encoding them as repository labels.
    """
    content = standard_path.read_text(encoding="utf-8-sig")
    specs: list[ProjectStatusOptionSpec] = []
    pattern = re.compile(
        r"^- name: `(?P<name>[^`]+)` \| color: `(?P<color>[0-9A-Fa-f]{6})` \| description: `(?P<description>[^`]+)`$",
        flags=re.MULTILINE,
    )
    for match in pattern.finditer(content):
        raw_color = match.group("color").lower()
        color = PROJECT_STATUS_COLOR_MAP.get(raw_color)
        if color is None:
            raise ValueError(f"unsupported project status color mapping for color {raw_color}")
        specs.append(
            ProjectStatusOptionSpec(
                name=match.group("name"),
                color=color,
                description=match.group("description"),
            )
        )
    return specs


def load_required_labels(standard_path: Path) -> list[str]:
    """Return the ordered list of label names required by the standard."""
    return [spec.name for spec in load_label_specs(standard_path)]


def load_initiating_task_template(template_path: Path) -> str:
    """Load the initiating-task template and normalize it to a single trailing newline."""
    return template_path.read_text(encoding="utf-8-sig").strip() + "\n"


def extract_markdown_sections(markdown_text: str) -> dict[str, str]:
    """Split a Markdown document into top-level ``##`` sections.

    The returned mapping preserves section names as keys and trims surrounding
    whitespace from each section body. This helper intentionally ignores other
    heading levels because the routing templates use ``##`` as the structural
    boundary.
    """
    sections: dict[str, str] = {}
    matches = list(re.finditer(r"^## (?P<name>[^\r\n]+)\r?\n", markdown_text, flags=re.MULTILINE))
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown_text)
        sections[match.group("name").strip()] = markdown_text[start:end].strip()
    return sections


def replace_markdown_section(markdown_text: str, section_name: str, section_body: str) -> str:
    """Replace or append a top-level Markdown ``##`` section.

    The helper preserves all sections other than ``section_name`` and normalizes
    the document to a single trailing newline.
    """
    heading = f"## {section_name}"
    pattern = re.compile(
        rf"(^## {re.escape(section_name)}\r?\n)(.*?)(?=^## |\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    replacement = f"{heading}\n\n{section_body.strip()}\n"
    if pattern.search(markdown_text):
        updated = pattern.sub(replacement, markdown_text, count=1)
    else:
        base = markdown_text.rstrip()
        if base:
            updated = f"{base}\n\n{replacement}"
        else:
            updated = replacement
    return updated.rstrip() + "\n"


def extract_code_value(section_value: str) -> str:
    """Extract the first inline-code value from a section body, if present."""
    match = re.search(r"`([^`]+)`", section_value)
    if match:
        return match.group(1).strip()
    return section_value.strip()


def get_project_status_field(repo_root: Path, project_id: str) -> dict[str, Any] | None:
    """Return the ``Status`` field definition for a GitHub Project, if present."""
    query = """
    query($projectId: ID!) {
      node(id: $projectId) {
        ... on ProjectV2 {
          fields(first: 100) {
            nodes {
              __typename
              ... on ProjectV2FieldCommon {
                id
                name
              }
              ... on ProjectV2SingleSelectField {
                options {
                  id
                  name
                  description
                  color
                }
              }
            }
          }
        }
      }
    }
    """
    payload = graphql_request(query, {"projectId": project_id}, repo_root)
    project = payload.get("node") or {}
    for field in ((project.get("fields") or {}).get("nodes") or []):
        if field.get("name") == "Status" and field.get("__typename") == "ProjectV2SingleSelectField":
            return field
    return None


def gh_branch_view(repo_root: Path, repo_full_name: str, branch_name: str) -> dict[str, Any] | None:
    """Return metadata for a GitHub branch, or ``None`` when it does not exist."""
    return github_rest_request("GET", f"/repos/{repo_full_name}/branches/{branch_name}", repo_root, allow_404=True)


def gh_branch_protection_view(repo_root: Path, repo_full_name: str, branch_name: str) -> dict[str, Any] | None:
    """Return the branch protection document for ``branch_name`` if it exists."""
    return github_rest_request(
        "GET",
        f"/repos/{repo_full_name}/branches/{branch_name}/protection",
        repo_root,
        allow_404=True,
    )


def gh_branch_protection_update(
    repo_root: Path,
    repo_full_name: str,
    branch_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Replace the branch protection document for ``branch_name``.

    The request is sent as a full ``PUT`` so the call is idempotent: repeated
    executions converge on the same protection policy without depending on any
    prior branch-protection state.
    """
    response = github_rest_request(
        "PUT",
        f"/repos/{repo_full_name}/branches/{branch_name}/protection",
        repo_root,
        payload=payload,
    )
    return response or {}


def main_branch_protection_payload() -> dict[str, Any]:
    """Return the canonical protection policy for the default branch.

    The policy blocks direct pushes by requiring pull-request based updates,
    enforces the restriction for admins, and disables force pushes and branch
    deletions. The payload is intentionally minimal so the policy remains
    stable and easy to audit.
    """
    return {
        "required_status_checks": None,
        "enforce_admins": True,
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": False,
            "require_code_owner_reviews": False,
            "required_approving_review_count": 0,
            "require_last_push_approval": False,
        },
        "restrictions": None,
        "required_linear_history": False,
        "allow_force_pushes": False,
        "allow_deletions": False,
        "block_creations": False,
        "required_conversation_resolution": False,
        "lock_branch": False,
        "allow_fork_syncing": False,
    }


def main_branch_protection_is_configured(protection: dict[str, Any] | None) -> bool:
    """Return whether ``protection`` matches the canonical default-branch policy."""
    if protection is None:
        return False
    required_reviews = protection.get("required_pull_request_reviews") or {}
    enforce_admins = protection.get("enforce_admins") or {}
    allow_force_pushes = protection.get("allow_force_pushes") or {}
    allow_deletions = protection.get("allow_deletions") or {}
    required_linear_history = protection.get("required_linear_history") or {}
    required_conversation_resolution = protection.get("required_conversation_resolution") or {}
    lock_branch = protection.get("lock_branch") or {}
    return (
        protection.get("required_status_checks") is None
        and enforce_admins.get("enabled") is True
        and required_reviews.get("dismiss_stale_reviews") is False
        and required_reviews.get("require_code_owner_reviews") is False
        and required_reviews.get("required_approving_review_count") == 0
        and required_reviews.get("require_last_push_approval") is False
        and allow_force_pushes.get("enabled") is False
        and allow_deletions.get("enabled") is False
        and protection.get("restrictions") is None
        and required_linear_history.get("enabled") is False
        and required_conversation_resolution.get("enabled") is False
        and lock_branch.get("enabled") is False
    )


def update_project_status_field(
    repo_root: Path,
    field_id: str,
    status_specs: list[ProjectStatusOptionSpec],
) -> dict[str, Any]:
    """Replace the options of a GitHub Project status field.

    The field is updated wholesale with the provided ``status_specs`` so the
    remote project remains aligned with the canonical label standard.
    """
    query = """
    mutation($fieldId: ID!, $options: [ProjectV2SingleSelectFieldOptionInput!]) {
      updateProjectV2Field(input: {fieldId: $fieldId, singleSelectOptions: $options}) {
        projectV2Field {
          ... on ProjectV2SingleSelectField {
            id
            name
            options {
              id
              name
              description
              color
            }
          }
        }
      }
    }
    """
    payload = graphql_request(
        query,
        {
            "fieldId": field_id,
            "options": [
                {
                    "name": spec.name,
                    "description": spec.description,
                    "color": spec.color,
                }
                for spec in status_specs
            ],
        },
        repo_root,
    )
    return ((payload.get("updateProjectV2Field") or {}).get("projectV2Field")) or {}


def list_project_items(repo_root: Path, project_id: str) -> list[dict[str, Any]]:
    """Return all items in a GitHub Project, following pagination automatically."""
    query = """
    query($projectId: ID!, $after: String) {
      node(id: $projectId) {
        ... on ProjectV2 {
          items(first: 100, after: $after) {
            pageInfo {
              hasNextPage
              endCursor
            }
            nodes {
              id
              fieldValueByName(name: "Status") {
                __typename
                ... on ProjectV2ItemFieldSingleSelectValue {
                  name
                  optionId
                }
              }
              content {
                __typename
                ... on Issue {
                  id
                  number
                  title
                  url
                  body
                  repository {
                    nameWithOwner
                  }
                  labels(first: 100) {
                    nodes {
                      name
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    items: list[dict[str, Any]] = []
    after: str | None = None
    while True:
        payload = graphql_request(query, {"projectId": project_id, "after": after}, repo_root)
        project = payload.get("node") or {}
        items_payload = (project.get("items") or {})
        items.extend(items_payload.get("nodes") or [])
        page_info = items_payload.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        after = page_info.get("endCursor")
    return items


def add_issue_to_project(repo_root: Path, project_id: str, issue_node_id: str) -> str:
    """Add an issue to a GitHub Project and return the created project item ID."""
    query = """
    mutation($projectId: ID!, $contentId: ID!) {
      addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
        item {
          id
        }
      }
    }
    """
    payload = graphql_request(query, {"projectId": project_id, "contentId": issue_node_id}, repo_root)
    item = ((payload.get("addProjectV2ItemById") or {}).get("item")) or {}
    item_id = item.get("id")
    if not item_id:
        raise CommandError("failed to add issue to GitHub Project")
    return item_id


def update_project_item_status(
    repo_root: Path,
    project_id: str,
    item_id: str,
    field_id: str,
    option_id: str,
) -> None:
    """Set the status of an existing GitHub Project item."""
    query = """
    mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
      updateProjectV2ItemFieldValue(
        input: {
          projectId: $projectId,
          itemId: $itemId,
          fieldId: $fieldId,
          value: {singleSelectOptionId: $optionId}
        }
      ) {
        projectV2Item {
          id
        }
      }
    }
    """
    graphql_request(
        query,
        {
            "projectId": project_id,
            "itemId": item_id,
            "fieldId": field_id,
            "optionId": option_id,
        },
        repo_root,
    )
