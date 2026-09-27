# Coding Standards

How code is written in this repo. The `code-review` skill's standards axis
checks diffs against this file; `docs/CONTRIBUTING.md` is the user-facing
subset.

## Formatting and linting (tooling-enforced)

- **black**, line length 88, target py310-py312 (`make format`). Don't
  hand-format; let black do it.
- **flake8** per `.flake8`: max line 88, `E203`/`W503` ignored (black
  compatibility), `.venv`, `site/`, caches excluded.
- **mypy** on `src/`: `python_version = "3.12"` (numpy 2.x stubs use `type`
  statements), `warn_return_any = false` (numpy ufunc results are typed
  `Any` by the stubs — the warning is noise here), `ignore_missing_imports`.
  New code must pass mypy; prefer `np.asarray(...)` narrowing at call sites
  over `# type: ignore`.

## Python style

- Type hints on all function signatures.
- Google-style docstrings on every public function/class; one-line summary
  minimum. Private helpers get docstrings when non-obvious.
- numpy idioms: vectorized operations, no Python loops over grid points.
  Scalar-or-array helpers return `np.ndarray | float` and callers that need
  arrays narrow with `np.asarray`.

## Tests

- pytest, no network: mock HTTP (see `tests/test_chom.py`), synthetic
  weather fields only.
- Keep test grids small — isochrone routing cost scales with points x
  headings x levels; the full suite should stay well under a minute.
- A bug fix lands with a regression test that fails without it.

## Dependencies

- numpy is the only core runtime dependency. cfgrib/xarray live in the
  optional `grib` group (lazy import with a clear error message); mkdocs in
  `docs`. Anything else needs a reason.
- `uv` for all environment work (`uv sync`, `uv run`).

## Repo layout and docs

- Package code in `src/light_router/`; tests mirror module names.
- `specs/` holds working implementation specs (not user-facing).
- **Notion is the internal workspace; `docs/` is user-facing.** Never copy
  workspace material into `docs/`.
- `CONTEXT.md` and `docs/adr/` are created lazily by `/domain-modeling`;
  don't scaffold them empty.

## Git

- Branches: `vibe/<topic>` or `chore/<topic>` off `master`; work lands via
  PR. Agents open PRs but do not merge — merging is a human decision.
- Commit messages: lowercase prefix (`feat:`, `fix:`, `docs:`, `chore:`,
  `test:`), imperative subject, body explains why.
- Force-push only with `--force-with-lease`, only on your own feature
  branches.
