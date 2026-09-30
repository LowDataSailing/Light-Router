# Light-Router

Agent instructions for this repository.

## Notion workspace (spec source of truth)

This project is backed by a Notion workspace: **LowDataSailing > Light-Router**.
Most specs live there (Goals, Baseline System, Benchmark Harness, Data
Pipeline, Compatibility Principles, Decisions Log) and it is the **source of
truth**. To avoid markdown duplication:

- Update the Notion page first; the repo mirrors it only when a PR needs a
  reviewable copy (`specs/*.md` are working mirrors for PR review, not the
  canonical text).
- Never copy workspace material into `docs/` — `docs/` is user-facing only.
- Access the workspace through the `connector_notion` tools; do not
  paraphrase Notion content from memory — fetch the page.

## Agent skills

### Issue tracker

Issues are tracked in GitHub Issues (LowDataSailing/Light-Router), via the
GitHub MCP connector (`connector_github_app`). See
`agents/issue-tracker.md`.

### Triage labels

Default triage vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`,
`ready-for-human`, `wontfix` (initialized in the repo, see issue #5). See
`agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` + `docs/adr/` at the repo root. See
`agents/domain.md`.
