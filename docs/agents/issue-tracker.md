# Issue tracker: GitHub (via the GitHub MCP connector)

Issues and specs for this repo live as GitHub issues. Use the **GitHub
connector** (`connector_github_app.*` tool functions) for all operations —
not the `gh` CLI. Repo: `LowDataSailing/Light-Router`.

## Conventions

- **Create an issue**: `connector_github_app.issue_write` with
  `method: "create"`, `title`, `body`, optional `labels` / `assignees`.
  Labels that don't exist yet are created automatically (write access
  required) — this is how the triage vocabulary was initialized (issue #5).
- **Read an issue**: `connector_github_app.issue_read` with
  `method: "get"` (details), `"get_comments"`, or `"get_labels"`.
- **List issues**: `connector_github_app.list_issues` with `state: "OPEN"`
  and `labels: ["<label>"]` filters. Use `fields` to trim large responses
  (drop `body` when you only need the queue).
- **Comment on an issue**: `connector_github_app.add_issue_comment`
  (also works on PRs by passing the PR number).
- **Apply labels**: `connector_github_app.issue_write` with
  `method: "update"`, `issue_number`, and the **full desired label set** in
  `labels` (update replaces, it doesn't append — read current labels first
  with `issue_read` `method: "get_labels"`).
- **Close**: `connector_github_app.issue_write` with `method: "update"`,
  `state: "closed"`, `state_reason: "completed"` (or `"not_planned"` for
  wontfix).

## Pull requests

- **Create**: `connector_github_app.create_pull_request`.
- **Read**: `connector_github_app.pull_request_read`; list with
  `list_pull_requests` / `search_pull_requests`.
- **Update / merge**: `update_pull_request`, `merge_pull_request` — merging
  is a human decision; agents do not merge without explicit instruction.

GitHub shares one number space across issues and PRs, so a bare `#42` may be
either: try `issue_read`, and fall back to `pull_request_read`.

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this repo treats external
PRs as feature requests; `/triage` reads this flag.)_

When set to `yes`, PRs run through the same labels and states as issues:
list external PRs with `list_pull_requests`, keep only authors who are not
`OWNER`/`MEMBER`/`COLLABORATOR`, and label/comment/close with the issue tools
above (they accept PR numbers).

## When a skill says "publish to the issue tracker"

Create a GitHub issue with `issue_write`.

## When a skill says "fetch the relevant ticket"

Run `issue_read` with `method: "get"` and `"get_comments"`.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as
tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes /
  Decisions-so-far / Fog body. Create with `issue_write` +
  `labels: ["wayfinder:map"]`.
- **Child ticket**: create with `issue_write` and `parent_issue_number`
  (attaches the sub-issue in the same operation), or attach an existing
  issue with `connector_github_app.sub_issue_write`. Labels:
  `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Once
  claimed, the ticket is assigned to the driving dev.
- **Blocking**: the connector does not expose GitHub's native issue
  dependencies, so use the body-line convention: put
  `Blocked by: #<n>, #<n>` at the top of the child body. A ticket is
  unblocked when every blocker is closed (check with `issue_read`).
- **Frontier query**: `list_issues` with `state: "OPEN"`, scope to the map's
  children (`issue_read` `method: "get_sub_issues"` on the map), drop any
  with an open blocker in its `Blocked by:` line or an assignee; first in
  map order wins.
- **Claim**: `issue_write` `method: "update"` with `assignees: ["<you>"]`,
  the session's first write.
- **Resolve**: `add_issue_comment` with the answer, then close via
  `issue_write`, then append a context pointer (gist + link) to the map's
  Decisions-so-far.
