# Light-Router

Agent instructions for this repository.

## Spec source of truth: Nextcloud Collectives (reliquary)

The project specs live in the **LowDataSailing collective** on the Nextcloud
instance (reliquary, `reliquary.pascal-internet.duckdns.org`) — migrated from
Notion on 2026-10-17. The collective is the **source of truth** (Goals,
Baseline System, Benchmark Harness, Data Pipeline, Compatibility Principles,
Decisions Log).

- Update the collective page first; the repo mirrors it only when a PR needs
  a reviewable copy (`specs/*.md` are working mirrors for PR review, not the
  canonical text).
- Never copy collective material into `docs/` — `docs/` is user-facing only.
- Notion is no longer maintained for this project — do not read or update it
  for spec purposes.
- Access the collective through the Nextcloud MCP server (Collectives app)
  or WebDAV; fetch the page, do not paraphrase spec content from memory.
- Collective quirk: a Collectives folder page is its `Readme.md`.

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
